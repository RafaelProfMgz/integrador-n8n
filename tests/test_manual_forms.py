import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'services/editorial'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from app import Editorial
from build_manual_forms import manual_form

class ManualForms(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.bot=Editorial(Path(self.temp.name)/'db.sqlite',workflows={p:'internal-'+p for p in ('instagram','facebook','x')},publish_enabled=True)
        self.data={'session_id':'manual-instagram-test','platform':'instagram','form':{'description':'Descricao final','hashtags':'livros, leitura','tags':'perfil','image_url':'https://media.test/foto.jpg','mode':'Simular'}}
    def tearDown(self):self.temp.cleanup()
    def test_defaults_simulate_without_openai(self):
        del self.data['form']['mode']
        result=self.bot.manual_prepare(self.data)
        p=result['jobs'][0]['payload']
        self.assertTrue(p['dry_run']);self.assertFalse(p['approved'])
        self.assertEqual(p['caption'],'Descricao final\n\n@perfil\n\n#livros #leitura')
    def test_live_demands_confirmation_and_enabled_flag(self):
        self.data['form']['mode']='Publicar'
        with self.assertRaises(ValueError):self.bot.manual_prepare(self.data)
        self.data['form']['confirmation']=['CONFIRMO'];self.bot.live=False
        with self.assertRaises(ValueError):self.bot.manual_prepare(self.data)
        self.bot.live=True
        p=self.bot.manual_prepare(self.data)['jobs'][0]['payload']
        self.assertFalse(p['dry_run']);self.assertTrue(p['approved'])
    def test_duplicate_submission_never_dispatches_twice(self):
        self.assertTrue(self.bot.manual_prepare(self.data)['jobs'])
        self.assertFalse(self.bot.manual_prepare(self.data)['jobs'])
    def test_order_must_be_complete_permutation(self):
        ids=['a'*32,'b'*32]
        with self.bot.media.db() as db:
            for i,name in zip(ids,['a.jpg','b.jpg']):db.execute('INSERT INTO media_assets VALUES (?,?,?,?,?)',(i,self.data['session_id'],name,'image/jpeg','jpg'))
        self.data['attachments']=ids;self.data['form'].update(image_url='',order='2,2')
        with self.assertRaises(ValueError):self.bot.manual_prepare(self.data)
        self.data['form']['order']='2,1'
        p=self.bot.manual_prepare(self.data)['jobs'][0]['payload']
        self.assertEqual([m['name'] for m in p['media']],['b.jpg','a.jpg'])
    def test_x_form_sends_only_text(self):
        self.data.update(session_id='manual-x-test',platform='x');self.data['form'].update(image_url='')
        p=self.bot.manual_prepare(self.data)['jobs'][0]['payload']
        self.assertIn('text',p);self.assertNotIn('media',p)
    def test_story_or_music_cannot_silently_fall_back_to_photo_url(self):
        self.data['form']['format']='Story'
        with self.assertRaises(ValueError):self.bot.manual_prepare(self.data)

    def test_forms_require_login_and_have_live_choice(self):
        for platform in ('instagram','facebook','x'):
            w=manual_form(platform);trigger=w['nodes'][0]
            self.assertFalse(w['active']);self.assertEqual(trigger['parameters']['authentication'],'n8nUserAuth')
            fields=trigger['parameters']['formFields']['values'];mode=next(f for f in fields if f['fieldName']=='mode')
            self.assertEqual(mode['defaultValue'],'Simular')
            self.assertEqual([v['option'] for v in mode['fieldOptions']['values']],['Simular','Publicar'])
            names={n['name'] for n in w['nodes']}
            for source,edge in w['connections'].items():
                self.assertIn(source,names)
                for output in edge['main']:
                    for target in output:self.assertIn(target['node'],names)
