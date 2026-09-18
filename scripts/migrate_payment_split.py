"""Back up first, add nullable-channel split schema, assert historical money unchanged."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.migrate_conversion import main as backup
from khcd import create_app, db
from khcd.live_schema import upgrade_payments


def main():
    backup()
    with create_app().app_context():
        sql='SELECT id,log_id,channel,direction,amount,cashPay,cardPay,bank_snapshot,reconciliation_state FROM cd_payments ORDER BY id'
        before=db.all(sql)
        upgrade_payments(db.db())
        after=db.all(sql)
        if before != after:
            raise RuntimeError('Dữ liệu thay đổi trong lúc nâng cấp. Dừng triển khai và đối chiếu backup.')
        print('Payment split ready; historical payment rows unchanged:',len(after))


if __name__=='__main__':main()
