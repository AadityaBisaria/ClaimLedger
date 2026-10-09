"""Local, single-operator HTTP server. Bound to loopback only."""
import argparse
import json
import mimetypes
import os
import secrets
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from app.store import Store

ROOT=Path(__file__).resolve().parent


def make_handler(store, token, port):
    class Handler(BaseHTTPRequestHandler):
        server_version='ClaimLedger/0.1'

        def log_message(self, fmt, *args):
            # Do not write filenames, financial data or request bodies to logs.
            pass

        def respond(self, status, body, mime='application/json', extra=None):
            if isinstance(body,(dict,list)):
                body=json.dumps(body,ensure_ascii=False).encode()
            elif isinstance(body,str):
                body=body.encode()
            self.send_response(status)
            self.send_header('Content-Type',mime)
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; frame-src 'self' blob:; object-src 'none'; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'self'")
            for k,v in (extra or {}).items(): self.send_header(k,v)
            self.end_headers()
            self.wfile.write(body)

        def dispatch(self,method):
            try:
                allowed={f'127.0.0.1:{port}',f'localhost:{port}'}
                if self.headers.get('Host') not in allowed:
                    return self.respond(403,{'error':'Local requests only.'})
                origin=self.headers.get('Origin')
                if origin and origin not in {f'http://{h}' for h in allowed}:
                    return self.respond(403,{'error':'Cross-origin requests are not permitted.'})
                url=urlsplit(self.path)
                path=unquote(url.path)
                query=parse_qs(url.query)
                workspace=query.get('workspace',['demo'])[0]
                if workspace not in {'demo','live'}:
                    raise ValueError('Unknown workspace.')
                payload={}
                if method=='POST':
                    if not secrets.compare_digest(self.headers.get('X-ClaimLedger-Token',''),token):
                        return self.respond(403,{'error':'Refresh the page and try again.'})
                    if self.headers.get_content_type()!='application/json':
                        raise ValueError('Expected a JSON request.')
                    length=int(self.headers.get('Content-Length','0'))
                    if length<=0 or length>16*1024*1024:
                        raise ValueError('Request must be between 1 byte and 16 MB.')
                    payload=json.loads(self.rfile.read(length))
                    if not isinstance(payload,dict): raise ValueError('Expected an object.')
                if method=='GET' and path=='/api/bootstrap':
                    return self.respond(200,{'token':token,'workspace':workspace,'name':'ClaimLedger','mode':'local','version':'0.1.0'})
                if method=='GET' and path=='/api/cases':
                    from app.service import list_cases
                    cases=list_cases(store,workspace)
                    return self.respond(200,{'cases':cases})
                if path.startswith('/api/'):
                    from app.service import route
                    result=route(store,workspace,method,path,payload,query)
                    if isinstance(result,tuple):
                        status,body,mime,extra=result
                        return self.respond(status,body,mime,extra)
                    return self.respond(200,result)
                if method=='GET':
                    # Serve only compiled frontend assets, never sources or application data.
                    public=(ROOT/'frontend'/'dist').resolve()
                    name='index.html' if path=='/' else path[1:]
                    file=(public/name).resolve()
                    allowed_asset=path.startswith('/assets/') and file.suffix in {'.js','.css','.svg','.png','.woff2'}
                    if file.is_relative_to(public) and (path in {'/','/favicon.svg'} or allowed_asset) and file.is_file():
                        mime='text/javascript' if file.suffix=='.js' else mimetypes.guess_type(name)[0] or 'application/octet-stream'
                        return self.respond(200,file.read_bytes(),mime)
                return self.respond(404,{'error':'Not found.'})
            except (ValueError,KeyError,TypeError,json.JSONDecodeError) as exc:
                return self.respond(400,{'error':str(exc)[:600]})
            except Exception:
                traceback.print_exc()
                return self.respond(500,{'error':'The operation could not be completed. Your existing records were preserved.'})

        def do_GET(self): self.dispatch('GET')
        def do_POST(self): self.dispatch('POST')

    return Handler


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--data-dir',default=str(ROOT/'data'))
    parser.add_argument('--no-demo',action='store_true')
    args=parser.parse_args()
    store=Store(args.data_dir)
    if not args.no_demo:
        store.seed()
        from app.demo import seed_evidence
        seed_evidence(store)
    httpd=ThreadingHTTPServer(('127.0.0.1',args.port),make_handler(store,secrets.token_urlsafe(32),args.port))
    httpd.daemon_threads=True
    print(f'ClaimLedger is running at http://127.0.0.1:{args.port}',flush=True)
    print(f'Local data: {store.root}',flush=True)
    try: httpd.serve_forever()
    except KeyboardInterrupt: pass
    finally: httpd.server_close()


if __name__=='__main__': main()
