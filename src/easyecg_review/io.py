"""Strict parser for the uncompressed, single-lead Easy ECG SCP subset.

Format interpretation informed by majbthrd/easyecg2gdf (GPL-2.0-or-later).
CRC uses Python's standard CCITT implementation, not copied C routines.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
import binascii
import hashlib
import re
import struct
import zipfile
import numpy as np

class FormatError(ValueError):
    pass

@dataclass
class Block:
    number: int
    path: str
    start: datetime
    amplitude_nv: int
    interval_us: int
    words: np.ndarray
    sha256: str
    lead_code: int
    @property
    def centered(self):
        return ((self.words & 0x0fff).astype(np.int32) - 2048).astype(np.int16)

@dataclass
class Recording:
    index: int
    part: int
    blocks: list[Block]
    fs: float
    warnings: list[str] = field(default_factory=list)
    @property
    def name(self):
        return f"r{self.index:03d}_p{self.part:02d}_{self.start:%Y%m%d_%H%M%S}"
    @property
    def start(self): return self.blocks[0].start
    @property
    def duration(self): return sum(len(b.words) for b in self.blocks) / self.fs
    @property
    def raw(self): return np.concatenate([b.centered for b in self.blocks])
    @property
    def words(self): return np.concatenate([b.words for b in self.blocks])
    @property
    def scale(self): return self.blocks[0].amplitude_nv / 1e6

class InputSource:
    """Reads directory or ZIP without extracting untrusted paths."""
    def __init__(self, path: Path):
        self.path = path
        self.archive = None
        self.files = {}
        if path.is_file() and zipfile.is_zipfile(path):
            self.archive = zipfile.ZipFile(path)
            try:
                infos = self.archive.infolist()
                if len(infos) > 10000 or sum(i.file_size for i in infos) > 512 * 1024**2:
                    raise FormatError("ZIP exceeds safety limits (10000 entries / 512 MiB)")
                for info in infos:
                    name = info.filename
                    pp = PurePosixPath(name)
                    if pp.is_absolute() or '..' in pp.parts or '\\' in name:
                        raise FormatError(f"Unsafe archive path: {name}")
                    if info.is_dir(): continue
                    key = name.casefold()
                    if key in self.files: raise FormatError(f"Duplicate ZIP path: {name}")
                    self.files[key] = info
            except Exception:
                self.close()
                raise
        elif path.is_dir():
            for file in path.rglob('*'):
                if file.is_file():
                    if not file.resolve().is_relative_to(path.resolve()):
                        raise FormatError(f"File symlink outside input: {file}")
                    key = file.relative_to(path).as_posix().casefold()
                    if key in self.files: raise FormatError(f"Duplicate input path: {file}")
                    self.files[key] = file
        else:
            raise FormatError("Input must be an Easy ECG directory or ZIP")
        roots = [k for k in self.files if PurePosixPath(k).name == 'readme.txt']
        roots = [k for k in roots if any(re.search(r'ecg_\d+/\d+\.scp$', p) for p in self.files if p.startswith(k[:-10]))]
        if len(roots) != 1:
            self.close()
            raise FormatError("Expected exactly one device README.TXT with ECG directories")
        self.index_path = roots[0]
        self.root = self.index_path[:-len('readme.txt')]

    def read(self, key):
        value = self.files.get(key.casefold())
        if value is None: raise FormatError(f"Missing input file: {key}")
        size = value.file_size if self.archive else value.stat().st_size
        if size > 2 * 1024**2: raise FormatError(f"File exceeds 2 MiB limit: {key}")
        try:
            return self.archive.read(value) if self.archive else value.read_bytes()
        except (zipfile.BadZipFile,RuntimeError,NotImplementedError) as ex:
            raise FormatError(f'Cannot read ZIP member {key}: {ex}') from ex
    def close(self):
        if self.archive: self.archive.close()
    def __enter__(self): return self
    def __exit__(self, *args): self.close()


def parse_scp(data: bytes, number=1, path='memory') -> Block:
    if len(data) < 22: raise FormatError(f"{path}: truncated SCP header")
    crc, length = struct.unpack_from('<HI', data)
    if length != len(data): raise FormatError(f"{path}: file size mismatch")
    if binascii.crc_hqx(data[2:], 0xffff) != crc:
        raise FormatError(f"{path}: file CRC mismatch")
    sections = {}; positions = {}
    pos = 6
    while pos < length:
        if length - pos < 16: raise FormatError(f"{path}: truncated section header")
        check, sid, size = struct.unpack_from('<HHI', data, pos)
        if size < 16 or pos + size > length: raise FormatError(f"{path}: invalid section size")
        section = data[pos:pos+size]
        if binascii.crc_hqx(section[2:], 0xffff) != check:
            raise FormatError(f"{path}: section {sid} CRC mismatch")
        if sid in sections: raise FormatError(f"{path}: duplicate section {sid}")
        sections[sid] = section[16:]; positions[sid] = (size,pos+1)
        if sid == 0 and section[10:16] != b'SCPECG':
            raise FormatError(f"{path}: missing SCP signature")
        pos += size
    if not {0, 1, 2, 3, 6}.issubset(sections):
        raise FormatError(f"{path}: required SCP sections missing")
    pointers = sections[0]
    if len(pointers) % 10: raise FormatError(f'{path}: invalid pointer table')
    mapped = set()
    for i in range(0,len(pointers),10):
        sid,size,offset=struct.unpack_from('<HII',pointers,i)
        if size == 0 and offset == 0: continue
        if sid in mapped or positions.get(sid) != (size,offset):
            raise FormatError(f'{path}: inconsistent section pointer')
        mapped.add(sid)
    if mapped != set(sections): raise FormatError(f'{path}: missing section pointers')
    # Restrict to the exact raw table descriptor observed in this device family.
    if sections[2] != bytes.fromhex('0100010000100100000008000000'):
        raise FormatError(f"{path}: unsupported Huffman/compression table")
    lead = sections[3]
    if len(lead) != 12 or lead[0] != 1 or lead[1] != 4:
        raise FormatError(f"{path}: unsupported lead count/flags")
    first, last, lead_code = struct.unpack_from('<IIB', lead, 2)
    if first != 1 or lead[11] != 0: raise FormatError(f"{path}: unsupported lead layout")
    tags = {}; p = sections[1]; i = 0; terminated = False
    while i + 3 <= len(p):
        tag, size = struct.unpack_from('<BH', p, i); i += 3
        if i + size > len(p): raise FormatError(f"{path}: truncated metadata tag")
        if tag == 255:
            terminated = True; break
        if tag in tags: raise FormatError(f"{path}: duplicate metadata tag {tag}")
        tags[tag] = p[i:i+size]; i += size
    if not terminated or len(tags.get(25,b'')) != 4 or len(tags.get(26,b'')) != 3:
        raise FormatError(f"{path}: missing date/time metadata")
    try:
        start = datetime(*struct.unpack('<HBB', tags[25]), *tags[26])
    except ValueError as ex: raise FormatError(f"{path}: invalid device time") from ex
    p = sections[6]
    if len(p) < 8: raise FormatError(f"{path}: truncated signal header")
    amp, interval, diff, bimodal, size = struct.unpack_from('<HHBBH', p)
    if diff != 0 or bimodal != 0:
        raise FormatError(f"{path}: compressed/differential signal unsupported")
    if amp == 0 or not 1000 <= interval <= 20000 or size == 0 or size % 2 or size != len(p)-8:
        raise FormatError(f"{path}: invalid signal calibration/payload")
    if last-first+1 != size//2: raise FormatError(f"{path}: lead sample count mismatch")
    words = np.frombuffer(p[8:], dtype='<u2').copy()
    return Block(number, path, start, amp, interval, words, hashlib.sha256(data).hexdigest(), lead_code)


def parse_index(text: bytes):
    try: decoded = text.decode('ascii')
    except UnicodeError as ex: raise FormatError("README.TXT must be ASCII") from ex
    if 'Easy ECG Monitor' not in decoded: raise FormatError("Not an Easy ECG index")
    result=[]; seen=set(); ids=set()
    for line in decoded.splitlines():
        if '.scp' not in line.casefold(): continue
        match = re.fullmatch(r'\s*(\d+)\s+(\d+)\.scp\s+(\d+)\.scp\s*', line, re.I)
        if not match: raise FormatError(f"Malformed index line: {line!r}")
        idx, first, last = map(int,match.groups())
        if idx < 1 or idx in ids or first < 1 or last < first or last > 100000:
            raise FormatError("Invalid/duplicate index range")
        ids.add(idx)
        numbers=set(range(first,last+1))
        if seen & numbers: raise FormatError("Overlapping recording ranges")
        seen |= numbers; result.append((idx,first,last))
    total = re.search(r'Total records:\s*(\d+)', decoded)
    if not result or total is None or int(total[1]) != len(result):
        raise FormatError("Index record total mismatch")
    return result


def load_recordings(path: Path, allow_missing=False, selected_ids=None):
    recordings=[]; manifest={'input_name':path.name, 'time_basis':'embedded device local time; timezone unverified',
                            'sample_rate_policy':'150 Hz nominal for 6666 us, matching upstream converter',
                            'warnings':[], 'skipped':[], 'ranges':[], 'files':[]}
    if path.is_file():
        h=hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda:stream.read(1024**2),b''):h.update(chunk)
        manifest['archive_sha256']=h.hexdigest()
    with InputSource(path) as source:
        index_bytes=source.read(source.index_path)
        manifest['index_sha256']=hashlib.sha256(index_bytes).hexdigest()
        ranges=parse_index(index_bytes)
        selection=set(selected_ids) if selected_ids is not None else None
        if selection is not None:
            unknown=selection-{idx for idx,_,_ in ranges}
            if unknown:raise FormatError(f'Unknown recording IDs: {sorted(unknown)}')
            if not selection:raise FormatError('No recordings selected')
        inventory={}
        for key in source.files:
            if not key.startswith(source.root): continue
            match=re.fullmatch(r'ecg_\d+/(\d+)\.scp',key[len(source.root):],re.I)
            if match:
                n=int(match[1])
                if n in inventory: raise FormatError(f"Duplicate SCP number: {n}")
                inventory[n]=key
        expected={n for _,lo,hi in ranges for n in range(lo,hi+1)}
        extra=sorted(set(inventory)-expected)
        if extra: manifest['warnings'].append(f"Unindexed SCP files not exported: {extra}")
        for idx,lo,hi in ranges:
            manifest['ranges'].append({'index':idx,'from':lo,'to':hi})
            if selection is not None and idx not in selection:continue
            blocks=[];part=1; warnings=[]
            def flush():
                nonlocal blocks,part,warnings
                if blocks:
                    interval=blocks[0].interval_us
                    fs=150.0 if interval==6666 else 1e6/interval
                    if any(len(b.words)<1500 for b in blocks): raise FormatError('Segments shorter than 10s are unsupported in this release')
                    if fs != 150: raise FormatError("This release only supports the 150 Hz PC-80B profile")
                    recordings.append(Recording(idx,part,blocks,fs,warnings.copy()))
                    part+=1; blocks=[]; warnings=[]
            for n in range(lo,hi+1):
                key=inventory.get(n)
                try:
                    if key is None: raise FormatError(f"Missing SCP file number {n}")
                    block=parse_scp(source.read(key),n,key)
                except FormatError as ex:
                    if not allow_missing: raise
                    flush(); msg=str(ex);manifest['skipped'].append({'number':n,'reason':msg})
                    manifest['warnings'].append(msg);warnings.append('INCOMPLETE INPUT: '+msg);continue
                if blocks:
                    previous=blocks[-1]
                    expected_time=previous.start+timedelta(seconds=len(previous.words)/150.0)
                    delta=(block.start-expected_time).total_seconds()
                    same=(block.amplitude_nv,block.interval_us,block.lead_code)==(previous.amplitude_nv,previous.interval_us,previous.lead_code)
                    if abs(delta)>0.05 or not same:
                        msg=f"Recording {idx} split before SCP {n}: time offset {delta:+.3f}s or calibration change"
                        manifest['warnings'].append(msg);flush();warnings.append(msg)
                blocks.append(block)
                manifest['files'].append({'number':n,'path':key,'sha256':block.sha256,'start':block.start.isoformat(),
                    'samples':len(block.words),'amplitude_nv':block.amplitude_nv,'interval_us':block.interval_us,'lead_code':block.lead_code})
            flush()
    if not recordings: raise FormatError("No valid data to export")
    return recordings,manifest


def list_recordings(path: Path):
    """Fast selection inventory: validates index and first/last blocks only.

    Estimated duration assumes 30s blocks. Full validation happens exclusively
    for selected sessions during conversion; row metadata is never a completion
    certificate. This keeps corrupt, unselected sessions from blocking a run.
    """
    rows=[]
    with InputSource(path) as source:
        ranges=parse_index(source.read(source.index_path));inventory={}
        for key in source.files:
            if not key.startswith(source.root):continue
            match=re.fullmatch(r'ecg_\d+/(\d+)\.scp',key[len(source.root):],re.I)
            if match:
                n=int(match[1])
                if n in inventory:raise FormatError(f'Duplicate SCP number: {n}')
                inventory[n]=key
        for idx,lo,hi in ranges:
            count=hi-lo+1;missing=sum(n not in inventory for n in range(lo,hi+1))
            row={'index':idx,'from':lo,'to':hi,'expected_files':count,'missing_files':missing,
                 'start_device_local':None,'end_device_local':None,'duration_estimate_s':count*30.0,'error':None}
            try:
                first=parse_scp(source.read(inventory[lo]),lo,inventory[lo])
                last=first if lo==hi else parse_scp(source.read(inventory[hi]),hi,inventory[hi])
                row['start_device_local']=first.start.isoformat()
                row['end_device_local']=(last.start+timedelta(seconds=len(last.words)/150.0)).isoformat()
            except (KeyError,FormatError) as ex:row['error']=str(ex)
            rows.append(row)
    return rows
