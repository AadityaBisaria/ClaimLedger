export function createEvidenceUI(h) {
  const {$,esc,S,api,url,modal,form,field,select,checked,bindForm,btn,head,toast,refresh,filePayload,label}=h;
  async function matches(){return (await api('documents/matches')).matches;}

  function uploadDialog(caseId='') {
    modal('Bulk upload evidence','Select up to 50 originals · PDF, PNG, JPEG or TXT · 10 MB per file.',form(`
      <div class="dropzone field full"><label for="upload-file">Choose documents</label>
      <input id="upload-file" type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.txt" required>
      <p>Originals stay unchanged. Each file is saved independently; failures do not discard successful uploads.</p></div>
      <label class="check-label field full"><input id="ocr-upload" type="checkbox">Run local OCR on image files and the first page of scans after upload.</label>
      <p id="upload-progress" class="metadata field full" role="status"></p>`,'Upload documents'));
    bindForm(async()=>{
      const files=[...$('#upload-file').files], useOCR=$('#ocr-upload').checked;
      if(files.length>50||files.reduce((n,f)=>n+f.size,0)>100*1024*1024)throw Error('Choose at most 50 files totalling no more than 100 MB.');
      const progress=$('#upload-progress'),results=[];
      $('#upload-file').disabled=true;$('#modal .close').disabled=true;
      const lockClose=e=>e.preventDefault();$('#modal').addEventListener('cancel',lockClose);
      try {
        for(let i=0;i<files.length;i++){
          progress.textContent=`Saving ${i+1}/${files.length}: ${files[i].name}`;
          try{
            const r=await api('documents',{...await filePayload(files[i]),case_id:caseId});
            let ocr='';
            if(useOCR){const d=await api(`documents/${r.id}`);if(d.extraction_status==='manual_review'){
              progress.textContent=`Reading ${files[i].name} locally…`;
              try{const o=await api(`documents/${r.id}/ocr`,{page:1});ocr=o.empty?'No text detected':'OCR suggestions ready';}catch(e){ocr=`Saved; OCR failed: ${e.message}`;}
            }}
            results.push({filename:files[i].name,id:r.id,ok:true,duplicate:r.duplicate,ocr,matches:r.matches.length});
          }catch(e){results.push({filename:files[i].name,ok:false,error:e.message});}
        }
      }finally{$('#modal').removeEventListener('cancel',lockClose);if($('#modal .close'))$('#modal .close').disabled=false;}
      await refresh();
      modal('Upload results','Review the suggested matches before confirming evidence.',`<div class="modal-body">
        ${results.map(r=>`<div class="evidence-card"><div><strong>${esc(r.filename)}</strong><span class="secondary">${r.ok?(r.duplicate?'Already saved':'Saved')+' · '+esc(r.ocr||`${r.matches} suggested match(es)`):esc(r.error)}</span></div>${r.ok?`<button class="btn small" data-result="${r.id}">Review</button>`:'<span class="pill danger">Failed</span>'}</div>`).join('')}
        <div class="notice">Uploads and OCR never confirm evidence automatically. For multi-page scans, run OCR on each relevant source page in the review screen.</div>
        <button id="review-matches" class="btn primary">Review suggested matches</button></div>`);
      document.querySelectorAll('[data-result]').forEach(b=>b.onclick=()=>reviewDocument(b.dataset.result,caseId).catch(e=>toast(e.message)));
      $('#review-matches').onclick=()=>matchQueue().catch(e=>toast(e.message));
    });
  }

  async function matchQueue(){
    const rows=await matches();
    modal('Suggested evidence matches',`${rows.length} unconfirmed suggestions. Exact references only; no automatic approvals.`,
      `<div class="modal-body">${rows.length?rows.map((r,i)=>`<div class="evidence-card"><div><strong>${esc(r.filename)}</strong><span class="secondary">${esc(r.claim_ref)} / ${esc(r.line_ref)} · ${esc(r.sku)} · page ${r.candidate.page}</span><span class="secondary">${esc(r.reason)}</span></div><button class="btn small" data-match="${i}">Review line</button></div>`).join(''):'<div class="notice">No unconfirmed exact matches. Upload evidence, run OCR where needed, or link an original manually.</div>'}</div>`,'',true);
    document.querySelectorAll('[data-match]').forEach(b=>b.onclick=()=>{const r=rows[Number(b.dataset.match)];reviewDocument(r.document_id,r.case_id,true).catch(e=>toast(e.message));});
  }

  async function reviewDocument(id,caseId='',next=false,targetPage=null) {
    const d=await api(`documents/${id}`);
    const existing=d.mappings.find(m=>m.case_id===caseId);
    const c=S.cases.find(c=>c.id===caseId);
    const candidate=d.candidates.find(r=>r.fields.sku===c?.sku&&(!r.fields.invoice_ref||r.fields.invoice_ref===c.invoice_ref));
    const m=existing?.confirmed?existing.meta:{...d.meta,...candidate?.fields,page:candidate?.page||1};
    if(targetPage)m.page=targetPage;
    let sourceIds=existing?.confirmed?(m.source_span_ids||[]):(candidate?.span_ids||[]);
    let mappingVersion=existing?.reviewed_at||'';
    const src=url(`documents/${id}/file`);
    const preview=d.mime==='application/pdf'?`<div class="source-page"><img id="pdf-page" src="${url(`documents/${id}/preview?page=${m.page||1}`)}" alt="Original PDF source page"><svg id="source-overlay" viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-hidden="true"></svg></div>`:d.mime.startsWith('image/')?`<div class="source-page"><img src="${src}" alt="Original source image"><svg id="source-overlay" viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-hidden="true"></svg></div>`:`<pre>${esc(d.extracted_text)}</pre>`;
    modal('Review a case line',d.filename,`<form id="form"><div class="modal-body"><div class="preview-layout">
      <div><div class="document-preview">${preview}</div><a class="btn small" href="${src}" target="_blank" rel="noopener">Open original</a>
      <div class="source-controls">${d.mime==='application/pdf'||d.mime.startsWith('image/')?'<button class="btn small" id="run-ocr" type="button">Read this page with OCR</button>':''}<span id="ocr-progress" class="metadata" role="status"></span></div>
      <div id="source-lines"></div><p class="metadata">Original SHA-256: ${esc(d.sha256)}</p></div>
      <div><div class="notice">Review is saved only for the selected deduction line. Other SKUs sharing this original retain their own evidence.</div>
      <div class="field"><label for="candidate">Extracted line suggestion</label><select id="candidate"><option value="">Keep entered fields</option>${d.candidates.map((r,i)=>`<option value="${i}" ${r===candidate&&!existing?.confirmed?'selected':''}>Page ${r.page} · ${esc(r.fields.sku||'Header')} · ${esc(r.fields.quantity||'?')} ${esc(r.fields.unit||'')} · ${r.method==='local_ocr'?Math.round(r.confidence*100)+'% model score':'Text layer'}</option>`).join('')}</select><small>Model score is not a guarantee. Every suggestion needs review.</small></div>
      <div class="form-grid">${select('case_id','Deduction line',[['','Choose a case line'],...S.cases.map(c=>[c.id,`${c.claim_ref} / ${c.line_ref} · ${c.sku||'SKU missing'}`])],caseId,true)+select('doc_type','Document type',[['','Choose type'],'invoice','dispatch','delivery','correspondence','other'],m.doc_type||'',true)+field('invoice_ref','Invoice reference',m.invoice_ref)+field('po_ref','Purchase order',m.po_ref)+field('sku','SKU for this case line',m.sku)+field('quantity','Quantity for this SKU',m.quantity)+select('unit','Quantity unit',[['','Not applicable'],'cases','units','kg','pallets'],m.unit||'')+field('page','Source page',m.page||1,'number',true)+select('qualification','Delivery qualification',[['unspecified','Not established / not applicable'],['full_count','SKU quantity explicitly confirmed'],['subject_to_count','Subject to count'],['pallets_only','Pallet count only'],['short_noted','Shortage noted']],m.qualification||'unspecified')+field('reviewer','Reviewer name',existing?.reviewed_by||d.reviewed_by,'text',true)+field('notes','Evidence notes',m.notes,'textarea')+checked('I checked this SKU, quantity, unit and source page against the original. Delivery qualification reflects the actual receipt.')}</div>
      <p id="form-error" class="inline-error" role="alert"></p></div></div></div><div class="modal-footer"><button class="btn primary" type="submit">${next?'Confirm & review next match':'Save this line review'}</button></div></form>`,'',true);
    const paintSources=()=>{
      const pg=d.extraction_pages.find(p=>p.page===Number($('#f-page').value));
      $('#source-lines').innerHTML=`<h3>Source text · page ${esc($('#f-page').value)}</h3>${pg?`<p class="metadata">${pg.method==='local_ocr'?'Local OCR — unverified. Select a line to highlight its position.':'PDF/text layer — unverified. Inspect the referenced page to verify the text.'}</p><div class="span-list">${pg.spans.map((s,i)=>`<button type="button" class="span-line ${s.confidence<.9?'uncertain':''}" data-span="${i}">${esc(s.text)}${pg.method==='local_ocr'?`<small>${Math.round(s.confidence*100)}% model score</small>`:''}</button>`).join('')}</div>`:'<p class="metadata">No extracted text on this page. Run OCR or inspect the original manually.</p>'}`;
      if($('#source-overlay'))$('#source-overlay').innerHTML='';
      document.querySelectorAll('[data-span]').forEach(b=>b.onclick=()=>{
        const s=pg.spans[Number(b.dataset.span)];
        document.querySelectorAll('[data-span]').forEach(e=>e.classList.toggle('selected',e===b));
        if(s.bbox&&$('#source-overlay')){const [x,y,x2,y2]=s.bbox;$('#source-overlay').innerHTML=`<rect x="${x*1000}" y="${y*1000}" width="${(x2-x)*1000}" height="${(y2-y)*1000}" class="ocr-box"/>`;}
      });
    };
    const pageChanged=()=>{const p=Number($('#f-page').value);if(Number.isInteger(p)&&p>=1&&p<=d.pages){if(sourceIds.some(id=>!id.startsWith(p+':')))sourceIds=[];if($('#pdf-page'))$('#pdf-page').src=url(`documents/${id}/preview?page=${p}`);paintSources();}else $('#form-error').textContent=`Choose a page from 1 to ${d.pages}.`;};
    $('#f-page').addEventListener('change',pageChanged);
    $('#candidate').onchange=e=>{const r=d.candidates[Number(e.target.value)];if(e.target.value!==''&&r){for(const [k,v] of Object.entries(r.fields))if($('#f-'+k))$('#f-'+k).value=v;$('#f-page').value=r.page;sourceIds=r.span_ids;$('#form input[name=verified]').checked=false;pageChanged();}};
    $('#f-case_id').onchange=async e=>{if(e.target.value)await reviewDocument(id,e.target.value,next);};
    if($('#run-ocr'))$('#run-ocr').onclick=async e=>{
      e.target.disabled=true;$('#ocr-progress').textContent='Reading this page locally…';
      try{const p=Number($('#f-page').value);const r=await api(`documents/${id}/ocr`,{page:p});await reviewDocument(id,$('#f-case_id').value,next,p);toast(r.empty?'No readable text detected. Manual review is available.':'OCR suggestions ready. Verify before confirming.');}
      catch(err){$('#ocr-progress').textContent=err.message;e.target.disabled=false;}
    };
    paintSources();
    bindForm(async p=>{await api(`documents/${id}/review`,{...p,verified:p.verified==='on',mapping_version:mappingVersion,source_span_ids:sourceIds});$('#modal').close();await refresh();if(next)await matchQueue();else toast('This case line saved. Other line reviews unchanged.');});
  }

  async function library(){
    const docs=(await api('documents')).documents, suggestions=await matches();
    $('#content').innerHTML=head('SOURCE RECORDS','Evidence library','Share originals across SKUs. Keep each line’s review independent.',btn(`Suggested matches (${suggestions.length})`,'matches')+btn('+ Bulk upload','upload',true))+`<div class="surface"><div class="table-scroll"><table><thead><tr><th>ORIGINAL</th><th>EXTRACTED LINES</th><th>CASE REVIEWS</th><th></th></tr></thead><tbody>${docs.length?docs.map(d=>`<tr><td>${esc(d.filename)}<span class="secondary">${d.pages} page(s) · ${Math.ceil(d.size/1024)} KB</span></td><td>${d.candidates.length}<span class="secondary">${esc(label(d.extraction_status))}</span></td><td>${d.mappings.filter(m=>m.confirmed).length} confirmed line(s)</td><td><button class="btn small" data-doc="${d.id}">Review line</button></td></tr>`).join(''):'<tr><td colspan="4"><div class="empty"><h2>No documents yet</h2><p>Upload invoices, dispatch records and delivery receipts together.</p></div></td></tr>'}</tbody></table></div></div>`;
    $('#upload').onclick=()=>uploadDialog();$('#matches').onclick=()=>matchQueue().catch(e=>toast(e.message));
    document.querySelectorAll('[data-doc]').forEach(b=>b.onclick=()=>reviewDocument(b.dataset.doc).catch(e=>toast(e.message)));
  }
  return {uploadDialog,reviewDocument,library,matchQueue};
}
