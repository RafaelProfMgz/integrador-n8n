"""Declarative, deterministic response skills. No social calls, no LLM, no invented facts."""
import hashlib
import json
import re
import unicodedata
from pathlib import Path


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFKD',text.casefold()) if not unicodedata.combining(c))


class ResponseSkills:
    def __init__(self,path,community_name='nossa comunidade'):
        self.path=Path(path)
        self.community_name=str(community_name or 'nossa comunidade')[:80]

    def decide(self,comment):
        raw=self.path.read_text()
        rules=json.loads(raw)
        text=comment.get('text','')
        if not isinstance(text,str) or not text.strip():return {'skill':'empty','action':'skip','reply':'','version':rules['version']}
        if len(text)>5000:return {'skill':'too_long','action':'review','reply':'','version':rules['version']}
        normalized=normalize(text)
        for rule in rules['rules']:
            if any(re.search(pattern,normalized) for pattern in rule['patterns']):
                choices=rule.get('replies',[])
                digest=hashlib.sha256((str(comment.get('comment_id',''))+rule['id']).encode()).hexdigest()
                reply=choices[int(digest[:8],16)%len(choices)] if choices else ''
                reply=reply.replace('{community_name}',self.community_name)
                if len(reply)>280:raise ValueError('Resposta da skill excede o limite local')
                return {'skill':rule['id'],'action':rule['action'],'reply':reply,
                        'version':rules['version'],'rules_hash':hashlib.sha256(raw.encode()).hexdigest()}
        fallback=rules['fallback']
        return {'skill':fallback['id'],'action':fallback['action'],'reply':fallback['reply'],'version':rules['version']}
