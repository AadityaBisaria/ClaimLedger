import base64
import csv
import io
import json
import tempfile
import unittest
import zipfile
import hashlib
from datetime import date
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from app.store import Store
from app.imports import money,normalize,parse_file
from app.evidence import upload,review,document
from app.service import route,detail,import_rows,mutate_case,export_packet
from app.packets import pdf_bytes

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.store=Store(self.tmp.name)
        self.raw={'retailer':'Retailer A','supplier_account':'S1','claim_ref':'D1','line_ref':'1','invoice_ref':'I1','po_ref':'P1','sku':'SKU1','amount':'240.50','currency':'GBP','unit':'cases'}
        self.id=route(self.store,'live','POST','/api/cases',self.raw,{})['id']
    def tearDown(self): self.tmp.cleanup()
    def mutate(self,action,**p):
        c=self.store.claim('live',self.id)
        return mutate_case(self.store,'live',self.id,action,{'version':c['version'],**p})
    def evidence(self,delivery_qty='100',qualification='full_count',unit='cases'):
        ids=[]
        for kind in ['invoice','dispatch','delivery']:
            qty=delivery_qty if kind=='delivery' else '100'
            r=upload(self.store,'live',{'filename':kind+'.txt','data':base64.b64encode(('Source '+kind+' I1 P1 SKU1 '+qty).encode()).decode(),'case_id':self.id})
            review(self.store,'live',r['id'],{'reviewed_at':'','doc_type':kind,'invoice_ref':'I1','po_ref':'P1','sku':'SKU1','quantity':qty,'unit':unit if kind=='delivery' else 'cases','qualification':qualification if kind=='delivery' else 'unspecified','page':1,'reviewer':'Test reviewer','verified':True,'case_id':self.id})
            ids.append(r['id'])
        return ids
    def ready(self): self.evidence(); return export_packet(self.store,'live',self.id,{'kind':'final','reviewer':'Test','verified':True})
    def submitted(self):
        self.ready(); self.mutate('submit',submission_ref='SUB1',submitted_at=date.today().isoformat())
    def approved(self): self.submitted(); self.mutate('decision',decision='approved',amount='200',source='Response 1')
    def payload(self,rows):
        out=io.StringIO(); w=csv.DictWriter(out,fieldnames=list(self.raw));w.writeheader();w.writerows(rows)
        return {'filename':'claims.csv','data':base64.b64encode(out.getvalue().encode()).decode()}
    def test_money_exact_and_rejects_ambiguous(self):
        self.assertEqual(money('240.50'),24050)
        for v in ['1.001','1,000','-2','NaN','Infinity','1e2','0']:
            with self.subTest(v=v),self.assertRaises(ValueError): money(v)
    def test_deadline_requires_source(self):
        with self.assertRaises(ValueError): normalize({**self.raw,'deadline':'2026-12-01'})
    def test_duplicate_import_idempotent(self):
        p=self.payload([{**self.raw,'claim_ref':'D2'},{**self.raw,'claim_ref':'D2'}]); a=import_rows(self.store,'live',p,True)
        self.assertEqual((a['new_count'],a['duplicates']),(1,1))
        self.assertEqual(import_rows(self.store,'live',p,True)['new_count'],0)
    def test_import_conflict_rolls_back_all_rows(self):
        p=self.payload([{**self.raw,'claim_ref':'D2'},{**self.raw,'amount':'999'}])
        with self.assertRaises(ValueError): import_rows(self.store,'live',p,True)
        self.assertEqual(len(self.store.list_claims('live')),1)
    def test_import_invalid_row_atomic(self):
        with self.assertRaises(ValueError): import_rows(self.store,'live',self.payload([{**self.raw,'claim_ref':'D2'},{**self.raw,'claim_ref':'D3','amount':'abc'}]),True)
        self.assertEqual(len(self.store.list_claims('live')),1)
    def test_original_import_provenance(self):
        import_rows(self.store,'live',self.payload([{**self.raw,'claim_ref':'D2'}]),True)
        c=next(c for c in self.store.list_claims('live') if c['claim_ref']=='D2');self.assertEqual(json.loads(c['source_json'])['row'],2)
    def test_missing_evidence_blocks_final(self):
        with self.assertRaises(ValueError): export_packet(self.store,'live',self.id,{'kind':'final','reviewer':'X','verified':True})
    def test_missing_evidence_allows_labelled_draft(self):
        r=export_packet(self.store,'live',self.id,{'kind':'draft'})
        from pypdf import PdfReader
        text=''.join(p.extract_text() for p in PdfReader(self.store.root/'exports'/(r['id']+'.pdf')).pages)
        self.assertIn('DRAFT - NOT READY',text)
    def test_draft_cannot_unlock_submission(self):
        self.evidence();export_packet(self.store,'live',self.id,{'kind':'draft'})
        with self.assertRaises(ValueError): self.mutate('submit',submission_ref='SUB',submitted_at=date.today().isoformat())
    def test_pallet_only_not_ready(self):
        self.evidence(qualification='pallets_only');self.assertNotEqual(detail(self.store,'live',self.id)['assessment']['readiness'],'ready')
    def test_subject_to_count_not_ready(self):
        self.evidence(qualification='subject_to_count');self.assertNotEqual(detail(self.store,'live',self.id)['assessment']['readiness'],'ready')
    def test_shortage_quantity_conflict(self):
        self.evidence('90');self.assertEqual(detail(self.store,'live',self.id)['assessment']['readiness'],'conflict')
    def test_unit_mismatch(self):
        self.evidence(unit='units');self.assertEqual(detail(self.store,'live',self.id)['assessment']['readiness'],'conflict')
    def test_zero_shipments_blocked(self):
        self.evidence('0');self.assertNotEqual(detail(self.store,'live',self.id)['assessment']['readiness'],'ready')
    def test_complete_packet_preserves_originals(self):
        r=self.ready()
        with zipfile.ZipFile(self.store.root/'exports'/(r['id']+'.zip')) as z:
            manifest=json.loads(z.read('manifest.json'))
            self.assertEqual(len(manifest['documents']),3)
            for d in manifest['documents']: self.assertEqual(hashlib.sha256(z.read(d['path'])).hexdigest(),d['sha256'])
    def test_stale_packet_blocked_after_edit(self):
        self.ready();self.mutate('edit',**{**self.raw,'amount':'230'})
        with self.assertRaises(ValueError): self.mutate('submit',submission_ref='SUB',submitted_at=date.today().isoformat())
    def test_stale_case_version(self):
        c=self.store.claim('live',self.id);self.mutate('followup',owner='A')
        with self.assertRaises(ValueError): mutate_case(self.store,'live',self.id,'followup',{'version':c['version'],'owner':'B'})
    def test_partial_approval_and_credit(self):
        self.approved();self.mutate('credit',credit_ref='CR1',amount='50',currency='GBP',credit_date=date.today().isoformat(),source='Remittance 1',verified=True)
        c=detail(self.store,'live',self.id)['case'];self.assertEqual((c['approved_cents'],c['credited_cents'],c['status']),(20000,5000,'approved'))
        self.mutate('credit',credit_ref='CR2',amount='150',currency='GBP',credit_date=date.today().isoformat(),source='Remittance 2',verified=True)
        self.assertEqual(self.store.claim('live',self.id)['status'],'credited')
    def test_credit_overpayment_rejected(self):
        self.approved()
        with self.assertRaises(ValueError): self.mutate('credit',credit_ref='CR1',amount='201',currency='GBP',credit_date=date.today().isoformat(),source='R',verified=True)
    def test_duplicate_credit_rejected(self):
        self.approved();p=dict(credit_ref='CR1',amount='50',currency='GBP',credit_date=date.today().isoformat(),source='R',verified=True);self.mutate('credit',**p)
        with self.assertRaises(ValueError): self.mutate('credit',**p)
        self.assertEqual(detail(self.store,'live',self.id)['case']['credited_cents'],5000)
    def test_cross_workspace_read_and_link_blocked(self):
        with self.assertRaises(ValueError): detail(self.store,'demo',self.id)
        with self.assertRaises(ValueError): upload(self.store,'demo',{'filename':'a.txt','data':base64.b64encode(b'test').decode(),'case_id':self.id})
    def test_file_dedup_and_basename(self):
        p={'filename':'..\\..\\secret.txt','data':base64.b64encode(b'hello').decode()};a=upload(self.store,'live',p);b=upload(self.store,'live',p)
        self.assertEqual(a['id'],b['id']);self.assertTrue(b['duplicate'])
        with self.store.connect() as db: self.assertEqual(document(self.store,'live',a['id'],db)['filename'],'secret.txt')
    def test_fake_pdf_rejected(self):
        with self.assertRaises(ValueError): upload(self.store,'live',{'filename':'x.pdf','data':base64.b64encode(b'not a pdf').decode()})
    def test_unreviewed_suggestion_not_evidence(self):
        upload(self.store,'live',{'filename':'x.txt','data':base64.b64encode(b'Invoice: I1\nPO: P1\nSKU: SKU1').decode()})
        d=detail(self.store,'live',self.id);self.assertEqual(len(d['documents']),1);self.assertFalse(d['documents'][0]['confirmed']);self.assertNotEqual(d['assessment']['readiness'],'ready')
    def test_persistence_reopen(self):
        reopened=Store(self.tmp.name);self.assertEqual(reopened.claim('live',self.id)['amount_cents'],24050)
    def test_duplicate_manual_case_rejected(self):
        with self.assertRaises(ValueError): route(self.store,'live','POST','/api/cases',self.raw,{})
    def test_xlsx_import(self):
        import openpyxl
        b=openpyxl.Workbook();b.active.append(list(self.raw));b.active.append(list({**self.raw,'claim_ref':'XLSX1'}.values()));out=io.BytesIO();b.save(out)
        r=import_rows(self.store,'live',{'filename':'test.xlsx','data':base64.b64encode(out.getvalue()).decode()},True);self.assertEqual(r['new_count'],1)
    def test_xlsx_native_date_cells(self):
        import openpyxl
        from datetime import datetime
        raw={**self.raw,'claim_ref':'EXCELDATE','claim_date':datetime(2026,10,1)}
        b=openpyxl.Workbook();b.active.append(list(raw));b.active.append(list(raw.values()));out=io.BytesIO();b.save(out)
        result=import_rows(self.store,'live',{'filename':'dates.xlsx','data':base64.b64encode(out.getvalue()).decode()},True)
        self.assertEqual(result['preview'][0]['claim_date'],'2026-10-01')
    def test_stale_document_review_rejected(self):
        ids=self.evidence()
        with self.assertRaises(ValueError): review(self.store,'live',ids[0],{'reviewed_at':''})
    def test_credit_concurrent_writes_cannot_double_allocate(self):
        self.approved();version=self.store.claim('live',self.id)['version']
        def allocate(ref):
            try:
                mutate_case(self.store,'live',self.id,'credit',{'version':version,'credit_ref':ref,'amount':'150','currency':'GBP','credit_date':date.today().isoformat(),'source':'R','verified':True})
                return True
            except ValueError:return False
        with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(allocate,['CR1','CR2']))
        self.assertEqual(sum(results),1);self.assertEqual(detail(self.store,'live',self.id)['case']['credited_cents'],15000)
    def test_scanned_pdf_requires_manual_review(self):
        from reportlab.pdfgen import canvas
        b=io.BytesIO();c=canvas.Canvas(b);c.rect(10,10,100,100);c.showPage();c.save()
        r=upload(self.store,'live',{'filename':'scan.pdf','data':base64.b64encode(b.getvalue()).decode()})
        with self.store.connect() as db:self.assertEqual(document(self.store,'live',r['id'],db)['extraction_status'],'manual_review')
    def test_packet_escapes_markup(self):
        self.mutate('followup',notes='<script>unsafe & markup</script>');self.ready()
    def test_impossible_shortage_blocked(self):
        self.evidence();self.mutate('edit',**{**self.raw,'claimed_qty':'200'})
        self.assertEqual(detail(self.store,'live',self.id)['assessment']['readiness'],'conflict')
    def test_credit_reversal_preserves_record_and_reopens_balance(self):
        self.approved();self.mutate('credit',credit_ref='CR1',amount='200',currency='GBP',credit_date=date.today().isoformat(),source='R',verified=True)
        d=detail(self.store,'live',self.id);cr=d['credits'][0]
        route(self.store,'live','POST','/api/credits/'+cr['id']+'/reverse',{'reason':'Entry error','verified':True},{})
        d=detail(self.store,'live',self.id);self.assertEqual(d['case']['credited_cents'],0);self.assertEqual(d['case']['status'],'approved');self.assertTrue(d['credits'][0]['voided_at']);self.assertEqual(d['credits'][0]['amount_cents'],20000)
        with self.assertRaises(ValueError): route(self.store,'live','POST','/api/credits/'+cr['id']+'/reverse',{'reason':'Again','verified':True},{})
        self.assertEqual(self.store.list_claims('live')[0]['credited_cents'],0)
    def test_original_pdf_page_renders_and_bounds_are_checked(self):
        from app.preview import render_page
        path=Path(self.tmp.name)/'preview.pdf';path.write_bytes(pdf_bytes('Original',['Invoice I1, quantity 100 cases']))
        rendered=render_page(path,1);self.assertTrue(rendered.startswith(b'\x89PNG'))
        with self.assertRaises(ValueError):render_page(path,2)

if __name__=='__main__': unittest.main()
