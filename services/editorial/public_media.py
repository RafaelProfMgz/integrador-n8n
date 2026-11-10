"""Public media-only gateway. No chat, credentials or editorial API routes."""
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*_):pass
    def do_HEAD(self):
        self.do_GET()
    def do_GET(self):
        if not re.fullmatch(r'/media/files/[a-f0-9]{32}\.(jpg|mp4)',self.path):return self.send_error(404)
        path=Path('/data/uploaded-media')/self.path.rsplit('/',1)[-1]
        if not path.is_file():return self.send_error(404)
        size=path.stat().st_size;start=0;end=size-1
        range_header=self.headers.get('Range')
        if range_header:
            match=re.fullmatch(r'bytes=(\d+)-(\d*)',range_header)
            if not match:return self.send_error(416)
            start=int(match[1]);end=min(int(match[2]),end) if match[2] else end
            if start>end or start>=size:return self.send_error(416)
        self.send_response(206 if range_header else 200)
        self.send_header('Content-Type','image/jpeg' if path.suffix=='.jpg' else 'video/mp4')
        self.send_header('Content-Length',str(end-start+1));self.send_header('Accept-Ranges','bytes')
        self.send_header('X-Content-Type-Options','nosniff')
        if range_header:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        self.end_headers()
        if self.command=='HEAD':return
        with path.open('rb') as stream:
            stream.seek(start);remaining=end-start+1
            while remaining:
                raw=stream.read(min(65536,remaining))
                if not raw:break
                self.wfile.write(raw);remaining-=len(raw)

if __name__=='__main__':ThreadingHTTPServer(('0.0.0.0',8083),Handler).serve_forever()
