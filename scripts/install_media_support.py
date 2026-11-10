#!/usr/bin/env python3
"""Update only chat and Instagram adapter; preserve the chat's publication state."""
import json
import argparse
import subprocess
from pathlib import Path
from build_chat_workflows import chatbot, publisher
ROOT=Path(__file__).resolve().parents[1]

def docker(*args, data=None):
    r=subprocess.run(['docker','compose','exec','-T','n8n',*args],input=data,text=True,capture_output=True,cwd=ROOT)
    if r.returncode:raise RuntimeError('Falha no comando n8n; nenhum envio foi iniciado.')
    return r.stdout

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--publish-chat',action='store_true');args=parser.parse_args()
    env=dict(l.split('=',1) for l in (ROOT/'.env').read_text().splitlines() if '=' in l and not l.startswith('#'))
    keys=['N8N_EDITORIAL_CHAT_WORKFLOW_ID','N8N_PUBLISH_INSTAGRAM_WORKFLOW_ID']
    definitions=[chatbot(),publisher('instagram')]
    active_chat=False
    for key,workflow in zip(keys,definitions):
        workflow_id=env.get(key,'').strip()
        if not workflow_id:raise ValueError('Instale primeiro o chatbot.')
        raw=docker('node','-e',"const cp=require('child_process'),fs=require('fs');const r=cp.spawnSync('n8n',['export:workflow','--id='+process.argv[1],'--output=/tmp/media-current.json'],{encoding:'utf8'});if(r.status!==0)process.exit(1);process.stdout.write(fs.readFileSync('/tmp/media-current.json','utf8'));fs.unlinkSync('/tmp/media-current.json');",workflow_id)
        current=json.loads(raw)[0]
        if key==keys[0]:active_chat=bool(current.get('active'))
        workflow['id']=workflow_id
    if args.publish_chat:
        definitions[0]['nodes'][0]['parameters']['public']=True
        definitions[0]['nodes'][0]['parameters']['initialMessages']='Envie suas fotos ou um video e diga a legenda. Para selecionar varios arquivos e mudar a ordem, digite MIDIAS.'
    docker('sh','-c','cat > /tmp/media-support.json && n8n import:workflow --input=/tmp/media-support.json',data=json.dumps(definitions))
    docker('n8n','publish:workflow','--id='+definitions[1]['id'])
    if active_chat or args.publish_chat:docker('n8n','publish:workflow','--id='+definitions[0]['id'])
    print('Chat e adaptador Instagram atualizados. Estado de publicacao do chat preservado. Nenhuma publicacao social executada.')

if __name__=='__main__':main()
