"""Deterministic local video assembly. No network, accounts or publishing permissions."""
import hashlib
import json
import math
import secrets
import subprocess
import tempfile
from pathlib import Path

FORMATS={'Automatico':'auto','Foto no feed':'image','Story':'story','Reels':'reel','Carrossel':'carousel','Carrossel em video (Reels)':'slideshow_reel','Carrossel em video (Story)':'slideshow_story'}
AUDIO={'Manter audio original':'original','Sem som':'mute','Musica enviada':'music'}

def number(value, default, low, high, label):
    try:result=float(default if value in ('',None) else value)
    except (ValueError,TypeError):raise ValueError(label+' invalido.') from None
    if not math.isfinite(result) or not low<=result<=high:raise ValueError(label+' fora do limite.')
    return result

class MediaTransform:
    def __init__(self, store):
        self.store=store
        with store.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS media_renders (session_id TEXT PRIMARY KEY,digest TEXT NOT NULL,state TEXT NOT NULL,result TEXT)')

    def duration(self,path):
        try:
            raw=subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(path)],stderr=subprocess.DEVNULL,timeout=20)
            return float(json.loads(raw)['format']['duration'])
        except (subprocess.SubprocessError,ValueError,KeyError):raise ValueError('Nao foi possivel ler a duracao da midia.') from None

    def run(self,args):
        try:subprocess.run(['ffmpeg','-nostdin','-v','error']+args,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=240)
        except subprocess.SubprocessError:raise ValueError('Nao foi possivel montar o video. Confira os arquivos e a duracao.') from None

    def prepare(self,sid,items,audio,form):
        fmt=FORMATS.get(form.get('format') or 'Automatico')
        audio_mode=AUDIO.get(form.get('audio_mode') or 'Manter audio original')
        if fmt is None or audio_mode is None:raise ValueError('Formato ou opcao de audio invalida.')
        seconds=number(form.get('seconds_per_image'),5,1,30,'Segundos por imagem')
        volume=number(form.get('music_volume'),60,0,100,'Volume da musica')/100
        offset=number(form.get('music_start'),0,0,3600,'Inicio da musica')
        if len(audio)>1:raise ValueError('Escolha somente uma musica.')
        if audio and audio_mode!='music':raise ValueError('Para usar a trilha anexada, escolha Musica enviada na opcao Audio.')
        if audio_mode=='music' and not audio:raise ValueError('Anexe a musica que deseja usar.')
        if fmt=='auto':fmt='carousel' if len(items)>1 else 'reel' if items and items[0]['mime_type']=='video/mp4' else 'image'
        if not items:raise ValueError('Anexe as imagens ou o video para escolher este formato.')
        all_images=all(m['mime_type']=='image/jpeg' for m in items)
        slideshow=fmt.startswith('slideshow_')
        target='story' if fmt in ('story','slideshow_story') else 'reel' if fmt in ('reel','slideshow_reel') else fmt
        if target=='image' and (len(items)!=1 or not all_images):raise ValueError('Foto no feed exige uma imagem.')
        if target=='carousel' and not 2<=len(items)<=10:raise ValueError('Carrossel exige de 2 a 10 itens.')
        if slideshow and not all_images:raise ValueError('Para transformar carrossel em video, selecione somente imagens.')
        if not slideshow and target in ('reel','story') and len(items)!=1:raise ValueError('Escolha Carrossel em video para juntar varias imagens.')
        if target=='reel' and not slideshow and all_images:raise ValueError('Para criar um Reel a partir de fotos, escolha Carrossel em video (Reels).')
        if target in ('image','carousel'):
            if audio_mode!='original':raise ValueError('Musica e controle de audio exigem Story, Reels ou Carrossel em video.')
            return items,{'format':target,'audio_mode':'original','source_names':[m['name'] for m in items]}
        # Stories are always normalized to a video, including a single still image.
        if all_images:duration=len(items)*seconds
        else:
            source=items[0];duration=self.duration(self.store.file(source['asset_id']+'.'+source['extension']))
        if not 3<=duration<=(60 if target=='story' else 900):raise ValueError('Duracao deve ser de 3 a '+('60' if target=='story' else '900')+' segundos para este formato.')
        music=audio[0] if audio else None
        if music:
            audio_path=self.store.file(music['asset_id']+'.'+music['extension'])
            if offset>=self.duration(audio_path):raise ValueError('O inicio da musica esta alem da duracao do arquivo.')
        options={'format':target,'audio_mode':audio_mode,'source_names':[m['name'] for m in items],'seconds_per_image':seconds,'duration':duration,'music_name':music['name'] if music else '', 'music_volume':volume,'music_start':offset}
        digest=hashlib.sha256(json.dumps({'items':items,'audio':audio,'options':options},sort_keys=True).encode()).hexdigest()
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT digest,state,result FROM media_renders WHERE session_id=?',(sid,)).fetchone()
            if row:
                if row[0]!=digest:raise ValueError('Este formulario ja iniciou uma montagem diferente. Abra uma nova submissao.')
                if row[1]=='completed':return json.loads(row[2]),options
                raise ValueError('Esta montagem ja foi iniciada. Confira o resultado antes de reenviar.')
            db.execute('INSERT INTO media_renders VALUES (?,?,?,NULL)',(sid,digest,'rendering'))
        asset_id=secrets.token_hex(16);output=self.store.directory/(asset_id+'.mp4')
        try:
            with tempfile.TemporaryDirectory(dir=self.store.directory) as tmp:
                tmp=Path(tmp)
                scale='scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps=30,format=yuv420p'
                encode=['-c:v','libx264','-preset','ultrafast','-crf','23','-threads','2','-pix_fmt','yuv420p']
                if all_images:
                    parts=[]
                    for i,m in enumerate(items):
                        path=self.store.file(m['asset_id']+'.jpg');part=tmp/(str(i)+'.mp4')
                        self.run(['-loop','1','-i',str(path),'-t',str(seconds),'-vf',scale,*encode,'-an',str(part)]);parts.append(part)
                    listing=tmp/'parts.txt';listing.write_text(''.join("file '"+str(p)+"'\n" for p in parts))
                    silent=tmp/'visual.mp4'
                    self.run(['-f','concat','-safe','0','-i',str(listing),'-c','copy','-an',str(silent)])
                    source=silent;has_original=False
                else:
                    m=items[0];source=self.store.file(m['asset_id']+'.mp4');has_original=True
                args=['-i',str(source)]
                if music:args+=['-stream_loop','-1','-ss',str(offset),'-i',str(audio_path)]
                args+=['-t',str(duration),'-map','0:v:0']
                if music:args+=['-map','1:a:0','-af','volume='+str(volume),'-c:a','aac','-ar','48000','-b:a','128k']
                elif audio_mode=='original' and has_original:args+=['-map','0:a?','-c:a','aac','-ar','48000','-b:a','128k']
                else:args+=['-an']
                args+=['-vf',scale,*encode,'-movflags','+faststart',str(output)]
                self.run(args)
            if output.stat().st_size>100*1024*1024:raise ValueError('Video montado excede 100 MB. Reduza a duracao.')
            output.chmod(0o600)
            item={'asset_id':asset_id,'name':('story' if target=='story' else 'reel')+'-montado.mp4','mime_type':'video/mp4','extension':'mp4'}
            with self.store.db() as db:
                db.execute('INSERT INTO media_assets VALUES (?,?,?,?,?)',(asset_id,sid,item['name'],item['mime_type'],'mp4'))
                db.execute('UPDATE media_renders SET state=?,result=? WHERE session_id=?',('completed',json.dumps([item]),sid))
            return [item],options
        except Exception:
            with self.store.db() as db:db.execute('UPDATE media_renders SET state=? WHERE session_id=?',('failed',sid))
            raise
