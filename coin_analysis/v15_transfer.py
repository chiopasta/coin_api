"""Manual V15 SQLite snapshots and verified, isolated restores. No scanner imports.

No merge, source writes, scheduler, deletion or network functionality is provided.
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import time
import uuid
import zipfile
import zlib

FORMAT = 1
TABLES = {'signals', 'signal_price_history', 'pullback_watch', 'pullback_paper_trades',
          'prepump_events', 'prepump_tracking', 'low_heat_watch', 'sqlite_sequence'}
TOKEN = re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----)')


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)


def readonly(path, immutable=False):
    db = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro' +
                         ('&immutable=1' if immutable else ''), uri=True, timeout=.05)
    db.execute('PRAGMA query_only=ON')
    return db


def describe(path):
    """Only call on an offline snapshot/import, never full-scan the live DB."""
    with closing(readonly(path, immutable=True)) as db:
        integrity = [r[0] for r in db.execute('PRAGMA integrity_check')]
        if integrity != ['ok']:
            raise ValueError('Snapshot integrity check failed')
        schema = list(db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master "
                                 "WHERE sql IS NOT NULL ORDER BY type,name"))
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'signals','signal_price_history'} <= tables or tables - TABLES:
            raise ValueError('Not an allowlisted V15-family database')
        if any(r[0] in ('trigger','view') or (r[3] and 'VIRTUAL TABLE' in r[3].upper()) for r in schema):
            raise ValueError('Executable/virtual schema is not accepted')
        required = {'id','created_at','exchange','market','score','price'}
        if not required <= {r[1] for r in db.execute('PRAGMA table_info(signals)')}:
            raise ValueError('Unsupported signals schema')
        counts = {t:db.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in sorted(tables)}
        foreign = list(db.execute('PRAGMA foreign_key_check'))
        return dict(user_version=db.execute('PRAGMA user_version').fetchone()[0],
                    application_id=db.execute('PRAGMA application_id').fetchone()[0],
                    schema_sha256=hashlib.sha256(json.dumps(schema,ensure_ascii=False).encode()).hexdigest(),
                    schema=schema, table_counts=counts, integrity='ok',
                    foreign_key_violations=len(foreign),
                    schema_version_note='V15 declares no application migration version; user_version may be 0. Use schema_sha256.')


def identity(registry_path, sources):
    registry_path = Path(registry_path)
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    if registry_path.exists():
        registry = json.loads(registry_path.read_text(encoding='utf-8'))
    else:
        registry = dict(pc_id=str(uuid.uuid4()), databases={})
    changed = False
    for label,path in sources.items():
        # Paths stay local. A copied DB on a new PC has unknown lineage until reviewed.
        key = hashlib.sha256(str(Path(path).resolve()).casefold().encode()).hexdigest()
        if key not in registry['databases']:
            registry['databases'][key] = str(uuid.uuid4())
            changed = True
    if registry_path.exists() and changed:
        # Registry updates are new files; no source DB or prior identity is overwritten.
        raise ValueError('New source not in registry; use a new registry path containing all desired sources')
    if not registry_path.exists():
        write_json(registry_path, registry)
    ids = {label:registry['databases'][hashlib.sha256(str(Path(path).resolve()).casefold().encode()).hexdigest()]
           for label,path in sources.items()}
    return registry['pc_id'], ids


def snapshot(source, destination, deadline_seconds=20):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination or not source.is_file():
        raise ValueError('Existing source and distinct fresh destination required')
    # Reserve destination without replacement, source is never opened writable.
    with destination.open('xb'):
        pass
    start = time.monotonic()
    def progress(status, remaining, total):
        if time.monotonic() - start > deadline_seconds:
            raise TimeoutError('Online backup budget exceeded; partial destination retained, not packaged')
    with closing(readonly(source)) as src, closing(sqlite3.connect(destination)) as dst:
        src.backup(dst, pages=64, progress=progress, sleep=.01)
    return round(time.monotonic()-start, 6)


def reject_secrets(path):
    tail = b''
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''):
            if TOKEN.search(tail+chunk):
                raise ValueError('Credential-like material detected; packaging blocked')
            tail = chunk[-512:]


def backup(sources, output, registry):
    if not sources or len(sources) > 8:
        raise ValueError('One to eight explicitly named DBs required')
    if any(not re.fullmatch(r'[a-z][a-z0-9_-]{0,39}', label) for label in sources):
        raise ValueError('Invalid source label')
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    pc_id, ids = identity(registry, sources)
    manifest = dict(format='v15-sqlite-backup',format_version=FORMAT,
                    backup_id=str(uuid.uuid4()), source_pc_id=pc_id,
                    created_at=datetime.now(timezone.utc).isoformat(), files=[],
                    consistency='Each database is an individual Online Backup API snapshot; no cross-DB transaction.',
                    merge_policy='QUARANTINE_ONLY; local integer IDs are not global identities')
    for label,source in sources.items():
        filename = label+'.db'
        destination = output/filename
        began = datetime.now(timezone.utc).isoformat()
        elapsed = snapshot(source,destination)
        description = describe(destination)
        reject_secrets(destination)
        manifest['files'].append(dict(filename=filename, original_filename=Path(source).name,
            source_database_id=ids[label], snapshot_started_at=began,
            snapshot_finished_at=datetime.now(timezone.utc).isoformat(), backup_seconds=elapsed,
            size_bytes=destination.stat().st_size, sha256=sha256(destination), **description))
    write_json(output/'manifest.json',manifest)
    reject_secrets(output/'manifest.json')
    archive=output/'v15-backup.zip'
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name in ['manifest.json']+[r['filename'] for r in manifest['files']]:
            z.write(output/name,name)
    digest=sha256(archive)
    with (output/'v15-backup.zip.sha256').open('x',encoding='ascii') as f:
        f.write(digest+'  v15-backup.zip\n')
    return dict(zip=str(archive),sha256=digest,manifest=manifest)


def restore(archive, expected_sha256, output, max_bytes=2*1024**3):
    """Verified restore into a NEW quarantine directory, never an operational DB."""
    if not re.fullmatch('[0-9a-f]{64}',expected_sha256) or sha256(archive)!=expected_sha256:
        raise ValueError('ZIP SHA-256 mismatch')
    output=Path(output).resolve()
    if output.exists():
        raise FileExistsError('Restore destination must not exist')
    with zipfile.ZipFile(archive) as z:
        infos=z.infolist(); names=[i.filename for i in infos]
        if len(infos)>10 or len(set(names))!=len(names) or sum(i.file_size for i in infos)>max_bytes:
            raise ValueError('ZIP size/count/duplicate limit')
        if any(not re.fullmatch(r'(manifest\.json|[a-z][a-z0-9_-]{0,39}\.db)',n) for n in names):
            raise ValueError('Unsafe ZIP entry')
        if any(i.flag_bits & 1 or ((i.external_attr >> 16)&0o170000)==0o120000 for i in infos):
            raise ValueError('Encrypted ZIP or symlink rejected')
        if 'manifest.json' not in names or z.getinfo('manifest.json').file_size>1024*1024:
            raise ValueError('Missing/oversized manifest')
        try:
            if z.testzip() is not None:
                raise ValueError('ZIP CRC check failed')
        except (zipfile.BadZipFile,zlib.error) as exc:
            raise ValueError('ZIP CRC/decompression check failed') from exc
        manifest=json.loads(z.read('manifest.json'))
        if manifest.get('format')!='v15-sqlite-backup' or manifest.get('format_version')!=FORMAT:
            raise ValueError('Unsupported backup format')
        records=manifest['files']
        expected=['manifest.json']+[r['filename'] for r in records]
        if len(set(expected))!=len(expected) or set(names)!=set(expected):
            raise ValueError('Manifest ZIP inventory mismatch')
        uuid.UUID(manifest['source_pc_id']);uuid.UUID(manifest['backup_id'])
        output.mkdir(parents=True,exist_ok=False)
        for name in names:
            # All names validated above; exclusive creation, no extractall.
            with (output/name).open('xb') as dst,z.open(name) as src:
                for block in iter(lambda:src.read(1024*1024), b''):
                    dst.write(block)
        for record in records:
            path=output/record['filename']
            uuid.UUID(record['source_database_id'])
            if path.stat().st_size!=record['size_bytes'] or sha256(path)!=record['sha256']:
                raise ValueError('DB size/SHA-256 mismatch; retained in quarantine')
            actual=describe(path)
            for key in ('schema_sha256','user_version','application_id','table_counts','foreign_key_violations'):
                if actual[key]!=record[key]:
                    raise ValueError('DB manifest mismatch; retained in quarantine')
        result=dict(status='VERIFIED_QUARANTINE',zip_sha256=expected_sha256,
                    source_pc_id=manifest['source_pc_id'],backup_id=manifest['backup_id'],
                    automatic_merge=False,files=[r['filename'] for r in records])
        write_json(output/'verification.json',result)
    return result


def compare(local_snapshot, incoming_snapshot):
    """Compare offline snapshots only. Never approves lineage or applies updates."""
    left,right=describe(local_snapshot),describe(incoming_snapshot)
    if left['schema_sha256']!=right['schema_sha256']:
        return dict(status='QUARANTINE_SCHEMA_MISMATCH',automatic_merge=False)
    tables={}
    with closing(readonly(local_snapshot,True)) as a,closing(readonly(incoming_snapshot,True)) as b:
        for table in left['table_counts']:
            if table=='sqlite_sequence':continue
            cols=list(a.execute(f'PRAGMA table_info("{table}")'))
            pk=[r[1] for r in sorted(cols,key=lambda r:r[5]) if r[5]]
            if not pk:
                tables[table]=dict(status='QUARANTINE_NO_PRIMARY_KEY');continue
            indices=[r[0] for key in pk for r in cols if r[1]==key]
            def rows(db):
                return {tuple(row[i] for i in indices):tuple(row) for row in db.execute(f'SELECT * FROM "{table}"')}
            x,y=rows(a),rows(b); shared=x.keys()&y.keys()
            tables[table]=dict(identical_keys=sum(x[k]==y[k] for k in shared),
                               conflicting_keys=sum(x[k]!=y[k] for k in shared),
                               local_only=len(x.keys()-y.keys()),incoming_only=len(y.keys()-x.keys()))
    return dict(status='QUARANTINE_REVIEW_REQUIRED',automatic_merge=False,tables=tables,
                note='IDs are DB-local. Different values may be tracking updates or identity collisions. Source lineage and FK remapping require human review.')


def main():
    p=argparse.ArgumentParser(description=__doc__); commands=p.add_subparsers(dest='command',required=True)
    b=commands.add_parser('backup');b.add_argument('--source',action='append',required=True,help='label=DB path')
    b.add_argument('--output',type=Path,required=True);b.add_argument('--registry',type=Path,required=True)
    r=commands.add_parser('restore');r.add_argument('--zip',type=Path,required=True)
    r.add_argument('--sha256',required=True);r.add_argument('--output',type=Path,required=True)
    c=commands.add_parser('compare');c.add_argument('--local-snapshot',type=Path,required=True)
    c.add_argument('--incoming-snapshot',type=Path,required=True)
    args=p.parse_args()
    if args.command=='backup':
        pairs=[value.split('=',1) for value in args.source]
        if any(len(v)!=2 for v in pairs) or len(dict(pairs))!=len(pairs):p.error('Unique label=path sources required')
        result=backup(dict(pairs),args.output,args.registry)
        result={k:v for k,v in result.items() if k!='manifest'}
    elif args.command=='restore':result=restore(args.zip,args.sha256,args.output)
    else:result=compare(args.local_snapshot,args.incoming_snapshot)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
