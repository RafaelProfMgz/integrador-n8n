import base64
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT/'services/editorial'))
from image_agent import ImageAgent
from app import Editorial, EMPTY
from build_image_workflow import image_agent

# Fixture apenas para testar o transporte binario e a validacao de assinatura, sem gerar uma arte.
JPEG=b'\xff\xd8\xff\xe0binary-test\xff\xd9'


class ImageGeneration(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.calls=[]
        def transport(payload):
            self.calls.append(payload)
            return {'data':[{'b64_json':base64.b64encode(JPEG).decode()}]}
        self.agent=ImageAgent(Path(self.temp.name)/'editorial.sqlite',transport=transport)
        self.request={'description':'Foto editorial de uma cafeteria acolhedora','dry_run':False,'request_id':'image-test-123'}
        self.env=patch.dict(os.environ,{'IMAGE_PUBLIC_BASE_URL':'','OPENAI_IMAGE_MODEL':'gpt-image-1.5'})
        self.env.start()
    def tearDown(self):self.env.stop();self.temp.cleanup()

    def test_simulation_never_calls_api_or_creates_file(self):
        result=self.agent.generate({'description':'Uma cafeteria'})
        self.assertEqual(result['status'],'dry_run');self.assertFalse(self.calls)
        self.assertFalse(list(self.agent.directory.iterdir()))

    def test_single_image_with_only_image_parameters_and_no_publication(self):
        result=self.agent.generate(self.request)
        self.assertEqual(result['status'],'image_generated');self.assertIsNone(result['image_url'])
        self.assertEqual(self.agent.file(result['asset_id']).read_bytes(),JPEG)
        payload=self.calls[0]
        self.assertEqual(payload['n'],1);self.assertEqual(payload['output_format'],'jpeg')
        self.assertNotIn('caption',payload);self.assertNotIn('destinations',payload)
        self.assertNotIn('b64_json',result)

    def test_repeated_request_returns_original_without_another_charge(self):
        first=self.agent.generate(self.request);second=self.agent.generate(self.request)
        self.assertEqual(first,second);self.assertEqual(len(self.calls),1)

    def test_same_id_cannot_be_reused_with_different_description(self):
        self.agent.generate(self.request)
        with self.assertRaises(ValueError):self.agent.generate({**self.request,'description':'Outra imagem'})
        self.assertEqual(len(self.calls),1)

    def test_uncertain_failure_is_not_retried(self):
        def failure(payload):self.calls.append(payload);raise TimeoutError('provider-secret')
        self.agent.transport=failure
        for _ in range(2):
            with self.assertRaises(ValueError) as caught:self.agent.generate(self.request)
            self.assertNotIn('provider-secret',str(caught.exception))
        self.assertEqual(len(self.calls),1)

    def test_invalid_description_flag_size_and_missing_id_stop_before_api(self):
        for change in [{'description':''},{'dry_run':'false'},{'size':'999x999'},{'quality':'max'},{'request_id':None}]:
            with self.assertRaises(ValueError):self.agent.generate({**self.request,**change})
        self.assertFalse(self.calls)

    def test_invalid_base64_and_wrong_format_are_not_returned_as_images(self):
        for i,encoded in enumerate(['not-base64','YWJjZA==']):
            self.agent.transport=lambda payload:{'data':[{'b64_json':encoded}]}
            with self.assertRaises(ValueError):self.agent.generate({**self.request,'request_id':'bad-image-'+str(i)})
        self.assertFalse(list(self.agent.directory.iterdir()))

    def test_public_url_is_configured_not_fabricated(self):
        with patch.dict(os.environ,{'IMAGE_PUBLIC_BASE_URL':'https://media.test/images/files/'}):
            result=self.agent.generate(self.request)
        self.assertEqual(result['image_url'],'https://media.test/images/files/'+result['asset_id']+'.jpg')

    def test_public_host_can_be_configured_after_generation_without_new_charge(self):
        first=self.agent.generate(self.request)
        self.assertIsNone(first['image_url'])
        with patch.dict(os.environ,{'IMAGE_PUBLIC_BASE_URL':'https://media.test/images/files'}):
            cached=self.agent.generate(self.request)
        self.assertTrue(cached['image_url'].startswith('https://media.test/'))
        self.assertEqual(len(self.calls),1)

    def test_invalid_public_base_stops_before_api(self):
        for url in ['http://media.test','https://user:secret@media.test','https://media.test/?key=secret']:
            with patch.dict(os.environ,{'IMAGE_PUBLIC_BASE_URL':url}):
                with self.assertRaises(ValueError):self.agent.generate(self.request)
        self.assertFalse(self.calls)

    def test_cannot_read_arbitrary_file(self):
        for asset in ['../.env','../../etc/passwd','zz'*16]:
            with self.assertRaises(ValueError):self.agent.file(asset)


class ImageChatIntegration(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.bot=Editorial(Path(self.temp.name)/'db.sqlite',workflows={'facebook':'fb','instagram':'ig','x':'x'},publish_enabled=False)
        self.bot.image_workflow_id='image-workflow'
        self.sid='image-session-123'
    def tearDown(self):self.temp.cleanup()

    def test_explicit_description_dispatches_only_image_subagent(self):
        result=self.bot.chat(self.sid,'SIMULAR IMAGEM: uma praia ao amanhecer')
        self.assertEqual(len(result['jobs']),1)
        job=result['jobs'][0]
        self.assertEqual(job['workflow_id'],'image-workflow');self.assertEqual(job['platform'],'image')
        self.assertTrue(job['payload']['dry_run']);self.assertNotIn('approved',job['payload'])
        self.assertFalse(self.bot.chat(self.sid,'SIMULAR IMAGEM: novamente')['jobs'])

    def test_image_generation_does_not_depend_on_live_publication_flag(self):
        result=self.bot.chat(self.sid,'GERAR IMAGEM: uma praia')
        self.assertFalse(result['jobs'][0]['payload']['dry_run'])
        self.assertNotIn('caption',result['jobs'][0]['payload'])

    def test_real_image_requires_recorded_generation_before_attach(self):
        job=self.bot.chat(self.sid,'GERAR IMAGEM: uma praia')['jobs'][0]
        result=self.bot.results([{'job_id':job['job_id'],'result':{'status':'image_generated','image_url':'https://invented.test/a.jpg'}}])
        self.assertIn('incerto',result['output'])

    def test_generated_image_without_public_url_clears_old_image_and_approval(self):
        with self.bot.db() as db:
            self.bot.view(db,self.sid)
            db.execute('UPDATE sessions SET draft=?,token=?,status=? WHERE id=?',(json.dumps(dict(EMPTY,image_url='https://old.test/a.jpg')),'old-code','preview',self.sid))
        job=self.bot.chat(self.sid,'GERAR IMAGEM: uma praia')['jobs'][0]
        self.bot.images.transport=lambda p:{'data':[{'b64_json':base64.b64encode(JPEG).decode()}]}
        with patch.dict(os.environ,{'IMAGE_PUBLIC_BASE_URL':''}):generated=self.bot.images.generate(job['payload'])
        result=self.bot.results([{'job_id':job['job_id'],'result':generated}])
        self.assertIn('arquivo esta disponivel',result['output'])
        with self.bot.db() as db:
            row=self.bot.view(db,self.sid)
            self.assertIsNone(row['token']);self.assertEqual(json.loads(row['draft'])['image_url'],'')

    def test_workflow_has_no_social_or_editorial_node(self):
        workflow=image_agent()
        self.assertFalse(workflow['active'])
        self.assertEqual(workflow['nodes'][0]['type'],'n8n-nodes-base.executeWorkflowTrigger')
        self.assertNotIn('graph.facebook.com',json.dumps(workflow));self.assertNotIn('api.x.com',json.dumps(workflow))
        self.assertNotIn('$env',json.dumps(workflow))
        self.assertFalse(any(n.get('retryOnFail') for n in workflow['nodes']))

if __name__=='__main__':unittest.main()
