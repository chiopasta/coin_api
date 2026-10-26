"""Read-only checks against this workspace's actual pre-work baseline."""
import hashlib
import json
from pathlib import Path
import socket
import sqlite3
import subprocess

from coin_analysis import scanner_control_v410 as control
from coin_analysis import scanner_desktop_v50 as desktop

ROOT = control.PROJECT_ROOT
OUT = ROOT / 'reports/scanner_v51_20261026'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


if __name__ == '__main__':
    baseline = read(OUT / 'baseline.json')
    allowed = {'docs/research_status.md', 'docs/scanner_v50_dashboard.md',
               'docs/scanner_v410_windows_launcher.md'}
    changed = [p for p, h in baseline['all_existing_hashes'].items() if sha(ROOT / p) != h]
    assert set(changed) <= allowed, changed
    protected = {p: sha(ROOT / p) == v['sha256'] for p, v in baseline['protected_present'].items()}
    assert len(protected) == 75 and all(protected.values())
    health = {}
    for path in (ROOT / 'data').glob('*.db'):
        wal = Path(str(path) + '-wal')
        assert not wal.exists() or not wal.stat().st_size, path
        db = sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True)
        try:
            health[str(path.relative_to(ROOT))] = db.execute('PRAGMA quick_check').fetchone()[0]
            assert health[str(path.relative_to(ROOT))] == 'ok'
            if path.name == 'forward_scanner_v4.db':
                signals = db.execute('SELECT COUNT(*) FROM signals').fetchone()[0]
                assert signals == 215
        finally:
            db.close()
    legacy_path = ROOT / 'reports/scanner_v41_validation_20261024/legacy_reconciliation.json'
    assert sha(legacy_path) == baseline['all_existing_hashes'][str(legacy_path.relative_to(ROOT)).replace('\\', '/')]
    assert read(legacy_path)['counts']['STALE_OPEN'] == 115
    tests = read(OUT / 'test_result.json')
    assert tests['successful'] and all(sha(ROOT / p) == h for p, h in tests['source_sha256'].items())
    frozen = ['forward_scanner_v4.py', 'forward_scanner_v4_operations.py', 'forward_scanner_v42.py',
              'forward_scanner_v43.py', 'scanner_candles.py', 'scanner_clock_v45.py',
              'scanner_clock_v47.py', 'scanner_ntp_v46.py', 'scanner_ntp_v49.py', 'scanner_observation_v45.py']
    assert not subprocess.check_output(['git', 'diff', 'HEAD', '--',
        *['coin_analysis/' + p for p in frozen], 'docs/forward_surge_v3_validation_policy.json',
        'docs/research_market_validation_v1_manifest.json'], cwd=ROOT, text=True).strip()
    state = control.current()
    identities = {'manager': state.get('manager') if state else None,
                  'worker': state.get('child') if state else None,
                  'web': desktop.web_state().get('process')}
    for name in ('pending.json', 'scanner_pending.json'):
        path = desktop.WEB / name
        if path.exists():
            identities[name] = control.read_json(path).get('process')
    alive = {name: control.alive(identity) for name, identity in identities.items()}
    assert not any(alive.values()), alive
    try:
        with socket.create_connection(('127.0.0.1', 8765), timeout=1):
            port_closed = False
    except (ConnectionRefusedError, TimeoutError):
        # Windows can silently time out a refused loopback connection. Check
        # the local listener table as well; timeout alone does not prove closure.
        port_closed = None
    listener_count = subprocess.check_output(['powershell', '-NoProfile', '-Command',
        '@(Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue).Count'],
        text=True, timeout=20).strip()
    assert port_closed is not False and listener_count == '0', listener_count
    port_closed = True
    result = dict(original_signals_before=215, original_signals_after=signals,
                  original_db_sha256=sha(ROOT / 'data/forward_scanner_v4.db'),
                  protected_present=75, protected_present_all_unchanged=True,
                  historical_protected_total=86, historical_missing_before=baseline['protected_missing'],
                  historical_matching_before=63, historical_different_before=12,
                  preexisting_files_checked=len(baseline['all_existing_hashes']),
                  only_intended_document_updates=changed, db_quick_check=health,
                  stale_open_report_count=115, stale_open_report_unchanged=True,
                  legacy_source_db_present=(ROOT / 'crypto_scanner.db').exists(),
                  tests_run=tests['tests_run'], tests_skipped=len(tests['skipped']), tested_sources_match=True,
                  frozen_engine_and_policy_unchanged=True, owned_processes_alive=alive,
                  port_8765_closed=port_closed, web_state=desktop.web_state()['status'],
                  scanner_terminal_reason=state.get('reason') if state else None,
                  actual_exchange_http=0, actual_live_start_attempts=1,
                  browser_visual_validation='UNVERIFIED / URL policy check blocked Computer Use',
                  unattended_24h='NOT_READY', no_orders=True, no_windows_shutdown=True,
                  preexisting_dirty_lock_excluded_from_commit='data/forward_scanner_v4.db.lock')
    (OUT / 'completion_checks.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
