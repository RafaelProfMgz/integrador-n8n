#!/usr/bin/env python3
"""Import only editorial workflows; keep their instance IDs exclusively in local .env."""
import json
import secrets
import subprocess
from pathlib import Path
from build_chat_workflows import chatbot, publisher

ROOT=Path(__file__).resolve().parents[1]

def main():
    env_path=ROOT/'.env'
    text=env_path.read_text()
    settings=dict(line.split('=',1) for line in text.splitlines() if '=' in line and not line.startswith('#'))
    workflows=[]
    definitions=[('N8N_EDITORIAL_CHAT_WORKFLOW_ID',chatbot())]+[('N8N_PUBLISH_'+p.upper()+'_WORKFLOW_ID',publisher(p)) for p in ('facebook','instagram','x')]
    for key,data in definitions:
        workflow_id=settings.get(key,'').strip()
        if not workflow_id:
            workflow_id=secrets.token_hex(8)
            if key in settings:
                text='\n'.join(key+'='+workflow_id if line.startswith(key+'=') else line for line in text.splitlines())+'\n'
            else: text += key+'='+workflow_id+'\n'
        data['id']=workflow_id;workflows.append(data)
    # No keys or account IDs enter this payload. Existing manual workflows are preserved.
    command=['docker','compose','exec','-T','n8n','sh','-c',
             'cat > /tmp/editorial-import.json && n8n import:workflow --input=/tmp/editorial-import.json; result=$?; rm -f /tmp/editorial-import.json; exit "$result"']
    subprocess.run(command,input=json.dumps(workflows),text=True,check=True,cwd=ROOT)
    env_path.write_text(text)
    for data in workflows[1:]:
        subprocess.run(['docker','compose','exec','-T','n8n','n8n','publish:workflow','--id='+data['id']],check=True,cwd=ROOT)
    print('Chat importado inativo; tres publicadores publicados somente com trigger interno. IDs registrados no .env; nenhum segredo exibido.')

if __name__=='__main__': main()
