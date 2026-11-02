"""Mounted-disk discovery and verified, opt-in data relocation. No mount/format commands."""
from __future__ import annotations
import json
import hashlib
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import uuid

STATE='.atlas-storage.json'


def ancestor(path):
    path=Path(path)
    while not path.exists():
        if path.is_symlink():raise RuntimeError('Data symlink target is not mounted: '+str(path))
        path=path.parent
    return path


def mountpoint(path):
    path=ancestor(path).resolve()
    while not os.path.ismount(path):path=path.parent
    return path


def load(root):
    file=Path(root)/STATE
    if not file.exists():return None
    value=json.loads(file.read_text())
    if not isinstance(value,dict) or not isinstance(value.get('data_dir'),str) or not isinstance(value.get('mountpoint'),str):
        raise RuntimeError('Invalid storage configuration: '+str(file))
    path=Path(value['data_dir'])
    if not os.path.ismount(value['mountpoint']) or not path.is_dir():
        raise RuntimeError('Selected data disk is not mounted or directory is missing: '+str(path)+'; refusing to fall back to the system disk.')
    return path.resolve()


def save(root,path):
    state=Path(root)/STATE
    payload={'data_dir':str(path),'mountpoint':str(mountpoint(path))}
    fd,temp=tempfile.mkstemp(prefix='.atlas-storage-',dir=root)
    try:
        with os.fdopen(fd,'w') as file:
            json.dump(payload,file);file.flush();os.fsync(file.fileno())
        os.replace(temp,state)
    finally:
        if Path(temp).exists():Path(temp).unlink()


def disk_candidates(current,tree=None):
    if tree is None:
        try:
            result=subprocess.run(['lsblk','--json','--bytes','--output','NAME,TYPE,MOUNTPOINTS,SIZE,FSTYPE,RO'],capture_output=True,text=True,timeout=5,check=True)
            tree=json.loads(result.stdout)
        except (OSError,ValueError,subprocess.SubprocessError):return []
    records=[]
    def walk(node,disk):
        if node.get('type')=='disk':disk=node['name']
        if disk and not node.get('ro'):
            for point in node.get('mountpoints') or []:
                if point and point.startswith('/'):
                    records.append((disk,Path(point),node.get('fstype')))
        for child in node.get('children',[]):walk(child,disk)
    for node in tree.get('blockdevices',[]):walk(node,None)
    system={disk for disk,p,_ in records if p==Path('/')}
    current=Path(current).resolve();candidates={}
    for disk,point,fs in records:
        if disk in system or not fs or str(point).startswith(('/boot','/snap','/proc','/sys','/dev')):continue
        try:
            if not point.is_dir() or not os.path.ismount(point) or not os.access(point,os.W_OK|os.X_OK):continue
            if point.stat().st_dev==ancestor(current).stat().st_dev:continue
            candidates[str(point)]={'mount':point,'disk':disk,'free':shutil.disk_usage(point).free}
        except OSError:continue
    return list(candidates.values())


def choose_path(current,interactive,choose,explicit=None):
    current=Path(current).resolve()
    candidates=disk_candidates(current)
    print('Data location: '+str(current),flush=True)
    print('Available space: '+f'{shutil.disk_usage(ancestor(current)).free/1024**3:.1f} GiB',flush=True)
    if explicit:
        selected=Path(explicit).expanduser()
        if not selected.is_absolute():raise RuntimeError('--data-dir requires an absolute path.')
    elif interactive:
        if not candidates:print('No other mounted writable disk detected; keep current location or enter a custom path.',flush=True)
        labels=['Keep current location']+[f"{item['mount']} ({item['disk']}, free {item['free']/1024**3:.1f} GiB)" for item in candidates]+['Custom directory path']
        index=choose('Database and snapshot location',labels)
        if index==0:return current
        if index==len(labels)-1:
            text=input('Enter absolute directory path (blank to cancel): ').strip()
            if not text:return current
            selected=Path(text).expanduser()
            if not selected.is_absolute():raise RuntimeError('Enter an absolute path.')
        else:selected=candidates[index-1]['mount']/'news-atlas-data'
    else:return current
    if any(ord(c)<32 for c in str(selected)):raise RuntimeError('Path cannot contain control characters.')
    selected=selected.resolve()
    if selected==current:return current
    if selected.is_relative_to(current) or current.is_relative_to(selected):raise RuntimeError('Source and target directories cannot contain each other.')
    if selected.exists() and (not selected.is_dir() or any(selected.iterdir())):
        raise RuntimeError('Target must be a new or empty directory; refusing to overwrite: '+str(selected))
    if not os.access(ancestor(selected),os.W_OK|os.X_OK):raise RuntimeError('Target path is not writable: '+str(selected))
    print('Will create/use: '+str(selected)+'\nRelocation retains original data as a backup and links project data/ to the new path.',flush=True)
    return selected


