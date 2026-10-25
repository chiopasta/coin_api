"""One bounded diagnostic. No service/system changes and no scanner launch."""
from datetime import datetime,timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

from coin_analysis import scanner_ntp_v46 as ntp

OUT=Path('reports/scanner_v46_20261025')
RAW=Path('data/scanner_v46_audit/20261025')


def sha(path):
    with open(path,'rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def write(name,value):
    with (OUT/name).open('x',encoding='utf8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False)


def command(argv,timeout=5):
    try:
        p=subprocess.run(argv,capture_output=True,timeout=timeout,creationflags=0x08000000)
        raw=p.stdout+p.stderr
        try:output=raw.decode('utf8')
        except UnicodeDecodeError:output=raw.decode('cp949',errors='replace')
        return dict(argv=argv,returncode=p.returncode,output=output)
    except (OSError,subprocess.TimeoutExpired) as exc:return dict(argv=argv,error=repr(exc))


def main():
    old=json.loads(Path('reports/scanner_v45_20261025/preflight.json').read_text(encoding='utf8'))
    protected={p:sha(p) for p in old['protected_hashes']}
    assert protected==old['protected_hashes'] and len(protected)==86
    prior=dict(old['prior_evidence_hashes'])
    assert all(sha(p)==h for p,h in prior.items())
    for folder in ['reports/scanner_v45_20261025']:
        prior.update({str(p):sha(p) for p in Path(folder).rglob('*') if p.is_file() and '__pycache__' not in str(p)})
    prior['docs/scanner_v45_observation_readiness_20261025.md']=sha('docs/scanner_v45_observation_readiness_20261025.md')
    bounds=dict(ntp_hosts=list(ntp.HOSTS),ntp_max_packets=6,ntp_probe_process_seconds=12,
        w32tm_diagnostic_max_packets=1,w32tm_max_seconds=5,
        exchanges=['UPBIT','BITHUMB'],markets=['KRW-BTC'],exchange_http_max=2,retries=0,http_seconds_per_call=3,
        no_system_changes=True,no_scanner=True,no_orders=True)
    write('preflight.json',dict(at=time.time(),baseline=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        protected_hashes=protected,prior_evidence_hashes=prior,bounds=bounds))
    RAW.mkdir(parents=True,exist_ok=False)
    commands=[]
    for argv in [['sc.exe','query','W32Time'],['sc.exe','qc','W32Time'],['sc.exe','qtriggerinfo','W32Time'],
        ['reg.exe','query',r'HKLM\SYSTEM\CurrentControlSet\Services\W32Time\Parameters'],
        ['reg.exe','query',r'HKLM\SYSTEM\CurrentControlSet\Services\W32Time\TimeProviders\NtpClient'],
        ['w32tm','/query','/status','/verbose'],
        ['w32tm','/stripchart','/computer:time.windows.com','/samples:1','/dataonly']]:
        commands.append(command(argv))
    measured=command([sys.executable,'-m','coin_analysis.scanner_ntp_v46'],12)
    try:ntp_result=json.loads(measured['output'])
    except (KeyError,ValueError):ntp_result=dict(error=measured,rows=[])
    write('clock_probe.json',dict(at=time.time(),commands=commands,ntp=ntp_result,assessment=ntp.assess(ntp_result)))
    records=[]
    for exchange,host in [('UPBIT','api.upbit.com'),('BITHUMB','api.bithumb.com')]:
        record=dict(exchange=exchange,endpoint='/v1/ticker',params=dict(markets='KRW-BTC'),started_at=time.time())
        mono=time.monotonic()
        try:
            request=urllib.request.Request('https://'+host+'/v1/ticker?markets=KRW-BTC',headers={'User-Agent':'ScannerV46-bounded-clock-audit/1'})
            with urllib.request.urlopen(request,timeout=3) as response:
                raw=response.read(131073)
                received=time.time();elapsed=time.monotonic()-mono
                if len(raw)>131072:raise ValueError('Response too large')
                body=json.loads(raw);path=RAW/(exchange.lower()+'_ticker.json');path.write_bytes(raw)
                date=response.headers.get('Date');server=parsedate_to_datetime(date).timestamp()
                record.update(status=response.status,received_at=received,elapsed_monotonic_seconds=elapsed,
                    server_date=date,date_minus_local_receipt_seconds=server-received,
                    date_offset_interval_seconds=[server-received,server+1-record['started_at']],
                    date_assumptions='Second quantization, unknown generation/cache point; not trusted clock admission',
                    age=response.headers.get('Age'),ticker_update_timestamp_ms=body[0].get('timestamp'),
                    raw_file=str(path),raw_sha256=sha(path))
        except Exception as exc:record.update(error=repr(exc),received_at=time.time())
        records.append(record)
    write('exchange_clock.json',dict(at=time.time(),records=records,http_attempts=len(records),
        source='HTTP Date approximate only; ticker timestamp is a data update timestamp, not server NOW',
        utc_now=datetime.now(timezone.utc).isoformat()))
    print(json.dumps(dict(ntp=ntp_result,assessment=ntp.assess(ntp_result),exchange=records)))


if __name__=='__main__':main()
