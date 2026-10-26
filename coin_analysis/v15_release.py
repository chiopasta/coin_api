"""Explicit private GitHub Release transport. Credentials remain in memory only.

Uses existing git credential helper (or GH_TOKEN/GITHUB_TOKEN). Never replaces a
tag, release or asset, changes visibility, deletes files, or schedules uploads.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request

from . import v15_transfer as transfer


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed=urllib.parse.urlsplit(newurl)
        if parsed.scheme!='https' or not (parsed.hostname=='github.com' or
                                          (parsed.hostname or '').endswith('.githubusercontent.com')):
            raise ValueError('Download redirect host rejected')
        result=super().redirect_request(req,fp,code,msg,headers,newurl)
        if urllib.parse.urlsplit(req.full_url).hostname!=parsed.hostname:
            result.remove_header('Authorization')
        return result


class GitHub:
    def __init__(self, repo):
        if not re.fullmatch(r'[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+',repo):
            raise ValueError('Expected owner/repository')
        self.repo=repo
        self.token=os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
        if not self.token:
            result=subprocess.run(['git','credential','fill'],input='protocol=https\nhost=github.com\n\n',
                capture_output=True,text=True,timeout=25,
                env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GCM_INTERACTIVE':'never'})
            fields=dict(line.split('=',1) for line in result.stdout.splitlines() if '=' in line)
            self.token=fields.get('password')
        if not self.token:raise ValueError('GitHub credential unavailable; use a credential manager')
        self.opener=urllib.request.build_opener(SafeRedirect())

    def request(self,path,method='GET',payload=None,binary=None,accept='application/vnd.github+json'):
        url=path if path.startswith('https://') else 'https://api.github.com'+path
        host=urllib.parse.urlsplit(url).hostname
        if host not in ('api.github.com','uploads.github.com'):
            raise ValueError('GitHub API host rejected')
        data=json.dumps(payload).encode() if payload is not None else binary
        headers={'Authorization':'Bearer '+self.token,'Accept':accept,'User-Agent':'V15-private-backup',
                 'X-GitHub-Api-Version':'2022-11-28'}
        if data is not None:headers['Content-Type']='application/json' if payload is not None else 'application/octet-stream'
        request=urllib.request.Request(url,data=data,headers=headers,method=method)
        return self.opener.open(request,timeout=60)

    def api(self,path,method='GET',payload=None,binary=None):
        with self.request(path,method,payload,binary) as response:return json.load(response)

    def private(self,write=False):
        repo=self.api('/repos/'+self.repo)
        if repo.get('private') is not True or repo.get('visibility')!='private' or repo.get('archived'):
            raise ValueError('Private, non-archived repository required; public upload blocked')
        if write and not repo.get('permissions',{}).get('push'):
            raise ValueError('Repository write permission unavailable')
        return repo

    def create_private(self):
        owner,name=self.repo.split('/')
        user=self.api('/user')
        if user['login'].casefold()!=owner.casefold():
            raise ValueError('Only authenticated personal-owner creation is supported')
        # Never change an existing repository or its visibility.
        try:self.api('/repos/'+self.repo)
        except urllib.error.HTTPError as exc:
            if exc.code!=404:raise
        else:raise FileExistsError('Repository already exists; not modified')
        self.api('/user/repos','POST',dict(name=name,private=True,auto_init=True,
            description='Private manual SQLite snapshots for V15 observation data; no secrets or source engine changes.'))
        repo=self.private(write=True)
        return dict(repository=self.repo,private=repo['private'],url=repo['html_url'])

    def absent(self,path):
        try:self.api(path)
        except urllib.error.HTTPError as exc:
            if exc.code==404:return
            raise
        raise FileExistsError('Tag/release already exists; no replacement allowed')

    def download_asset(self,asset,destination):
        destination=Path(destination)
        with destination.open('xb') as out:
            with self.request('/repos/'+self.repo+'/releases/assets/'+str(asset['id']),
                              accept='application/octet-stream') as response:
                received=0
                for block in iter(lambda:response.read(1024*1024),b''):
                    received+=len(block)
                    if received>asset['size'] or received>1024**3:
                        raise ValueError('Download size budget exceeded')
                    out.write(block)
        if destination.stat().st_size!=asset['size']:raise ValueError('Download truncated')
        digest=asset.get('digest')
        if digest and digest!='sha256:'+transfer.sha256(destination):
            raise ValueError('GitHub asset digest mismatch')

    def upload(self,archive,tag,download_directory):
        if not re.fullmatch(r'v15-backup-[A-Za-z0-9_.-]{1,100}',tag):
            raise ValueError('Explicit v15-backup- unique tag required')
        archive=Path(archive)
        checksum=archive.with_name(archive.name+'.sha256')
        expected=checksum.read_text(encoding='ascii').split()[0]
        download_directory=Path(download_directory)
        # Fully validate the local artifact before the first upload.
        transfer.restore(archive,expected,download_directory/'local-preflight')
        self.private(write=True)
        base='/repos/'+self.repo
        encoded=urllib.parse.quote(tag,safe='')
        self.absent(base+'/releases/tags/'+encoded)
        self.absent(base+'/git/ref/tags/'+encoded)
        release=self.api(base+'/releases','POST',dict(tag_name=tag,name=tag,draft=True,
            make_latest='false',body='Manual V15 SQLite Online Backup API snapshot.\n\n'
            'SHA-256 (`v15-backup.zip`): `'+expected+'`\n\n'
            'Restore only into a fresh quarantine directory; never overwrite or automatically merge operational DBs.'))
        upload_url=release['upload_url'].split('{')[0]
        assets=[]
        for path in (archive,checksum):
            if path.stat().st_size>1024**3:raise ValueError('Upload exceeds 1 GiB manual tool limit')
            # This release was just created by this invocation; no existing asset is modified.
            asset=self.api(upload_url+'?name='+urllib.parse.quote(path.name,safe=''),
                           'POST',binary=path.read_bytes())
            digest=asset.get('digest')
            if asset.get('state')!='uploaded' or asset['size']!=path.stat().st_size or (
                    digest and digest!='sha256:'+transfer.sha256(path)):
                raise ValueError('Upload receipt mismatch; draft retained, not published')
            assets.append(asset)
        self.download_asset(assets[0],download_directory/archive.name)
        self.download_asset(assets[1],download_directory/checksum.name)
        if (download_directory/checksum.name).read_bytes()!=checksum.read_bytes():
            raise ValueError('Downloaded checksum mismatch')
        verified=transfer.restore(download_directory/archive.name,expected,download_directory/'restored')
        self.private(write=True)
        published=self.api(base+'/releases/'+str(release['id']),'PATCH',dict(draft=False,make_latest='false'))
        return dict(repository=self.repo,private=True,tag=tag,release_id=release['id'],
                    url=published['html_url'],sha256=expected,download_verification=verified,
                    assets=[dict(id=a['id'],name=a['name'],size=a['size'],digest=a.get('digest')) for a in assets])

    def download(self,tag,output,expected_sha256=None):
        self.private()
        release=self.api('/repos/'+self.repo+'/releases/tags/'+urllib.parse.quote(tag,safe=''))
        assets={a['name']:a for a in release['assets']}
        if not {'v15-backup.zip','v15-backup.zip.sha256'}<=assets.keys():
            raise ValueError('Required backup assets missing')
        output=Path(output);output.mkdir(parents=True,exist_ok=False)
        for name in ('v15-backup.zip','v15-backup.zip.sha256'):
            self.download_asset(assets[name],output/name)
        expected=(output/'v15-backup.zip.sha256').read_text(encoding='ascii').split()[0]
        if expected_sha256 is not None and expected!=expected_sha256:
            raise ValueError('Pinned SHA-256 differs from Release checksum; quarantine retained')
        result=transfer.restore(output/'v15-backup.zip',expected,output/'restored')
        return dict(repository=self.repo,tag=tag,**result)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',required=True)
    commands=parser.add_subparsers(dest='command',required=True)
    commands.add_parser('preflight');commands.add_parser('create-private')
    upload=commands.add_parser('upload');upload.add_argument('--zip',type=Path,required=True)
    upload.add_argument('--tag',required=True);upload.add_argument('--verification-output',type=Path,required=True)
    download=commands.add_parser('download');download.add_argument('--tag',required=True)
    download.add_argument('--output',type=Path,required=True)
    download.add_argument('--sha256',help='Optional independently pinned ZIP SHA-256')
    args=parser.parse_args()
    try:
        client=GitHub(args.repo)
        if args.command=='create-private':result=client.create_private()
        elif args.command=='preflight':
            repo=client.private(write=True);result=dict(repository=client.repo,private=True,push=repo['permissions']['push'])
        elif args.command=='upload':result=client.upload(args.zip,args.tag,args.verification_output)
        else:result=client.download(args.tag,args.output,args.sha256)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except Exception as exc:
        # Never log request headers, credentials, signed redirect URLs, or response bodies.
        print(json.dumps(dict(status='FAILED',error=type(exc).__name__,http_status=getattr(exc,'code',None))))
        raise SystemExit(1)


if __name__=='__main__':main()
