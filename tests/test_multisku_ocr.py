import base64
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from app.store import Store,SCHEMA,now
from app.evidence import upload,review,document,fingerprint
from app.service import route,detail
from app.extraction import native_pages,candidates,suggest_matches
from app.ocr import run

class MultiSkuTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(self.tmp.name)
        self.a=self.case('A','TEA');self.b=self.case('B','OAT')
        self.doc=upload(self.store,'live',{'filename':'multi.txt','data':base64.b64encode(b'Document type: invoice\nInvoice: INV1\nPO: PO1\nSKU: TEA\nQuantity: 50\nUnit: cases\nSKU: OAT\nQuantity: 80\nUnit: cases').decode()})['id']
    def tearDown(self):self.tmp.cleanup()
    def case(self,ref,sku):return route(self.store,'live','POST','/api/cases',{'retailer':'Example','claim_ref':ref,'invoice_ref':'INV1','po_ref':'PO1','sku':sku,'amount':'100','currency':'GBP'}, {})['id']
    def save(self,case,sku,qty,version=''):
        review(self.store,'live',self.doc,{'case_id':case,'doc_type':'invoice','invoice_ref':'INV1','po_ref':'PO1','sku':sku,'quantity':qty,'unit':'cases','qualification':'unspecified','page':1,'reviewer':'QA','verified':True,'mapping_version':version})
    def test_extracted_two_skus_and_exact_matches(self):
        with self.store.connect() as db:d=document(self.store,'live',self.doc,db)
        self.assertEqual([r['fields']['sku'] for r in d['candidates']],['TEA','OAT'])
        matches=route(self.store,'live','GET','/api/documents/matches',{}, {})['matches']
        self.assertEqual({(r['case_id'],r['candidate']['fields']['sku']) for r in matches},{(self.a,'TEA'),(self.b,'OAT')})
    def test_one_review_does_not_confirm_other_sku(self):
        self.save(self.a,'TEA','50');a=detail(self.store,'live',self.a);b=detail(self.store,'live',self.b)
        self.assertTrue(a['documents'][0]['confirmed']);self.assertFalse(b['documents'][0]['confirmed'])
    def test_review_isolation_and_fingerprint(self):
        self.save(self.a,'TEA','50');a=detail(self.store,'live',self.a);old=fingerprint(a['case'],a['documents'])
        self.save(self.b,'OAT','80');a=detail(self.store,'live',self.a);b=detail(self.store,'live',self.b)
        self.assertEqual(a['documents'][0]['meta']['quantity'],'50');self.assertEqual(b['documents'][0]['meta']['quantity'],'80');self.assertEqual(fingerprint(a['case'],a['documents']),old)
        version=b['documents'][0]['reviewed_at'];self.save(self.b,'OAT','90',version)
        a=detail(self.store,'live',self.a);self.assertEqual(fingerprint(a['case'],a['documents']),old)
    def test_stale_mapping_blocked_independently(self):
        self.save(self.a,'TEA','50');self.save(self.b,'OAT','80')
        version=detail(self.store,'live',self.a)['documents'][0]['reviewed_at']
        self.save(self.a,'TEA','51',version)
        with self.assertRaises(ValueError):self.save(self.a,'TEA','52',version)
    def test_suggestions_exclude_conflicting_sku(self):
        rows=candidates(native_pages('Invoice: INV1\nPO: PO1\nSKU: WRONG\nQuantity: 30\nUnit: cases'))
        self.assertEqual(suggest_matches(self.store.list_claims('live'),rows,{}),[])
    def test_original_dedup_keeps_separate_mappings(self):
        self.save(self.a,'TEA','50');self.save(self.b,'OAT','80')
        d=upload(self.store,'live',{'filename':'copy.txt','data':base64.b64encode((self.store.root/'files'/self.doc).read_bytes()).decode()})
        self.assertTrue(d['duplicate']);self.assertEqual(d['id'],self.doc);self.assertEqual(detail(self.store,'live',self.b)['documents'][0]['meta']['quantity'],'80')
    def test_unlink_one_line_keeps_other(self):
        self.save(self.a,'TEA','50');self.save(self.b,'OAT','80')
        route(self.store,'live','POST',f'/api/documents/{self.doc}/unlink',{'case_id':self.a},{})
        self.assertEqual(detail(self.store,'live',self.a)['documents'],[]);self.assertTrue(detail(self.store,'live',self.b)['documents'][0]['confirmed'])
    def test_cross_workspace_mapping_blocked(self):
        with self.assertRaises(ValueError):review(self.store,'demo',self.doc,{'case_id':self.a})
    def test_source_span_wrong_page_rejected(self):
        with self.assertRaises(ValueError):review(self.store,'live',self.doc,{'case_id':self.a,'mapping_version':'','doc_type':'invoice','qualification':'unspecified','page':1,'source_span_ids':['2:0']})
    def test_delimited_sku_rows(self):
        rows=candidates(native_pages('Invoice: INV1\nPO: PO1\nSKU | Quantity | Unit\nTEA | 50 | cases\nOAT | 80 | cases'))
        self.assertEqual(len(rows),2);self.assertEqual(rows[1]['fields']['quantity'],'80')
    def test_review_freezes_source_snippets(self):
        with self.store.connect() as db:d=document(self.store,'live',self.doc,db)
        row=d['candidates'][0]
        review(self.store,'live',self.doc,{'case_id':self.a,'mapping_version':'','doc_type':'invoice','invoice_ref':'INV1','po_ref':'PO1','sku':'TEA','quantity':'50','unit':'cases','qualification':'unspecified','page':1,'reviewer':'QA','verified':True,'source_span_ids':row['span_ids']})
        d=detail(self.store,'live',self.a);old=fingerprint(d['case'],d['documents'])
        with self.store.connect() as db:db.execute('UPDATE extraction_pages SET spans_json=? WHERE document_id=?',(json.dumps([{'id':'1:0','text':'Changed extraction','confidence':.5,'bbox':None}]),self.doc))
        d=detail(self.store,'live',self.a);self.assertEqual(fingerprint(d['case'],d['documents']),old)
        self.assertTrue(any('Quantity: 50' in s['text'] for s in d['documents'][0]['meta']['source_snippets']))

