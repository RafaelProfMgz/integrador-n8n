#!/usr/bin/env python3
"""Generate credential-free, inactive manual publishing templates."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATE = r"""
const p = $input.first().json;
if (typeof p.dry_run !== 'boolean') throw new Error('dry_run deve ser booleano');
if (!['facebook', 'instagram'].includes(p.platform)) throw new Error('Plataforma invalida');
if (typeof p.caption !== 'string' || !p.caption.trim()) throw new Error('Legenda obrigatoria');
if (p.platform === 'instagram' && p.caption.length > 2200) throw new Error('Legenda Instagram excede 2200 caracteres');
if (typeof p.image_url !== 'string' || !/^https:\/\/[^\s/]+\/\S+$/.test(p.image_url)) throw new Error('Informe URL HTTPS publica da imagem');
if (!p.dry_run) {
  if (p.approved !== true) throw new Error('Aprovacao explicita necessaria');
  const account = p.platform === 'facebook' ? $env.META_FACEBOOK_PAGE_ID : $env.META_INSTAGRAM_ACCOUNT_ID;
  const token = p.platform === 'facebook' ? $env.META_FACEBOOK_PAGE_ACCESS_TOKEN : $env.META_INSTAGRAM_ACCESS_TOKEN;
  if (!/^\d+$/.test(account || '')) throw new Error('Configure o ID Meta no .env');
  if (!/^v\d+\.\d+$/.test($env.META_GRAPH_VERSION || '')) throw new Error('Configure META_GRAPH_VERSION no .env');
  if (!token || !token.trim()) throw new Error('Configure o access token Meta no .env');
  if (p.image_url.includes('example.com')) throw new Error('Substitua a imagem de exemplo');
}
return [{json: p}];
""".strip()

def node(name, kind, params, x, y=0, version=1):
    return {'id': name.lower().replace(' ', '-'), 'name': name, 'type': 'n8n-nodes-base.' + kind,
            'typeVersion': version, 'position': [x,y], 'parameters': params}

def http(name, method, url, fields, x, platform, query=False):
    token_var = 'META_FACEBOOK_PAGE_ACCESS_TOKEN' if platform == 'facebook' else 'META_INSTAGRAM_ACCESS_TOKEN'
    params = {'method': method, 'url': url, 'authentication': 'none',
              'sendHeaders': True, 'headerParameters': {'parameters': [
                  {'name': 'Authorization', 'value': "={{ 'Bearer ' + $env." + token_var + " }}"}]},
              'options': {'timeout': 30000}}
    if fields:
        if query:
            params.update(sendQuery=True, queryParameters={'parameters': [{'name': k, 'value': v} for k,v in fields.items()]})
        else:
            params.update(sendBody=True, contentType='form-urlencoded',
                          bodyParameters={'parameters': [{'name': k, 'value': v} for k,v in fields.items()]})
    result = node(name, 'httpRequest', params, x, 120, 4.2)
    result['retryOnFail'] = False
    return result

def build(platform):
    config = {'platform': platform, 'dry_run': True, 'approved': False, 'caption': 'Minha primeira publicacao de teste',
              'image_url': 'https://example.com/imagem.jpg'}
    nodes = [node('Inicio manual', 'manualTrigger', {}, 0),
             node('Conteudo', 'code', {'jsCode': 'return [{json: ' + json.dumps(config, ensure_ascii=False) + '}];'}, 220, version=2),
             node('Validar', 'code', {'jsCode': VALIDATE}, 440, version=2),
             node('Simular', 'if', {'conditions': {'options': {'caseSensitive': True, 'leftValue': '', 'typeValidation': 'strict', 'version': 2},
                    'conditions': [{'id': 'dry-run', 'leftValue': '={{ $json.dry_run }}', 'rightValue': True,
                                    'operator': {'type': 'boolean', 'operation': 'true', 'singleValue': True}}], 'combinator': 'and'},
                    'options': {}}, 660, version=2.2),
             node('Previa sem publicar', 'code', {'jsCode': "return [{json: {status: 'dry_run', content: $input.first().json, message: 'Nenhuma chamada externa realizada'}}];"}, 900, -140, 2)]
    edges = {}
    def connect(a,b,output=0):
        main = edges.setdefault(a, {'main': []})['main']
        while len(main) <= output: main.append([])
        main[output].append({'node': b, 'type': 'main', 'index': 0})
    for a,b in [('Inicio manual','Conteudo'),('Conteudo','Validar'),('Validar','Simular'),('Simular','Previa sem publicar')]: connect(a,b)
    base = "https://graph.facebook.com/"
    account_var = 'META_FACEBOOK_PAGE_ID' if platform == 'facebook' else 'META_INSTAGRAM_ACCOUNT_ID'
    account_url = "={{ '" + base + "' + $env.META_GRAPH_VERSION + '/' + $env." + account_var
    if platform == 'facebook':
        nodes.append(http('Publicar foto Facebook', 'POST', account_url + " + '/photos' }}",
                          {'url': "={{ $('Validar').first().json.image_url }}", 'caption': "={{ $('Validar').first().json.caption }}", 'published': 'true'}, 900, platform))
        connect('Simular','Publicar foto Facebook',1)
    else:
        nodes.extend([
            http('Criar container Instagram', 'POST', account_url + " + '/media' }}",
                 {'image_url': "={{ $('Validar').first().json.image_url }}", 'caption': "={{ $('Validar').first().json.caption }}"}, 900, platform),
            node('Esperar processamento', 'wait', {'amount': 15, 'unit': 'seconds'}, 1120, 120, 1.1),
            http('Consultar container', 'GET', "={{ '" + base + "' + $env.META_GRAPH_VERSION + '/' + $('Criar container Instagram').first().json.id }}", {'fields': 'status_code,status'}, 1340, platform, query=True),
            node('Exigir FINISHED', 'code', {'jsCode': "const status = $input.first().json; const id = $('Criar container Instagram').first().json.id; if (status.status_code !== 'FINISHED') throw new Error('Container ' + id + ': ' + status.status_code + '. Consulte este ID e reconcilie antes de repetir; nao recrie automaticamente.'); return [{json: {creation_id: id}}];"}, 1560, 120, 2),
            http('Publicar Instagram', 'POST', account_url + " + '/media_publish' }}", {'creation_id': '={{ $json.creation_id }}'}, 1780, platform)])
        for a,b in [('Simular','Criar container Instagram'),('Criar container Instagram','Esperar processamento'),('Esperar processamento','Consultar container'),('Consultar container','Exigir FINISHED'),('Exigir FINISHED','Publicar Instagram')]: connect(a,b,1 if a=='Simular' else 0)
    return {'name': f'Meta - {platform} - foto manual (dry-run)', 'active': False, 'nodes': nodes,
            'connections': edges, 'settings': {'executionOrder': 'v1', 'timezone': 'America/Cuiaba',
            'saveManualExecutions': True}, 'pinData': {}, 'tags': []}


X_VALIDATE = r"""
const p = $input.first().json;
if (typeof p.dry_run !== 'boolean') throw new Error('dry_run deve ser booleano');
const check = p.operation === 'check_account';
if (!check && p.operation !== 'publish_text') throw new Error('Operacao X invalida');
let text;
let weight = 0;
if (!check) {
  if (typeof p.text !== 'string' || !p.text.trim()) throw new Error('Texto obrigatorio');
  text = p.text.normalize('NFC');
  // Estimativa local baseada nos pesos twitter-text v3.
  // Sem parser completo de URLs/emojis; a API continua sendo a validacao final.
  for (const char of text) {
    const cp = char.codePointAt(0);
    if (cp === 0xFFFE || cp === 0xFFFF || cp === 0xFEFF || (cp >= 0xD800 && cp <= 0xDFFF)) throw new Error('Texto contem caractere invalido');
    weight += (cp <= 0x10FF || (cp >= 0x2000 && cp <= 0x200D) || (cp >= 0x2010 && cp <= 0x201F) || (cp >= 0x2032 && cp <= 0x2037)) ? 1 : 2;
  }
  if (weight > 280) throw new Error('Texto excede a estimativa local de 280; reduza o texto ou a URL');
}
if (!p.dry_run) {
  if (!check && p.approved !== true) throw new Error('Aprovacao explicita necessaria');
  if (!($env.X_OAUTH2_ACCESS_TOKEN || '').trim()) throw new Error('Configure X_OAUTH2_ACCESS_TOKEN no .env (token de usuario)');
  if (!check && !/^\d+$/.test($env.X_USER_ID || '')) throw new Error('Configure X_USER_ID numerico no .env');
}
// Retorne apenas campos editoriais; nunca copie ambiente/tokens para a saida.
return [{json: {platform: 'x', operation: p.operation, dry_run: p.dry_run,
  approved: p.approved === true, ...(check ? {} : {text, estimated_weight: weight})}}];
