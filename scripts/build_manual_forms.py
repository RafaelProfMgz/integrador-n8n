#!/usr/bin/env python3
"""Authenticated manual publishing forms, using the same guarded editorial dispatch."""
import json
from pathlib import Path
from build_chat_workflows import chatbot
from build_workflows import node
ROOT=Path(__file__).resolve().parents[1]

def manual_form(platform):
    if platform not in ('instagram','facebook','x'):raise ValueError('Plataforma invalida')
    workflow=chatbot()
    label={'instagram':'Instagram','facebook':'Facebook (Pagina)','x':'X'}[platform]
    fields=[{'fieldLabel':'Descricao / legenda','fieldName':'description','fieldType':'textarea','requiredField':True},
            {'fieldLabel':'Hashtags','fieldName':'hashtags','placeholder':'Separe por espacos ou virgulas'},
            {'fieldLabel':'Mencoes / tags','fieldName':'tags','placeholder':'@perfil1 @perfil2'}]
    if platform!='x':
        fields += [{'fieldLabel':'Imagens ou video','fieldName':'media','fieldType':'file','multipleFiles':platform=='instagram','acceptFileTypes':'.jpg,.jpeg,.png,.mp4,.mov' if platform=='instagram' else '.jpg,.jpeg,.png'},
                   {'fieldLabel':'URL HTTPS da foto (opcional se anexou arquivo)','fieldName':'image_url'}]
    if platform=='instagram':
        fields += [{'fieldLabel':'Formato da publicacao','fieldName':'format','fieldType':'dropdown','defaultValue':'Automatico','requiredField':True,'fieldOptions':{'values':[{'option':v} for v in ('Automatico','Foto no feed','Story','Reels','Carrossel','Carrossel em video (Reels)','Carrossel em video (Story)')]}},
                   {'fieldLabel':'Audio','fieldName':'audio_mode','fieldType':'dropdown','defaultValue':'Manter audio original','fieldOptions':{'values':[{'option':v} for v in ('Manter audio original','Sem som','Musica enviada')]}},
                   {'fieldLabel':'Musica (arquivo com direito de uso)','fieldName':'music','fieldType':'file','multipleFiles':False,'acceptFileTypes':'.mp3,.wav,.m4a,.aac,.ogg'},
                   {'fieldLabel':'Segundos por imagem ao montar video','fieldName':'seconds_per_image','fieldType':'number','defaultValue':'5'},
                   {'fieldLabel':'Volume da musica (0 a 100)','fieldName':'music_volume','fieldType':'number','defaultValue':'60'},
                   {'fieldLabel':'Comecar musica em (segundos)','fieldName':'music_start','fieldType':'number','defaultValue':'0'},
                   {'fieldLabel':'Ordem dos arquivos (opcional)','fieldName':'order','placeholder':'Exemplo: 2,1,3. Vazio: ordem da selecao.'}]
    fields += [{'fieldLabel':'Modo','fieldName':'mode','fieldType':'dropdown','defaultValue':'Simular','requiredField':True,'fieldOptions':{'values':[{'option':'Simular'},{'option':'Publicar'}]}},
               {'fieldLabel':'Confirmacao de publicacao','fieldName':'confirmation','fieldType':'checkbox','fieldOptions':{'values':[{'option':'CONFIRMO'}]}}]
    form=workflow['nodes'][0]
    form.update(name='Formulario de publicacao',type='n8n-nodes-base.formTrigger',typeVersion=2.6,webhookId='manual-'+platform)
    form['parameters']={'authentication':'n8nUserAuth','requireExecuteAccess':True,'formTitle':'Publicar no '+label,
        'formDescription':'Preencha o conteudo final. Simular nao envia nada. Para envio real, selecione Publicar e marque CONFIRMO: o conteudo sera enviado a conta '+label+' configurada nesta instalacao. '+('Escolha foto, Story, Reels ou Carrossel. Pode montar video com as fotos em ordem e musica enviada. O catalogo de musicas do Instagram nao esta conectado. Stories exigem conta Business e nao exibem a legenda/hashtags deste formulario como texto na tela; inclua o texto na propria midia.' if platform=='instagram' else 'Aceita uma foto.' if platform=='facebook' else 'Aceita texto de ate 280 unidades ponderadas.'),
        'formFields':{'values':fields},'responseMode':'lastNode',
        'options':{'path':'publicar-'+platform,'buttonLabel':'Executar','appendAttribution':False,'includeUserInOutput':False}}
    context=node('Identificar formulario','code',{'jsCode':"const i=$input.first();return [{json:{...i.json,sessionId:'manual-"+platform+"-'+$execution.id},binary:i.binary}];"},40,version=2)
    workflow['nodes'].append(context)
    for n in workflow['nodes']:
        if n['type'].endswith('.httpRequest'):
            n['parameters']['url']=n['parameters']['url'].replace('Chat editorial','Identificar formulario')
        if n['name']=='Conversar e preparar':
            n['name']='Preparar formulario'
            n['parameters']['url']='http://editorial:8080/manual/prepare'
            n['parameters']['options']['timeout']=900000
            n['parameters']['jsonBody']="={{ JSON.stringify({session_id:$('Identificar formulario').first().json.sessionId,platform:'"+platform+"',form:$('Identificar formulario').first().json,attachments:$json.attachments || []}) }}"
    edges=workflow['connections'];edges['Formulario de publicacao']={'main':[[{'node':'Identificar formulario','type':'main','index':0}]]};edges['Identificar formulario']=edges.pop('Chat editorial')
    edges['Preparar formulario']=edges.pop('Conversar e preparar')
    for edge in edges.values():
        for output in edge['main']:
            for target in output:
                if target['node']=='Conversar e preparar':target['node']='Preparar formulario'
    completion=node('Resultado do formulario','form',{'operation':'completion','completionTitle':'Resultado da publicacao','completionMessage':'={{ $json.output }}','options':{}},1800,version=2.6)
    workflow['nodes'].append(completion)
    edges['Responder']={'main':[[{'node':'Resultado do formulario','type':'main','index':0}]]}
    workflow['name']='Manual - publicar no '+label+' (formulario)'
    return workflow

def main():
    for platform,filename in [('instagram','instagram-photo.json'),('facebook','facebook-photo.json'),('x','x-text.json')]:
        (ROOT/'workflows'/filename).write_text(json.dumps(manual_form(platform),ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
