import csv
import io
import json
import sqlite3
from datetime import date
from .store import now,uid
from .imports import FIELDS,REQUIRED,clean,money,iso,normalize,parse_file,suggestions
from .evidence import document,documents_for,upload,review,assess,fingerprint
from .packets import build

def list_cases(store,workspace):
    cases=store.list_claims(workspace)
    with store.connect() as db:
        for c in cases:
            c['assessment']=assess(c,documents_for(store,workspace,c['id'],db))
            c['overdue']=bool(c['deadline'] and c['deadline']<date.today().isoformat() and c['status'] in {'open','submitted'})
    return cases

def detail(store,workspace,case_id):
    with store.connect() as db:
        c=store.claim(workspace,case_id,db)
        docs=documents_for(store,workspace,case_id,db)
        events=[dict(r) for r in db.execute('SELECT * FROM events WHERE workspace=? AND claim_id=? ORDER BY id DESC',(workspace,case_id))]
        for e in events: e['detail']=json.loads(e['detail'])
        credits=[dict(r) for r in db.execute('SELECT * FROM credits WHERE workspace=? AND claim_id=? ORDER BY created_at DESC',(workspace,case_id))]
        exports=[dict(r) for r in db.execute('SELECT * FROM exports WHERE workspace=? AND claim_id=? ORDER BY created_at DESC,rowid DESC',(workspace,case_id))]
        fp=fingerprint(c,docs)
        for e in exports: e['current']=e['fingerprint']==fp
        c['credited_cents']=sum(r['amount_cents'] for r in credits if not r['voided_at'])
        return {'case':c,'documents':docs,'assessment':assess(c,docs),'events':events,'credits':credits,'exports':exports}

def insert_case(store,db,workspace,c,source):
    case_id=uid(); fields=list(c)
    db.execute('INSERT INTO claims(id,workspace,'+','.join(fields)+',source_json,created_at,updated_at) VALUES('+','.join('?' for _ in range(len(fields)+5))+')',
               [case_id,workspace]+[c[k] for k in fields]+[json.dumps(source),now(),now()])
    store.event(db,workspace,case_id,'Case created',source)
    return case_id

def import_rows(store,workspace,p,commit=False):
    headers,rows=parse_file(p)
    mapping=p.get('mapping') or suggestions(headers)
    if not isinstance(mapping,dict): raise ValueError('Invalid column mapping.')
    missing=REQUIRED-set(k for k,v in mapping.items() if v in headers)
    if missing: return {'headers':headers,'mapping':mapping,'fields':FIELDS,'required':sorted(REQUIRED),'sample':rows[0][1],'errors':['Map required columns: '+', '.join(sorted(missing))],'count':len(rows),'new_count':0,'duplicates':0,'preview':[]}
    prepared=[]; errors=[]; duplicates=0; seen={}
    with store.connect() as db:
        if commit: db.execute('BEGIN IMMEDIATE')
        for line,raw in rows:
            try:
                c=normalize({k:raw.get(mapping.get(k,''),'') for k in FIELDS})
                key=tuple(c[k] for k in ('retailer','supplier_account','claim_ref','line_ref'))
                prior=seen.get(key)
                old=db.execute('SELECT * FROM claims WHERE workspace=? AND retailer=? AND supplier_account=? AND claim_ref=? AND line_ref=?',(workspace,*key)).fetchone()
                previous=prior or (dict(old) if old else None)
                if previous:
                    keys=('amount_cents','currency','invoice_ref','po_ref','sku','claimed_qty','unit')
                    if any(previous[k]!=c[k] for k in keys): raise ValueError('Existing deduction identity has different financial or shipment fields; review it instead of importing again.')
                    duplicates+=1
                else:
                    prepared.append((c,{'filename':clean(p['filename'],200),'row':line,'original':raw})); seen[key]=c
            except ValueError as exc: errors.append(f'Row {line}: {exc}')
        if commit:
            if errors: raise ValueError('Import cancelled. '+errors[0])
            for c,source in prepared: insert_case(store,db,workspace,c,source)
    return {'headers':headers,'mapping':mapping,'fields':FIELDS,'required':sorted(REQUIRED),'sample':rows[0][1],'errors':errors[:100],'count':len(rows),'new_count':len(prepared),'duplicates':duplicates,'preview':[c for c,s in prepared[:8]],'committed':commit}

