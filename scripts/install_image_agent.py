#!/usr/bin/env python3
"""Install only the dedicated image subagent, preserving the chat and publishers."""
import json
import secrets
import subprocess
from pathlib import Path
from build_image_workflow import image_agent
ROOT=Path(__file__).resolve().parents[1]


def main():
    path=ROOT/'.env';text=path.read_text();key='N8N_IMAGE_AGENT_WORKFLOW_ID'
    env=dict(l.split('=',1) for l in text.splitlines() if '=' in l and not l.startswith('#'))
    workflow_id=env.get(key,'').strip() or secrets.token_hex(8)
    workflow=image_agent();workflow['id']=workflow_id
    command=['docker','compose','exec','-T','n8n','sh','-c','cat > /tmp/image-agent-import.json && n8n import:workflow --input=/tmp/image-agent-import.json; result=$?; rm -f /tmp/image-agent-import.json; exit "$result"']
    subprocess.run(command,input=json.dumps(workflow),text=True,check=True,cwd=ROOT)
    if key in env:text='\n'.join(key+'='+workflow_id if l.startswith(key+'=') else l for l in text.splitlines())+'\n'
    else:text+=key+'='+workflow_id+'\n'
    path.write_text(text)
    subprocess.run(['docker','compose','exec','-T','n8n','n8n','publish:workflow','--id='+workflow_id],check=True,cwd=ROOT)
    print('Subagente de imagem instalado para chamadas internas. ID registrado no .env; nenhum segredo exibido.')

if __name__=='__main__':main()
