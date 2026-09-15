"""Snapshot legacy pawn→CustID links without changing any customer or pawn row.

Default is read-only preview. --apply only adds proven links, never overwrites one.
"""
import argparse
import json
import sys
import unicodedata
from collections import defaultdict,Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from flask import g
from khcd import create_app,db,auth,customer_master as M
from khcd.domain import now
from scripts.migrate import DDL


def name_key(value):
    return ' '.join(unicodedata.normalize('NFC',str(value or '')).casefold().split())


def plan(local,pawns,directory,existing):
    remote={str(r['CustID']):r for r in directory['rows']}
    phones=defaultdict(list)
    for row in remote.values():
        for key in row['phone_keys']:phones[key].append(row)
    receipts={r['source_id']:r for r in directory['receipts']}
    byid={r['id']:r for r in local};byphone=defaultdict(list)
    for row in local:byphone[row['phone']].append(row)
    links=[];counts=Counter()
    separators=str.maketrans('','',' .()-\t\r\n\u00a0')
    for pawn in pawns:
        if pawn['id'] in existing:counts['already_linked']+=1;continue
        candidates=[byid[pawn['customer_id']]] if pawn.get('customer_id') in byid else byphone[pawn['phone']]
        if len(candidates)!=1:counts['legacy_customer_ambiguous_or_missing']+=1;continue
        source=candidates[0];key=str(source['phone'] or '').translate(separators)
        receipt=receipts.get(source['id']);target=None;reason=None
        if receipt and receipt['phone']==key and receipt['cust_id'] in remote:
            target=remote[receipt['cust_id']];reason='sync_receipt'
        else:
            found=phones.get(key,[]) if key else []
            if len(found)!=1:counts['pmv_ambiguous_or_missing']+=1;continue
            candidate=found[0]
            oldid=str(source.get('cccd') or '').strip();newid=str(candidate.get('CMND') or '').strip()
            if oldid and newid and oldid!=newid:counts['identity_conflict']+=1;continue
            if not ((oldid and oldid==newid) or (name_key(source['name']) and name_key(source['name'])==name_key(candidate['CustName']))):
                # Owner chose phone as legacy business key. Only one exact match
                # across all three PMV phone fields, never when identity conflicts.
                reason='unique_phone'
            else:reason='phone_identity'
            target=candidate
        links.append((pawn['id'],str(target['CustID']),reason));counts[reason]+=1
    return links,dict(counts)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    app=create_app()
    with app.app_context():
        g.auth_user=db.one('SELECT * FROM '+auth.source_table()+" WHERE is_active=1 AND is_superuser=1 ORDER BY id LIMIT 1")
        directory=M.call('directory')
        local=db.all('SELECT id,name,phone,cccd FROM customer')
        pawns=db.all('SELECT p.id,p.phone,m.customer_id FROM pawn p LEFT JOIN khcd_pawn_meta m ON m.pawn_id=p.id')
        exists=db.one("SELECT COUNT(*) n FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='khcd_pawn_customer'")['n']
        existing={r['pawn_id'] for r in db.all('SELECT pawn_id FROM khcd_pawn_customer')} if exists else set()
        links,counts=plan(local,pawns,directory,existing)
        report=dict(pmv_customers=len(directory['rows']),cd_customers=len(local),pawns=len(pawns),sync_receipts=len(directory['receipts']),classification=counts,apply=args.apply)
        if args.apply:
            folder=Path('backups');folder.mkdir(exist_ok=True)
            backup=folder/('customer_master_links_before_'+now().strftime('%Y%m%d_%H%M%S')+'.json')
            backup.write_text(json.dumps(db.all('SELECT * FROM khcd_pawn_customer') if exists else [],default=str),encoding='utf-8')
            db.execute(DDL[0])
            with db.transaction():
                for pid,cid,reason in links:
                    db.execute('INSERT INTO khcd_pawn_customer (pawn_id,pmv_cust_id,source,linked_at) VALUES (%s,%s,%s,%s)',(pid,cid,reason,now()))
        Path('output').mkdir(exist_ok=True)
        Path('output/customer-master-cutover.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
