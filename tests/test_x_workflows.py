import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from build_manual_forms import manual_form

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('builder_x', ROOT/'scripts/build_workflows.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def run_code(code, payload, env=None):
    source = 'const $env='+json.dumps(env or {})+'; const $input={first:()=>({json:'+json.dumps(payload)+'})};'
    source += 'const run=()=>{'+code+'};console.log(JSON.stringify(run()));'
    return subprocess.run(['node','-e',source],capture_output=True,text=True)


class XWorkflows(unittest.TestCase):
    def content(self, **overrides):
        return dict(operation='publish_text', text='Ola, mundo!', dry_run=True, approved=False, **overrides)

    def test_dry_run_without_token(self):
        result = run_code(builder.X_VALIDATE, self.content())
        self.assertEqual(result.returncode,0,result.stderr)

    def test_live_requires_approval_token_and_account(self):
        p=self.content(); p['dry_run']=False
        self.assertNotEqual(run_code(builder.X_VALIDATE,p).returncode,0)
        p['approved']=True
        for env in [{}, {'X_OAUTH2_ACCESS_TOKEN':'dummy'}, {'X_USER_ID':'123'}]:
            self.assertNotEqual(run_code(builder.X_VALIDATE,p,env).returncode,0)
        result=run_code(builder.X_VALIDATE,p,{'X_OAUTH2_ACCESS_TOKEN':'dummy-secret','X_USER_ID':'123'})
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertNotIn('dummy-secret',result.stdout)
        self.assertNotIn('123',result.stdout)

    def test_boolean_and_text_validation(self):
        for field,value in [('dry_run','false'),('text','  '),('text','a'*281),('text','漢'*141),('text',None),('operation','delete')]:
            p=self.content();p[field]=value
            self.assertNotEqual(run_code(builder.X_VALIDATE,p).returncode,0)
        p=self.content();p['text']='a'*280
        self.assertEqual(run_code(builder.X_VALIDATE,p).returncode,0)

    def test_normalizes_accents_and_discards_extra_fields(self):
        p=self.content();p.update(text='cafe\u0301',access_token='must-not-leak')
        result=run_code(builder.X_VALIDATE,p)
        data=json.loads(result.stdout)[0]['json']
        self.assertEqual(data['text'],'café')
        self.assertNotIn('must-not-leak',result.stdout)

    def test_account_check_never_needs_publication_approval(self):
        p=dict(operation='check_account',dry_run=False)
        result=run_code(builder.X_VALIDATE,p,{'X_OAUTH2_ACCESS_TOKEN':'dummy'})
        self.assertEqual(result.returncode,0,result.stderr)

    def test_wrong_account_and_partial_errors_stop_publication(self):
        env={'X_USER_ID':'123'}
        for payload in [{'data':{'id':'456'}},{'data':{'id':123}},{'errors':[{'title':'error'}],'data':{'id':'123'}},{}]:
            self.assertNotEqual(run_code(builder.X_CONFIRM_ACCOUNT,payload,env).returncode,0)
        self.assertEqual(run_code(builder.X_CONFIRM_ACCOUNT,{'data':{'id':'123','username':'test'}},env).returncode,0)

    def test_post_result_requires_unambiguous_string_id(self):
        for payload in [{},{'data':{'id':123}},{'errors':[{}],'data':{'id':'123'}}]:
            self.assertNotEqual(run_code(builder.X_RESULT,payload).returncode,0)
        result=run_code(builder.X_RESULT,{'data':{'id':'123','text':'posted'}})
        self.assertIn('https://x.com/i/web/status/123',result.stdout)

    def test_read_only_workflow_has_no_write_path(self):
        workflow=builder.build_x(True)
        http=[n for n in workflow['nodes'] if n['type'].endswith('.httpRequest')]
        self.assertEqual([n['parameters']['method'] for n in http],['GET'])

    def test_dry_run_cannot_reach_http_and_account_guard_precedes_post(self):
        workflow=builder.build_x()
        edges=workflow['connections']
        preview=edges['Simular']['main'][0][0]['node']
        self.assertNotIn(preview,edges)
        self.assertEqual(edges['Conferir conta X']['main'][0][0]['node'],'Publicar texto X')
        post=next(n for n in workflow['nodes'] if n['name']=='Publicar texto X')
        self.assertEqual(post['parameters']['url'],'https://api.x.com/2/tweets')
        self.assertFalse(post['retryOnFail'])
        self.assertNotIn('media',post['parameters']['jsonBody'])
        for filename,check in [('x-text.json',False),('x-check-account.json',True)]:
            artifact=json.loads((ROOT/'workflows'/filename).read_text())
            self.assertEqual(artifact,builder.build_x(True) if check else manual_form('x'))
            self.assertFalse(artifact['active'])
