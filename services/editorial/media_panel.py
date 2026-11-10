"""Loopback-only attachment selector. Session capabilities never authorize publication."""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse, unquote
from media_store import LIMIT

class PanelHandler(BaseHTTPRequestHandler):
    editorial = None
    def log_message(self, *_): pass
    def send(self, code, body, mime='application/json; charset=utf-8'):
        if not isinstance(body, bytes): body=json.dumps(body,ensure_ascii=False).encode()
        self.send_response(code);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer');self.send_header('X-Frame-Options','DENY');self.end_headers();self.wfile.write(body)
    def auth(self):
        q=parse_qs(urlparse(self.path).query);sid=q.get('session',[''])[0]
        key=self.headers.get('X-Media-Key') or q.get('key',[''])[0]
        if not self.editorial.media.authorize(sid,key): raise ValueError('Abra o seletor pelo link da sua conversa.')
        return sid
    def do_GET(self):
        try:
            sid=self.auth();path=urlparse(self.path).path
            if path=='/': return self.send(200,Path('/app/media-panel.html').read_bytes(),'text/html; charset=utf-8')
            if path=='/state':
                with self.editorial.db() as db: items=self.editorial.media.items(db,sid)
                return self.send(200,{'items':items})
            if path.startswith('/preview/'):
                asset=path.split('/')[-1]
                with self.editorial.db() as db: item=self.editorial.media.asset(db,sid,asset)
                file=self.editorial.media.file(asset+'.'+item['extension'])
                return self.send(200,file.read_bytes(),item['mime_type'])
            self.send(404,{'error':'Nao encontrado.'})
        except ValueError as e:self.send(400,{'error':str(e)})
    def do_POST(self):
        try:
            sid=self.auth();path=urlparse(self.path).path
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=LIMIT:raise ValueError('Arquivo vazio ou acima de 100 MB.')
            if path=='/upload':
                name=unquote(self.headers.get('X-Filename',''))
                return self.send(200,self.editorial.media.upload(sid,name,self.rfile.read(size)))
            if size>65536:raise ValueError('Pedido muito grande.')
            data=json.loads(self.rfile.read(size))
            if path=='/select':return self.send(200,self.editorial.attach(sid,data.get('ids')))
            if path=='/import':
                items=self.editorial.media.import_local(sid,data.get('path',''))
                return self.send(200,{'items':items})
            self.send(404,{'error':'Nao encontrado.'})
        except (ValueError,TypeError) as e:self.send(400,{'error':str(e)})
        except Exception:self.send(500,{'error':'Nao foi possivel carregar as midias.'})

def serve(editorial):
    PanelHandler.editorial=editorial
    ThreadingHTTPServer(('0.0.0.0',8081),PanelHandler).serve_forever()
