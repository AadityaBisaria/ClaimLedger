"""Strict, atomic-friendly import normalization. Money never passes through float."""
import base64
import csv
import io
import re
import zipfile
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

FIELDS = ['retailer','supplier_account','claim_ref','line_ref','invoice_ref','po_ref','sku','description','amount','currency','claimed_qty','unit','claim_date','deadline','deadline_source','owner','notes']
REQUIRED = {'retailer','claim_ref','amount','currency'}

def clean(value, maximum=2000):
    value = str(value if value is not None else '').strip()
    if len(value)>maximum or any(ord(c)<32 and c not in '\n\t\r' for c in value):
        raise ValueError('Text is too long or contains control characters.')
    return value

def money(value, allow_zero=False):
    text=clean(value,30)
    if not re.fullmatch(r'\d+(?:\.\d{1,2})?',text):
        raise ValueError('Amounts must be positive numbers with at most two decimals (e.g. 240.50).')
    result=int(Decimal(text)*100)
    if result>100_000_000_00 or (result==0 and not allow_zero):
        raise ValueError('Amount is outside the supported range.')
    return result

def quantity(value):
    text=clean(value,30)
    if text and (not re.fullmatch(r'\d+(?:\.\d{1,4})?',text) or Decimal(text)>100000000):
        raise ValueError('Quantity must be a nonnegative number, up to four decimals.')
    return text

def iso(value):
    text=clean(value,10)
    if text:
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',text): raise ValueError('Dates must use YYYY-MM-DD.')
        date.fromisoformat(text)
    return text

def normalize(row):
    c={k:clean(row.get(k,'')) for k in FIELDS if k!='amount'}
    for key in REQUIRED-{'amount'}:
        if not c[key]: raise ValueError(f'{key.replace("_"," ").title()} is required.')
    c['currency']=c['currency'].upper()
    if c['currency'] not in {'GBP','CAD','USD','EUR'}: raise ValueError('Currency must be GBP, CAD, USD or EUR.')
    c['amount_cents']=money(row.get('amount',''))
    c['line_ref']=c['line_ref'] or '1'
    c['unit']=c['unit'].lower() or 'cases'
    if c['unit'] not in {'cases','units','kg','pallets'}: raise ValueError('Unit must be cases, units, kg or pallets.')
    c['claimed_qty']=quantity(c['claimed_qty'])
    for k in ('claim_date','deadline'): c[k]=iso(c[k])
    if c['deadline'] and not c['deadline_source']: raise ValueError('Add the source of the deadline; retailer deadlines are not assumed.')
    return c

def decode(payload, limit=10*1024*1024):
    try: data=base64.b64decode(payload.get('data',''),validate=True)
    except Exception: raise ValueError('Invalid file encoding.')
    if not data or len(data)>limit: raise ValueError(f'File must be nonempty and no larger than {limit//1024//1024} MB.')
    return data

def parse_file(payload):
    data=decode(payload,5*1024*1024)
    name=clean(payload.get('filename',''),200)
    if name.lower().endswith('.xlsx'):
        import openpyxl
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                if sum(x.file_size for x in z.infolist())>30*1024*1024: raise ValueError('Workbook is too large when expanded.')
            book=openpyxl.load_workbook(io.BytesIO(data),read_only=True,data_only=False)
            rows=[]
            for i,row in enumerate(book.active.iter_rows(values_only=True)):
                if i>2000: raise ValueError('Maximum 2,000 rows per import.')
                if len(row)>80: raise ValueError('Maximum 80 columns.')
                if any(isinstance(v,str) and v.startswith('=') for v in row): raise ValueError('Export formula cells as values before importing.')
                rows.append([v.date().isoformat() if isinstance(v,datetime) else v.isoformat() if isinstance(v,date) else str(v) if v is not None else '' for v in row])
            book.close()
        except ValueError: raise
        except Exception: raise ValueError('Could not read this XLSX workbook.')
    elif name.lower().endswith('.csv'):
        try:
            text=data.decode('utf-8-sig')
            rows=list(csv.reader(io.StringIO(text)))
        except (UnicodeDecodeError,csv.Error): raise ValueError('Save the file as UTF-8 CSV.')
    else: raise ValueError('Import a CSV or XLSX file.')
    if len(rows)<2 or len(rows)>2001: raise ValueError('Import between 1 and 2,000 data rows.')
    headers=[clean(h,100) for h in rows[0]]
    if not headers or len(headers)>80 or any(not h for h in headers) or len(set(headers))!=len(headers):
        raise ValueError('Column headers must be unique and nonempty (maximum 80).')
    out=[]
    for i,row in enumerate(rows[1:],2):
        if not any(str(v).strip() for v in row): continue
        if len(row)>len(headers): raise ValueError(f'Row {i} has more values than column headers.')
        out.append((i,dict(zip(headers,row+['']*(len(headers)-len(row))))))
    if not out: raise ValueError('The file contains no data rows.')
    return headers,out

def suggestions(headers):
    aliases={'deduction_id':'claim_ref','deduction_ref':'claim_ref','invoice':'invoice_ref','po':'po_ref','deduction_amount':'amount','product':'sku','due_date':'deadline'}
    result={}
    for h in headers:
        key=re.sub(r'[^a-z0-9]+','_',h.lower()).strip('_')
        key=aliases.get(key,key)
        if key in FIELDS: result[key]=h
    return result
