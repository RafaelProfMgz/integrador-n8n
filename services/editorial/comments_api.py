"""Official-API adapters, bounded polling on owned posts, no search on third-party content."""
from datetime import datetime,timezone
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request


class APIError(Exception):pass


def epoch(value):
    if not isinstance(value,str):return None
    try:
        date=datetime.fromisoformat(value.replace('Z','+00:00'))
        return date.replace(tzinfo=date.tzinfo or timezone.utc).timestamp()
    except ValueError:return None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


class HTTP:
    def __call__(self,host,path,token,params=None,body=None,json_body=False):
        if host not in ('https://graph.facebook.com','https://api.x.com'):raise APIError('Host nao permitido')
        if not re.fullmatch(r'/[a-zA-Z0-9_./-]+',path):raise APIError('Caminho invalido')
        url=host+path+('?' + urllib.parse.urlencode(params) if params else '')
        headers={'Authorization':'Bearer '+token}
        data=None
        if body is not None:
            headers['Content-Type']='application/json' if json_body else 'application/x-www-form-urlencoded'
            data=(json.dumps(body) if json_body else urllib.parse.urlencode(body)).encode()
        request=urllib.request.Request(url,data=data,headers=headers,method='POST' if body is not None else 'GET')
        try:
            with urllib.request.build_opener(NoRedirect).open(request,timeout=25) as response:
                raw=response.read(5*1024*1024+1)
            if len(raw)>5*1024*1024:raise APIError('Resposta acima do limite local')
            result=json.loads(raw)
            if not isinstance(result,dict) or result.get('error') or result.get('errors'):raise APIError('A API retornou erros; verifique acesso e limites')
            return result
        except urllib.error.HTTPError as error:
            raise APIError('API HTTP '+str(error.code)+'; confira permissoes, validade do token e limites') from None
        except (urllib.error.URLError,TimeoutError,json.JSONDecodeError):
            raise APIError('Falha ou timeout de API; nao ha retry automatico') from None