class MigrationTests(unittest.TestCase):
    def test_legacy_confirmed_evidence_is_preserved(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'claimledger.sqlite3';db=sqlite3.connect(path);db.executescript(SCHEMA)
            meta=json.dumps({'doc_type':'invoice','sku':'LEGACY','quantity':'10','unit':'cases','page':1})
            db.execute('INSERT INTO claims(id,workspace,retailer,claim_ref,amount_cents,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',('c','live','Retailer','D1',10000,now(),now()))
            db.execute('INSERT INTO documents(id,workspace,filename,mime,size,sha256,extracted_text,extraction_status,pages,meta_json,reviewed_by,reviewed_at,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',('d','live','legacy.txt','text/plain',10,'hash','SKU: LEGACY\nQuantity: 10\nUnit: cases','text_extracted',1,meta,'Original reviewer','original-time',now()))
            db.execute('INSERT INTO links VALUES(?,?,?,?)',('c','d',1,'Confirmed'));db.commit();db.close()
            store=Store(root);d=detail(store,'live','c')['documents'][0]
            self.assertEqual(d['meta']['quantity'],'10');self.assertEqual(d['reviewed_by'],'Original reviewer');self.assertEqual(d['reviewed_at'],'original-time');self.assertTrue(d['confirmed'])
            self.assertTrue(d['candidates']);Store(root)
            self.assertEqual(detail(store,'live','c')['documents'][0]['meta']['sku'],'LEGACY')

class OCRTests(unittest.TestCase):
    def test_scanned_pdf_second_page_ocr_preserves_original(self):
        from reportlab.pdfgen import canvas
        from reportlab.lib.utils import ImageReader
        import hashlib
        with tempfile.TemporaryDirectory() as root:
            store=Store(root);im=Image.new('RGB',(1400,700),'white');draw=ImageDraw.Draw(im)
            draw.text((50,70),'Invoice: INV-PDF-2\nPO: PO-PDF-2\nSKU: OAT-PDF\nQuantity: 80\nUnit: cases',fill='black',font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',42),spacing=15)
            out=io.BytesIO();pdf=canvas.Canvas(out,pagesize=(700,350));pdf.rect(1,1,10,10);pdf.showPage();pdf.drawImage(ImageReader(im),0,0,width=700,height=350);pdf.showPage();pdf.save()
            raw=out.getvalue();doc=upload(store,'live',{'filename':'two-page-scan.pdf','data':base64.b64encode(raw).decode()})['id']
            result=run(store,'live',doc,{'page':2})
            self.assertTrue(any(r['page']==2 and r['fields'].get('sku')=='OAT-PDF' for r in result['candidates']))
            self.assertEqual(hashlib.sha256((store.root/'files'/doc).read_bytes()).digest(),hashlib.sha256(raw).digest())
            with self.assertRaises(ValueError):run(store,'live',doc,{'page':3})
    def test_real_local_ocr_has_boxes_and_never_confirms(self):
        with tempfile.TemporaryDirectory() as root:
            store=Store(root)
            case=route(store,'live','POST','/api/cases',{'retailer':'Example','claim_ref':'SCAN','invoice_ref':'INV-SCAN-1','po_ref':'PO-SCAN-1','sku':'TEA-SCAN','amount':'100','currency':'GBP'}, {})['id']
            im=Image.new('RGB',(1400,700),'white');draw=ImageDraw.Draw(im)
            font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',42)
            draw.text((60,80),'Invoice: INV-SCAN-1\nPO: PO-SCAN-1\nSKU: TEA-SCAN\nQuantity: 50\nUnit: cases',fill='black',font=font,spacing=15)
            b=io.BytesIO();im.save(b,format='PNG');doc=upload(store,'live',{'filename':'scan.png','data':base64.b64encode(b.getvalue()).decode()})['id']
            result=run(store,'live',doc,{'page':1});self.assertFalse(result['empty']);self.assertTrue(all(len(s['bbox'])==4 for s in result['spans']))
            self.assertTrue(any(r['fields'].get('sku')=='TEA-SCAN' and r['fields'].get('quantity')=='50' for r in result['candidates']))
            self.assertFalse(detail(store,'live',case)['documents'][0]['confirmed'])
            self.assertNotEqual(detail(store,'live',case)['assessment']['readiness'],'ready')
            with self.assertRaises(ValueError):run(store,'demo',doc,{'page':1})

if __name__=='__main__':unittest.main()
