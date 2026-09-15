"""Backup, verify staged rows and add native ledger columns. No source edits."""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.migrate_conversion import main as backup_and_schema
from khcd import create_app,db,loan_conversion as C
from khcd.live_schema import upgrade

def main():
    backup_and_schema()
    app=create_app({'CD_LIVE':'0'})
    with app.app_context():
        rows=db.all("SELECT id,legacy_pawn_id,source_hash,target_hash FROM cd_loans WHERE migration_state='STAGED'")
        problems=[]
        for row in rows:
            if C.digest(C.source(row['legacy_pawn_id']))!=row['source_hash'] or C.plan_hash(C.target(row['legacy_pawn_id'])[1])!=row['target_hash']:problems.append(row['id'])
        if problems:raise RuntimeError('Cutover stopped: source/target changed: '+str(problems))
        upgrade(db.db())
        with db.transaction():
            db.execute("UPDATE cd_loans SET migration_state='LIVE' WHERE migration_state='STAGED'")
        print('Native ledger schema ready; promoted',len(rows),'verified receipts. Legacy rows unchanged.')
if __name__=='__main__':main()
