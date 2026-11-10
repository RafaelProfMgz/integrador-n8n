#!/usr/bin/env python3
"""Replace manual demo workflows with authenticated forms; preserve instance IDs in .env."""
import argparse
import json
import secrets
import subprocess
from pathlib import Path
from build_manual_forms import manual_form
ROOT=Path(__file__).resolve().parents[1]

def docker(*args,data=None):
    r=subprocess.run(['docker','compose','exec','-T','n8n',*args],input=data,text=True,capture_output=True,cwd=ROOT)
    if r.returncode:raise RuntimeError('Falha ao instalar formularios n8n; confira o servico.')
    return r.stdout

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--publish',action='store_true');args=parser.parse_args()
    path=ROOT/'.env';text=path.read_text();env=dict(l.split('=',1) for l in text.splitlines() if '=' in l and not l.startswith('#'))
    raw=docker('node','-e',"const fs=require('fs'),cp=require('child_process');const r=cp.spawnSync('n8n',['export:workflow','--all','--output=/tmp/manual-current.json'],{encoding:'utf8'});if(r.status!==0)process.exit(1);process.stdout.write(fs.readFileSync('/tmp/manual-current.json','utf8'));fs.unlinkSync('/tmp/manual-current.json');")
    existing=json.loads(raw);definitions=[]
    names={'instagram':'Meta - instagram - foto manual (dry-run)','facebook':'Meta - facebook - foto manual (dry-run)','x':'X - publicar texto manual (dry-run)'}
    for platform in ('instagram','facebook','x'):
        workflow=manual_form(platform);key='N8N_MANUAL_'+platform.upper()+'_WORKFLOW_ID'
        matches=[w for w in existing if w['name'] in (names[platform],workflow['name'])]
        workflow_id=env.get(key,'').strip()
        if not workflow_id:
            if len(matches)>1:raise ValueError('Ha modelos manuais duplicados; defina '+key+' no .env antes de instalar.')
            workflow_id=matches[0]['id'] if matches else secrets.token_hex(8)
        workflow['id']=workflow_id;definitions.append(workflow)
        if key in env:text='\n'.join(key+'='+workflow_id if l.startswith(key+'=') else l for l in text.splitlines())+'\n'
        else:text+=key+'='+workflow_id+'\n'
    docker('sh','-c','cat > /tmp/manual-forms.json && n8n import:workflow --input=/tmp/manual-forms.json',data=json.dumps(definitions))
    path.write_text(text);path.chmod(0o600)
    if args.publish:
        for workflow in definitions:docker('n8n','publish:workflow','--id='+workflow['id'])
    print('Tres formularios instalados'+(' e publicados com login n8n.' if args.publish else ' inativos.')+' Nenhum post enviado.')
if __name__=='__main__':main()