def mutate_case(store,workspace,case_id,action,p):
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        c=store.claim(workspace,case_id,db)
        if int(p.get('version',0))!=c['version']: raise ValueError('This case changed. Reopen it before saving.')
        credited=db.execute("SELECT COALESCE(SUM(amount_cents),0) FROM credits WHERE claim_id=? AND voided_at=''",(case_id,)).fetchone()[0]
        changes={}
        if action=='edit':
            if c['status']!='open': raise ValueError('Financial and shipment fields are locked after submission or closure.')
            changes=normalize(p)
        elif action=='followup':
            changes={'followup_date':iso(p.get('followup_date','')),'owner':clean(p.get('owner',''),100),'notes':clean(p.get('notes',''))}
        elif action=='submit':
            if c['status']!='open': raise ValueError('Only an open case can be submitted.')
            docs=documents_for(store,workspace,case_id,db)
            fp=fingerprint(c,docs)
            packet=db.execute("SELECT 1 FROM exports WHERE claim_id=? AND kind='final' AND fingerprint=?",(case_id,fp)).fetchone()
            if not packet or assess(c,docs)['readiness']!='ready': raise ValueError('Generate a current reviewed packet before recording submission.')
            ref=clean(p.get('submission_ref',''),200)
            if not ref: raise ValueError('Enter the retailer submission reference.')
            submitted=iso(p.get('submitted_at',''))
            if not submitted or submitted>date.today().isoformat(): raise ValueError('Enter the actual submission date, not a future date.')
            changes={'status':'submitted','submission_ref':ref,'submitted_at':submitted,'disputed_cents':c['amount_cents'],'followup_date':iso(p.get('followup_date',''))}
        elif action=='decision':
            decision=p.get('decision')
            source=clean(p.get('source',''),500)
            if not source: raise ValueError('Record the retailer response or decision reference.')
            if decision=='accepted':
                if c['status']!='open' or credited: raise ValueError('Only an open deduction can be accepted.')
                changes={'status':'accepted','approved_cents':0}
            elif decision in {'approved','rejected'}:
                if c['status']!='submitted': raise ValueError('Record submission before the retailer decision.')
                amt=money(p.get('amount','0'),True) if decision=='approved' else 0
                if decision=='approved' and amt==0: raise ValueError('An approval must have a positive amount.')
                if amt>c['disputed_cents'] or amt<credited: raise ValueError('Approval must not exceed the disputed amount or fall below credits.')
                changes={'status':decision,'approved_cents':amt}
            else: raise ValueError('Choose approved, rejected or accepted.')
            store.event(db,workspace,case_id,'Decision source',{'source':source})
        elif action=='credit':
            if c['status']!='approved': raise ValueError('Record an approval before allocating credits.')
            amt=money(p.get('amount',''))
            if amt>c['approved_cents']-credited: raise ValueError('Credit exceeds the remaining approved amount.')
            if p.get('currency')!=c['currency']: raise ValueError('Credit currency must match the case.')
            ref=clean(p.get('credit_ref',''),150); source=clean(p.get('source',''),500); when=iso(p.get('credit_date',''))
            if not ref or not source or not when or when>date.today().isoformat(): raise ValueError('Enter a unique credit reference, source and actual credit date.')
            if p.get('verified') is not True: raise ValueError('Confirm the credit against the retailer record.')
            try:
                db.execute('INSERT INTO credits(id,workspace,claim_id,credit_ref,amount_cents,currency,credit_date,source,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(uid(),workspace,case_id,ref,amt,c['currency'],when,source,now()))
            except sqlite3.IntegrityError: raise ValueError('This credit reference is already allocated in this workspace.')
            changes={'status':'credited' if amt+credited==c['approved_cents'] else 'approved'}
            store.event(db,workspace,case_id,'Credit recorded',{'reference':ref,'amount_cents':amt,'currency':c['currency'],'source':source})
        else: raise ValueError('Unknown case action.')
        before={k:c[k] for k in changes}
        changes.update(updated_at=now(),version=c['version']+1)
        try: db.execute('UPDATE claims SET '+','.join(k+'=?' for k in changes)+' WHERE id=?',[*changes.values(),case_id])
        except sqlite3.IntegrityError: raise ValueError('A case with this deduction identity already exists.')
        store.event(db,workspace,case_id,'Case '+action,{'before':before,'after':changes})
    return {'saved':True}

def export_packet(store,workspace,case_id,p):
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        c=store.claim(workspace,case_id,db); docs=documents_for(store,workspace,case_id,db); a=assess(c,docs)
        kind=p.get('kind','draft'); reviewer=clean(p.get('reviewer',''),100)
        if kind not in {'draft','final'}: raise ValueError('Unknown packet type.')
        if kind=='final' and (a['readiness']!='ready' or not reviewer or p.get('verified') is not True): raise ValueError('Complete evidence checks and confirm review before exporting a final packet.')
        if c['status'] not in {'open','submitted'}: raise ValueError('This case is closed for dispute preparation.')
        pdf,zipdata=build(store,c,docs,a,kind,reviewer)
        export_id=uid()
        (store.root/'exports'/(export_id+'.pdf')).write_bytes(pdf)
        (store.root/'exports'/(export_id+'.zip')).write_bytes(zipdata)
        db.execute('INSERT INTO exports VALUES(?,?,?,?,?,?,?)',(export_id,workspace,case_id,fingerprint(c,docs),kind,reviewer,now()))
        store.event(db,workspace,case_id,'Packet generated',{'kind':kind,'reviewer':reviewer,'export_id':export_id})
    return {'id':export_id}

def file_response(data,mime,filename,inline=False):
    safe=''.join(c if c.isascii() and (c.isalnum() or c in '.-_ ') else '_' for c in filename)
    return 200,data,mime,{'Content-Disposition':('inline' if inline else 'attachment')+'; filename="'+safe+'"'}

def reverse_credit(store,w,credit_id,p):
    reason=clean(p.get('reason',''),500)
    if not reason or p.get('verified') is not True: raise ValueError('Enter a correction reason and confirm reversal of this local record.')
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        credit=db.execute('SELECT * FROM credits WHERE id=? AND workspace=?',(credit_id,w)).fetchone()
        if not credit: raise ValueError('Credit not found in this workspace.')
        if credit['voided_at']: raise ValueError('This credit is already reversed.')
        c=store.claim(w,credit['claim_id'],db)
        db.execute('UPDATE credits SET voided_at=?,void_reason=? WHERE id=?',(now(),reason,credit_id))
        db.execute("UPDATE claims SET status='approved',version=version+1,updated_at=? WHERE id=?",(now(),c['id']))
        store.event(db,w,c['id'],'Credit reversed',{'reference':credit['credit_ref'],'amount_cents':credit['amount_cents'],'reason':reason,'note':'Local record correction only; no financial transaction was sent.'})
    return {'saved':True}

def route(store,w,method,path,p,q):
    parts=path.strip('/').split('/')
    if len(parts)==4 and parts[1]=='credits' and parts[3]=='reverse' and method=='POST': return reverse_credit(store,w,parts[2],p)
    if path=='/api/import/preview' and method=='POST': return import_rows(store,w,p)
    if path=='/api/import/commit' and method=='POST': return import_rows(store,w,p,True)
    if path=='/api/template' and method=='GET':
        out=io.StringIO(); writer=csv.writer(out); writer.writerow(FIELDS)
        writer.writerow(['Example retailer','ACCOUNT-1','DED-001','1','INV-001','PO-001','SKU-1','Sample product','240.00','GBP','10','cases',date.today().isoformat(),'','','','',''][:len(FIELDS)])
        return file_response(out.getvalue().encode(),'text/csv','deduction-template.csv')
    if path=='/api/cases' and method=='POST':
        c=normalize(p)
        try:
            with store.connect() as db: case_id=insert_case(store,db,w,c,{'source':'Manual entry'})
        except sqlite3.IntegrityError: raise ValueError('A case with this deduction identity already exists.')
        return {'id':case_id}
    if len(parts)==3 and parts[1]=='cases' and method=='GET': return detail(store,w,parts[2])
    if len(parts)==4 and parts[1]=='cases' and method=='POST':
        if parts[3]=='export': return export_packet(store,w,parts[2],p)
        return mutate_case(store,w,parts[2],parts[3],p)
    if path=='/api/documents' and method=='GET':
        with store.connect() as db: return {'documents':[document(store,w,r['id'],db) for r in db.execute('SELECT id FROM documents WHERE workspace=? ORDER BY created_at DESC',(w,))]}
    if path=='/api/documents' and method=='POST': return upload(store,w,p)
    if path=='/api/documents/matches' and method=='GET':
        from .extraction import suggest_matches
        with store.connect() as db:
            claims=[dict(r) for r in db.execute('SELECT * FROM claims WHERE workspace=?',(w,))]
            out=[]
            for r in db.execute('SELECT id FROM documents WHERE workspace=?',(w,)):
                d=document(store,w,r['id'],db)
                for m in suggest_matches(claims,d['candidates'],d['meta']):
                    prior=next((x for x in d['mappings'] if x['case_id']==m['case_id']),None)
                    if not prior or not prior['confirmed']:out.append({**m,'document_id':d['id'],'filename':d['filename']})
        return {'matches':out}
    if len(parts)>=3 and parts[1]=='documents':
        with store.connect() as db: d=document(store,w,parts[2],db)
        if len(parts)==3 and method=='GET': return d
        if len(parts)==4 and parts[3]=='ocr' and method=='POST':
            from .ocr import run
            return run(store,w,d['id'],p)
        if len(parts)==4 and parts[3]=='preview' and method=='GET':
            if d['mime']!='application/pdf': raise ValueError('Page previews require a PDF.')
            from .preview import render_page
            return file_response(render_page(store.root/'files'/d['id'],int(q.get('page',['1'])[0])),'image/png','source-page.png',True)
        if len(parts)==4 and parts[3]=='file' and method=='GET': return file_response((store.root/'files'/d['id']).read_bytes(),d['mime'],d['filename'],True)
        if len(parts)==4 and parts[3]=='review' and method=='POST': return review(store,w,d['id'],p)
        if len(parts)==4 and parts[3]=='unlink' and method=='POST':
            with store.connect() as db:
                c=store.claim(w,p.get('case_id'),db)
                db.execute('DELETE FROM links WHERE claim_id=? AND document_id=?',(c['id'],d['id']))
                store.event(db,w,c['id'],'Evidence unlinked',{'filename':d['filename']})
            return {'saved':True}
    if len(parts)==4 and parts[1]=='exports' and method=='GET' and parts[3] in {'pdf','zip'}:
        with store.connect() as db:
            r=db.execute('SELECT * FROM exports WHERE id=? AND workspace=?',(parts[2],w)).fetchone()
            if not r: raise ValueError('Export not found in this workspace.')
        ext=parts[3]
        return file_response((store.root/'exports'/(r['id']+'.'+ext)).read_bytes(),'application/pdf' if ext=='pdf' else 'application/zip','claimledger-'+r['kind']+'.'+ext)
    if path=='/api/credits' and method=='GET':
        with store.connect() as db: return {'credits':[dict(r) for r in db.execute('SELECT cr.*,c.claim_ref,c.retailer FROM credits cr JOIN claims c ON c.id=cr.claim_id WHERE cr.workspace=? ORDER BY cr.credit_date DESC',(w,))]}
    raise ValueError('Unknown operation.')
