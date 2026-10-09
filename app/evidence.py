import base64
import hashlib
import io
import json
import re
from decimal import Decimal
from pathlib import PureWindowsPath
from .imports import clean,decode,quantity
from .store import now,uid
from .extraction import native_pages,candidates,suggest_matches

TYPES={'invoice','dispatch','delivery','correspondence','other'}
QUALIFICATIONS={'full_count','subject_to_count','pallets_only','short_noted','unspecified'}

def document(store,workspace,doc_id,db):
    r=db.execute('SELECT * FROM documents WHERE id=? AND workspace=?',(doc_id,workspace)).fetchone()
    if not r: raise ValueError('Document not found in this workspace.')
    d=dict(r); d['meta']=json.loads(d.pop('meta_json'))
    pages=[{'page':r['page'],'method':r['method'],'spans':json.loads(r['spans_json'])} for r in db.execute('SELECT * FROM extraction_pages WHERE document_id=? ORDER BY page',(doc_id,))]
    d['extraction_pages']=pages
    d['candidates']=candidates(pages)
    d['mappings']=[{'case_id':r['claim_id'],'meta':json.loads(r['review_json']),'reviewed_by':r['reviewed_by'],'reviewed_at':r['reviewed_at'],'confirmed':bool(r['confirmed'])} for r in db.execute('SELECT * FROM links WHERE document_id=?',(doc_id,))]
    return d

def documents_for(store,workspace,case_id,db):
    store.claim(workspace,case_id,db)
    out=[]
    for l in db.execute('SELECT * FROM links WHERE claim_id=?',(case_id,)):
        d=document(store,workspace,l['document_id'],db)
        if l['review_json']!='{}':
            d.update(meta=json.loads(l['review_json']),reviewed_by=l['reviewed_by'],reviewed_at=l['reviewed_at'])
        d.update(confirmed=bool(l['confirmed']),reason=l['reason'])
        out.append(d)
    return out

