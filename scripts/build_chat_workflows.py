#!/usr/bin/env python3
"""Build the editorial chat and subworkflow entry points using existing publishers."""
import json
from pathlib import Path
from build_workflows import build, build_x, node

ROOT=Path(__file__).resolve().parents[1]


def publisher(platform):
    workflow=build_x() if platform=='x' else build(platform)
    workflow['name']='Editorial - publicador '+platform
    workflow['nodes']=[n for n in workflow['nodes'] if n['name'] not in ('Inicio manual','Conteudo')]
    for name in ('Inicio manual','Conteudo'): workflow['connections'].pop(name,None)
    trigger=node('Entrada editorial','executeWorkflowTrigger',{'inputSource':'passthrough'},0,version=1.1)
    fields="text: p.text, operation: 'publish_text'" if platform=='x' else 'caption: p.caption, image_url: p.image_url'
    prepare=node('Preparar publicacao','code',{'jsCode':"const p=$input.first().json.payload; if (!p || typeof p !== 'object') throw new Error('Payload editorial ausente'); return [{json:{platform: '"+platform+"',dry_run:p.dry_run,approved:p.approved,"+fields+"}}];"},220,version=2)
    workflow['nodes']=[trigger,prepare]+workflow['nodes']
    workflow['connections']['Entrada editorial']={'main':[[{'node':'Preparar publicacao','type':'main','index':0}]]}
    workflow['connections']['Preparar publicacao']={'main':[[{'node':'Validar','type':'main','index':0}]]}
    if platform!='x':
        name='Publicar foto Facebook' if platform=='facebook' else 'Publicar Instagram'
        result=node('Resultado editorial','code',{'jsCode':"const r=$input.first().json;const id="+("r.post_id || r.id" if platform=='facebook' else 'r.id')+";if(r.error || r.errors?.length || typeof id !== 'string' || !/^[0-9_]+$/.test(id)) throw new Error('Resultado remoto ambiguo; reconcilie antes de repetir');return [{json:{status:'published',platform:'"+platform+"',post_id:id}}];"},2000,120,2)
        workflow['nodes'].append(result)
        workflow['connections'][name]={'main':[[{'node':'Resultado editorial','type':'main','index':0}]]}
    return workflow


def service(name,path,body,x):
    return node(name,'httpRequest',{'method':'POST','url':'http://editorial:8080'+path,
         'sendBody':True,'specifyBody':'json','jsonBody':body,
         'options':{'timeout':90000}},x,version=4.2)


def chatbot():
    chat=node('Chat editorial','manualTrigger',{},0)
    chat.update(type='@n8n/n8n-nodes-langchain.chatTrigger',typeVersion=1.5,webhookId='editorial-social-chat')
    chat['parameters']={'public':False,'mode':'hostedChat','authentication':'n8nUserAuth','requireExecuteAccess':True,
       'availableInChat':False,'initialMessages':'Ola! Vamos criar sua publicacao. Qual e o assunto?',
       'options':{'responseMode':'lastNode','title':'Assistente de publicacoes','subtitle':'Prepare, revise e escolha suas redes','allowFileUploads':False}}
    nodes=[chat,
      service('Conversar e preparar','/chat',"={{ JSON.stringify({session_id:$json.sessionId,message:$json.chatInput}) }}",220),
      node('Tem envios','if',{'conditions':{'options':{'caseSensitive':True,'leftValue':'','typeValidation':'strict','version':2},
         'conditions':[{'id':'dispatch','leftValue':'={{ $json.jobs.length > 0 }}','rightValue':True,
            'operator':{'type':'boolean','operation':'true','singleValue':True}}],'combinator':'and'},'options':{}},440,version=2.2),
      node('Responder','code',{'jsCode':"return [{json:{output:$input.first().json.output}}];"},1500,200,2),
      node('Preparar envios','code',{'jsCode':"return $input.first().json.jobs.map(job=>({json:job}));"},660,0,2),
      node('Chamar publicador','executeWorkflow',{'source':'database','workflowId':{'__rl':True,'value':'={{ $json.workflow_id }}','mode':'id'},
          'mode':'each','options':{'waitForSubWorkflow':True}},880,version=1.3),
      node('Reunir resultados','code',{'jsCode':"const jobs=$('Preparar envios').all();const results=$input.all();if(jobs.length!==results.length) throw new Error('Numero inesperado de retornos; confira as execucoes antes de repetir');return [{json:{results:results.map((item,i)=>({job_id:jobs[i].json.job_id,result:item.json}))}}];"},1100,version=2),
      service('Registrar resultados','/results','={{ JSON.stringify($json) }}',1320)]
    nodes[5]['onError']='continueRegularOutput'
    edges={}
    def connect(a,b,index=0):
        main=edges.setdefault(a,{'main':[]})['main']
        while len(main)<=index: main.append([])
        main[index].append({'node':b,'type':'main','index':0})
    for a,b in [('Chat editorial','Conversar e preparar'),('Conversar e preparar','Tem envios'),('Tem envios','Preparar envios'),
                ('Preparar envios','Chamar publicador'),('Chamar publicador','Reunir resultados'),
                ('Reunir resultados','Registrar resultados'),('Registrar resultados','Responder')]: connect(a,b)
    connect('Tem envios','Responder',1)
    return {'name':'Editorial - chatbot de publicacoes','active':False,'nodes':nodes,'connections':edges,
            'settings':{'executionOrder':'v1','timezone':'America/Cuiaba','saveManualExecutions':True},'pinData':{},'tags':[]}


if __name__=='__main__':
    (ROOT/'workflows'/'editorial-chatbot.json').write_text(json.dumps(chatbot(),ensure_ascii=False,indent=2)+'\n')
    for platform in ('facebook','instagram','x'):
        (ROOT/'workflows'/'subworkflows'/f'publish-{platform}.json').write_text(json.dumps(publisher(platform),ensure_ascii=False,indent=2)+'\n')
