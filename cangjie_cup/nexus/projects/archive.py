"""Bounded in-memory project archives; never extracts or executes user material."""
import io
from pathlib import PurePosixPath
import stat
import unicodedata
import zipfile

MAX_ARCHIVE=2*1024*1024
MAX_TOTAL=2*1024*1024
MAX_FILE=128*1024
MAX_FILES=100


def safe_name(name,directory=False):
    if not isinstance(name,str) or not name or len(name)>256 or any(ord(c)<32 or ord(c)==127 for c in name):
        raise ValueError('工程文件名为空、过长或包含控制字符')
    if '\\' in name or ':' in name:raise ValueError('工程路径不支持反斜线或驱动器前缀')
    clean=name[:-1] if directory and name.endswith('/') else name
    path=PurePosixPath(clean)
    if (path.is_absolute() or path.as_posix()!=clean or any(p in ('','..','.') or p.startswith('.') for p in clean.split('/'))):
        raise ValueError('工程路径必须为规范相对路径，不能穿越或包含隐藏材料')
    return clean


def read_entries(entries):
    if not isinstance(entries,dict) or not 1<=len(entries)<=MAX_FILES:raise ValueError('工程需1至100个文件')
    output={};seen=set();total=0;prefixes={}
    for raw,data in entries.items():
        name=safe_name(raw)
        key=unicodedata.normalize('NFC',name).casefold()
        if key in seen:raise ValueError('工程包含重复或文件系统规范化冲突路径')
        seen.add(key)
        parts=name.split('/')
        for index in range(1,len(parts)+1):
            prefix='/'.join(parts[:index]);normalized=unicodedata.normalize('NFC',prefix).casefold()
            if normalized in prefixes and prefixes[normalized]!=prefix:raise ValueError('工程父目录存在规范化冲突')
            prefixes[normalized]=prefix
        if not isinstance(data,bytes) or len(data)>MAX_FILE:raise ValueError('单个工程文件最多128KiB')
        total+=len(data)
        if total>MAX_TOTAL:raise ValueError('工程解压总大小最多2MiB')
        output[name]=data
    for name in output:
        if any(parent.as_posix() in output for parent in PurePosixPath(name).parents if parent.as_posix()!='.'):
            raise ValueError('工程文件与目录路径冲突')
    roots=[n[:-len('cjpm.toml')] for n in output if PurePosixPath(n).name=='cjpm.toml']
    if len(roots)!=1:raise ValueError('请选择只包含一个明确cjpm.toml构建根的工程')
    prefix=roots[0]
    if any(not n.startswith(prefix) for n in output):raise ValueError('工程存在构建根之外的材料')
    normalized={name[len(prefix):]:data for name,data in output.items()}
    for name,data in normalized.items():
        p=PurePosixPath(name)
        if p.name=='build.cj':raise ValueError('工程不允许build.cj构建脚本')
        if name in ('cjpm.toml','cjpm.lock') or p.suffix=='.md':continue
        if name.startswith('src/') and p.suffix=='.cj':
            if len(data)>65536:raise ValueError('仓颉文件最多64KiB')
            try:text=data.decode('utf-8')
            except UnicodeError:raise ValueError('仓颉源码必须为UTF-8') from None
            if '\0' in text or len(text.splitlines())>1000:raise ValueError('仓颉源码含空字节或超过1000行')
            continue
        raise ValueError('工程包含不支持的材料：'+name)
    if not any(n.startswith('src/') and n.endswith('.cj') and not n.endswith('_test.cj') for n in normalized):
        raise ValueError('工程缺少src下的生产仓颉源码')
    return normalized


def read_archive(data):
    if not isinstance(data,bytes) or not 0<len(data)<=MAX_ARCHIVE:raise ValueError('工程ZIP限2MiB')
    files={};seen=set();total=0
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos=archive.infolist()
            if not 1<=len(infos)<=MAX_FILES*2:raise ValueError('工程归档条目过多或为空')
            for info in infos:
                directory=info.is_dir();name=safe_name(info.filename,directory)
                mode=info.external_attr>>16;kind=stat.S_IFMT(mode)
                if kind not in (0,stat.S_IFREG,stat.S_IFDIR) or kind==stat.S_IFDIR and not directory:
                    raise ValueError('工程不允许链接或特殊文件')
                if info.flag_bits&1:raise ValueError('不支持加密工程归档')
                key=unicodedata.normalize('NFC',name).casefold()
                if key in seen:raise ValueError('归档包含重复或规范化冲突路径')
                seen.add(key)
                if directory:continue
                if kind==stat.S_IFREG and mode&0o111:raise ValueError('工程源文件不能有执行权限')
                if info.file_size>MAX_FILE or len(files)>=MAX_FILES:raise ValueError('工程文件数量或大小超限')
                total+=info.file_size
                if total>MAX_TOTAL:raise ValueError('工程解压总大小超过2MiB')
                with archive.open(info) as stream:content=stream.read(MAX_FILE+1)
                if len(content)!=info.file_size or len(content)>MAX_FILE:raise ValueError('归档文件实际大小与声明不符')
                files[name]=content
    except (zipfile.BadZipFile,zipfile.LargeZipFile,NotImplementedError,RuntimeError,OSError) as exc:
        raise ValueError('工程ZIP无效或压缩格式不支持') from exc
    return read_entries(files)
