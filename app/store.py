import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def uid():
    return uuid.uuid4().hex


SCHEMA = '''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS claims (
 id TEXT PRIMARY KEY, workspace TEXT NOT NULL, retailer TEXT NOT NULL,
 supplier_account TEXT NOT NULL DEFAULT '', claim_ref TEXT NOT NULL, line_ref TEXT NOT NULL DEFAULT '1',
 invoice_ref TEXT NOT NULL DEFAULT '', po_ref TEXT NOT NULL DEFAULT '', sku TEXT NOT NULL DEFAULT '',
 description TEXT NOT NULL DEFAULT '', amount_cents INTEGER NOT NULL CHECK(amount_cents>0),
 currency TEXT NOT NULL DEFAULT 'GBP', claimed_qty TEXT NOT NULL DEFAULT '', unit TEXT NOT NULL DEFAULT 'cases',
 claim_date TEXT NOT NULL DEFAULT '', deadline TEXT NOT NULL DEFAULT '', deadline_source TEXT NOT NULL DEFAULT '',
 owner TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'open',
 disputed_cents INTEGER NOT NULL DEFAULT 0, approved_cents INTEGER NOT NULL DEFAULT 0,
 submission_ref TEXT NOT NULL DEFAULT '', submitted_at TEXT NOT NULL DEFAULT '',
 followup_date TEXT NOT NULL DEFAULT '', source_json TEXT NOT NULL DEFAULT '{}',
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1,
 UNIQUE(workspace,retailer,supplier_account,claim_ref,line_ref)
);
CREATE INDEX IF NOT EXISTS idx_claims_workspace ON claims(workspace,created_at);
CREATE TABLE IF NOT EXISTS documents (
 id TEXT PRIMARY KEY, workspace TEXT NOT NULL, filename TEXT NOT NULL,
 mime TEXT NOT NULL, size INTEGER NOT NULL, sha256 TEXT NOT NULL,
 extracted_text TEXT NOT NULL DEFAULT '', extraction_status TEXT NOT NULL,
 pages INTEGER NOT NULL DEFAULT 1, meta_json TEXT NOT NULL DEFAULT '{}',
 reviewed_by TEXT NOT NULL DEFAULT '', reviewed_at TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL, UNIQUE(workspace,sha256)
);
CREATE TABLE IF NOT EXISTS links (
 claim_id TEXT NOT NULL REFERENCES claims(id), document_id TEXT NOT NULL REFERENCES documents(id),
 confirmed INTEGER NOT NULL DEFAULT 0, reason TEXT NOT NULL,
 PRIMARY KEY(claim_id,document_id)
);
CREATE TABLE IF NOT EXISTS credits (
 id TEXT PRIMARY KEY, workspace TEXT NOT NULL, claim_id TEXT NOT NULL REFERENCES claims(id),
 credit_ref TEXT NOT NULL, amount_cents INTEGER NOT NULL CHECK(amount_cents>0), currency TEXT NOT NULL,
 credit_date TEXT NOT NULL, source TEXT NOT NULL, created_at TEXT NOT NULL,
 UNIQUE(workspace,credit_ref)
);
CREATE INDEX IF NOT EXISTS idx_credits_claim ON credits(claim_id);
CREATE TABLE IF NOT EXISTS events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, workspace TEXT NOT NULL, claim_id TEXT,
 action TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_case ON events(workspace,claim_id,id);
CREATE TABLE IF NOT EXISTS exports (
 id TEXT PRIMARY KEY, workspace TEXT NOT NULL, claim_id TEXT NOT NULL REFERENCES claims(id),
 fingerprint TEXT NOT NULL, kind TEXT NOT NULL, reviewer TEXT NOT NULL,
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
 key TEXT PRIMARY KEY, value TEXT NOT NULL
);
PRAGMA user_version=1;
'''


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root/'files').mkdir(exist_ok=True)
        (self.root/'exports').mkdir(exist_ok=True)
        self.db_path = self.root/'claimledger.sqlite3'
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript(SCHEMA)
            columns={r['name'] for r in db.execute('PRAGMA table_info(credits)')}
            if 'voided_at' not in columns:
                db.execute("ALTER TABLE credits ADD COLUMN voided_at TEXT NOT NULL DEFAULT ''")
                db.execute("ALTER TABLE credits ADD COLUMN void_reason TEXT NOT NULL DEFAULT ''")
            link_columns={r['name'] for r in db.execute('PRAGMA table_info(links)')}
            if 'review_json' not in link_columns:
                db.execute("ALTER TABLE links ADD COLUMN review_json TEXT NOT NULL DEFAULT '{}'")
                db.execute("ALTER TABLE links ADD COLUMN reviewed_by TEXT NOT NULL DEFAULT ''")
                db.execute("ALTER TABLE links ADD COLUMN reviewed_at TEXT NOT NULL DEFAULT ''")
                db.execute('''UPDATE links SET review_json=(SELECT meta_json FROM documents WHERE id=document_id),
                  reviewed_by=(SELECT reviewed_by FROM documents WHERE id=document_id),
                  reviewed_at=(SELECT reviewed_at FROM documents WHERE id=document_id) WHERE confirmed=1''')
            db.execute('''CREATE TABLE IF NOT EXISTS extraction_pages (
              document_id TEXT NOT NULL REFERENCES documents(id), page INTEGER NOT NULL,
              method TEXT NOT NULL, spans_json TEXT NOT NULL, created_at TEXT NOT NULL,
              PRIMARY KEY(document_id,page))''')
            from .extraction import native_pages
            for d in db.execute('''SELECT id,extracted_text FROM documents WHERE extracted_text!=''
              AND NOT EXISTS(SELECT 1 FROM extraction_pages p WHERE p.document_id=documents.id)''').fetchall():
                for pg in native_pages(d['extracted_text']):
                    db.execute('INSERT INTO extraction_pages VALUES(?,?,?,?,?)',(d['id'],pg['page'],pg['method'],json.dumps(pg['spans']),now()))
            db.execute('PRAGMA user_version=2')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.db_path, timeout=20)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def event(self, db, workspace, claim_id, action, detail):
        db.execute('INSERT INTO events(workspace,claim_id,action,detail,created_at) VALUES(?,?,?,?,?)',
                   (workspace,claim_id,action,json.dumps(detail,ensure_ascii=False),now()))

    def list_claims(self, workspace):
        with self.connect() as db:
            return [dict(r) for r in db.execute('''SELECT c.*,
              COALESCE((SELECT SUM(amount_cents) FROM credits cr WHERE cr.claim_id=c.id AND cr.voided_at=''),0) AS credited_cents,
              (SELECT COUNT(*) FROM links l WHERE l.claim_id=c.id) AS document_count
              FROM claims c WHERE workspace=? ORDER BY created_at DESC,claim_ref''',(workspace,))]

    def claim(self, workspace, case_id, db=None):
        if db is None:
            with self.connect() as conn:
                return self.claim(workspace,case_id,conn)
        row=db.execute('SELECT * FROM claims WHERE id=? AND workspace=?',(case_id,workspace)).fetchone()
        if not row:
            raise ValueError('Case not found in this workspace.')
        return dict(row)

    def seed(self):
        with self.connect() as db:
            if db.execute("SELECT 1 FROM settings WHERE key='demo_seed'").fetchone():
                return
            today=date.today()
            items=[
                ('NF-1042','INV-2081','PO-48012','OAT-12','Oat & honey granola',60000,'20',4),
                ('NF-1043','INV-2086','PO-48019','TEA-24','Earl Grey tea',28800,'12',7),
                ('NF-1044','INV-2090','PO-48026','OIL-06','Extra virgin olive oil',42000,'10',12),
                ('NF-1045','INV-2075','PO-47980','JAM-12','Strawberry preserve',18000,'6',-2),
                ('NF-1046','INV-2093','PO-48031','PASTA-12','Durum wheat pasta',36000,'15',None),
            ]
            for ref,inv,po,sku,desc,amt,qty,days in items:
                case_id=uid()
                db.execute('''INSERT INTO claims(id,workspace,retailer,supplier_account,claim_ref,
                   invoice_ref,po_ref,sku,description,amount_cents,claimed_qty,claim_date,deadline,
                   deadline_source,owner,notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                   (case_id,'demo','Northfield Markets (fictional)','DEMO-001',ref,inv,po,sku,desc,amt,qty,
                    (today-timedelta(days=14)).isoformat(),(today+timedelta(days=days)).isoformat() if days is not None else '',
                    'Fictional demo deadline; not a retailer policy.' if days is not None else '',
                    'Alex Morgan','Fictional sample for exploring the product.',now(),now()))
                self.event(db,'demo',case_id,'Case created',{'source':'Fictional sample data'})
            db.execute("INSERT INTO settings(key,value) VALUES('demo_seed','1')")
