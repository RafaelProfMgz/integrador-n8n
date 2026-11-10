"""Single-purpose image generator. No editorial, social credentials or publishing tools."""
import base64
import hashlib
import json
import os
import re
import secrets
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


def public_base():
    value=os.getenv('IMAGE_PUBLIC_BASE_URL','').strip().rstrip('/')
    if not value:return ''
    url=urlparse(value)
    if url.scheme!='https' or not url.hostname or url.username or url.password or url.query or url.fragment or any(c.isspace() for c in value):
        raise ValueError('IMAGE_PUBLIC_BASE_URL deve ser uma URL HTTPS sem usuario, senha, query ou fragmento.')
    return value


class ImageAgent:
    def __init__(self,db_path,transport=None):
        self.db_path=str(db_path)
        self.directory=Path(db_path).parent/'generated-images'
        self.directory.mkdir(parents=True,exist_ok=True)
        self.transport=transport or self.openai
        db=sqlite3.connect(self.db_path)
        try:
            db.execute('CREATE TABLE IF NOT EXISTS image_requests (id TEXT PRIMARY KEY, digest TEXT NOT NULL, state TEXT NOT NULL, result TEXT)')
            db.commit()
        finally:db.close()

    def openai(self,payload):
        key=os.getenv('OPENAI_API_KEY','').strip()
        if not key:raise ValueError('Configure OPENAI_API_KEY no .env para gerar imagens.')
        request=urllib.request.Request('https://api.openai.com/v1/images/generations',data=json.dumps(payload).encode(),
                    headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
        try:
            with urllib.request.urlopen(request,timeout=180) as response:
                data=response.read(32*1024*1024+1)
            if len(data)>32*1024*1024:raise ValueError('Resposta de imagem acima do limite local.')
            return json.loads(data)
        except (urllib.error.URLError,TimeoutError,json.JSONDecodeError):
            raise ValueError('Nao foi possivel concluir a geracao. Confira acesso ao modelo/chave/saldo; nao ha retry automatico.') from None

    def generate(self,request):
        if not isinstance(request,dict):raise ValueError('Entrada de imagem invalida')
        description=request.get('description')
        if not isinstance(description,str) or not description.strip() or len(description)>12000:raise ValueError('Informe description com 1 a 12000 caracteres.')
        dry=request.get('dry_run',True)
        if type(dry) is not bool:raise ValueError('dry_run deve ser booleano')
        size=request.get('size','1024x1024')
        if size not in ('1024x1024','1024x1536','1536x1024'):raise ValueError('Tamanho de imagem invalido')
        quality=request.get('quality','medium')
        if quality not in ('low','medium','high'):raise ValueError('Qualidade de imagem invalida')
        model=os.getenv('OPENAI_IMAGE_MODEL','gpt-image-1.5').strip()
        if not model:raise ValueError('Configure OPENAI_IMAGE_MODEL no .env')
        payload={'model':model,'prompt':description.strip(),'n':1,'size':size,'quality':quality,'output_format':'jpeg','background':'opaque'}
        if dry:return {'status':'dry_run','operation':'generate_image','description':description.strip(),'size':size,'quality':quality,'mime_type':'image/jpeg','message':'Simulacao: nenhuma chamada OpenAI foi realizada.'}
        request_id=request.get('request_id')
        if not isinstance(request_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,100}',request_id):raise ValueError('request_id e obrigatorio na geracao real (8 a 100 caracteres).')
        # Valide configuracao antes de registrar uma tentativa potencialmente paga.
        base=public_base()
        digest=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
        db=sqlite3.connect(self.db_path,timeout=65)
        try:
            db.execute('BEGIN IMMEDIATE')
            existing=db.execute('SELECT digest,state,result FROM image_requests WHERE id=?',(request_id,)).fetchone()
            if existing:
                db.rollback()
                if existing[0]!=digest:raise ValueError('request_id ja usado com outra descricao/configuracao.')
                if existing[1]=='completed':
                    cached=json.loads(existing[2])
                    cached['image_url']=base+'/'+cached['asset_id']+'.jpg' if base else None
                    cached['public_url_configured']=bool(base)
                    db.execute('UPDATE image_requests SET result=? WHERE id=?',(json.dumps(cached),request_id));db.commit()
                    return cached
                raise ValueError('Esta geracao ja foi tentada ou esta em andamento. Verifique o resultado antes de pedir outra imagem.')
            if self.transport==self.openai and not os.getenv('OPENAI_API_KEY','').strip():raise ValueError('Configure OPENAI_API_KEY no .env para gerar imagens.')
            db.execute('INSERT INTO image_requests VALUES (?,?,?,NULL)',(request_id,digest,'generating'));db.commit()
            try:
                response=self.transport(payload)
                items=response.get('data',[])
                if response.get('error') or len(items)!=1:raise ValueError('Resposta de geracao invalida.')
                encoded=items[0].get('b64_json')
                if not isinstance(encoded,str) or len(encoded)>28*1024*1024:raise ValueError('Imagem ausente ou acima do limite local.')
                try:raw=base64.b64decode(encoded,validate=True)
                except (ValueError,TypeError):raise ValueError('Imagem retornada em formato invalido.') from None
                if not raw.startswith(b'\xff\xd8\xff') or not raw.endswith(b'\xff\xd9'):raise ValueError('A API nao retornou um arquivo JPEG valido.')
                asset_id=secrets.token_hex(16)
                path=self.directory/(asset_id+'.jpg')
                with path.open('xb') as stream:stream.write(raw)
                path.chmod(0o600)
                result={'status':'image_generated','asset_id':asset_id,'request_id':request_id,'mime_type':'image/jpeg',
                        'file_name':asset_id+'.jpg','size':size,'quality':quality,
                        'image_url':base+'/'+asset_id+'.jpg' if base else None,
                        'public_url_configured':bool(base),'bytes':len(raw)}
                db.execute('UPDATE image_requests SET state=?,result=? WHERE id=?',('completed',json.dumps(result),request_id));db.commit()
                return result
            except Exception:
                db.execute('UPDATE image_requests SET state=? WHERE id=?',('unknown',request_id));db.commit()
                raise ValueError('Geracao nao concluida. A tentativa foi registrada sem retry; confira a operacao antes de repetir.') from None
        finally:db.close()

    def file(self,asset_id):
        if not re.fullmatch(r'[a-f0-9]{32}',asset_id):raise ValueError('Imagem desconhecida')
        path=self.directory/(asset_id+'.jpg')
        if not path.is_file():raise ValueError('Imagem desconhecida')
        return path
