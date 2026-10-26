"""Independent SQL comparison on a private in-memory projection. No source writes."""
from contextlib import closing
from datetime import datetime,timedelta
import json
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from coin_analysis import v15_dashboard as v,v15_transfer as t

view=v.View();proof={};module=v.analyzer()
for group,path in v.catalog().items():
    reported=view.report(group)['summary']
    with closing(t.readonly(path)) as source:
        source.row_factory=sqlite3.Row
        signals=[dict(r) for r in source.execute('SELECT id,created_at,price,return_30m,max_profit_30m,max_drawdown_30m FROM signals')]
        histories=list(source.execute('SELECT signal_id,minute,observed_at,price FROM signal_price_history'))
    # Decode using the existing analyzer, then close source before SQL joins.
    with closing(sqlite3.connect(':memory:')) as db:
        db.executescript('CREATE TABLE signals(id INTEGER PRIMARY KEY,t TEXT,price REAL,ret REAL,mfe REAL,mae REAL);'
                         'CREATE TABLE history(sid INTEGER,m INTEGER,t TEXT,p REAL,PRIMARY KEY(sid,m));')
        db.executemany('INSERT INTO signals VALUES(?,?,?,?,?,?)',[(module.as_int(s['id']),s['created_at'],*[module.as_float(s[k]) for k in ('price','return_30m','max_profit_30m','max_drawdown_30m')]) for s in signals])
        db.executemany('INSERT INTO history VALUES(?,?,?,?)',[(module.as_int(sid),module.as_int(m),at,module.as_float(p)) for sid,m,at,p in histories])
        now=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        due=(datetime.now()-timedelta(minutes=30)).strftime('%Y-%m-%d %H:%M:%S')
        result=db.execute('''WITH usable AS (
           SELECT s.*,COUNT(h.m) samples,
             SUM(CASE WHEN h.p>0 AND h.t<=? AND
                 CAST(strftime('%s',h.t) AS INTEGER)-CAST(strftime('%s',s.t) AS INTEGER)>=h.m*60 AND
                 CAST(strftime('%s',h.t) AS INTEGER)-CAST(strftime('%s',s.t) AS INTEGER)<(h.m+1)*60 THEN 1 ELSE 0 END) good,
             MAX(CASE WHEN h.m=30 THEN h.p END) endpoint
           FROM signals s JOIN history h ON s.id=h.sid AND h.m BETWEEN 0 AND 30
           WHERE s.t<=? GROUP BY s.id)
           SELECT COUNT(ret),AVG(ret),100.0*SUM(CASE WHEN ret>0 THEN 1 ELSE 0 END)/COUNT(ret),
                  COUNT(mfe),AVG(mfe),COUNT(mae),AVG(mae)
           FROM usable WHERE samples=31 AND good=31 AND ret IS NOT NULL AND price>0
             AND ABS(ret-(endpoint/price-1)*100)<0.0000001''',(now,due)).fetchone()
    for key,n,value in [('return_30m',result[0],result[1]),('mfe_30m',result[3],result[4]),('mae_30m',result[5],result[6])]:
        assert reported[key]['n']==n,(group,key,reported[key],result)
        assert reported[key]['value'] is None and value is None or abs(reported[key]['value']-value)<1e-10
    assert abs(reported['rise_30m']['value']-result[2])<1e-10
    proof[group]=dict(summary=reported,independent_sql_30m=list(result),result='PASS')
output=Path(__file__).with_name('analysis_sql_comparison.json')
if not output.exists():t.write_json(output,proof)
print(json.dumps({k:dict(valid30=r['summary']['return_30m']['n'],result=r['result']) for k,r in proof.items()}))
