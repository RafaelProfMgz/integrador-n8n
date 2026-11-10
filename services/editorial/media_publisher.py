"""Instagram upload adapter. Isolated from the model and editorial credentials."""
import hashlib
from contextlib import contextmanager
import json
import os
import re
import sqlite3
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

class Publisher:
    def __init__(self, path, transport=None, sleep=time.sleep):
        self.path=str(path);self.transport=transport or self.graph;self.sleep=sleep
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS attempts (id TEXT PRIMARY KEY,digest TEXT NOT NULL,state TEXT NOT NULL,receipt TEXT NOT NULL)')

    @contextmanager
    def db(self):
        db=sqlite3.connect(self.path,timeout=65)
        try:
            with db:yield db
        finally:db.close()

    def graph(self, route, data=None):
        request=urllib.request.Request('https://graph.facebook.com/'+os.environ['META_GRAPH_VERSION']+'/'+route,
            data=urllib.parse.urlencode(data).encode() if data is not None else None,
            headers={'Authorization':'Bearer '+os.environ['META_INSTAGRAM_ACCESS_TOKEN']})
        with urllib.request.urlopen(request,timeout=45) as response:return json.load(response)

    def publish(self, p):
        if not isinstance(p,dict) or type(p.get('dry_run')) is not bool:raise ValueError('Modo invalido.')
        media=p.get('media');caption=p.get('caption')
        if not isinstance(media,list) or not 1<=len(media)<=10:raise ValueError('Selecione de 1 a 10 midias.')
        if not isinstance(caption,str) or not caption.strip() or len(caption)>2200:raise ValueError('Legenda Instagram invalida.')
        for m in media:
            if not isinstance(m,dict) or m.get('mime_type') not in ('image/jpeg','video/mp4') or not re.fullmatch(r'[a-f0-9]{32}',m.get('asset_id','')):
                raise ValueError('Midia invalida.')
        if p['dry_run']:return {'status':'dry_run','media_count':len(media),'format':'carousel' if len(media)>1 else 'reel' if media[0]['mime_type']=='video/mp4' else 'image'}
        if p.get('approved') is not True:raise ValueError('Confirmacao explicita necessaria.')
        request_id=p.get('request_id','')
        if not re.fullmatch(r'[a-f0-9]{32}',request_id):raise ValueError('Identificador da tentativa invalido.')
        account=os.getenv('META_INSTAGRAM_ACCOUNT_ID','');version=os.getenv('META_GRAPH_VERSION','')
        if not re.fullmatch(r'\d+',account) or not re.fullmatch(r'v\d+\.\d+',version) or not os.getenv('META_INSTAGRAM_ACCESS_TOKEN',''):
            raise ValueError('Configure a conta e o token Instagram no .env.')
        base=os.getenv('MEDIA_PUBLIC_BASE_URL','').rstrip('/')
        u=urllib.parse.urlparse(base)
        if u.scheme!='https' or not u.hostname or u.username or u.password:raise ValueError('Hospedagem HTTPS pendente.')
        for m in media:
            ext='jpg' if m['mime_type']=='image/jpeg' else 'mp4'
            if m.get('url')!=base+'/'+m['asset_id']+'.'+ext:raise ValueError('URL nao pertence ao armazenamento configurado.')
        digest=hashlib.sha256(json.dumps({'account':account,'caption':caption,'media':media},sort_keys=True).encode()).hexdigest()
        receipt={'containers':[],'publish_started':False}
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT digest,state,receipt FROM attempts WHERE id=?',(request_id,)).fetchone()
            if row:
                if row[0]!=digest:raise ValueError('Tentativa vinculada a outro conteudo.')
                if row[1]=='published':return json.loads(row[2])['result']
                raise ValueError('Tentativa ja iniciada. Reconcilie os containers antes de repetir.')
            db.execute('INSERT INTO attempts VALUES (?,?,?,?)',(request_id,digest,'preparing',json.dumps(receipt)));db.commit()
            def save(state):
                db.execute('UPDATE attempts SET state=?,receipt=? WHERE id=?',(state,json.dumps(receipt),request_id));db.commit()
            def wait(container):
                for _ in range(30):
                    result=self.transport(container+'?fields=status_code,status')
                    if result.get('status_code')=='FINISHED':return
                    if result.get('status_code') in ('ERROR','EXPIRED','PUBLISHED'):raise ValueError('Confira o container registrado antes de repetir.')
                    self.sleep(2)
                raise ValueError('Processamento pendente. Consulte o container registrado; nao recrie o envio.')
            def create(params):
                receipt['next_post']='create_container';save('posting')
                result=self.transport(account+'/media',params)
                container=result.get('id','')
                if not re.fullmatch(r'\d+',container):raise ValueError('Resposta remota sem container valido.')
                receipt['containers'].append(container);save('processing');wait(container)
                return container
            try:
                # GET verifies that the configured identifier belongs to a readable Instagram account.
                profile=self.transport(account+'?fields=username')
                if not profile.get('username'):raise ValueError('Conta nao confirmada.')
                children=[]
                for m in media:
                    video=m['mime_type']=='video/mp4'
                    params={'video_url' if video else 'image_url':m['url']}
                    if len(media)>1:
                        params['is_carousel_item']='true'
                        if video:params['media_type']='VIDEO'
                    else:
                        params['caption']=caption
                        if video:params.update(media_type='REELS',share_to_feed='true')
                    children.append(create(params))
                container=create({'media_type':'CAROUSEL','children':','.join(children),'caption':caption}) if len(media)>1 else children[0]
                receipt['publish_started']=True;receipt['next_post']='media_publish';save('publishing')
                result=self.transport(account+'/media_publish',{'creation_id':container})
                post_id=result.get('id','')
                if not re.fullmatch(r'\d+',post_id):raise ValueError('Publicacao sem identificador confirmado.')
                receipt['result']={'status':'published','platform':'instagram','post_id':post_id};save('published')
                return receipt['result']
            except Exception:
                save('unknown')
                raise ValueError('Tentativa registrada como incerta. Confira a plataforma e os containers; nao ha retry automatico.') from None

class Handler(BaseHTTPRequestHandler):
    publisher=None
    def log_message(self,*_):pass
    def do_POST(self):
        try:
            size=int(self.headers.get('Content-Length','0'))
            if self.path!='/publish' or not 0<size<=65536:raise ValueError('Pedido invalido.')
            result=self.publisher.publish(json.loads(self.rfile.read(size)));code=200
        except ValueError as e:result={'error':str(e)};code=400
        except Exception:result={'error':'Falha interna; confira os registros antes de repetir.'};code=500
        raw=json.dumps(result).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)

if __name__=='__main__':
    os.umask(0o077)
    Handler.publisher=Publisher('/data/media-publisher.sqlite')
    ThreadingHTTPServer(('0.0.0.0',8082),Handler).serve_forever()
