"""Loopback dashboard with authenticated, explicit observer start/STOP.

Original archive is immutable and must have an empty WAL. Observation databases
use short read-only transactions, including their WAL. Chart gaps stay gaps.
"""
from contextlib import contextmanager
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
from logging.handlers import RotatingFileHandler
import math
from pathlib import Path
import re
import secrets
import socket
import sqlite3
import threading
import time
import traceback
from urllib.parse import parse_qs, urlsplit

from . import scanner_control_v410 as control

ARCHIVE = control.DATA_DIR / 'forward_scanner_v4.db'
ASSETS = Path(__file__).with_name('dashboard_assets')
HOST, PORT = '127.0.0.1', 8765
URL = f'http://{HOST}:{PORT}'
LIMIT = 200


@contextmanager
def readonly(path, archive=False):
    path = Path(path)
    wal = Path(str(path) + '-wal')
    if archive and wal.exists() and wal.stat().st_size:
        raise sqlite3.DatabaseError('Archive has an active WAL; archive view blocked')
    db = sqlite3.connect(path.resolve().as_uri() + '?mode=ro' + ('&immutable=1' if archive else ''),
                         uri=True, timeout=.5)
    try:
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        yield db
    finally:
        db.close()


def tables(db):
    return {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def catalog():
    result = {}
    if ARCHIVE.is_file():
        result['archive'] = dict(path=ARCHIVE, exchange='UPBIT', archive=True, root=None)
    base = control.observer.RUNTIME_ROOT
    if base.exists():
        # Fixed discovery boundary; request parameters can never supply file paths.
        roots = sorted((p for p in base.iterdir() if p.is_dir() and not p.is_symlink()
                        and p.resolve().parent == base.resolve() and (p/'config.json').is_file()),
                       key=lambda p: p.stat().st_mtime, reverse=True)[:32]
        for root in roots:
            for exchange in control.observer.v42.HOSTS:
                path = root/(exchange.lower()+'.db')
                if path.is_file() and not path.is_symlink():
                    result[root.name+'_'+exchange.lower()] = dict(path=path, exchange=exchange,
                                                                archive=False, root=root)
    return result


def horizon_view(db, row, available, candles=None):
    """Reuse saved metrics, or display exact, contiguous stored bars only.

    This presentation calculation never writes a horizon/label or feeds signals.
    No last-price fill, missing-bar substitution, or partial MFE/MAE.
    """
    if 'live_horizons' in available:
        saved = {r['minutes']: dict(r) for r in db.execute(
            'SELECT * FROM live_horizons WHERE signal_id=?', (row['signal_id'],))}
        return [dict(saved[n], basis='SAVED_LIVE_HORIZON') if n in saved else
                dict(minutes=n, status='NO_DATA', return_pct=None, mfe_pct=None, mae_pct=None,
                     basis='NO_SAVED_HORIZON') for n in (5, 15, 30, 60)]
    if candles is None:
        candles = [dict(r) for r in db.execute(
            'SELECT ts,high,low,close FROM minute_candles WHERE market=? AND ts>=? AND ts<? ORDER BY ts',
            (row['market'], row['signal_time'], row['signal_time']+3600))]
    output = []
    for n in (5, 15, 30, 60):
        t = row['signal_time']; end = t+n*60
        bars = [b for b in candles if t <= b['ts'] < end]
        full = (time.time() >= end and len(bars) == n and
                all(b['ts'] == t+i*60 for i, b in enumerate(bars)) and
                row['signal_price'] is not None and row['signal_price'] > 0 and
                all(b[k] is not None and math.isfinite(b[k]) and b[k] > 0
                    for b in bars for k in ('high', 'low', 'close')))
        values = (100*(bars[-1]['close']/row['signal_price']-1),
                  100*(max(b['high'] for b in bars)/row['signal_price']-1),
                  100*(min(b['low'] for b in bars)/row['signal_price']-1)) if full else (None, None, None)
        output.append(dict(minutes=n, status='COMPLETE' if full else 'PENDING' if time.time()<end else 'NO_DATA',
                           return_pct=values[0], mfe_pct=values[1], mae_pct=values[2],
                           basis='STORED_CANDLES_VIEW_ONLY', observed_minutes=len(bars)))
    return output


def signal_view(db, row, key, source, active_root, available, detail=False):
    value = {k: row[k] for k in ('signal_id', 'market', 'signal_time', 'signal_price', 'detected_at', 'source')}
    value.update(dataset=key, exchange=source['exchange'], score=None, pattern='UNKNOWN',
                 scope='ARCHIVE' if source['archive'] else 'CURRENT_LIVE' if source['root']==active_root else 'STORED_OBSERVATION',
                 detection_price=row['signal_price'], price_basis='SAVED_SIGNAL_PRICE')
    if 'live_signal_details' in available:
        saved = db.execute('SELECT * FROM live_signal_details WHERE signal_id=?', (row['signal_id'],)).fetchone()
        if saved:
            value.update(score=saved['score'], pattern=saved['pattern'], detection_price=saved['detection_price'],
                         price_basis=saved['price_basis'])
    elif source['archive']:
        cfg = json.loads(db.execute('SELECT payload FROM scanner_config WHERE id=1').fetchone()[0])
        if cfg.get('policy', {}).get('range_threshold') == 4:
            value['pattern'] = 'RANGE_30M_GE4_FIRST_CLUSTER'
    metrics = horizon_view(db, row, available)
    value['horizons'] = metrics
    complete = [h for h in metrics if h['status']=='COMPLETE' and h['return_pct'] is not None]
    value['return_pct'] = complete[-1]['return_pct'] if complete else None
    value['return_minutes'] = complete[-1]['minutes'] if complete else None
    value['evaluation'] = ' / '.join(f"{h['minutes']}m {h['status']}" for h in metrics)
    if detail:
        now = int(time.time())
        value['candles'] = [dict(r) for r in db.execute(
            'SELECT ts,open,high,low,close FROM minute_candles WHERE market=? AND ts>=? AND ts<? AND ts+60<=? ORDER BY ts LIMIT 91',
            (row['market'], row['signal_time']-1800, row['signal_time']+3600, now))]
        value['outcomes'] = ([dict(r) for r in db.execute(
            'SELECT label,status,max_return,observed_minutes,expected_minutes FROM signal_outcomes WHERE signal_id=?',
            (row['signal_id'],))] if 'signal_outcomes' in available else [])
    return value


class View:
    def __init__(self):
        self.lock = threading.Lock()
        self.cached = None
        self.cached_at = 0.
        self.cached_scope = None

    def snapshot(self, scope='ALL'):
        if scope not in ('ALL','ARCHIVE','CURRENT_LIVE','STORED_OBSERVATION'):
            raise LookupError('Unknown scope')
        with self.lock:
            if self.cached is not None and self.cached_scope==scope and time.monotonic()-self.cached_at < 4:
                return self.cached
            errors = []
            try:
                state = control.snapshot()
            except Exception:
                state = dict(status='BLOCKED', reason='SCANNER_STATE_UNAVAILABLE', clock='UNKNOWN')
                errors.append('Scanner 상태를 읽을 수 없습니다. status_coin_api.bat을 확인하세요.')
            active_root = Path(state['root']) if state.get('root') else None
            # Explicit public fields only: no process identities, environment, keys or paths.
            public = {k: state.get(k) for k in ('status', 'phase', 'started_at', 'elapsed_monotonic_seconds',
                      'clock', 'db_saved', 'signals', 'size', 'collected', 'last_signal')}
            public['live_collecting'] = state.get('status')=='RUNNING' and state.get('phase')=='OBSERVING'
            public['markets'] = state.get('markets') if public['live_collecting'] else 0
            public['venue_pairs'] = state.get('venue_pairs') if public['live_collecting'] else 0
            public['reason'] = state['reason'] if 'CLOCK' in (state.get('reason') or '') and re.fullmatch(r'CLOCK_[A-Z0-9_]+',state['reason']) else (
                'SCANNER_BLOCKED; see status_coin_api.bat' if state.get('status')=='BLOCKED' else None)
            public['connections'] = self.connections(active_root, public['live_collecting'])
            rows = []; total = 0; today_live = 0
            today = datetime.now(control.KST).replace(hour=0,minute=0,second=0,microsecond=0).timestamp()
            sources = catalog()
            for key, source in sources.items():
                try:
                    with readonly(source['path'], source['archive']) as db:
                        available = tables(db)
                        total += db.execute('SELECT COUNT(*) FROM signals').fetchone()[0]
                        if not source['archive']:
                            today_live += db.execute("SELECT COUNT(*) FROM signals WHERE source='LIVE' AND detected_at>=? AND detected_at<?",
                                                     (today,today+86400)).fetchone()[0]
                        group = 'ARCHIVE' if source['archive'] else 'CURRENT_LIVE' if source['root']==active_root else 'STORED_OBSERVATION'
                        if scope in ('ALL',group):
                            recent = db.execute('SELECT * FROM signals ORDER BY detected_at DESC,signal_id LIMIT ?', (LIMIT,)).fetchall()
                            for row in recent:
                                rows.append(signal_view(db,row,key,source,active_root,available))
                except (OSError, ValueError, sqlite3.DatabaseError):
                    errors.append(f"{source['exchange']} {'보관' if source['archive'] else '관측'} DB 조회 실패 · 일부 결과 누락")
            rows.sort(key=lambda r:(r['detected_at'] or 0,r['dataset'],r['signal_id']),reverse=True)
            result = dict(web='RUNNING',scanner=public,signals=rows[:LIMIT],total=total,
                          today_live_signals=today_live,errors=errors,at=time.time(),limit=LIMIT)
            self.cached = result; self.cached_scope = scope; self.cached_at = time.monotonic()
            return result

    @staticmethod
    def connections(root, collecting):
        result = {e:dict(status='DISCONNECTED' if not collecting else 'UNKNOWN',at=None)
                  for e in control.observer.v42.HOSTS}
        if not root or not (root/'control.db').is_file():
            return result
        try:
            with readonly(root/'control.db') as db:
                for e in result:
                    r = db.execute('SELECT status,ended_at,details_json FROM http_attempts WHERE exchange=? AND ended_at IS NOT NULL ORDER BY seq DESC LIMIT 1',(e,)).fetchone()
                    if r:
                        fresh = 0 <= time.time()-r['ended_at'] <= 150
                        try: http_status=json.loads(r['details_json'] or '{}').get('http_status')
                        except (ValueError,AttributeError):http_status=None
                        healthy=r['status']=='HTTP_END' and http_status==200
                        failed=r['status']=='HTTP_ERROR' or r['status']=='HTTP_END' and isinstance(http_status,int) and http_status!=200
                        result[e] = dict(status=('CONNECTED' if healthy and fresh else
                                                 'STALE' if healthy else 'ERROR' if failed else 'UNKNOWN') if collecting else 'DISCONNECTED',
                                         at=r['ended_at'])
        except (OSError,sqlite3.DatabaseError):
            for e in result: result[e]['status']='UNKNOWN'
        return result

    def detail(self, key, signal_id):
        source = catalog().get(key)
        if source is None or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',signal_id):
            raise LookupError('Signal not found')
        with self.lock, readonly(source['path'],source['archive']) as db:
            row = db.execute('SELECT * FROM signals WHERE signal_id=?',(signal_id,)).fetchone()
            if row is None: raise LookupError('Signal not found')
            state = control.current()
            active_root = control.owned_root(state) if state else None
            return signal_view(db,row,key,source,active_root,tables(db),True)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 8
    allow_reuse_address = False

    def __init__(self, address, view=None, logger=None, seconds=control.observer.MAX_SECONDS,
                 max_requests=control.observer.MAX_REQUESTS):
        if address[0] != HOST: raise ValueError('Loopback binding required')
        if not 30<=seconds<=control.observer.MAX_SECONDS or not 26<=max_requests<=control.observer.MAX_REQUESTS:
            raise ValueError('Outside existing Scanner safety limits')
        from .scanner_analysis_v51 import Analysis
        self.view = view or View()
        self.analysis = Analysis()
        self.logger = logger or logging.getLogger('scanner_dashboard')
        self.operations = Operations(seconds,max_requests,self.logger)
        self.csrf = secrets.token_urlsafe(32)
        self.slots = threading.BoundedSemaphore(8)
        super().__init__(address, Handler)

    def server_bind(self):
        # Windows must reject a second listener, even if another application uses
        # SO_REUSEADDR. Never steal an existing port.
        if hasattr(socket,'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        super().server_bind()

    def process_request(self, request, client_address):
        if not self.slots.acquire(False):
            self.shutdown_request(request); return
        try: super().process_request(request,client_address)
        except BaseException:
            self.slots.release(); raise

    def process_request_thread(self, request, client_address):
        try: super().process_request_thread(request,client_address)
        finally: self.slots.release()


class Handler(BaseHTTPRequestHandler):
    server_version = 'CHIOScanner/5.1'
    sys_version = ''

    def setup(self):
        super().setup()
        self.connection.settimeout(3)

    def log_message(self, *_): pass

    def respond(self, code, value, mime='application/json; charset=utf-8'):
        body = json.dumps(value,ensure_ascii=False,allow_nan=False).encode('utf8') if isinstance(value,dict) else value
        self.send_response(code)
        for key,val in {'Content-Type':mime,'Content-Length':str(len(body)), 'Cache-Control':'no-store',
                        'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer',
                        'Cross-Origin-Resource-Policy':'same-origin','X-Frame-Options':'DENY',
                        'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"}.items():
            self.send_header(key,val)
        self.end_headers()
        try: self.wfile.write(body)
        except (BrokenPipeError,ConnectionResetError): pass

    def local_request(self, write=False):
        expected = f'{HOST}:{self.server.server_port}'
        return (self.client_address[0]==HOST and self.headers.get('Host')==expected and
                self.headers.get('Origin', None if write else f'http://{expected}')==f'http://{expected}' and
                self.headers.get('Sec-Fetch-Site','same-origin') in ('same-origin','none'))

    def do_GET(self):
        if not self.local_request():
            self.respond(403,dict(error='Local origin required')); return
        parsed = urlsplit(self.path)
        try:
            if len(self.path)>1024:
                self.respond(414,dict(error='Request too long')); return
            if parsed.path=='/api/snapshot':
                query=parse_qs(parsed.query)
                self.respond(200,self.server.view.snapshot(query.get('scope',['ALL'])[0]))
            elif parsed.path=='/api/signal':
                query=parse_qs(parsed.query)
                self.respond(200,self.server.view.detail(query.get('dataset',[''])[0],query.get('id',[''])[0]))
            elif parsed.path=='/api/control':
                self.respond(200,dict(token=self.server.csrf,**self.server.operations.status()))
            elif parsed.path=='/api/analysis':
                query=parse_qs(parsed.query)
                self.respond(200,self.server.analysis.report(query.get('group',['ARCHIVE_LIVE'])[0],
                                                           int(query.get('offset',['0'])[0])))
            elif parsed.path=='/api/analysis/signal':
                query=parse_qs(parsed.query)
                self.respond(200,self.server.analysis.detail(query.get('dataset',[''])[0],query.get('id',[''])[0]))
            elif parsed.path in ('/','/analysis','/app.js','/style.css'):
                file,mime={'/':('index.html','text/html; charset=utf-8'),'/analysis':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),
                           '/style.css':('style.css','text/css; charset=utf-8')}[parsed.path]
                self.respond(200,(ASSETS/file).read_bytes(),mime)
            else: self.respond(404,dict(error='Not found'))
        except LookupError:
            self.respond(404,dict(error='신호를 찾을 수 없습니다. 목록을 새로 고침하세요.'))
        except Exception as exc:
            self.server.logger.warning('Read request failed (%s)',type(exc).__name__)
            self.respond(503,dict(error='저장 데이터 조회 실패. 잠시 후 다시 시도하거나 상태 BAT를 확인하세요.'))

    def do_POST(self):
        parsed=urlsplit(self.path)
        if parsed.query or parsed.path not in ('/api/control/start','/api/control/stop'):
            self.respond(405,dict(error='Unsupported action'));return
        token=self.headers.get('X-CSRF-Token','')
        if not self.local_request(True) or not token.isascii() or not secrets.compare_digest(token,self.server.csrf):
            self.respond(403,dict(error='로컬 페이지 인증이 필요합니다. 새로 고침하세요.'));return
        if (self.headers.get('Content-Type')!='application/json' or
                self.headers.get('Content-Length')!='2' or self.headers.get('Transfer-Encoding')):
            self.respond(400,dict(error='Invalid local control request'));return
        if self.rfile.read(2)!=b'{}':
            self.respond(400,dict(error='Control options cannot be changed'));return
        try:
            action=parsed.path.rsplit('/',1)[-1]
            self.server.operations.request(action)
            self.respond(202,self.server.operations.status())
            control_event(self.server.logger,'CONTROL_HTTP_RESPONSE',action=action,http_status=202)
        except RuntimeError as exc:
            control_event(self.server.logger,'CONTROL_HTTP_REJECTED',http_status=409,**exception_details(exc))
            self.respond(409,dict(error=str(exc)))
        except Exception as exc:
            control_event(self.server.logger,'CONTROL_HTTP_ERROR',stage='POST_RESPONSE',**exception_details(exc))
            self.respond(503,dict(error='로컬 프로세스 상태 확인 실패. 상태 BAT를 확인하세요.'))

    def unsupported(self): self.respond(405,dict(error='Unsupported method'))
    do_PUT=do_DELETE=do_PATCH=do_OPTIONS=unsupported


def control_message(reason):
    reason=reason or ''
    code=re.match(r'[A-Z][A-Z0-9_]+',reason)
    code=code.group(0) if code else 'SCANNER_CONTROL_FAILED'
    descriptions={
        'CLOCK_WINDOWS_ROOT_UNCERTAINTY':'Windows 시간 품질의 불확실성이 크고 직접 NTP 교차 검증도 완료되지 않았습니다.',
        'CLOCK_WINDOWS_SYNC_STALE':'Windows의 마지막 정상 동기화가 오래됐습니다.',
        'CLOCK_WINDOWS_UNSYNCHRONIZED':'Windows가 미동기화·윤초 경고·동기화 오류를 보고했습니다.',
        'CLOCK_WINDOWS_TIME_SERVICE_UNVERIFIED':'Windows 시간 서비스 상태를 확인할 수 없습니다.',
        'CLOCK_REFERENCE_MEASUREMENT_UNAVAILABLE':'필수 두 제공자의 NTP 측정을 완료하지 못했습니다.',
        'CLOCK_REFERENCE_INDEPENDENCE_UNVERIFIED':'두 NTP 제공자의 독립된 응답 주소를 확인하지 못했습니다.',
        'CLOCK_REFERENCE_OFFSET_OR_UNCERTAINTY':'직접 NTP 오차와 측정 불확실성의 합이 1초를 초과했습니다.',
        'CLOCK_REFERENCE_STALE':'직접 NTP 측정이 오래되어 다시 검증해야 합니다.'}
    if code in descriptions:return f'시계 안전 검증 실패 ({code}). {descriptions[code]}'
    if 'CLOCK' in code:
        return f'시계 안전 검증 실패 ({code}). Windows 시간 동기화와 NTP 연결을 확인하세요.'
    if 'DUPLICATE' in code or 'Another scanner' in reason:
        return '스캐너가 이미 실행 중이거나 다른 관측 작업이 잠금을 사용 중입니다.'
    return f'시작·종료를 확인하지 못했습니다 ({code}). status_coin_api.bat에서 원인을 확인하세요.'


def control_event(logger,event,**fields):
    """Structured local lifecycle evidence; never log headers or request bodies."""
    logger.info(json.dumps(dict(at=time.time(),event=event,**fields),ensure_ascii=True))


def exception_details(exc):
    """Allowlist error identity and project stack locations, excluding messages."""
    frames=[]
    for frame in traceback.extract_tb(exc.__traceback__)[-8:]:
        path=Path(frame.filename).resolve()
        if path.is_relative_to(control.PROJECT_ROOT):
            frames.append(dict(file=path.relative_to(control.PROJECT_ROOT).as_posix(),line=frame.lineno,function=frame.name))
    code=str(exc)
    return dict(error_type=type(exc).__name__,errno=getattr(exc,'errno',None),winerror=getattr(exc,'winerror',None),
                code=code if re.fullmatch(r'[A-Z][A-Z0-9_]{2,80}',code) else None,frames=frames)


class Operations:
    """Only explicit local POSTs launch; status and analysis never start LIVE."""
    def __init__(self, seconds, max_requests, logger=None):
        self.seconds,self.max_requests=seconds,max_requests
        self.logger=logger or logging.getLogger('scanner_dashboard')
        self.lock=threading.Lock()
        self.active=set()
        self.generation=0
        self.closing=False
        self.cancel_start=threading.Event()
        self.threads=[]
        self.result=dict(action=None,state='IDLE',message='스캐너 시작 버튼으로 관측을 시작하세요.')

    def status(self):
        with self.lock:
            result=dict(self.result,busy=bool(self.active),starting='start' in self.active,
                        stopping='stop' in self.active,seconds=self.seconds,max_requests=self.max_requests)
        try:
            raw=control.current()
            s=control.snapshot()
            result['process_alive']=bool(raw and (control.alive(raw.get('manager')) or control.alive(raw.get('child'))))
            result['scanner']={k:s.get(k) for k in ('status','phase','clock','db_saved')}
            if (s['status']=='BLOCKED' and s.get('reason') and not result['busy'] and
                    not (result['action']=='stop' and result['state']=='SUCCEEDED')):
                result.update(state='FAILED',message=control_message(s['reason']))
        except Exception as exc:
            control_event(self.logger,'CONTROL_STATUS_ERROR',stage='STATUS_READ',**exception_details(exc))
            result.update(process_alive=None,state='FAILED',message='프로세스 상태 확인 실패. 상태 BAT를 확인하세요.')
        return result

    def request(self, action):
        if action not in ('start','stop'):raise RuntimeError('지원하지 않는 동작입니다.')
        with self.lock:
            if self.closing:raise RuntimeError('웹 서버를 종료하고 있습니다.')
            if action in self.active or action=='start' and self.active:
                raise RuntimeError('시작·종료 확인이 진행 중입니다.')
            raw=control.current()
            alive=bool(raw and (control.alive(raw.get('manager')) or control.alive(raw.get('child'))))
            if action=='start' and alive:
                raise RuntimeError('스캐너가 이미 실행 중입니다.')
            if action=='start':self.cancel_start.clear()
            else:self.cancel_start.set()
            self.active.add(action);self.generation+=1;generation=self.generation
            operation_id=secrets.token_hex(12)
            self.result=dict(action=action,operation_id=operation_id,state='WORKING',message='시계 검증 및 실제 수집 시작 확인 중…' if action=='start' else '저장 완료와 정상 종료 확인 중…')
        control_event(self.logger,'CONTROL_REQUEST',action=action,operation_id=operation_id,source='WEB_API')

        def run():
            from . import scanner_desktop_v50 as desktop
            try:
                result=desktop.start_scanner(self.seconds,self.max_requests,self.cancel_start) if action=='start' else desktop.stop_scanner()
                if action=='stop':
                    # A stop arriving before the manager publishes PRECHECK also
                    # waits for the cancelled start operation to finish.
                    for thread in list(self.threads):
                        if thread is not threading.current_thread() and thread.name=='scanner-start':
                            thread.join(control.STOP_WAIT_SECONDS)
                            if thread.is_alive():raise RuntimeError('SCANNER_STOP_UNCONFIRMED')
                    result=desktop.stop_scanner()
                success=(result['status']=='RUNNING' and result['phase']=='OBSERVING') if action=='start' else result['status']=='STOPPED'
                message=('스캐너 수집 시작을 확인했습니다.' if action=='start' else
                         '실행 중인 스캐너가 없습니다. 웹 대시보드는 계속 사용할 수 있습니다.' if result.get('reason')=='NO_RUNNING_SCANNER' else
                         '스캐너 정상 종료를 확인했습니다. 웹 대시보드는 계속 사용할 수 있습니다.') if success else control_message(result.get('reason'))
                outcome=dict(action=action,operation_id=operation_id,state='SUCCEEDED' if success else 'FAILED',message=message)
                control_event(self.logger,'CONTROL_FINISHED',action=action,operation_id=operation_id,
                              outcome=outcome['state'],scanner_status=result['status'],phase=result.get('phase'))
            except Exception as exc:
                control_event(self.logger,'CONTROL_EXCEPTION',action=action,operation_id=operation_id,
                              stage='START_HELPER' if action=='start' else 'STOP_HELPER',**exception_details(exc))
                outcome=dict(action=action,operation_id=operation_id,state='FAILED',message=control_message(str(exc)))
            with self.lock:
                self.active.discard(action)
                if generation==self.generation:self.result=outcome
        thread=threading.Thread(target=run,name='scanner-'+action,daemon=True)
        with self.lock:
            self.threads=[t for t in self.threads if t.is_alive()]
            self.threads.append(thread)
            thread.start()

    def close(self):
        with self.lock:
            self.closing=True
            self.cancel_start.set()
            active=bool(self.active)
            threads=list(self.threads)
        if active:
            from . import scanner_desktop_v50 as desktop
            desktop.cancel_pending_start()
            control.stop()
        for thread in threads:
            thread.join(control.STOP_WAIT_SECONDS+3)


def rotating_logger(folder):
    logger=logging.getLogger('scanner_dashboard');logger.setLevel(logging.INFO);logger.propagate=False
    handler=RotatingFileHandler(folder/'web.log',maxBytes=1024*1024,backupCount=1,encoding='utf8')
    logger.addHandler(handler)
    return logger
