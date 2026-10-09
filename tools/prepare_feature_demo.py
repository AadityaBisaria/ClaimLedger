"""Generate clearly fictional examples. Does not import them or alter any workspace."""
import csv
import io
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.packets import pdf_bytes
from PIL import Image,ImageDraw,ImageFont

root=Path(__file__).resolve().parents[1]/'fixtures'/'multi-sku'
root.mkdir(exist_ok=True)
headers=['retailer','supplier_account','claim_ref','line_ref','invoice_ref','po_ref','sku','description','amount','currency','claimed_qty','unit']
with (root/'deductions.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.writer(f);w.writerow(headers)
    w.writerow(['Northfield Markets (fictional)','MULTI-DEMO','MULTI-2001','1','INV-MULTI-1','PO-MULTI-1','TEA-MULTI','Fictional tea','125','GBP','5','cases'])
    w.writerow(['Northfield Markets (fictional)','MULTI-DEMO','MULTI-2001','2','INV-MULTI-1','PO-MULTI-1','OAT-MULTI','Fictional oats','200','GBP','8','cases'])
for kind in ('invoice','dispatch','delivery'):
    paragraphs=['FICTIONAL DEMO ONLY - NOT A REAL TRANSACTION',f'Document type: {kind}','Invoice: INV-MULTI-1','PO: PO-MULTI-1',f'Qualification: {"full_count" if kind=="delivery" else "unspecified"}','SKU | Quantity | Unit','TEA-MULTI | 50 | cases','OAT-MULTI | 80 | cases','This synthetic document demonstrates separate SKU reviews on one shared original.']
    (root/(kind+'.pdf')).write_bytes(pdf_bytes('Multi-SKU '+kind,paragraphs))
image=Image.new('RGB',(1500,1050),'white');draw=ImageDraw.Draw(image);font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',38)
text='FICTIONAL DEMO ONLY\nDocument type: invoice\nInvoice: INV-MULTI-1\nPO: PO-MULTI-1\nSKU: TEA-MULTI\nQuantity: 50\nUnit: cases\nSKU: OAT-MULTI\nQuantity: 80\nUnit: cases'
draw.multiline_text((60,50),text,font=font,fill='black',spacing=18)
image.save(root/'scanned-invoice.png')
print('Created multi-SKU PDF, CSV and scanned-image fixtures.')
