"""Session-owned media; local library access is explicitly confined to one read-only mount."""
import json
from contextlib import contextmanager
import os
import re
import secrets
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse, unquote

LIMIT = 100 * 1024 * 1024

class MediaStore:
    def __init__(self, db_path):
        self.db_path = str(db_path)
        self.directory = Path(db_path).parent / 'uploaded-media'
        self.directory.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS media_assets
              (id TEXT PRIMARY KEY, session_id TEXT NOT NULL, name TEXT NOT NULL, mime TEXT NOT NULL, extension TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS session_media (session_id TEXT PRIMARY KEY, items TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS media_panels (session_id TEXT PRIMARY KEY, key TEXT NOT NULL);''')

    @contextmanager
    def db(self):
        db=sqlite3.connect(self.db_path,timeout=65)
        try:
            with db:yield db
        finally:db.close()

    def panel_key(self, db, sid):
        row = db.execute('SELECT key FROM media_panels WHERE session_id=?', (sid,)).fetchone()
        if row: return row[0]
        key = secrets.token_urlsafe(32)
        db.execute('INSERT INTO media_panels VALUES (?,?)', (sid, key))
        return key

    def authorize(self, sid, key):
        if not isinstance(key, str): return False
        with self.db() as db:
            row = db.execute('SELECT key FROM media_panels WHERE session_id=?', (sid,)).fetchone()
        return bool(row and secrets.compare_digest(row[0], key))

    def asset(self, db, sid, asset_id):
        row = db.execute('SELECT id,name,mime,extension FROM media_assets WHERE session_id=? AND id=?', (sid, asset_id)).fetchone()
        if not row: raise ValueError('Midia nao pertence a esta conversa.')
        return dict(zip(('asset_id','name','mime_type','extension'), row))

    def items(self, db, sid):
        row = db.execute('SELECT items FROM session_media WHERE session_id=?', (sid,)).fetchone()
        return [self.asset(db, sid, i) for i in json.loads(row[0])] if row else []

    def select(self, db, sid, ids):
        if not isinstance(ids, list) or any(not isinstance(i,str) for i in ids) or len(ids) > 10 or len(set(ids)) != len(ids):
            raise ValueError('Selecione ate 10 midias diferentes.')
        for i in ids:
            if not isinstance(i, str): raise ValueError('Midia invalida.')
            self.asset(db, sid, i)
        db.execute('INSERT INTO session_media VALUES (?,?) ON CONFLICT(session_id) DO UPDATE SET items=excluded.items', (sid, json.dumps(ids)))

    def upload(self, sid, name, raw):
        if not isinstance(sid, str) or not re.fullmatch(r'[\w-]{8,160}', sid): raise ValueError('Sessao invalida.')
        if not raw or len(raw) > LIMIT: raise ValueError('Arquivo vazio ou acima de 100 MB.')
        name = Path(name).name[:180]
        suffix = Path(name).suffix.lower()
        if suffix not in ('.jpg','.jpeg','.png','.mp4','.mov'): raise ValueError('Use JPEG, PNG, MP4 ou MOV.')
        asset_id = secrets.token_hex(16)
        with tempfile.TemporaryDirectory(dir=self.directory) as tmp:
            source = Path(tmp) / ('input' + suffix); source.write_bytes(raw)
            try:
                info = json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(source)], stderr=subprocess.DEVNULL, timeout=20))
                video = next(s for s in info['streams'] if s['codec_type']=='video')
                if suffix in ('.jpg','.jpeg','.png'):
                    if video['codec_name'] not in ('mjpeg','png') or video['width'] * video['height'] > 40_000_000:
                        raise ValueError('Imagem invalida ou muito grande.')
                    output = self.directory / (asset_id + '.jpg')
                    subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(source),'-frames:v','1','-vf',"scale=1080:1350:force_original_aspect_ratio=decrease,pad=1080:1350:(ow-iw)/2:(oh-ih)/2:white",'-q:v','2',str(output)], check=True, timeout=30, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    mime, ext = 'image/jpeg', 'jpg'
                else:
                    duration = float(info['format']['duration'])
                    if video['codec_name'] != 'h264' or not 3 <= duration <= 900:
                        raise ValueError('Video deve usar H.264 e durar de 3 a 900 segundos.')
                    if any(s['codec_type']=='audio' and s['codec_name']!='aac' for s in info['streams']):
                        raise ValueError('Audio do video deve usar AAC.')
                    mime, ext = 'video/mp4', 'mp4'
                    output = self.directory / (asset_id + '.mp4')
                    subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(source),'-map','0:v:0','-map','0:a?','-c','copy','-movflags','+faststart',str(output)],check=True,timeout=30,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            except (subprocess.SubprocessError, KeyError, StopIteration, json.JSONDecodeError):
                raise ValueError('Arquivo de midia invalido ou nao suportado.') from None
        output.chmod(0o600)
        with self.db() as db:
            db.execute('INSERT INTO media_assets VALUES (?,?,?,?,?)', (asset_id,sid,name,mime,ext))
        return {'asset_id':asset_id,'name':name,'mime_type':mime,'extension':ext}

    def import_local(self, sid, value):
        root = Path(os.getenv('MEDIA_LIBRARY_ROOT','/library')).resolve()
        original = os.getenv('MEDIA_LIBRARY_HOST_PATH','').rstrip('/')
        value = unquote(urlparse(value).path) if value.startswith('file://') else value
        if original and (value == original or value.startswith(original + '/')): value = value[len(original):].lstrip('/')
        path = (root / value).resolve()
        if not path.is_relative_to(root) or not path.exists(): raise ValueError('Arquivo fora da biblioteca autorizada ou inexistente.')
        files = sorted(p for p in path.iterdir() if p.suffix.lower() in ('.jpg','.jpeg','.png','.mp4','.mov')) if path.is_dir() else [path]
        if not 1 <= len(files) <= 10: raise ValueError('Escolha uma pasta com 1 a 10 midias.')
        if any(not p.resolve().is_relative_to(root) or not p.is_file() for p in files): raise ValueError('Arquivo fora da biblioteca autorizada.')
        if any(p.stat().st_size > LIMIT for p in files): raise ValueError('Arquivo acima de 100 MB.')
        return [self.upload(sid, p.name, p.read_bytes()) for p in files]

    def public_items(self, items):
        base = os.getenv('MEDIA_PUBLIC_BASE_URL','').strip().rstrip('/')
        u = urlparse(base)
        if base and (u.scheme!='https' or not u.hostname or u.username or u.password or u.query or u.fragment):
            raise ValueError('Configure MEDIA_PUBLIC_BASE_URL como URL HTTPS publica.')
        return [{**m, 'url': base + '/' + m['asset_id'] + '.' + m['extension'] if base else None} for m in items]

    def file(self, filename):
        if not re.fullmatch(r'[a-f0-9]{32}\.(jpg|mp4)', filename): raise ValueError('Midia desconhecida.')
        path = self.directory / filename
        if not path.is_file(): raise ValueError('Midia desconhecida.')
        return path
