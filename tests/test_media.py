import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'services/editorial'))
from app import Editorial, EMPTY
from media_store import MediaStore
from media_publisher import Publisher

class MediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=tempfile.TemporaryDirectory()
        p=Path(cls.fixture.name)/'image.jpg'
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=red:s=64x64','-frames:v','1','-threads','1',str(p)],check=True)
        cls.jpeg=p.read_bytes()
    @classmethod
    def tearDownClass(cls):cls.fixture.cleanup()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.draft=dict(EMPTY,instagram_caption='Legenda de teste',destinations=['instagram'])
        self.bot=Editorial(self.root/'editorial.sqlite',writer=lambda h,d:{'reply':'Rascunho','draft':self.draft},workflows={'instagram':'internal'},publish_enabled=True)
        self.sid='session-media-test'
    def tearDown(self):self.temp.cleanup()
    def upload(self,name='foto.jpg'):return self.bot.media.upload(self.sid,name,self.jpeg)
    def test_upload_rejects_fake_media(self):
        with self.assertRaises(ValueError):self.bot.media.upload(self.sid,'foto.jpg',b'not an image')
    def test_normalized_jpeg_and_session_isolation(self):
        m=self.upload()
        with self.bot.db() as db:
            self.assertEqual(self.bot.media.asset(db,self.sid,m['asset_id'])['mime_type'],'image/jpeg')
            with self.assertRaises(ValueError):self.bot.media.asset(db,'other-session',m['asset_id'])
        self.assertTrue(self.bot.media.file(m['asset_id']+'.jpg').read_bytes().startswith(b'\xff\xd8'))
    def test_video_upload_validates_and_preserves_mp4(self):
        video=self.root/'video.mp4'
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=blue:s=64x64:d=3','-c:v','libx264','-pix_fmt','yuv420p','-threads','1',str(video)],check=True)
        item=self.bot.media.upload(self.sid,'video.mp4',video.read_bytes())
        self.assertEqual(item['mime_type'],'video/mp4')
        self.assertTrue(self.bot.media.file(item['asset_id']+'.mp4').is_file())

    def test_library_confines_paths_and_symlinks(self):
        library=self.root/'library';library.mkdir();outside=self.root/'outside.jpg';outside.write_bytes(self.jpeg)
        (library/'escape.jpg').symlink_to(outside)
        with patch.dict(os.environ,{'MEDIA_LIBRARY_ROOT':str(library),'MEDIA_LIBRARY_HOST_PATH':'/authorized'}):
            for path in ['../outside.jpg','escape.jpg','/etc/passwd','/authorized/escape.jpg']:
                with self.assertRaises(ValueError):self.bot.media.import_local(self.sid,path)
    def test_local_import_and_direct_file_url(self):
        library=self.root/'library';library.mkdir();(library/'foto.jpg').write_bytes(self.jpeg)
        with patch.dict(os.environ,{'MEDIA_LIBRARY_ROOT':str(library),'MEDIA_LIBRARY_HOST_PATH':'/authorized'}):
            r=self.bot.chat(self.sid,'file:///authorized/foto.jpg')
        self.assertIn('Importei 1',r['output'])
    def test_panel_key_only_accesses_own_session(self):
        self.bot.chat(self.sid,'MIDIAS')
        with self.bot.db() as db:key=self.bot.media.panel_key(db,self.sid)
        self.assertTrue(self.bot.media.authorize(self.sid,key));self.assertFalse(self.bot.media.authorize('other-session',key))
    def test_reordering_invalidates_confirmation_and_preserves_order(self):
        a=self.upload('a.jpg');b=self.upload('b.jpg');ids=[a['asset_id'],b['asset_id']]
        self.bot.attach(self.sid,ids)
        r=self.bot.chat(self.sid,'Prepare Instagram');token=re.search('SIMULAR ([a-f0-9]{8})',r['output'])[1]
        self.bot.attach(self.sid,ids[::-1])
        self.assertFalse(self.bot.chat(self.sid,'CONFIRMAR '+token)['jobs'])
        r=self.bot.chat(self.sid,'PREVIA');token=re.search('SIMULAR ([a-f0-9]{8})',r['output'])[1]
        job=self.bot.chat(self.sid,'SIMULAR '+token)['jobs'][0]
        self.assertEqual([m['name'] for m in job['payload']['media']],['b.jpg','a.jpg'])
        self.assertTrue(job['payload']['dry_run'])
    def test_live_without_hosting_does_not_consume_confirmation(self):
        self.bot.attach(self.sid,[self.upload()['asset_id']])
        with patch.dict(os.environ,{'MEDIA_PUBLIC_BASE_URL':''}):
            r=self.bot.chat(self.sid,'Prepare Instagram');token=re.search('SIMULAR ([a-f0-9]{8})',r['output'])[1]
            self.assertFalse(self.bot.chat(self.sid,'CONFIRMAR '+token)['jobs'])
            self.assertTrue(self.bot.chat(self.sid,'SIMULAR '+token)['jobs'])
    def test_duplicate_or_foreign_attachments_rejected(self):
        m=self.upload()
        with self.assertRaises(ValueError):self.bot.attach(self.sid,[m['asset_id']]*2)
        with self.assertRaises(ValueError):self.bot.attach('other-session',[m['asset_id']])
    def test_dispatch_blocks_media_edits(self):
        self.bot.attach(self.sid,[self.upload()['asset_id']])
        r=self.bot.chat(self.sid,'Prepare Instagram');token=re.search('SIMULAR ([a-f0-9]{8})',r['output'])[1]
        self.bot.chat(self.sid,'SIMULAR '+token)
        with self.assertRaises(ValueError):self.bot.attach(self.sid,[])
    def test_clear_attachments_does_not_reuse_previous_url(self):
        with self.bot.db() as db:
            self.bot.view(db,self.sid)
            draft=dict(self.draft,image_url='https://old.test/image.jpg')
            db.execute('UPDATE sessions SET draft=? WHERE id=?',(json.dumps(draft),self.sid))
        self.bot.attach(self.sid,[])
        with self.bot.db() as db:
            self.assertEqual(json.loads(self.bot.view(db,self.sid)['draft'])['image_url'],'')

    def test_cancel_clears_attachments(self):
        self.bot.attach(self.sid,[self.upload()['asset_id']]);self.bot.chat(self.sid,'cancelar')
        with self.bot.db() as db:self.assertEqual(self.bot.media.items(db,self.sid),[])

class PublishingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.calls=[];self.fail=False;self.counter=0
        def graph(route,data=None):
            self.calls.append((route,data))
            if data is not None:
                if self.fail:raise TimeoutError()
                self.counter+=1;return {'id':str(self.counter)}
            if 'username' in route:return {'username':'test-account'}
            return {'status_code':'FINISHED'}
        self.publisher=Publisher(Path(self.temp.name)/'publisher.sqlite',transport=graph,sleep=lambda _:None)
        self.env=patch.dict(os.environ,{'META_INSTAGRAM_ACCOUNT_ID':'123','META_GRAPH_VERSION':'v99.0','META_INSTAGRAM_ACCESS_TOKEN':'fake-test-token','MEDIA_PUBLIC_BASE_URL':'https://media.test/media/files'})
        self.env.start()
        self.p={'dry_run':False,'approved':True,'request_id':'a'*32,'caption':'Legenda de teste','media':[self.item('b'*32)]}
    def item(self,asset,mime='image/jpeg'):
        ext='jpg' if mime=='image/jpeg' else 'mp4'
        return {'asset_id':asset,'mime_type':mime,'url':'https://media.test/media/files/'+asset+'.'+ext}
    def tearDown(self):self.env.stop();self.temp.cleanup()
    def test_dry_run_does_not_call_api_or_require_credentials(self):
        with patch.dict(os.environ,{'META_INSTAGRAM_ACCESS_TOKEN':''}):
            self.assertEqual(self.publisher.publish(dict(self.p,dry_run=True))['status'],'dry_run')
        self.assertEqual(self.calls,[])
    def test_carousel_keeps_order_and_publishes_once(self):
        self.p['media'].append(self.item('c'*32))
        first=self.publisher.publish(self.p);count=len(self.calls)
        self.assertEqual(self.publisher.publish(self.p),first);self.assertEqual(len(self.calls),count)
        posts=[data for _,data in self.calls if data]
        self.assertEqual(posts[0]['image_url'],self.p['media'][0]['url'])
        self.assertEqual(posts[1]['image_url'],self.p['media'][1]['url'])
        self.assertEqual(posts[2]['children'],'1,2')
        self.assertEqual(posts[3],{'creation_id':'3'})
    def test_reel_and_mixed_carousel(self):
        self.p['media']=[self.item('b'*32,'video/mp4')]
        self.publisher.publish(self.p)
        data=[d for _,d in self.calls if d][0]
        self.assertEqual(data['media_type'],'REELS');self.assertIn('video_url',data)
    def test_story_uses_stories_without_caption_or_feed_flag(self):
        self.p.update(format='story',media=[self.item('b'*32,'video/mp4')])
        self.publisher.publish(self.p)
        data=[d for _,d in self.calls if d][0]
        self.assertEqual(data['media_type'],'STORIES')
        self.assertNotIn('caption',data);self.assertNotIn('share_to_feed',data)
        self.p['format']='reel'
        with self.assertRaises(ValueError):self.publisher.publish(self.p)

    def test_story_and_explicit_carousel_validate_before_api(self):
        for fmt in ('story','reel','carousel','invalid'):
            with self.assertRaises(ValueError):self.publisher.publish(dict(self.p,format=fmt))
        self.assertFalse(self.calls)

    def test_timeout_recorded_without_retry(self):
        self.fail=True
        with self.assertRaises(ValueError):self.publisher.publish(self.p)
        count=len(self.calls)
        with self.assertRaises(ValueError):self.publisher.publish(self.p)
        self.assertEqual(len(self.calls),count)
        with self.publisher.db() as db:self.assertEqual(db.execute('SELECT state FROM attempts').fetchone()[0],'unknown')
    def test_unapproved_or_arbitrary_url_never_posts(self):
        self.p['approved']=False
        with self.assertRaises(ValueError):self.publisher.publish(self.p)
        self.p['approved']=True;self.p['media'][0]['url']='https://other.test/file.jpg'
        with self.assertRaises(ValueError):self.publisher.publish(self.p)
        self.assertFalse(self.calls)
    def test_unfinished_container_never_publishes(self):
        def graph(route,data=None):
            if data is not None:
                self.assertFalse(route.endswith('/media_publish'));return {'id':'1'}
            return {'username':'test-account'} if 'username' in route else {'status_code':'IN_PROGRESS'}
        self.publisher.transport=graph
        with self.assertRaises(ValueError):self.publisher.publish(self.p)
        with self.publisher.db() as db:
            receipt=json.loads(db.execute('SELECT receipt FROM attempts').fetchone()[0])
        self.assertEqual(receipt['containers'],['1']);self.assertFalse(receipt['publish_started'])
