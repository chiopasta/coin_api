"""Bounded offline V4 integration check; temporary scanner DB, original DB read-only."""
from contextlib import closing
import json
import math
from pathlib import Path
import tempfile

from . import forward_scanner_v4 as s
from . import forward_surge_success_failure as sf
from .paths import DATA_DIR,REPORTS_DIR

def run():
    source=DATA_DIR/'research_market_validation_v1.db';before=s.v3.v2.digest(source)
    start=s.collector.parse('2026-09-15T00:00:00+09:00');end=start+86400
    markets=['KRW-BTC','KRW-CPOOL','KRW-FLOCK','KRW-NEAR','KRW-ENA']
    with closing(s.v3.v2.old.open_readonly(source)) as original:
        data={m:[tuple(r) for r in original.execute('SELECT ts,open,high,low,close,trade_value FROM minute_candles WHERE market=? AND ts>=? AND ts<? ORDER BY ts',(m,start-s.WARMUP,end+3600))] for m in markets}
    panel={m:s.v3.v2.old.Series(rows) for m,rows in data.items()};btc=panel.pop('KRW-BTC')
    reference=s.v3.v2.old.Research(panel,[],start,end,btc)
    expected=sorted((m,r['t']) for m,series in panel.items() for r in sf.starts(series,start-s.WARMUP,end) if r['t']>=start)
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'replay.db';db=s.connect(path);s.initialize(db,markets,start);indices={m:0 for m in markets}
        try:
            for now in range(start-s.WARMUP,end+3600+s.GRACE+1,s.STEP):
                with db:
                    for m in markets:
                        rows=data[m];a=indices[m]
                        while indices[m]<len(rows) and rows[indices[m]][0]<now:indices[m]+=1
                        db.executemany('INSERT OR IGNORE INTO minute_candles VALUES(?,?,?,?,?,?,?)',[(m,)+r for r in rows[a:indices[m]]])
                    db.execute('UPDATE scanner_state SET verified_until=?',(min(now,end+3600),))
                if now<end:s.process_observations(db,now,lambda _:None)
                s.evaluate_outcomes(db,now,lambda _:None)
                if now==start+12*3600:
                    db.close();db=s.connect(path)  # genuine persisted restart mid-replay
            signals=list(db.execute('SELECT * FROM signals ORDER BY market,signal_time'))
            actual=[(r['market'],r['signal_time']) for r in signals]
            if actual!=expected:raise AssertionError(('V3 first clusters differ',actual,expected))
            for r in signals:
                saved=db.execute('SELECT * FROM signal_features WHERE signal_id=?',(r['signal_id'],)).fetchone()
                f=s.v3.features(reference,r['market'],r['signal_time'])
                for section,column in [('values','values_json'),('flags','flags_json')]:
                    for k,x in json.loads(saved[column]).items():
                        y=f[section][k]
                        if isinstance(x,(float,int)) and isinstance(y,(float,int)):
                            if not math.isclose(x,y,rel_tol=1e-8,abs_tol=1e-8):raise AssertionError((k,x,y))
                        elif x!=y:raise AssertionError((k,x,y))
                for outcome in db.execute('SELECT * FROM signal_outcomes WHERE signal_id=?',(r['signal_id'],)):
                    h,p=s.LABELS[outcome['label']];label=s.v3.label_at(panel[r['market']],r['signal_time'],h,p)
                    expected_status='UNKNOWN' if not label['complete'] else 'SUCCESS' if label['value'] else 'FAILURE'
                    if outcome['status']!=expected_status:raise AssertionError((outcome['status'],expected_status))
            report=dict(source=str(source),source_hash_before=before,source_hash_after=s.v3.v2.digest(source),
                        markets=markets,period_kst=[s.collector.iso(start,s.collector.KST),s.collector.iso(end,s.collector.KST)],
                        warmup_hours=6,label_buffer_hours=1,stats=s.statistics(db,'ALL'),matched_v3_first_clusters=len(expected),
                        features_match_v3=True,outcomes_match_v3=True,restart_tested=True,
                        note='Bounded offline replay, not a new efficacy study. Relative strength uses the four replay alts, not the 50-market universe. No network. Temporary scanner DB removed.')
            if report['source_hash_before']!=report['source_hash_after']:raise AssertionError('Source DB changed')
        finally:db.close()
    out=REPORTS_DIR/'forward_scanner_v4_replay.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2));return report

if __name__=='__main__':run()
