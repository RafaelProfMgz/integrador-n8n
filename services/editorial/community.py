"""Bounded comment monitoring, deterministic book-community skills and persistent reply ledger."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from comments_api import Adapter,APIError,epoch
from response_engine import ResponseSkills


def flag(config,key):return str(config.get(key,'false')).lower()=='true'
def number(config,key,default,maximum):
    try:return max(1,min(maximum,int(config.get(key,default))))
    except (TypeError,ValueError):return default

def fingerprint(comment):
    return hashlib.sha256(json.dumps({k:comment.get(k) for k in ('platform','account_id','post_id','post_text','comment_id','text','author')},sort_keys=True,ensure_ascii=False).encode()).hexdigest()


class Community:
    def __init__(self,path,rules_path,config=None,adapters=None,now=None):
        self.path=str(path);Path(path).parent.mkdir(parents=True,exist_ok=True)
        self.config=dict(os.environ if config is None else config);self.skills=ResponseSkills(rules_path,self.config.get('COMMUNITY_NAME','nossa comunidade'))
        self.adapters=adapters;self.now=now or time.time;self.run_lock=threading.Lock()
        with self.db() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS comments (
              id TEXT PRIMARY KEY,platform TEXT NOT NULL,account_id TEXT NOT NULL,comment_id TEXT NOT NULL,
              source TEXT NOT NULL,fingerprint TEXT NOT NULL,proposal TEXT NOT NULL,state TEXT NOT NULL,
              approval_token TEXT NOT NULL,updated_at REAL NOT NULL,attempt_at REAL,reply_id TEXT,reason TEXT,
              UNIQUE(platform,account_id,comment_id));
              CREATE TABLE IF NOT EXISTS optouts (platform TEXT,account_id TEXT,author TEXT,PRIMARY KEY(platform,account_id,author));''')

    @contextmanager
    def db(self):
        db=sqlite3.connect(self.path,timeout=30);db.row_factory=sqlite3.Row
        try:
            with db:yield db
        finally:db.close()

    def adapter(self,platform):
        if self.adapters is not None:return self.adapters[platform]
        names={'instagram':('META_INSTAGRAM_ACCOUNT_ID','META_INSTAGRAM_ACCESS_TOKEN'),
               'facebook':('META_FACEBOOK_PAGE_ID','META_FACEBOOK_PAGE_ACCESS_TOKEN'),'x':('X_USER_ID','X_OAUTH2_ACCESS_TOKEN')}
        if platform not in names:raise APIError('Plataforma nao implementada')
        account,token=names[platform]
        return Adapter(platform,self.config.get(account,''),self.config.get(token,''),self.config.get('META_GRAPH_VERSION',''),
            post_days=number(self.config,'COMMENTS_POST_DAYS',30,90),comment_days=number(self.config,'COMMENTS_LOOKBACK_DAYS',7,30),
            max_posts=number(self.config,'COMMENTS_MAX_POSTS',10,25),max_comments=number(self.config,'COMMENTS_MAX_COMMENTS',20,100),now=self.now)

    def status(self):
        return {'read_enabled':flag(self.config,'COMMENTS_READ_ENABLED'),'send_enabled':flag(self.config,'COMMENTS_SEND_ENABLED'),
            'mode':self.config.get('COMMENTS_MODE','review'),'site_url':self.config.get('COMMUNITY_SITE_URL',''),
            'platforms':self.config.get('COMMENTS_PLATFORMS','instagram').split(',')}

    def stage(self,comment):
        proposal=self.skills.decide(comment);fp=fingerprint(comment)
        reason='';state='suggested' if proposal['action']=='auto' else 'review'
        if proposal['action']=='skip':state='skipped';reason='empty'
        if comment.get('own_comment') or comment.get('own_reply'):state='skipped';reason='already_answered_or_self'
        elif not comment.get('author') or comment.get('replies_complete') is not True:state='review';reason='identity_or_history_incomplete'
        elif epoch(comment.get('created_at')) is None:state='review';reason='missing_timestamp'
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            if proposal['action']=='opt_out':
                if comment.get('author'):db.execute('INSERT OR IGNORE INTO optouts VALUES (?,?,?)',(comment['platform'],comment['account_id'],comment['author']))
                state='skipped';reason='opt_out'
            if db.execute('SELECT 1 FROM optouts WHERE platform=? AND account_id=? AND author=?',
                          (comment['platform'],comment['account_id'],comment.get('author',''))).fetchone():state='skipped';reason='opt_out'
            existing=db.execute('SELECT * FROM comments WHERE platform=? AND account_id=? AND comment_id=?',
                                (comment['platform'],comment['account_id'],comment['comment_id'])).fetchone()
            if existing and existing['state'] in ('replied','replying','unknown'):return existing['id']
            if existing and existing['fingerprint']==fp and json.loads(existing['proposal'])==proposal and existing['state']==state:return existing['id']
            record_id=existing['id'] if existing else secrets.token_hex(16)
            values=(json.dumps(comment,ensure_ascii=False),fp,json.dumps(proposal,ensure_ascii=False),state,secrets.token_hex(16),self.now(),reason)
            if existing:db.execute('UPDATE comments SET source=?,fingerprint=?,proposal=?,state=?,approval_token=?,updated_at=?,reason=? WHERE id=?',(*values,record_id))
            else:db.execute('INSERT INTO comments (id,platform,account_id,comment_id,source,fingerprint,proposal,state,approval_token,updated_at,reason) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                   (record_id,comment['platform'],comment['account_id'],comment['comment_id'],*values))
            return record_id

    def review(self):
        with self.db() as db:
            rows=db.execute("SELECT * FROM comments WHERE state IN ('review','suggested','unknown','replying') ORDER BY updated_at DESC LIMIT 100").fetchall()
            return {'items':[{'record_id':r['id'],'platform':r['platform'],'comment':json.loads(r['source']),
                 'suggestion':json.loads(r['proposal']),'state':r['state'],'reason':r['reason'],
                 'approval_token':r['approval_token'] if r['state'] in ('suggested','review') else None} for r in rows]}

    def set_state(self,record_id,state,reason):
        with self.db() as db:db.execute('UPDATE comments SET state=?,reason=?,approval_token=? WHERE id=?',(state,reason,secrets.token_hex(16),record_id))

    def send(self,record_id,approval_token=None,automatic=False):
        if not flag(self.config,'COMMENTS_READ_ENABLED') or not flag(self.config,'COMMENTS_SEND_ENABLED'):
            return {'status':'disabled','message':'Leitura/envio reais desabilitados no .env.'}
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            r=db.execute('SELECT * FROM comments WHERE id=?',(record_id,)).fetchone()
            if not r or r['state'] not in ('review','suggested'):return {'status':'not_sendable'}
            r=dict(r);source=json.loads(r['source']);proposal=json.loads(r['proposal'])
            if r['platform']=='x' and not flag(self.config,'COMMENTS_X_REPLY_ENABLED'):return {'status':'x_review_only'}
            if not automatic and (not isinstance(approval_token,str) or not secrets.compare_digest(approval_token,r['approval_token'])):return {'status':'invalid_approval'}
            if self.now()-r['updated_at']>3600:return {'status':'expired_approval'}
            if automatic and (self.config.get('COMMENTS_MODE')!='auto' or proposal['action']!='auto' or r['state']!='suggested'):return {'status':'review_required'}
            if proposal['action'] in ('skip','opt_out') or not proposal['reply']:return {'status':'review_required'}
            if not source.get('author') or source.get('own_comment') or source.get('own_reply') or source.get('replies_complete') is not True:return {'status':'review_required'}
            if db.execute('SELECT 1 FROM optouts WHERE platform=? AND account_id=? AND author=?',(r['platform'],r['account_id'],source['author'])).fetchone():return {'status':'opt_out'}
            attempted=db.execute("SELECT source FROM comments WHERE platform=? AND account_id=? AND state IN ('replied','replying','unknown') AND attempt_at>=?",(r['platform'],r['account_id'],self.now()-86400)).fetchall()
            daily=number(self.config,'COMMENTS_DAILY_LIMIT',20,100)
            if len(attempted)>=daily:return {'status':'daily_limit'}
            author_attempts=[json.loads(a['source']) for a in attempted if json.loads(a['source']).get('author')==source['author']]
            same_post=db.execute("SELECT 1 FROM comments WHERE platform=? AND account_id=? AND state IN ('replied','replying','unknown') AND json_extract(source,'$.author')=? AND json_extract(source,'$.post_id')=? LIMIT 1",(r['platform'],r['account_id'],source['author'],source['post_id'])).fetchone()
            if same_post:return {'status':'author_post_limit'}
            if len(author_attempts)>=number(self.config,'COMMENTS_AUTHOR_DAILY_LIMIT',2,10):return {'status':'author_daily_limit'}
            db.execute('UPDATE comments SET state=?,attempt_at=? WHERE id=?',('replying',self.now(),record_id))
        try:
            adapter=self.adapter(r['platform']);current=adapter.current(source)
            if not current or fingerprint(current)!=r['fingerprint']:
                self.set_state(record_id,'review','source_changed');return {'status':'source_changed'}
            current_proposal=self.skills.decide(current)
            if current_proposal!=proposal:
                self.set_state(record_id,'review','skills_changed');return {'status':'skills_changed'}
            if current.get('own_comment') or current.get('own_reply') or current.get('replies_complete') is not True:
                self.set_state(record_id,'skipped','already_answered_or_incomplete');return {'status':'already_answered_or_incomplete'}
        except Exception:
            self.set_state(record_id,'review','preflight_failed');return {'status':'preflight_failed'}
        try:
            reply_id=adapter.reply(current,proposal['reply'])
        except Exception:
            self.set_state(record_id,'unknown','post_outcome_unknown');return {'status':'unknown','message':'Confira a plataforma antes de repetir; nenhum retry sera feito.'}
        with self.db() as db:db.execute('UPDATE comments SET state=?,reply_id=?,reason=? WHERE id=?',('replied',reply_id,'sent',record_id))
        return {'status':'replied','reply_id':reply_id,'platform':r['platform'],'record_id':record_id}

    def run(self,request=None):
        request=request or {}
        if not isinstance(request,dict):raise ValueError('Entrada invalida')
        dry=request.get('dry_run',self.config.get('COMMENTS_MODE','review')!='auto')
        if type(dry) is not bool:raise ValueError('dry_run deve ser booleano')
        if not flag(self.config,'COMMENTS_READ_ENABLED'):
            return {'status':'setup_required','message':'Configure credenciais e COMMENTS_READ_ENABLED no .env; nenhuma API foi chamada.','settings':self.status()}
        if not self.run_lock.acquire(blocking=False):return {'status':'already_running'}
        try:
            platforms=[p.strip() for p in self.config.get('COMMENTS_PLATFORMS','instagram').split(',') if p.strip()]
            if any(p not in ('instagram','facebook','x') for p in platforms):raise ValueError('Plataforma de comentarios nao implementada')
            report=[];sent=0
            for platform in platforms:
                try:
                    adapter=self.adapter(platform);comments=adapter.collect()
                    ids=[self.stage(c) for c in comments]
                    outcomes=[]
                    if not dry and self.config.get('COMMENTS_MODE')=='auto':
                        for record_id in ids:
                            if sent>=number(self.config,'COMMENTS_RUN_REPLY_LIMIT',3,10):break
                            outcome=self.send(record_id,automatic=True);outcomes.append(outcome)
                            if outcome['status'] in ('replied','unknown'):sent+=1
                    report.append({'platform':platform,'scanned':len(comments),'partial_scan':bool(getattr(adapter,'truncated',False)),
                                   'record_ids':ids,'outcomes':outcomes})
                except APIError as error:report.append({'platform':platform,'status':'api_unavailable','message':str(error)})
            return {'status':'review_ready' if dry else 'cycle_completed','dry_run':dry,'report':report,'reply_attempts':sent}
        finally:self.run_lock.release()


class Handler(BaseHTTPRequestHandler):
    community=None
    def log_message(self,*args):pass
    def reply_json(self,status,data):
        raw=json.dumps(data,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        if self.path=='/healthz':return self.reply_json(200,{'status':'ok'})
        if self.path=='/review':return self.reply_json(200,self.community.review())
        if self.path=='/status':return self.reply_json(200,self.community.status())
        return self.reply_json(404,{'error':'not_found'})
    def do_POST(self):
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=65536:raise ValueError('Requisicao invalida')
            data=json.loads(self.rfile.read(size))
            if not isinstance(data,dict):raise ValueError('Requisicao invalida')
            if self.path=='/run':result=self.community.run(data)
            elif self.path=='/draft':result=self.community.skills.decide({'text':data.get('text',''),'comment_id':data.get('comment_id','')})
            elif self.path=='/approve':result=self.community.send(data.get('record_id'),data.get('approval_token'))
            else:return self.reply_json(404,{'error':'not_found'})
            self.reply_json(200,result)
        except ValueError as error:self.reply_json(400,{'error':str(error)})
        except Exception:self.reply_json(500,{'error':'Falha interna; consulte os registros locais antes de repetir.'})

if __name__=='__main__':
    os.umask(0o077)
    Handler.community=Community('/data/community.sqlite',os.getenv('RESPONSE_SKILLS_PATH','/app/response-skills/book-community/rules.json'))
    ThreadingHTTPServer(('0.0.0.0',8080),Handler).serve_forever()
