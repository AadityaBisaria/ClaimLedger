"""Fictional examples only. Never seed the live workspace."""
import base64
from datetime import date
from .evidence import upload,review,document
from .packets import pdf_bytes
from .service import detail,export_packet,mutate_case

def seed_evidence(store):
    with store.connect() as db:
        if db.execute("SELECT 1 FROM settings WHERE key='demo_evidence_seed'").fetchone(): return
    for c in store.list_claims('demo'):
        if c['claim_ref']=='NF-1046': continue
        for kind in ('invoice','dispatch','delivery'):
            quantity='90' if c['claim_ref']=='NF-1044' and kind=='delivery' else '100'
            qualification='pallets_only' if c['claim_ref']=='NF-1042' and kind=='delivery' else 'short_noted' if c['claim_ref']=='NF-1044' and kind=='delivery' else 'full_count' if kind=='delivery' else 'unspecified'
            unit='pallets' if qualification=='pallets_only' else 'cases'
            if unit=='pallets': quantity='2'
            text=['FICTIONAL DEMO DOCUMENT - NOT A REAL TRANSACTION',f'Document type: {kind}',f'Invoice: {c["invoice_ref"]}',f'PO: {c["po_ref"]}',f'SKU: {c["sku"]}',f'Quantity: {quantity}',f'Unit: {unit}',f'Qualification: {qualification}', 'This synthetic example demonstrates evidence review. No retailer has issued or accepted this document.']
            data=pdf_bytes('Northfield Markets - '+kind,text)
            r=upload(store,'demo',{'filename':c['claim_ref']+'-'+kind+'.pdf','data':base64.b64encode(data).decode(),'case_id':c['id']})
            with store.connect() as db: old=document(store,'demo',r['id'],db)
            review(store,'demo',r['id'],{'doc_type':kind,'invoice_ref':c['invoice_ref'],'po_ref':c['po_ref'],'sku':c['sku'],'quantity':quantity,'unit':unit,'qualification':qualification,'page':1,'reviewer':'Demo reviewer','verified':True,'case_id':c['id'],'reviewed_at':old['reviewed_at'],'notes':'Fictional training record.'})
        if c['claim_ref']=='NF-1045' and c['status']=='open':
            export_packet(store,'demo',c['id'],{'kind':'final','reviewer':'Demo reviewer','verified':True})
            mutate_case(store,'demo',c['id'],'submit',{'version':c['version'],'submission_ref':'FICTIONAL-SUB-1045','submitted_at':date.today().isoformat()})
            c=store.claim('demo',c['id'])
            mutate_case(store,'demo',c['id'],'decision',{'version':c['version'],'decision':'approved','amount':'120','source':'Fictional retailer response'})
            c=store.claim('demo',c['id'])
            mutate_case(store,'demo',c['id'],'credit',{'version':c['version'],'amount':'60','currency':'GBP','credit_ref':'FICTIONAL-CR-1045','source':'Fictional remittance','credit_date':date.today().isoformat(),'verified':True})
    with store.connect() as db: db.execute("INSERT OR REPLACE INTO settings VALUES('demo_evidence_seed','1')")
