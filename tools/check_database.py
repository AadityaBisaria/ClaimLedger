"""Create a consistent SQLite snapshot and verify migration integrity."""
import sqlite3
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'data'
backup=root/'backups';backup.mkdir(exist_ok=True)
with sqlite3.connect(root/'claimledger.sqlite3') as db:
    with sqlite3.connect(backup/'multisku-upgrade.sqlite3') as snapshot:db.backup(snapshot)
    assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert not db.execute('PRAGMA foreign_key_check').fetchall()
    print('SQLite integrity and foreign keys: OK')
    for table in ('claims','documents','links','credits','events','exports'):
        print(table,db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0])
    print('Independent confirmed mappings:',db.execute("SELECT COUNT(*) FROM links WHERE confirmed=1 AND review_json!='{}'").fetchone()[0])
