"""Local OCR. Bundled models run without document transmission or network calls."""
import io
import json
import threading
from PIL import Image
from .store import now
from .extraction import candidates,suggest_matches

OCR_LOCK=threading.Lock()
ENGINE=None

def recognize(image_bytes):
    global ENGINE
    with OCR_LOCK:
        from rapidocr_onnxruntime import RapidOCR
        if ENGINE is None:ENGINE=RapidOCR(intra_op_num_threads=2,inter_op_num_threads=1)
        with Image.open(io.BytesIO(image_bytes)) as im:
            if im.width*im.height>24_000_000:raise ValueError('Image is too large for OCR (maximum 24 megapixels).')
            image=im.convert('RGB')
            try:result,_=ENGINE(image)
            finally:image.close()
        return result or []

def run(store,workspace,doc_id,p):
    from .evidence import document
    from .preview import render_page
    with store.connect() as db:d=document(store,workspace,doc_id,db)
    number=int(p.get('page',1))
    if not 1<=number<=d['pages']:raise ValueError('Choose a page within the document.')
    path=store.root/'files'/doc_id
    if d['mime']=='application/pdf':data=render_page(path,number)
    elif d['mime'] in {'image/png','image/jpeg'}:data=path.read_bytes()
    else:raise ValueError('OCR requires a PDF or image.')
    result=recognize(data)
    spans=[]
    with Image.open(io.BytesIO(data)) as im:width,height=im.size
    for i,(box,text,score) in enumerate(result):
        xs=[float(x[0])/width for x in box];ys=[float(x[1])/height for x in box]
        spans.append({'id':f'{number}:{i}','text':str(text),'confidence':float(score),'bbox':[max(0,min(xs)),max(0,min(ys)),min(1,max(xs)),min(1,max(ys))]})
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        document(store,workspace,doc_id,db)
        db.execute('INSERT OR REPLACE INTO extraction_pages VALUES(?,?,?,?,?)',(doc_id,number,'local_ocr',json.dumps(spans),now()))
        db.execute("UPDATE documents SET extraction_status='ocr_suggestions' WHERE id=?",(doc_id,))
        d=document(store,workspace,doc_id,db)
        claims=[dict(r) for r in db.execute('SELECT * FROM claims WHERE workspace=?',(workspace,))]
        matches=suggest_matches(claims,d['candidates'],d['meta'])
        for m in matches:db.execute('INSERT OR IGNORE INTO links(claim_id,document_id,confirmed,reason) VALUES(?,?,0,?)',(m['case_id'],doc_id,m['reason']))
        store.event(db,workspace,None,'Local OCR completed',{'document_id':doc_id,'page':number,'spans':len(spans),'note':'Unverified suggestions only; confirmed evidence unchanged.'})
    return {'page':number,'spans':spans,'candidates':d['candidates'],'matches':matches,'empty':not bool(spans)}