def upload(store,workspace,p):
    data=decode(p)
    name=PureWindowsPath(clean(p.get('filename','document'),200)).name
    ext=name.rsplit('.',1)[-1].lower()
    pages=1; text=''
    if ext=='pdf' and data.startswith(b'%PDF-'):
        from pypdf import PdfReader
        try:
            reader=PdfReader(io.BytesIO(data))
            if reader.is_encrypted: raise ValueError('Encrypted PDFs are not supported.')
            pages=len(reader.pages)
            if not 0<pages<=100: raise ValueError('PDF must contain 1 to 100 pages.')
            text='\n'.join(f'--- Page {i+1} ---\n{page.extract_text() or ""}' for i,page in enumerate(reader.pages))[:300000]
            if not re.search(r'[A-Za-z]{3}', re.sub(r'--- Page \d+ ---','',text)): text=''
        except ValueError: raise
        except Exception: raise ValueError('The PDF could not be read. Use an unencrypted PDF.')
        mime='application/pdf'
    elif ext in {'jpg','jpeg'} and data.startswith(b'\xff\xd8\xff'): mime='image/jpeg'
    elif ext=='png' and data.startswith(b'\x89PNG\r\n\x1a\n'): mime='image/png'
    elif ext=='txt':
        try: text=data.decode('utf-8-sig')
        except UnicodeDecodeError: raise ValueError('Text files must use UTF-8.')
        mime='text/plain'
    else: raise ValueError('Use a valid PDF, PNG, JPEG or UTF-8 TXT document.')
    meta={}
    labels={'invoice_ref':'Invoice','po_ref':'PO','sku':'SKU','quantity':'Quantity','unit':'Unit','doc_type':'Document type','qualification':'Qualification'}
    for key,label in labels.items():
        m=re.search(r'^'+label+r':\s*([^\r\n]+)',text,re.I|re.M)
        if m: meta[key]=m.group(1).strip()[:200]
    sha=hashlib.sha256(data).hexdigest()
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        if p.get('case_id'): store.claim(workspace,p['case_id'],db)
        old=db.execute('SELECT id FROM documents WHERE workspace=? AND sha256=?',(workspace,sha)).fetchone()
        doc_id=old['id'] if old else uid()
        if not old:
            (store.root/'files'/doc_id).write_bytes(data)
            db.execute('INSERT INTO documents(id,workspace,filename,mime,size,sha256,extracted_text,extraction_status,pages,meta_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                       (doc_id,workspace,name,mime,len(data),sha,text,'text_extracted' if text else 'manual_review',pages,json.dumps(meta),now()))
            for pg in native_pages(text):db.execute('INSERT INTO extraction_pages VALUES(?,?,?,?,?)',(doc_id,pg['page'],pg['method'],json.dumps(pg['spans']),now()))
        d=document(store,workspace,doc_id,db)
        claims=[dict(r) for r in db.execute('SELECT * FROM claims WHERE workspace=?',(workspace,))]
        matches=suggest_matches(claims,d['candidates'],meta)
        for m in matches:db.execute('INSERT OR IGNORE INTO links(claim_id,document_id,confirmed,reason) VALUES(?,?,0,?)',(m['case_id'],doc_id,m['reason']))
        if p.get('case_id'):db.execute('INSERT OR IGNORE INTO links(claim_id,document_id,confirmed,reason) VALUES(?,?,0,?)',(p['case_id'],doc_id,'Uploaded from this case; confirm manually'))
        store.event(db,workspace,p.get('case_id'),'Document uploaded',{'filename':name,'duplicate':bool(old)})
    return {'id':doc_id,'duplicate':bool(old),'matches':matches}

def review(store,workspace,doc_id,p):
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        d=document(store,workspace,doc_id,db)
        case_id=p.get('case_id')
        mapping=db.execute('SELECT * FROM links WHERE claim_id=? AND document_id=?',(case_id,doc_id)).fetchone() if case_id else None
        current=mapping['reviewed_at'] if mapping else ''
        expected=p.get('mapping_version',p.get('reviewed_at',''))
        if expected!=current and not (not mapping and 'mapping_version' not in p and expected==d['reviewed_at']):
            raise ValueError('This evidence mapping changed. Reopen it before saving.')
        meta={k:clean(p.get(k,''),500) for k in ('doc_type','invoice_ref','po_ref','sku','quantity','unit','qualification','notes')}
        if meta['doc_type'] not in TYPES or meta['qualification'] not in QUALIFICATIONS: raise ValueError('Select a document type and delivery qualification.')
        meta['quantity']=quantity(meta['quantity'])
        if meta['unit'] not in {'cases','units','kg','pallets',''}: raise ValueError('Choose a supported quantity unit.')
        meta['page']=int(p.get('page',1))
        if not 1<=meta['page']<=d['pages']: raise ValueError('Source page is outside this document.')
        source_ids=p.get('source_span_ids',[])
        if not isinstance(source_ids,list) or len(source_ids)>200:raise ValueError('Invalid source text references.')
        valid={s['id'] for pg in d['extraction_pages'] if pg['page']==meta['page'] for s in pg['spans']}
        if any(not isinstance(s,str) or s not in valid for s in source_ids):raise ValueError('Source text references must belong to the selected document page.')
        meta['source_span_ids']=source_ids
        meta['source_method']=next((pg['method'] for pg in d['extraction_pages'] if pg['page']==meta['page']),'manual')
        meta['source_snippets']=[s for pg in d['extraction_pages'] if pg['page']==meta['page'] for s in pg['spans'] if s['id'] in source_ids]
        reviewer=clean(p.get('reviewer',''),100)
        if not reviewer or p.get('verified') is not True: raise ValueError('Confirm that you checked these fields against the original document.')
        if case_id: store.claim(workspace,case_id,db)
        elif meta['doc_type'] in {'invoice','dispatch','delivery'}:raise ValueError('Select a case line to confirm quantity evidence.')
        stamp=now()
        # Document-level values remain extraction suggestions; financial evidence belongs to the link.
        db.execute('UPDATE documents SET reviewed_by=?,reviewed_at=? WHERE id=?',(reviewer,stamp,doc_id))
        if case_id:
            db.execute('''INSERT INTO links(claim_id,document_id,confirmed,reason,review_json,reviewed_by,reviewed_at)
              VALUES(?,?,1,?,?,?,?) ON CONFLICT(claim_id,document_id) DO UPDATE SET confirmed=1,
              reason=excluded.reason,review_json=excluded.review_json,reviewed_by=excluded.reviewed_by,reviewed_at=excluded.reviewed_at''',
              (case_id,doc_id,'Confirmed by '+reviewer,json.dumps(meta),reviewer,stamp))
        store.event(db,workspace,case_id,'Evidence reviewed',{'document':d['filename'],'reviewer':reviewer,'fields':meta})
    return {'saved':True}

def assess(c,docs):
    checks=[]
    def check(label,passed,detail): checks.append({'label':label,'passed':bool(passed),'detail':detail})
    check('Case references',all(c[k] for k in ('invoice_ref','po_ref','sku')),'Invoice, purchase order and SKU are required for this single-line workflow.')
    check('Claim quantity is usable',bool(c['claimed_qty']) and c['unit']!='pallets','Enter the alleged shortage as cases, units or kg. A pallet count alone cannot be compared to a SKU quantity.')
    selected=[d for d in docs if d['confirmed'] and d['reviewed_by']]
    quantities={}; conflict=False
    sources={
        'invoice':'Get this from your finance or ERP team: the bill your company issued to the retailer.',
        'dispatch':'Get this from your warehouse or 3PL: dispatch note, ASN, bill of lading, or shipment export.',
        'delivery':'Get this from the retailer portal/receiving team, carrier, or 3PL: POD, receipt, or EDI receiving record.',
    }
    for kind,label in [('invoice','Invoice'),('dispatch','Dispatch'),('delivery','Delivery receipt')]:
        group=[d for d in selected if d['meta'].get('doc_type')==kind]
        matching=[d for d in group if all(d['meta'].get(k)==c[k] and c[k] for k in ('invoice_ref','po_ref','sku','unit'))]
        check(label+' reviewed',bool(matching),', '.join(d['filename'] for d in matching) if matching else 'No reviewed document supports this case line. '+sources[kind])
        if group:
            references_match=len(matching)==len(group)
            check(label+' references and unit',references_match,'Every reviewed '+label.lower()+' must match the case invoice, PO, SKU and unit; no implicit unit conversions.')
            if not references_match: conflict=True
        if matching:
            values=[d['meta'].get('quantity','') for d in matching]
            has_quantity=all(values)
            check(label+' quantity',has_quantity,'Each reviewed copy needs a numeric SKU quantity and source page.')
            agree=has_quantity and len(set(values))==1
            if len(matching)>1:
                check(label+' copies agree',agree,'Multiple reviewed copies must show the same SKU quantity. Resolve any difference before exporting.')
            if has_quantity and agree: quantities[kind]=values[0]
            if has_quantity and not agree: conflict=True
            if kind=='delivery':
                delivery_count=all(d['meta'].get('qualification')=='full_count' for d in matching)
                check('Delivery count confirmed',delivery_count,'The receipt must explicitly substantiate the SKU quantity. Pallet-only, subject-to-count and shortages need investigation.')
                if not delivery_count: conflict=True
    if len(quantities)==3:
        same=len({Decimal(v) for v in quantities.values()})==1
        check('Quantities reconcile',same,'Invoiced, dispatched and received quantities must agree for this full-delivery dispute. Differences need manual investigation.')
        check('Positive shipment quantity',all(Decimal(v)>0 for v in quantities.values()),'Zero-quantity shipments cannot support a full-delivery dispute.')
        conflict=conflict or not same
        if c['claimed_qty']:
            plausible=Decimal(c['claimed_qty'])>0 and Decimal(c['claimed_qty'])<=Decimal(quantities['invoice'])
            check('Alleged shortage is plausible',plausible,'Alleged shortage must be positive and cannot exceed the invoiced quantity.')
            conflict=conflict or not plausible
    ready=all(x['passed'] for x in checks)
    return {'readiness':'ready' if ready else 'conflict' if conflict else 'missing','checks':checks,'quantities':quantities,'deadline_warning':not bool(c['deadline'] and c['deadline_source'])}

def fingerprint(c,docs):
    fields=['retailer','supplier_account','claim_ref','line_ref','invoice_ref','po_ref','sku','description','amount_cents','currency','claimed_qty','unit','deadline','deadline_source','notes']
    value={'case':{k:c[k] for k in fields},'documents':sorted([{'id':d['id'],'sha256':d['sha256'],'meta':d['meta'],'reviewed_by':d['reviewed_by'],'reviewed_at':d['reviewed_at']} for d in docs if d['confirmed']],key=lambda d:d['id'])}
    return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
