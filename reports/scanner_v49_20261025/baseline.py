"""Two frozen V4.8 checks, six packets each; never launches LIVE."""
import hashlib
import json
from pathlib import Path
import time
from coin_analysis import scanner_clock_v45 as clock

OUT=Path('reports/scanner_v49_20261025')

if __name__=='__main__':
    hashes={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in
            ('coin_analysis/scanner_clock_v45.py','coin_analysis/scanner_ntp_v46.py')}
    for index in range(2):
        path=OUT/f'baseline_{index+1}.json'
        if path.exists():raise RuntimeError('Never overwrite a diagnostic')
        result=clock.verify_clock()
        with path.open('x',encoding='utf8') as stream:json.dump(dict(result=result,source_hashes=hashes),stream,ensure_ascii=False,indent=2)
        print(json.dumps(dict(index=index+1,status=result['status'],reason=result['reason'],
            rows=[dict(host=r['host'],status=r['status'],error=r.get('error'),delay=r.get('delay_seconds')) for r in result.get('measurement',{}).get('rows',[])])),flush=True)
        if index==0:time.sleep(30)
