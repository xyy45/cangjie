"""Download pinned official runtime archives into this project only."""
import hashlib
from pathlib import Path
import platform
import tarfile
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
ARCHIVES=[
    ('sdk.tar.gz','https://cangjie-lang.cn/v1/files/auth/downLoad?nsId=142267&fileName=cangjie-sdk-mac-aarch64-1.0.5.tar.gz&objectKey=698acea5bd66ae22b62330ae',
     'e07d22584237f065b30a771b7110a87a8931334c40be3a148090944ae916ed1f','sdk'),
    ('stdx.zip','https://gitcode.com/Cangjie/cangjie_stdx/releases/download/v1.0.5.1/cangjie-stdx-mac-aarch64-1.0.5.1.zip',
     '202b91110996c60de35f2dc07c278bc19a08df2029dc3376710c9f3e84121e7b','stdx')]


def main():
    if platform.system()!='Darwin' or platform.machine()!='arm64':
        raise SystemExit('This pinned runtime currently supports macOS ARM64 only')
    runtime=ROOT/'.runtime'
    downloads=runtime/'downloads'
    downloads.mkdir(parents=True,exist_ok=True)
    for name,url,expected,folder in ARCHIVES:
        archive=downloads/name
        if not archive.exists():
            print('Downloading',name,flush=True)
            with urllib.request.urlopen(url,timeout=60) as response, archive.open('wb') as stream:
                while chunk:=response.read(1024*1024): stream.write(chunk)
        if hashlib.sha256(archive.read_bytes()).hexdigest()!=expected:
            raise SystemExit(f'Checksum mismatch: {archive}; remove the failed download before retrying')
        destination=runtime/folder
        destination.mkdir(exist_ok=True)
        if name.endswith('.gz'):
            with tarfile.open(archive) as package: package.extractall(destination,filter='data')
        else:
            with zipfile.ZipFile(archive) as package:
                for entry in package.infolist():
                    path=Path(entry.filename)
                    if path.is_absolute() or '..' in path.parts or (entry.external_attr>>16)&0o170000==0o120000:
                        raise SystemExit('Unsafe archive entry')
                package.extractall(destination)
        print('Installed',folder,expected,flush=True)


if __name__=='__main__': main()
