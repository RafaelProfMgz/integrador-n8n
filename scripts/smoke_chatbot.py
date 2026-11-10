#!/usr/bin/env python3
"""Exercise the real n8n->editorial->three subworkflows path, without an LLM or social API call."""
import json
import re
import secrets
import subprocess
from pathlib import Path
from build_chat_workflows import chatbot
from build_workflows import node

ROOT=Path(__file__).resolve().parents[1]

def docker(*args,stdin=None):
    result=subprocess.run(['docker','compose',*args],input=stdin,text=True,capture_output=True,cwd=ROOT)
    if result.returncode:
        raise RuntimeError('Falha no comando Docker de teste; consulte a execucao local.')
    return result.stdout


def import_workflow(workflow):
    docker('exec','-T','n8n','sh','-c','cat > /tmp/editorial-smoke-workflow.json && n8n import:workflow --input=/tmp/editorial-smoke-workflow.json; result=$?; rm -f /tmp/editorial-smoke-workflow.json; exit "$result"',stdin=json.dumps(workflow))


def main():
    env=dict(line.split('=',1) for line in (ROOT/'.env').read_text().splitlines() if '=' in line and not line.startswith('#'))
    workflow_id=env['N8N_EDITORIAL_CHAT_WORKFLOW_ID'].strip()
    if not workflow_id:raise RuntimeError('Instale primeiro com scripts/install_chatbot.py')
    exported=docker('exec','-T','n8n','node','-e',
        "const fs=require('fs'),cp=require('child_process');const result=cp.spawnSync('n8n',['export:workflow','--id='+process.argv[1],'--output=/tmp/editorial-current.json'],{encoding:'utf8'});if(result.status!==0)process.exit(1);process.stdout.write(fs.readFileSync('/tmp/editorial-current.json','utf8'));fs.unlinkSync('/tmp/editorial-current.json');",workflow_id)
    original=json.loads(exported)[0]
    if original.get('active'):
        raise RuntimeError('O chatbot esta publicado. Pare o teste para preservar as conversas em uso.')
    sid='editorial-smoke-'+secrets.token_hex(12)
    fixture="""import json\nfrom app import Editorial\nbot=Editorial('/data/editorial.sqlite')\nsid="""+repr(sid)+"""\ndraft={'facebook_caption':'Teste simulado Facebook','instagram_caption':'Teste simulado Instagram','x_text':'Teste simulado X','image_url':'https://example.com/imagem.jpg','destinations':['facebook','instagram','x']}\nwith bot.db() as db:\n db.execute('BEGIN IMMEDIATE')\n s=bot.view(db,sid)\n db.execute('UPDATE sessions SET revision=1,draft=? WHERE id=?',(json.dumps(draft),sid))\n s.update(revision=1)\n print(json.dumps(bot.preview(db,s,draft)))\n"""
    result=json.loads(docker('exec','-T','editorial','python','-',stdin=fixture))
    token=re.search(r'SIMULAR ([0-9a-f]{8})',result['output'])[1]
    smoke=chatbot();smoke['id']=workflow_id
    first=smoke['nodes'][0]
    first.update(type='n8n-nodes-base.manualTrigger',typeVersion=1,parameters={})
    first.pop('webhookId',None)
    smoke['nodes'].append(node('Entrada de teste','code',{'jsCode':'return [{json:'+json.dumps({'sessionId':sid,'chatInput':'SIMULAR '+token})+'}];'},100,version=2))
    smoke['connections']['Chat editorial']={'main':[[{'node':'Entrada de teste','type':'main','index':0}]]}
    smoke['connections']['Entrada de teste']={'main':[[{'node':'Conversar e preparar','type':'main','index':0}]]}
    try:
        import_workflow(smoke)
        log=docker('exec','-T','-e','N8N_RUNNERS_BROKER_PORT=5681','n8n','n8n','execute','--id='+workflow_id)
        assert 'Execution was successful' in log, 'Execucao nao concluiu'
        status_script="import json\nfrom app import Editorial\nbot=Editorial('/data/editorial.sqlite')\nwith bot.db() as db:\n row=db.execute('SELECT results,status FROM sessions WHERE id=?',("+repr(sid)+",)).fetchone()\n print(json.dumps(dict(row)))"
        status=json.loads(docker('exec','-T','editorial','python','-',stdin=status_script))
        results=json.loads(status['results'])
        assert status['status']=='completed'
        assert set(results)=={'facebook','instagram','x'}
        if not all(r['status']=='simulated' for r in results.values()):
            parsed=json.loads(log[log.index('{'):])
            runs=parsed['data']['resultData']['runData'].get('Chamar publicador',[])
            for run in runs:
                for output in run.get('data',{}).get('main',[]):
                    for item in output:
                        if item.get('json',{}).get('error'):print('Erro no subworkflow de teste:',item['json']['error'])
            raise AssertionError('Um subworkflow nao concluiu a simulacao')
        print('Simulacao completa passou: chat -> aprovacao -> Facebook/Instagram/X -> resultados separados. Nenhuma chamada OpenAI/social foi feita.')
    finally:
        import_workflow(original)

if __name__=='__main__':main()
