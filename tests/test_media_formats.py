import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'services/editorial'))
from media_store import MediaStore
from media_transform import MediaTransform

class VideoAssembly(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name);cls.store=MediaStore(cls.root/'media.sqlite');cls.sid='format-test-session'
        photo=cls.root/'photo.jpg'
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=blue:s=64x64','-frames:v','1','-threads','1',str(photo)],check=True)
        cls.items=[cls.store.upload(cls.sid,n,photo.read_bytes()) for n in ('primeira.jpg','segunda.jpg')]
        track=cls.root/'track.wav'
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=440:duration=4',str(track)],check=True)
        cls.track=cls.store.upload(cls.sid,'trilha.wav',track.read_bytes())
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def info(self,m):
        path=self.store.file(m['asset_id']+'.'+m['extension'])
        return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)]))
    def test_slideshow_music_duration_codecs_and_cached_render(self):
        options={'format':'Carrossel em video (Reels)','audio_mode':'Musica enviada','seconds_per_image':'1.5','music_volume':'40','music_start':'1'}
        renderer=MediaTransform(self.store)
        output,meta=renderer.prepare(self.sid,self.items,[self.track],options)
        info=self.info(output[0]);video=next(s for s in info['streams'] if s['codec_type']=='video');audio=next(s for s in info['streams'] if s['codec_type']=='audio')
        self.assertEqual((video['width'],video['height']),(720,1280));self.assertEqual(video['codec_name'],'h264');self.assertEqual(audio['codec_name'],'aac')
        self.assertAlmostEqual(float(info['format']['duration']),3,delta=.2)
        self.assertEqual(meta['source_names'],['primeira.jpg','segunda.jpg']);self.assertEqual(meta['format'],'reel')
        self.assertEqual(renderer.prepare(self.sid,self.items,[self.track],options)[0],output)
        with self.assertRaises(ValueError):renderer.prepare(self.sid,self.items[::-1],[self.track],options)
    def test_story_photo_becomes_vertical_video(self):
        output,meta=MediaTransform(self.store).prepare('story-test-session',self.items[:1],[],{'format':'Story','seconds_per_image':'3'})
        self.assertEqual(meta['format'],'story');info=self.info(output[0]);self.assertTrue(any(s['codec_type']=='video' for s in info['streams']));self.assertFalse(any(s['codec_type']=='audio' for s in info['streams']))
    def test_rejects_incompatible_formats_audio_and_duration(self):
        renderer=MediaTransform(self.store)
        for items,audio,options in [
            (self.items,[],{'format':'Story'}),
            (self.items,[],{'format':'Foto no feed'}),
            (self.items[:1],[],{'format':'Reels'}),
            (self.items[:1],[],{'format':'Carrossel'}),
            (self.items,[self.track],{'format':'Carrossel','audio_mode':'Musica enviada'}),
            (self.items,[],{'format':'Carrossel em video (Reels)','audio_mode':'Musica enviada'}),
            (self.items,[self.track],{'format':'Carrossel em video (Reels)'}),
            (self.items*2,[],{'format':'Carrossel em video (Story)','seconds_per_image':'30'}),
            (self.items,[],{'format':'Carrossel em video (Reels)','seconds_per_image':'nan'}),
            (self.items,[self.track],{'format':'Carrossel em video (Reels)','audio_mode':'Musica enviada','music_start':'300'}),
        ]:
            with self.subTest(options=options):
                with self.assertRaises(ValueError):renderer.prepare('invalid-format-session',items,audio,options)
