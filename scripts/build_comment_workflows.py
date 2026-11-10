#!/usr/bin/env python3
"""Owned-account comment polling and explicit review workflows."""
import json
from pathlib import Path
from build_workflows import node
ROOT=Path(__file__).resolve().parents[1]


def http(name,path,x=220,method='POST',body='={{ JSON.stringify({}) }}'):
    p={'method':method,'url':'http://community:8080'+path,'options':{'timeout':300000}}
    if method=='POST':p.update(sendBody=True,specifyBody='json',jsonBody=body)
    n=node(name,'httpRequest',p,x,version=4.2);n['retryOnFail']=False
    return n


def workflow(kind):
    edges={}
    def connect(a,b):edges[a]={'main':[[{'node':b,'type':'main','index':0}]]}
    if kind=='monitor':
        nodes=[node('Verificar agora','manualTrigger',{},0),node('A cada 15 minutos','scheduleTrigger',{'rule':{'interval':[{'field':'minutes','minutesInterval':15}]}},0,220,1.2),
          http('Buscar e classificar comentarios','/run',body='={{ JSON.stringify({}) }}'),
          node('Resumo do ciclo','code',{'jsCode':'return [{json:$input.first().json}];'},440,version=2)]
        connect('Verificar agora','Buscar e classificar comentarios');connect('A cada 15 minutos','Buscar e classificar comentarios');connect('Buscar e classificar comentarios','Resumo do ciclo')
        name='Comunidade livros - monitorar comentarios recentes'
    elif kind=='review':
        nodes=[node('Consultar revisao','manualTrigger',{},0),http('Fila de respostas','/review',method='GET')]
        connect('Consultar revisao','Fila de respostas');name='Comunidade livros - revisar respostas'
    elif kind=='approve':
        nodes=[node('Aprovacao recebida','executeWorkflowTrigger',{'inputSource':'passthrough'},0,version=1.1),
          node('Validar aprovacao','code',{'jsCode':"const p=$input.first().json;if(typeof p.record_id!=='string'||typeof p.approval_token!=='string')throw new Error('Informe record_id e approval_token vistos na fila de revisao');return [{json:{record_id:p.record_id,approval_token:p.approval_token}}];"},220,version=2),
          http('Enviar resposta aprovada','/approve',440,body='={{ JSON.stringify($json) }}')]
        connect('Aprovacao recebida','Validar aprovacao');connect('Validar aprovacao','Enviar resposta aprovada');name='Comunidade livros - aprovar resposta'
    else:
        nodes=[node('Comentario recebido','executeWorkflowTrigger',{'inputSource':'passthrough'},0,version=1.1),
          http('Aplicar skill de resposta','/draft',body="={{ JSON.stringify({text:$json.text,comment_id:$json.comment_id || ''}) }}")]
        connect('Comentario recebido','Aplicar skill de resposta');name='Subagente - skills de resposta comunidade de livros'
    return {'name':name,'active':False,'nodes':nodes,'connections':edges,'settings':{'executionOrder':'v1','timezone':'America/Cuiaba','saveManualExecutions':True},'pinData':{},'tags':[]}

if __name__=='__main__':
    for kind in ('monitor','review','approve','skills'):
        (ROOT/'workflows'/('community-comments-'+kind+'.json')).write_text(json.dumps(workflow(kind),ensure_ascii=False,indent=2)+'\n')
