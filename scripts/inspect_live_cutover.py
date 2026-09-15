import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from khcd import create_app,db,loan_conversion as C
app=create_app({'CD_LIVE':'0'})
with app.app_context():
    loans=db.all('SELECT id,legacy_pawn_id,source_hash,target_hash FROM cd_loans');changed=[];broken=[]
    for l in loans:
        if C.digest(C.source(l['legacy_pawn_id']))!=l['source_hash']:changed.append(l['id'])
        if C.plan_hash(C.target(l['legacy_pawn_id'])[1])!=l['target_hash']:broken.append(l['id'])
    pending=db.all('SELECT p.id FROM pawn p LEFT JOIN cd_loans l ON l.legacy_pawn_id=p.id WHERE p.status IN(1,2,3,4,7) AND l.id IS NULL')
    # No bridge authentication is fabricated: source-only projection reports missing links separately.
    result={'converted':len(loans),'source_changed_ids':changed,'target_changed_ids':broken,'pending':[]}
    for r in pending:
        src=C.source(r['id']);plan=C.project(src,None)
        result['pending'].append({'id':r['id'],'has_cust_id':bool(src['link']),'errors':[c['label'] for c in plan['checks'] if c['state']=='error']})
    Path('output/live-cutover-inspection.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))
