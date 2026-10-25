"""Fixed comparison/admission/post checks; never overwrites evidence."""
import argparse
import json
from pathlib import Path
from coin_analysis.scanner_clock_v45 import verify_clock

OUT=Path('reports/scanner_v49_20261025')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['paced_1','paced_2','admission','post'])
    stage=parser.parse_args().stage;target=OUT/f'clock_{stage}.json'
    if target.exists():raise RuntimeError('Never overwrite a check')
    result=verify_clock()
    with target.open('x',encoding='utf8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2)
    print(json.dumps(dict(stage=stage,status=result['status'],reason=result['reason'],windows=result.get('windows_status'),
        packets=len(result.get('measurement',{}).get('attempts',[])),elapsed=result.get('elapsed_monotonic_seconds'),
        rows=[{k:r.get(k) for k in ('host','status','slot_id','attempt_number','offset_seconds','uncertainty_seconds','error')} for r in result.get('measurement',{}).get('rows',[])])),flush=True)
