import hashlib
import io
import json
import zipfile
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from .store import now

def pdf_bytes(title, paragraphs):
    output=io.BytesIO(); styles=getSampleStyleSheet()
    styles['Title'].textColor=colors.HexColor('#123d37')
    styles['BodyText'].leading=15
    story=[Paragraph(escape(title),styles['Title']),Spacer(1,16)]
    for text in paragraphs:
        story += [Paragraph(escape(str(text)).replace('\n','<br/>'),styles['BodyText']),Spacer(1,10)]
    def footer(canvas,doc):
        canvas.setFont('Helvetica',8); canvas.setFillColor(colors.HexColor('#66756e'))
        canvas.drawString(42,28,'ClaimLedger | Customer-reviewed evidence | '+str(doc.page))
    SimpleDocTemplate(output,pagesize=(595,842),rightMargin=42,leftMargin=42,topMargin=42,bottomMargin=48).build(story,onFirstPage=footer,onLaterPages=footer)
    return output.getvalue()

def build(store,c,docs,assessment,kind,reviewer):
    included=[d for d in docs if d['confirmed']]
    label='REVIEWED DISPUTE PACKET' if kind=='final' else 'DRAFT - NOT READY FOR SUBMISSION'
    paragraphs=[('FICTIONAL DEMO DATA. ' if c['workspace']=='demo' else '')+label,
      f"Retailer: {c['retailer']} | Supplier account: {c['supplier_account'] or 'Not supplied'}",
      f"Deduction: {c['claim_ref']} / line {c['line_ref']} | Invoice: {c['invoice_ref']} | PO: {c['po_ref']}",
      f"SKU: {c['sku']} | {c['description']}",
      f"Requested reversal: {c['currency']} {c['amount_cents']/100:.2f}. Alleged shortage: {c['claimed_qty'] or 'Not supplied'} {c['unit']}.",
      'Request: Please review this shortage deduction against the attached records and advise whether a credit can be issued. This packet records the supplier\'s evidence; it does not determine liability or confirm retailer acceptance.',
      f"Deadline entered by operator: {c['deadline'] or 'Unconfirmed'}. Source: {c['deadline_source'] or 'Not supplied; check the applicable retailer procedure.'}",
      f"Reviewed by: {reviewer or 'Not reviewed'} | Generated: {now()}",
      'EVIDENCE CHECKS']
    paragraphs += [('PASS' if x['passed'] else 'REVIEW NEEDED')+' - '+x['label']+': '+x['detail'] for x in assessment['checks']]
    paragraphs += ['CONFIRMED DOCUMENT INDEX']
    manifest=[]
    for i,d in enumerate(included,1):
        m=d['meta']; name=f"evidence/{i:02d}-{d['filename']}"
        paragraphs += [f"{i}. {d['filename']} | type: {m.get('doc_type','unclassified')} | source page: {m.get('page','unconfirmed')}\nQuantity: {m.get('quantity','not entered')} {m.get('unit','')} | delivery qualification: {m.get('qualification','unspecified')}\nReviewed by {d['reviewed_by'] or 'unreviewed'} at {d['reviewed_at'] or 'not recorded'}\nSHA-256: {d['sha256']}"]
        manifest.append({'path':name,'sha256':d['sha256'],'fields':m,'reviewed_by':d['reviewed_by'],'reviewed_at':d['reviewed_at']})
        if m.get('source_snippets'):
            paragraphs.append('Source extraction snapshot ('+m.get('source_method','manual')+'): '+ ' / '.join(s['text'] for s in m['source_snippets'])+'. Extracted text was used as a suggestion; the operator reviewed the stated fields against the original.')
    if c['notes']: paragraphs += ['OPERATOR NOTES',c['notes']]
    paragraphs += ['Scope: Single SKU, single shipment, full-delivery shortage dispute. Confirm the retailer\'s required forms, deadlines and submission channel before submitting. Approval and actual credits are tracked separately.']
    pdf=pdf_bytes('Deduction '+c['claim_ref'],paragraphs)
    zbuf=io.BytesIO()
    with zipfile.ZipFile(zbuf,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('dispute-summary.pdf',pdf)
        z.writestr('manifest.json',json.dumps({'case':c,'assessment':assessment,'kind':kind,'reviewer':reviewer,'documents':manifest},indent=2))
        z.writestr('READ-ME.txt','Review the summary and originals. Submit through the retailer-approved channel. No submission has been sent by ClaimLedger.\n')
        for entry,d in zip(manifest,included): z.write(store.root/'files'/d['id'],entry['path'])
    return pdf,zbuf.getvalue()
