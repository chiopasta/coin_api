"""V4.3 bounded diagnosis. No historical input writes; no retries."""
import hashlib
import json
from pathlib import Path
import sqlite3
import time
import urllib.parse
import urllib.request

from coin_analysis import forward_scanner_v42 as v

OUT = Path('reports/scanner_v43_20261024')
PRIVATE = Path('data/scanner_v43_live/diagnostic_raw')


def sha(path):
    with open(path, 'rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    if (OUT/'diagnosis.json').exists():
        raise RuntimeError('Do not overwrite evidence or repeat HTTP')
    manifest = json.loads(Path('reports/scanner_v41_validation_20261024/input_manifest.json').read_text(encoding='utf8'))
    checks = {p: sha(p) == row['sha256'] for p, row in manifest['inputs'].items()}
    assert len(checks) == 86 and all(checks.values())
    oldroot = Path('data/scanner_v42_live/episode_20261024_supported')
    oldhash = {str(p): sha(p) for p in oldroot.iterdir() if p.is_file()}
    PRIVATE.mkdir(parents=True, exist_ok=False)
    start = time.time(); deadline = start + 60
    bounds = dict(max_requests=8, max_seconds=60, min_spacing_seconds=.3,
                  markets=['KRW-FLOCK', 'KRW-SAND', 'KRW-BTC'], units=[1, 5, 15], retries=0)
    v.write_json(OUT/'diagnostic_bounds.json', dict(frozen_at=start, **bounds))
    cutoff = v.scanner.collector.parse('2026-10-24T23:36:00+09:00')
    observations = [cutoff-660, cutoff-360, cutoff-60]
    queries = [(e, m, 1) for e in v.HOSTS for m in ('KRW-FLOCK', 'KRW-SAND')]
    queries += [(e, 'KRW-BTC', n) for e in v.HOSTS for n in (5, 15)]
    results = []
    for index, (exchange, market, unit) in enumerate(queries):
        assert time.time() < deadline and index < bounds['max_requests']
        to = cutoff//(unit*60)*(unit*60)
        params = dict(market=market, count=200, to=v.candles.api_to(exchange, to))
        began = time.time()
        request = urllib.request.Request(v.HOSTS[exchange]+f'/v1/candles/minutes/{unit}?'+urllib.parse.urlencode(params),
                                         headers={'Accept':'application/json','User-Agent':'CHIO-v4.3-bounded-diagnosis/1'})
        result = dict(exchange=exchange, market=market, unit=unit, requested_at=began, params=params)
        try:
            with urllib.request.urlopen(request, timeout=min(5, deadline-time.time())) as response:
                raw = json.load(response)
            v.write_json(PRIVATE/f'{index}.json', raw)
            rows = [v.candles.candle(r, market, unit, to) for r in raw]
            stamps = {r[0] for r in rows}
            result.update(received_at=time.time(), rows=len(rows), raw_sha256=sha(PRIVATE/f'{index}.json'))
            with v.ops.readonly(oldroot/(exchange.lower()+'.db')) as db:
                if unit == 1:
                    windows = []
                    for t in observations:
                        stored = {r[0] for r in db.execute('SELECT ts FROM minute_candles WHERE market=? AND ts>=? AND ts<?', (market,t-1800,t))}
                        missing = set(range(t-1800,t,60))-stored
                        covered = min(stamps)<=t-1800 and max(stamps)>=t-60
                        windows.append(dict(t=t, stored=len(stored), missing=sorted(missing),
                            historical_response_spans_window=covered,
                            missing_now_returned=sorted(missing & stamps),
                            missing_still_source_absent=sorted(missing-stamps) if covered else None))
                    result['windows'] = windows
                else:
                    diffs=[]
                    for r in rows:
                        if r[0] < cutoff-1800 or r[0]+unit*60>to: continue
                        minute=db.execute('SELECT COUNT(*),SUM(trade_value) FROM minute_candles WHERE market=? AND ts>=? AND ts<?',
                                          (market,r[0],r[0]+unit*60)).fetchone()
                        if minute[0]==unit:
                            error=abs(minute[1]-r[-1]); tolerance=v.candles.value_tolerance(r[-1])
                            diffs.append(dict(ts=r[0],native_value=r[-1],minute_value=minute[1],absolute_error=error,tolerance=tolerance,within_tolerance=error<=tolerance))
                    result['native_value_crosscheck']=diffs
        except Exception as exc:
            result['error']=repr(exc)
        results.append(result)
        time.sleep(.3)
    report=dict(started_at=start,ended_at=time.time(),bounds=bounds,http_attempts=len(results),results=results,
                protected_inputs_unchanged=checks,v42_runtime_hashes=oldhash,
                v42_runtime_preserved=all(sha(p)==h for p,h in oldhash.items()))
    v.write_json(OUT/'diagnosis.json',report)
    print(json.dumps(dict(http_attempts=len(results),errors=[r for r in results if 'error' in r],
                         source_absent_windows=[dict(exchange=r['exchange'],market=r['market'],windows=r['windows']) for r in results if 'windows' in r])))


if __name__=='__main__':main()