class Adapter:
    def __init__(self,platform,account,token,version='',transport=None,post_days=30,comment_days=7,max_posts=10,max_comments=20,max_pages=3,now=None):
        if platform not in ('instagram','facebook','x') or not re.fullmatch(r'\d+',account or '') or not token:
            raise APIError('Configure conta e token para '+platform)
        if platform!='x' and not re.fullmatch(r'v\d+\.\d+',version):raise APIError('Configure META_GRAPH_VERSION')
        self.platform=platform;self.account=account;self.token=token;self.version=version
        self.http=transport or HTTP();self.post_days=post_days;self.comment_days=comment_days
        self.max_posts=max_posts;self.max_comments=max_comments;self.max_pages=max_pages;self.now=now or time.time
        self.username='';self.truncated=False

    def call(self,path,params=None,body=None):
        host='https://api.x.com' if self.platform=='x' else 'https://graph.facebook.com'
        prefix='/2' if self.platform=='x' else '/'+self.version
        return self.http(host,prefix+path,self.token,params,body,self.platform=='x')

    def verify(self):
        if self.platform=='x':identity=self.call('/users/me').get('data',{})
        elif self.platform=='facebook':identity=self.call('/me',{'fields':'id,name'})
        else:identity=self.call('/'+self.account,{'fields':'id,username'})
        if not isinstance(identity,dict):raise APIError('Identidade de conta invalida')
        if str(identity.get('id',''))!=self.account:raise APIError('O token nao corresponde a conta configurada')
        self.username=identity.get('username','')
        if self.platform=='instagram' and not self.username:raise APIError('Nao foi possivel verificar o username do Instagram')
        return identity

    def pages(self,path,params,limit):
        rows=[];cursor=None;complete=False
        for _ in range(self.max_pages):
            query=dict(params)
            if cursor:query['pagination_token' if self.platform=='x' else 'after']=cursor
            response=self.call(path,query)
            data=response.get('data',[])
            if not isinstance(data,list):raise APIError('Lista de API invalida')
            rows.extend(data)
            if self.platform=='x':nxt=response.get('meta',{}).get('next_token');has_next=bool(nxt)
            else:
                paging=response.get('paging',{});has_next=bool(paging.get('next'));nxt=paging.get('cursors',{}).get('after')
            if not has_next:complete=True;break
            if len(rows)>=limit or not nxt or nxt==cursor:break
            cursor=nxt
        if len(rows)>limit:complete=False
        if not complete:self.truncated=True
        return rows[:limit],complete

    def author(self,item):
        if self.platform=='x':return str(item.get('author_id',''))
        author=item.get('from') or {}
        if author.get('id'):return str(author['id'])
        return 'username:'+str(item.get('username','')).lower() if item.get('username') else ''

    def is_self(self,author):
        return author==self.account or bool(self.username and author=='username:'+self.username.lower())

    def replies(self,comment_id,post_id):
        if self.platform=='x':
            if not self.username:return False,False
            try:
                rows,complete=self.pages('/tweets/search/recent',{'query':'conversation_id:'+post_id+' from:'+self.username,
                   'tweet.fields':'author_id,referenced_tweets','max_results':100},300)
                return any(self.is_self(self.author(r)) and any(x.get('type')=='replied_to' and str(x.get('id'))==comment_id for x in r.get('referenced_tweets',[])) for r in rows),complete
            except APIError:return False,False
        edge='replies' if self.platform=='instagram' else 'comments'
        fields='id,username,text' if self.platform=='instagram' else 'id,from,message'
        rows,complete=self.pages('/'+comment_id+'/'+edge,{'fields':fields,'limit':100},300)
        if any(not self.author(r) for r in rows):complete=False
        return any(self.is_self(self.author(r)) for r in rows),complete

    def normalize(self,item,post):
        comment_id=str(item.get('id',''))
        if not re.fullmatch(r'[0-9_]+',comment_id):return None
        author=self.author(item)
        own,complete=(True,True) if self.is_self(author) else self.replies(comment_id,str(post['id']))
        return {'platform':self.platform,'account_id':self.account,'post_id':str(post['id']),
            'post_text':post.get('caption',post.get('message',post.get('text','')))[:5000],
            'comment_id':comment_id,'text':item.get('text',item.get('message','')),
            'author':author,'created_at':item.get('timestamp',item.get('created_time',item.get('created_at'))),
            'own_comment':self.is_self(author),'own_reply':own,'replies_complete':complete}

    def comments_for(self,post):
        fields='id,text,timestamp,username' if self.platform=='instagram' else 'id,message,created_time,from'
        params={'fields':fields,'limit':100}
        if self.platform=='facebook':params.update(filter='toplevel',order='reverse_chronological')
        return self.pages('/'+str(post['id'])+'/comments',params,self.max_comments)

    def collect(self):
        self.verify()
        if self.platform=='x':
            start=datetime.fromtimestamp(self.now()-self.post_days*86400,timezone.utc).isoformat().replace('+00:00','Z')
            posts,_=self.pages('/users/'+self.account+'/tweets',{'tweet.fields':'created_at,referenced_tweets','exclude':'retweets','max_results':100,'start_time':start},self.max_posts)
            posts=[p for p in posts if not any(r.get('type')=='replied_to' for r in p.get('referenced_tweets',[]))]
            by_id={str(p['id']):p for p in posts}
            start=datetime.fromtimestamp(self.now()-self.comment_days*86400,timezone.utc).isoformat().replace('+00:00','Z')
            mentions,_=self.pages('/users/'+self.account+'/mentions',{'tweet.fields':'created_at,author_id,referenced_tweets','max_results':100,'start_time':start},self.max_comments)
            pairs=[]
            for c in mentions:
                parents=[str(x['id']) for x in c.get('referenced_tweets',[]) if x.get('type')=='replied_to']
                if parents and parents[0] in by_id:pairs.append((c,by_id[parents[0]]))
        else:
            edge='media' if self.platform=='instagram' else 'published_posts'
            fields='id,caption,timestamp' if self.platform=='instagram' else 'id,message,created_time'
            posts,_=self.pages('/'+self.account+'/'+edge,{'fields':fields,'limit':self.max_posts},self.max_posts)
            pairs=[]
            for post in posts:
                created=epoch(post.get('timestamp',post.get('created_time')))
                if created is None or created<self.now()-self.post_days*86400:continue
                comments,_=self.comments_for(post)
                for c in comments:pairs.append((c,post))
        pairs.sort(key=lambda pair:epoch(pair[0].get('timestamp',pair[0].get('created_time',pair[0].get('created_at')))) or 0,reverse=True)
        result=[]
        for item,post in pairs:
            created=epoch(item.get('timestamp',item.get('created_time',item.get('created_at'))))
            if created is None or created<self.now()-self.comment_days*86400:continue
            normalized=self.normalize(item,post)
            if normalized:result.append(normalized)
            if len(result)>=self.max_comments:break
        return result

    def current(self,record):
        if record.get('account_id')!=self.account:return None
        self.verify()
        if self.platform=='x':
            item=self.call('/tweets/'+record['comment_id'],{'tweet.fields':'created_at,author_id,referenced_tweets'}).get('data',{})
            if not any(r.get('type')=='replied_to' and str(r.get('id'))==record['post_id'] for r in item.get('referenced_tweets',[])):
                return None
        else:
            rows,_=self.comments_for({'id':record['post_id']})
            item=next((r for r in rows if str(r.get('id'))==record['comment_id']),None)
            if not item:return None
        return self.normalize(item,{'id':record['post_id'],'text':record.get('post_text','')})

    def reply(self,comment,text):
        if self.platform=='x':result=self.call('/tweets',body={'text':text,'reply':{'in_reply_to_tweet_id':comment['comment_id']}}).get('data',{})
        else:result=self.call('/'+comment['comment_id']+('/replies' if self.platform=='instagram' else '/comments'),body={'message':text})
        reply_id=result.get('id')
        if not isinstance(reply_id,str) or not re.fullmatch(r'[0-9_]+',reply_id):raise APIError('Resposta de envio ambigua; reconcilie antes de repetir')
        return reply_id