def copy_verified(source,target):
    """Caller stops its container first. SQLite backup also handles an existing WAL."""
    def copy_file(src,dst):
        src=Path(src);dst=Path(dst)
        with src.open('rb') as file:sqlite=file.read(16)==b'SQLite format 3\x00'
        if sqlite:
            with sqlite3.connect(src.as_uri()+'?mode=ro',uri=True) as old,sqlite3.connect(dst) as new:
                old.backup(new)
                if new.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise RuntimeError('SQLite verification failed: '+src.name)
            shutil.copystat(src,dst)
        else:
            shutil.copy2(src,dst)
            def digest(path):
                result=hashlib.sha256()
                with path.open('rb') as file:
                    for chunk in iter(lambda:file.read(1024*1024),b''):result.update(chunk)
                return result.digest()
            if digest(src)!=digest(dst):raise RuntimeError('File copy verification failed: '+src.name)
        return str(dst)
    def ignore(directory,names):
        ignored=[]
        for name in names:
            base=Path(directory)/name.rsplit('-',1)[0]
            if name.endswith(('-wal','-shm','-journal')) and base.is_file():
                with base.open('rb') as file:
                    if file.read(16)==b'SQLite format 3\x00':ignored.append(name)
        return ignored
    # Refuse links inside the store so a misplaced link cannot copy unrelated data.
    if any(p.is_symlink() for p in source.rglob('*')):raise RuntimeError('Data directory contains symbolic links; resolve them before relocation.')
    shutil.copytree(source,target,copy_function=copy_file,ignore=ignore)


def relocate(root,source,target):
    root,source,target=Path(root),Path(source).resolve(),Path(target).resolve()
    if source==target:return target
    if target.is_relative_to(source) or source.is_relative_to(target):raise RuntimeError('Source and target directories cannot contain each other.')
    if target.exists() and (not target.is_dir() or any(target.iterdir())):raise RuntimeError('Target directory is not empty; not relocated.')
    size=sum(p.stat().st_size for p in source.rglob('*') if p.is_file())
    if shutil.disk_usage(ancestor(target)).free<size+16*1024**2:raise RuntimeError('Insufficient free space on target disk.')
    target.parent.mkdir(parents=True,exist_ok=True)
    stage=target.parent/('.news-atlas-copy-'+uuid.uuid4().hex)
    backup=None;old_link=None;link=root/'data';temporary=root/('.data-link-'+uuid.uuid4().hex)
    try:
        copy_verified(source,stage)
        if target.exists():target.rmdir()  # only an empty, explicitly selected folder
        stage.rename(target)
        temporary.symlink_to(target,target_is_directory=True)
        if link.is_symlink():old_link=os.readlink(link)
        elif link.exists():
            backup=root/('.data-backup-'+uuid.uuid4().hex[:12]);link.rename(backup)
        try:
            os.replace(temporary,link)
            save(root,target)
        except BaseException:
            if link.is_symlink() and link.resolve()==target:link.unlink()
            if not link.exists() and not link.is_symlink():
                if old_link is not None:link.symlink_to(old_link,target_is_directory=True)
                elif backup:backup.rename(link)
            raise
        print('[OK] Data verified; '+str(link)+' → '+str(target),flush=True)
        print('Original data backup: '+str(backup or source)+' (remove manually after verifying the new location)',flush=True)
        return target
    finally:
        if temporary.is_symlink():temporary.unlink()
        if stage.exists():shutil.rmtree(stage)
