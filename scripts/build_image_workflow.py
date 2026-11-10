#!/usr/bin/env python3
"""Single-purpose image generation subworkflow; no editorial or publishing nodes."""
import json
from pathlib import Path
from build_workflows import node
from build_chat_workflows import service
ROOT=Path(__file__).resolve().parents[1]


def image_agent():
    prepare=r"""const input=$input.first().json;const p=input.payload ?? input;
if(typeof p.description!=='string'||!p.description.trim())throw new Error('Informe description');
const dry=p.dry_run ?? true;if(typeof dry!=='boolean')throw new Error('dry_run deve ser booleano');
return [{json:{description:p.description,dry_run:dry,request_id:p.request_id ?? ('image-request-'+$execution.id),size:p.size ?? '1024x1024',quality:p.quality ?? 'medium'}}];"""
    generate=service('Gerar imagem','/images/generate','={{ JSON.stringify($json) }}',440)
    generate['parameters']['options']['timeout']=240000
    generate['retryOnFail']=False
    gate=node('Verificar geracao','code',{'jsCode':"const r=$input.first().json;if(r.status==='dry_run')return [{json:r}];if(r.status!=='image_generated'||!/^[a-f0-9]{32}$/.test(r.asset_id))throw new Error('Geracao nao concluida; verifique chave, modelo e registro da tentativa antes de repetir');return [{json:r}];"},660,version=2)
    condition=node('Tem arquivo','if',{'conditions':{'options':{'caseSensitive':True,'leftValue':'','typeValidation':'strict','version':2},
        'conditions':[{'id':'image-file','leftValue':"={{ $json.status === 'image_generated' }}",'rightValue':True,
        'operator':{'type':'boolean','operation':'true','singleValue':True}}],'combinator':'and'},'options':{}},880,version=2.2)
    download=node('Baixar JPEG','httpRequest',{'method':'GET','url':"={{ 'http://editorial:8080/images/files/' + $json.asset_id + '.jpg' }}",
        'options':{'timeout':30000,'response':{'response':{'responseFormat':'file','outputPropertyName':'data'}}}},1100,version=4.2)
    result=node('Retornar imagem','code',{'jsCode':"return [{json:$('Verificar geracao').first().json,binary:$input.first().binary}];"},1320,version=2)
    nodes=[node('Descricao recebida','executeWorkflowTrigger',{'inputSource':'passthrough'},0,version=1.1),
           node('Preparar descricao','code',{'jsCode':prepare},220,version=2),generate,gate,condition,download,result]
    edges={}
    for a,b in [('Descricao recebida','Preparar descricao'),('Preparar descricao','Gerar imagem'),('Gerar imagem','Verificar geracao'),('Verificar geracao','Tem arquivo'),('Tem arquivo','Baixar JPEG'),('Baixar JPEG','Retornar imagem')]:
        edges[a]={'main':[[{'node':b,'type':'main','index':0}]]}
    # O ramo falso retorna diretamente os metadados de simulacao, sem chamar provedor/baixar arquivo.
    preview=node('Retornar simulacao','code',{'jsCode':'return $input.all();'},1100,220,2)
    nodes.append(preview)
    edges['Tem arquivo']['main'].append([{'node':'Retornar simulacao','type':'main','index':0}])
    return {'name':'Subagente - gerar imagem para publicacao','active':False,'nodes':nodes,'connections':edges,
      'settings':{'executionOrder':'v1','timezone':'America/Cuiaba','saveManualExecutions':True},'pinData':{},'tags':[]}

if __name__=='__main__':
    (ROOT/'workflows/subworkflows/generate-image.json').write_text(json.dumps(image_agent(),ensure_ascii=False,indent=2)+'\n')