""".strip()

X_CONFIRM_ACCOUNT = r"""
const result = $input.first().json;
const user = result.data;
if (result.errors?.length || !user || typeof user.id !== 'string' || !/^\d+$/.test(user.id)) throw new Error('Resposta X sem conta valida');
const expected = $env.X_USER_ID || '';
if (expected && user.id !== expected) throw new Error('Conta autenticada diverge de X_USER_ID; publicacao bloqueada');
return [{json: {status: expected ? 'account_verified' : 'account_identified', user_id: user.id, username: user.username}}];
""".strip()

X_RESULT = r"""
const result = $input.first().json;
if (result.errors?.length || !result.data || typeof result.data.id !== 'string' || !/^\d+$/.test(result.data.id)) throw new Error('Resposta de publicacao X ambigua; reconcilie na plataforma antes de repetir');
return [{json: {status: 'published', platform: 'x', post_id: result.data.id,
  url: 'https://x.com/i/web/status/' + result.data.id}}];
""".strip()


def build_x(check_only=False):
    operation = 'check_account' if check_only else 'publish_text'
    config = {'operation': operation, 'dry_run': True}
    if not check_only:
        config.update(approved=False, text='Minha primeira publicacao de teste no X')
    # Mesmos controles de simulacao dos fluxos Meta, com contrato X independente.
    template = build('facebook')
    nodes = template['nodes'][:5]
    nodes[1]['parameters']['jsCode'] = 'return [{json: ' + json.dumps(config, ensure_ascii=False) + '}];'
    nodes[2]['parameters']['jsCode'] = X_VALIDATE
    edges = {name: template['connections'][name] for name in ('Inicio manual','Conteudo','Validar')}
    edges['Simular'] = {'main': [[{'node': 'Previa sem publicar', 'type': 'main', 'index': 0}],
                                [{'node': 'Consultar conta X', 'type': 'main', 'index': 0}]]}
    def request(name, method, url, x):
        result = node(name, 'httpRequest', {'method': method, 'url': url, 'authentication': 'none',
            'sendHeaders': True, 'headerParameters': {'parameters': [
                {'name': 'Authorization', 'value': "={{ 'Bearer ' + $env.X_OAUTH2_ACCESS_TOKEN }}"}]},
            'options': {'timeout': 30000, 'redirect': {'redirect': {'followRedirects': False}}}}, x, 120, 4.2)
        result['retryOnFail'] = False
        return result
    nodes.extend([request('Consultar conta X', 'GET', 'https://api.x.com/2/users/me', 900),
                  node('Conferir conta X', 'code', {'jsCode': X_CONFIRM_ACCOUNT}, 1120, 120, 2)])
    edges['Consultar conta X'] = {'main': [[{'node': 'Conferir conta X', 'type': 'main', 'index': 0}]]}
    if not check_only:
        publish = request('Publicar texto X', 'POST', 'https://api.x.com/2/tweets', 1340)
        publish['parameters'].update(sendBody=True, specifyBody='json',
            jsonBody="={{ JSON.stringify({text: $('Validar').first().json.text}) }}")
        nodes.extend([publish, node('Resultado X', 'code', {'jsCode': X_RESULT}, 1560, 120, 2)])
        edges['Conferir conta X'] = {'main': [[{'node': 'Publicar texto X', 'type': 'main', 'index': 0}]]}
        edges['Publicar texto X'] = {'main': [[{'node': 'Resultado X', 'type': 'main', 'index': 0}]]}
    return {'name': 'X - ' + ('verificar conta' if check_only else 'publicar texto manual') + ' (dry-run)',
            'active': False, 'nodes': nodes, 'connections': edges,
            'settings': {'executionOrder': 'v1', 'timezone': 'America/Cuiaba', 'saveManualExecutions': True},
            'pinData': {}, 'tags': []}


if __name__ == '__main__':
    for platform in ('facebook','instagram'):
        (ROOT / 'workflows' / f'{platform}-photo.json').write_text(json.dumps(build(platform), ensure_ascii=False, indent=2) + '\n')
    for filename, check in [('x-text.json', False), ('x-check-account.json', True)]:
        (ROOT / 'workflows' / filename).write_text(json.dumps(build_x(check), ensure_ascii=False, indent=2) + '\n')
