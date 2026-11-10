#!/usr/bin/env python3
"""Verify monitoring with reads disabled and native skill routing, without social API access."""
import json
from pathlib import Path
from build_workflows import node
from smoke_chatbot import docker,import_workflow
ROOT=Path(__file__).resolve().parents[1]


def main():
    env=dict(l.split('=',1) for l in (ROOT/'.env').read_text().splitlines() if '=' in l and not l.startswith('#'))
    monitor_id=env['N8N_COMMENTS_MONITOR_WORKFLOW_ID'].strip();skills_id=env['N8N_COMMENTS_SKILLS_WORKFLOW_ID'].strip()
    status=json.loads(docker('exec','-T','n8n','node','-e',"fetch('http://community:8080/status').then(r=>r.json()).then(v=>process.stdout.write(JSON.stringify(v)))"))
    if status['read_enabled'] or status['send_enabled']:raise RuntimeError('Teste requer leitura/envio desligados no servico real.')
    exported=docker('exec','-T','n8n','node','-e',"const fs=require('fs'),cp=require('child_process');const r=cp.spawnSync('n8n',['export:workflow','--id='+process.argv[1],'--output=/tmp/comments-current.json'],{encoding:'utf8'});if(r.status)process.exit(1);process.stdout.write(fs.readFileSync('/tmp/comments-current.json','utf8'));fs.unlinkSync('/tmp/comments-current.json');",monitor_id)
    original=json.loads(exported)[0]
    if original.get('active'):raise RuntimeError('Nao teste sobre monitor publicado/em uso.')
    log=docker('exec','-T','-e','N8N_RUNNERS_BROKER_PORT=5681','n8n','n8n','execute','--id='+monitor_id)
    assert 'Execution was successful' in log and 'setup_required' in log
    print('Monitor n8n -> servico: leitura/envio desligados confirmados.')
    fixture={'id':monitor_id,'name':'Comunidade - teste temporario de skills','active':False,'settings':{'executionOrder':'v1'},'nodes':[
      node('Inicio','manualTrigger',{},0),node('Comentario de teste','code',{'jsCode':"return [{json:{text:'Onde encontro o link do site?',comment_id:'test-comment'}}];"},220,version=2),
      node('Skill de resposta','executeWorkflow',{'source':'database','workflowId':{'__rl':True,'value':skills_id,'mode':'id'},'mode':'each','options':{'waitForSubWorkflow':True}},440,version=1.3),
      node('Validar resposta','code',{'jsCode':"const r=$input.first().json;if(r.skill!=='bio_access'||r.action!=='auto'||!r.reply.includes('bio')||r.reply.includes('{community_name}'))throw new Error('Skill invalida');return [{json:{status:'skill_verified'}}];"},660,version=2)],'connections':{}}
    for a,b in [('Inicio','Comentario de teste'),('Comentario de teste','Skill de resposta'),('Skill de resposta','Validar resposta')]:fixture['connections'][a]={'main':[[{'node':b,'type':'main','index':0}]]}
    try:
        import_workflow(fixture)
        log=docker('exec','-T','-e','N8N_RUNNERS_BROKER_PORT=5681','n8n','n8n','execute','--id='+monitor_id)
        assert 'Execution was successful' in log and 'skill_verified' in log
        print('Workflow -> subagente de resposta -> skill link na bio: passou. Nenhuma API social ou LLM foi chamada.')
    finally:import_workflow(original)

if __name__=='__main__':main()
