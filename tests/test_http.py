import base64
import http.client
import json
import re
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from app.store import Store
from server import make_handler

class HttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(self.tmp.name)
        self.http=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.store,'test-token',0))
        self.port=self.http.server_address[1];self.http.RequestHandlerClass=make_handler(self.store,'test-token',self.port)
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
    def tearDown(self): self.http.shutdown();self.http.server_close();self.thread.join();self.tmp.cleanup()
    def request(self,method,path,body=None,headers=None):
        c=http.client.HTTPConnection('127.0.0.1',self.port,timeout=5)
        c.request(method,path,body,headers or {});r=c.getresponse();out=(r.status,dict(r.getheaders()),r.read());c.close();return out
    def test_bootstrap_and_static_headers(self):
        status,h,b=self.request('GET','/api/bootstrap');self.assertEqual(status,200);self.assertEqual(json.loads(b)['token'],'test-token')
        status,h,b=self.request('GET','/');self.assertEqual(status,200);self.assertIn('Content-Security-Policy',h);self.assertEqual(h['X-Content-Type-Options'],'nosniff')
    def test_wrong_origin_blocked(self):
        self.assertEqual(self.request('GET','/api/cases',headers={'Origin':'https://evil.example'})[0],403)
    def test_dns_rebinding_host_blocked(self):
        self.assertEqual(self.request('GET','/api/bootstrap',headers={'Host':'evil.example'})[0],403)
    def test_missing_csrf_blocked(self):
        self.assertEqual(self.request('POST','/api/cases','{}',{'Content-Type':'application/json'})[0],403)
    def test_traversal_cannot_serve_database(self):
        for path in ['/../data/claimledger.sqlite3','/%2e%2e/server.py','/data/claimledger.sqlite3']:
            self.assertEqual(self.request('GET',path)[0],404)
    def test_compiled_frontend_assets_served_with_safe_mime(self):
        status,h,html=self.request('GET','/')
        self.assertEqual(status,200)
        assets=re.findall(r'(?:src|href)="(/assets/[^" ]+)"',html.decode())
        self.assertTrue(any(p.endswith('.js') for p in assets))
        self.assertTrue(any(p.endswith('.css') for p in assets))
        for path in assets:
            status,headers,body=self.request('GET',path)
            self.assertEqual(status,200)
            self.assertTrue(body)
            self.assertEqual(headers['Content-Type'],'text/javascript' if path.endswith('.js') else 'text/css')
            self.assertNotIn("unsafe-inline",headers['Content-Security-Policy'])
    def test_frontend_sources_and_legacy_scripts_are_not_public(self):
        for path in ['/src/App.tsx','/frontend/package.json','/app.js','/evidence-ui.js','/style.css','/assets/../../src/App.tsx']:
            self.assertEqual(self.request('GET',path)[0],404,path)
    def test_encoded_asset_traversal_and_unknown_asset_are_blocked(self):
        for path in ['/assets/%2e%2e/%2e%2e/server.py','/assets/%2e%2e/%2e%2e/data/claimledger.sqlite3','/assets/missing.js','/assets/../index.html']:
            self.assertEqual(self.request('GET',path)[0],404,path)
    def test_create_and_persist_over_http(self):
        p={'retailer':'Test','claim_ref':'HTTP1','amount':'10.01','currency':'CAD'}
        s,h,b=self.request('POST','/api/cases?workspace=live',json.dumps(p),{'Content-Type':'application/json','X-ClaimLedger-Token':'test-token'});self.assertEqual(s,200,b)
        s,h,b=self.request('GET','/api/cases?workspace=live');self.assertEqual(json.loads(b)['cases'][0]['amount_cents'],1001)
        s,h,b=self.request('GET','/api/cases?workspace=demo');self.assertEqual(json.loads(b)['cases'],[])
    def test_download_template_has_consistent_columns(self):
        import csv,io
        s,h,b=self.request('GET','/api/template');rows=list(csv.reader(io.StringIO(b.decode())));self.assertEqual(len(rows[0]),len(rows[1]));self.assertEqual(s,200)

if __name__=='__main__':unittest.main()
