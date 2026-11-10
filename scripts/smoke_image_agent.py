#!/usr/bin/env python3
"""Validate image chat routing and native binary output using a recorded fixture, with no paid API call."""
import json
import secrets
from pathlib import Path
from build_chat_workflows import chatbot
from build_workflows import node
from smoke_chatbot import docker, import_workflow
ROOT=Path(__file__).resolve().parents[1]


def main():
    env=dict(l.split('=',1) for l in (ROOT/'.env').read_text().splitlines() if '=' in l and not l.startswith('#'))
    root_id=env['N8N_EDITORIAL_CHAT_WORKFLOW_ID'].strip();image_id=env['N8N_IMAGE_AGENT_WORKFLOW_ID'].strip()
    exported=docker('exec','-T','n8n','node','-e',
      "const fs=require('fs'),cp=require('child_process');const r=cp.spawnSync('n8n',['export:workflow','--id='+process.argv[1],'--output=/tmp/image-smoke-current.json'],{encoding:'utf8'});if(r.status)process.exit(1);process.stdout.write(fs.readFileSync('/tmp/image-smoke-current.json','utf8'));fs.unlinkSync('/tmp/image-smoke-current.json');",root_id)
    original=json.loads(exported)[0]
    if original.get('active'):raise RuntimeError('Nao execute o teste sobre um chatbot publicado/em uso.')
    sid='image-smoke-'+secrets.token_hex(12);request_id='fixture-'+secrets.token_hex(12);asset_id=None
    try:
        smoke=chatbot();smoke['id']=root_id
        first=smoke['nodes'][0];first.update(type='n8n-nodes-base.manualTrigger',typeVersion=1,parameters={});first.pop('webhookId',None)
        smoke['nodes'].append(node('Entrada de teste','code',{'jsCode':'return [{json:'+json.dumps({'sessionId':sid,'chatInput':'SIMULAR IMAGEM: arte de uma cafeteria acolhedora'})+'}];'},100,version=2))
        smoke['connections']['Chat editorial']={'main':[[{'node':'Entrada de teste','type':'main','index':0}]]}
        smoke['connections']['Entrada de teste']={'main':[[{'node':'Conversar e preparar','type':'main','index':0}]]}
        import_workflow(smoke)
        log=docker('exec','-T','-e','N8N_RUNNERS_BROKER_PORT=5681','n8n','n8n','execute','--id='+root_id)
        assert 'Execution was successful' in log
        check="import json\nfrom app import Editorial\nb=Editorial('/data/editorial.sqlite')\nwith b.db() as d:\n r=d.execute('SELECT results FROM sessions WHERE id=?',("+repr(sid)+",)).fetchone()\n print(r['results'])"
        state=json.loads(docker('exec','-T','editorial','python','-',stdin=check))
        assert state['image']['status']=='simulated'
        print('Chat -> subagente de imagem -> simulacao: passou.')
        description='Fixture binaria de teste; sem arte gerada por IA'
        payload={'description':description,'dry_run':False,'request_id':request_id}
        seed="import base64,json\nfrom image_agent import ImageAgent\na=ImageAgent('/data/editorial.sqlite',transport=lambda p:{'data':[{'b64_json':base64.b64encode(b'\\xff\\xd8\\xff\\xe0binary-test\\xff\\xd9').decode()}]})\nprint(json.dumps(a.generate("+repr(payload)+")))"
        metadata=json.loads(docker('exec','-T','editorial','python','-',stdin=seed));asset_id=metadata['asset_id']
        harness={'id':root_id,'name':'Editorial - teste temporario de binario','active':False,'settings':{'executionOrder':'v1'},'nodes':[
            node('Inicio','manualTrigger',{},0),node('Entrada','code',{'jsCode':'return [{json:{payload:'+json.dumps(payload)+'}}];'},200,version=2),
            node('Subagente','executeWorkflow',{'source':'database','workflowId':{'__rl':True,'value':image_id,'mode':'id'},'mode':'each','options':{'waitForSubWorkflow':True}},400,version=1.3),
            node('Conferir binario','code',{'jsCode':"const r=$input.first();if(r.json.status!=='image_generated'||!r.binary?.data||r.binary.data.mimeType!=='image/jpeg')throw new Error('Binario JPEG ausente');return [{json:{status:'binary_verified'}}];"},600,version=2)],'connections':{}}
        for a,b in [('Inicio','Entrada'),('Entrada','Subagente'),('Subagente','Conferir binario')]:harness['connections'][a]={'main':[[{'node':b,'type':'main','index':0}]]}
        import_workflow(harness)
        log=docker('exec','-T','-e','N8N_RUNNERS_BROKER_PORT=5681','n8n','n8n','execute','--id='+root_id)
        assert 'Execution was successful' in log and 'binary_verified' in log, 'Binario nao retornou ao workflow chamador'
        print('Subagente -> arquivo interno -> binario JPEG no n8n: passou com fixture offline; nenhuma chamada OpenAI/social.')
    finally:
        import_workflow(original)
        if asset_id:
            cleanup="import sqlite3\nfrom pathlib import Path\np=Path('/data/generated-images')/"+repr(asset_id+'.jpg')+"\np.unlink(missing_ok=True)\nd=sqlite3.connect('/data/editorial.sqlite')\nd.execute('DELETE FROM image_requests WHERE id=?',("+repr(request_id)+",))\nd.commit();d.close()"
            docker('exec','-T','editorial','python','-',stdin=cleanup)

if __name__=='__main__':main()
