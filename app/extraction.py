"""Unverified field suggestions with explicit page/span provenance."""
import re

LABELS={'invoice_ref':'Invoice','po_ref':'PO','sku':'SKU','quantity':'Quantity','unit':'Unit','doc_type':'Document type','qualification':'Qualification'}

def candidates(pages):
    output=[]
    for page in pages:
        spans=page['spans']; text='\n'.join(s['text'] for s in spans)
        header={}
        for key in ('invoice_ref','po_ref','doc_type','qualification'):
            m=re.search(r'^'+LABELS[key]+r':\s*([^\r\n]+)',text,re.I|re.M)
            if m:header[key]=m.group(1).strip()
        def candidate(values,indices):
            source=[spans[i] for i in indices]
            confidence=min((s.get('confidence',1) for s in source),default=1)
            output.append({'fields':{**header,**values},'page':page['page'],'method':page['method'],'confidence':round(confidence,3),'needs_review':True,'span_ids':[s['id'] for s in source]})
        # Labelled SKU blocks, including repeated SKU/quantity sections.
        active=None; indices=[]
        for i,s in enumerate(spans):
            m=re.match(r'^SKU:\s*(.+)$',s['text'],re.I)
            if m:
                if active:candidate(active,indices)
                active={'sku':m.group(1).strip()};indices=[i];continue
            if active:
                for key in ('quantity','unit'):
                    m=re.match('^'+LABELS[key]+r':\s*(.+)$',s['text'],re.I)
                    if m:active[key]=m.group(1).strip();indices.append(i)
        if active:candidate(active,indices)
        # Delimited rows. Do not infer unknown table layouts or quantities.
        for i,s in enumerate(spans):
            m=re.fullmatch(r'\s*([\w./-]+)\s*[|,;]\s*(\d+(?:\.\d{1,4})?)\s*[|,;]\s*(cases|units|kg|pallets)\s*',s['text'],re.I)
            if m:candidate({'sku':m[1],'quantity':m[2],'unit':m[3].lower()},[i])
        if not any(c['page']==page['page'] for c in output) and header:candidate(header,list(range(min(len(spans),15))))
    return output

def native_pages(text):
    pages=[]
    chunks=re.split(r'--- Page (\d+) ---\n',text)
    pairs=[(int(chunks[i]),chunks[i+1]) for i in range(1,len(chunks)-1,2)] if len(chunks)>1 else [(1,text)]
    for number,content in pairs:
        spans=[{'id':f'{number}:{i}','text':line.strip(),'confidence':1.0,'bbox':None} for i,line in enumerate(content.splitlines()) if line.strip()]
        if spans:pages.append({'page':number,'method':'native_text','spans':spans})
    return pages

def suggest_matches(claims,rows,meta):
    out=[]
    for c in claims:
        for row in rows or [{'fields':meta,'page':1,'confidence':1,'span_ids':[],'method':'native_text'}]:
            f=row['fields'];matched=[k for k in ('invoice_ref','po_ref','sku') if f.get(k) and f[k]==c[k]]
            conflicts=[k for k in ('invoice_ref','po_ref','sku') if f.get(k) and c[k] and f[k]!=c[k]]
            if any(k in matched for k in ('invoice_ref','po_ref')) and not conflicts:
                out.append({'case_id':c['id'],'claim_ref':c['claim_ref'],'line_ref':c['line_ref'],'sku':c['sku'],'matched':matched,'candidate':row,'reason':'Exact '+', '.join(matched)+' match; review required'})
    return out
