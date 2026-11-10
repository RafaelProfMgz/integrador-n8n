#!/usr/bin/env python3
"""Import only comment workflows; keep polling inactive and publish internal helpers."""
import json
import secrets
import subprocess
from pathlib import Path
from build_comment_workflows import workflow
ROOT=Path(__file__).resolve().parents[1]


def main():
    path=ROOT/'.env';text=path.read_text();env=dict(l.split('=',1) for l in text.splitlines() if '=' in l and not l.startswith('#'));workflows=[]
    for kind in ('monitor','review','approve','skills'):
        key='N8N_COMMENTS_'+kind.upper()+'_WORKFLOW_ID';value=env.get(key,'').strip() or secrets.token_hex(8)
        if key in env:text='\n'.join(key+'='+value if line.startswith(key+'=') else line for line in text.splitlines())+'\n'
        else:text+=key+'='+value+'\n'
        data=workflow(kind);data['id']=value;workflows.append(data)
    command=['docker','compose','exec','-T','n8n','sh','-c','cat > /tmp/community-import.json && n8n import:workflow --input=/tmp/community-import.json; result=$?; rm -f /tmp/community-import.json; exit "$result"']
    subprocess.run(command,input=json.dumps(workflows),text=True,check=True,cwd=ROOT);path.write_text(text)
    for data in workflows[2:]:subprocess.run(['docker','compose','exec','-T','n8n','n8n','publish:workflow','--id='+data['id']],check=True,cwd=ROOT)
    print('Monitor/revisao importados inativos; helpers internos publicados. Nenhuma conta foi consultada nem resposta enviada.')

if __name__=='__main__':main()
