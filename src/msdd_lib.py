"""Shared helpers for the MSDD notebooks (00 audit, 01 split, 02 train).

The notebooks inline this file (tools/build_notebooks.py writes it with %%writefile), so it must stay a
single self-contained module with only standard-library + numpy/pandas/PIL/yaml imports at module level.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import tarfile
import time
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

REPO_CLASSES = ['knocked', 'inclusion', 'misrun', 'burr', 'parting_line',
                'dater_collapse', 'pocking_mark', 'scraped', 'cutting', 'smudge']
IMG_EXT = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff'}
FRAME_RE = re.compile(r'^(?P<base>.+)_(?P<idx>\d{1,2})$')  # <capture>_<light index>
GB = 1024 ** 3


# --------------------------------------------------------------------------- environment
def detect_env() -> str:
    if Path('/kaggle/working').exists():
        return 'kaggle'
    if 'COLAB_RELEASE_TAG' in os.environ or 'google.colab' in sys.modules:
        return 'colab'
    return 'local'


def get_paths(local_root: str = '_local_work') -> dict:
    """work = fast scratch disk, persist = where results/checkpoints are mirrored every epoch."""
    env = os.environ.get('MSDD_ENV') or detect_env()
    if os.environ.get('MSDD_WORK'):
        work = Path(os.environ['MSDD_WORK'])
        persist = work / 'persist'
    elif env == 'kaggle':
        work, persist = Path('/kaggle/working'), Path('/kaggle/working/persist')
    elif env == 'colab':
        work, persist = Path('/content'), Path('/content/drive/MyDrive/msdd')
        if not Path('/content/drive/MyDrive').exists():
            try:
                from google.colab import drive  # type: ignore
                drive.mount('/content/drive')
            except Exception as e:  # noqa: BLE001
                print('WARNING: Drive not mounted, persistence falls back to /content/persist:', e)
                persist = Path('/content/persist')
    else:
        work = Path(local_root).resolve()
        persist = work / 'persist'
    persist.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    return dict(env=env, work=work, persist=persist)


def free_gb(path) -> float:
    p = Path(path)
    while not p.exists():
        p = p.parent
    return shutil.disk_usage(p).free / GB


def dir_size(path) -> int:
    total = 0
    for dp, _, fns in os.walk(path):
        for f in fns:
            try:
                total += os.path.getsize(os.path.join(dp, f))
            except OSError:
                pass
    return total


def sha256_file(path, chunk=1 << 24) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(chunk), b''):
            h.update(b)
    return h.hexdigest()


# --------------------------------------------------------------------------- download
MAGIC = {b'PK\x03\x04': 'zip', b'PK\x05\x06': 'zip(empty)', b'7z\xbc\xaf\x27\x1c': '7z',
         b'Rar!': 'rar', b'\x1f\x8b': 'gzip', b'BZh': 'bzip2', b'\xfd7zXZ': 'xz'}


def sniff(head: bytes) -> str:
    for m, name in MAGIC.items():
        if head.startswith(m):
            return name
    if len(head) > 262 and head[257:262] == b'ustar':
        return 'tar'
    low = head[:512].lower()
    if b'<!doctype html' in low or b'<html' in low:
        return 'HTML (login/blocked page, NOT the data)'
    return 'unknown'


def probe_url(url: str, nbytes: int = 4 * 1024 * 1024, headers: dict | None = None) -> dict:
    """Fetch only the first few MB and report status/content type so a login page is caught early."""
    import requests
    h = {'Range': f'bytes=0-{nbytes - 1}', 'User-Agent': 'Mozilla/5.0'}
    h.update(headers or {})
    r = requests.get(url, headers=h, stream=True, timeout=60, allow_redirects=True)
    body = b''
    for chunk in r.iter_content(1 << 16):
        body += chunk
        if len(body) >= nbytes:
            break
    r.close()
    total = None
    cr = r.headers.get('Content-Range')
    if cr and '/' in cr:
        try:
            total = int(cr.split('/')[-1])
        except ValueError:
            pass
    if total is None and r.headers.get('Content-Length') and r.status_code == 200:
        total = int(r.headers['Content-Length'])
    info = dict(status=r.status_code, content_type=r.headers.get('Content-Type'), total_bytes=total,
                accepts_ranges=(r.status_code == 206) or r.headers.get('Accept-Ranges') == 'bytes',
                sniffed=sniff(body), final_url=r.url.split('?')[0], got_bytes=len(body))
    print('PROBE', json.dumps(info, indent=1))
    if info['status'] >= 400 or info['sniffed'].startswith('HTML'):
        raise RuntimeError('URL did not return archive bytes (status/content type above). '
                           'It is probably a login page, an expired link or a blocked request. Get a fresh link.')
    if not info['accepts_ranges']:
        print('WARNING: server ignored Range; resume (-c) may restart from zero.')
    return info


def download_url(url: str, dest: str | Path, retries: int = 6) -> Path:
    """wget -c / curl -C - with retries. Resumes partial files."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tool = shutil.which('wget')
    for attempt in range(1, retries + 1):
        if tool:
            cmd = ['wget', '-c', '--tries=3', '--retry-connrefused', '--timeout=60', '--waitretry=5',
                   '-q', '--show-progress', '-O', str(dest), url]
        else:
            cmd = ['curl', '-L', '-C', '-', '--retry', '5', '--retry-delay', '5', '-o', str(dest), url]
        print(f'[download attempt {attempt}/{retries}]', ' '.join(cmd[:3]), '...')
        rc = subprocess.call(cmd)
        if rc == 0:
            return dest
        time.sleep(min(60, 5 * attempt))
    raise RuntimeError(f'download failed after {retries} attempts: {dest} ({dest.stat().st_size if dest.exists() else 0} bytes on disk)')


def download_gdown(url_or_id: str, dest: str | Path) -> Path:
    import gdown  # type: ignore
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    out = gdown.download(url_or_id if 'http' in url_or_id else None, str(dest), id=None if 'http' in url_or_id else url_or_id,
                         fuzzy=True, resume=True, quiet=False)
    if not out:
        raise RuntimeError('gdown returned nothing (quota exceeded or link not public)')
    return Path(out)


def ensure_7z():
    """RAR/7z need the 7z binary (apt p7zip-full). Installed on demand on Colab/Kaggle (both run as root or with sudo)."""
    if shutil.which('7z'):
        return
    print('installing p7zip-full for RAR/7z extraction ...')
    cmd = ['apt-get', 'install', '-y', '-q', 'p7zip-full']
    if os.geteuid() != 0:
        cmd = ['sudo'] + cmd
    subprocess.check_call(['sh', '-c', 'apt-get update -q >/dev/null 2>&1; ' + ' '.join(cmd) + ' >/dev/null 2>&1'])
    if not shutil.which('7z'):
        raise RuntimeError('7z is not available; install p7zip-full manually')


def verify_archive(path: str | Path, expected_bytes: int | None = None) -> dict:
    path = Path(path)
    size = path.stat().st_size
    res = dict(path=str(path), bytes=size, kind=None, ok=False)
    with open(path, 'rb') as f:
        head = f.read(512)
    res['kind'] = sniff(head)
    if expected_bytes and size != expected_bytes:
        res['warning'] = f'size {size} != expected {expected_bytes}'
    if res['kind'].startswith('zip'):
        with zipfile.ZipFile(path) as z:
            bad = z.testzip()
            res['ok'] = bad is None
            res['n_members'] = len(z.namelist())
            res['first_bad'] = bad
    elif res['kind'] in ('tar', 'gzip', 'bzip2', 'xz'):
        res['ok'] = tarfile.is_tarfile(path)
    elif res['kind'] in ('7z', 'rar'):
        ensure_7z()
        res['ok'] = subprocess.call(['7z', 't', '-bd', str(path)], stdout=subprocess.DEVNULL) == 0
    else:
        res['ok'] = False
    print('VERIFY', res)
    if not res['ok']:
        raise RuntimeError(f'archive failed verification: {res}')
    return res


def extract_archive(path: str | Path, out_dir: str | Path, delete_after: bool = False) -> Path:
    path, out_dir = Path(path), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(path, 'rb') as f:
        kind = sniff(f.read(512))
    if kind.startswith('zip'):
        with zipfile.ZipFile(path) as z:
            z.extractall(out_dir)
    elif kind in ('tar', 'gzip', 'bzip2', 'xz'):
        with tarfile.open(path) as t:
            t.extractall(out_dir, filter='data') if sys.version_info >= (3, 12) else t.extractall(out_dir)
    elif kind in ('7z', 'rar'):
        ensure_7z()
        subprocess.check_call(['7z', 'x', '-y', f'-o{out_dir}', str(path)])
    else:
        raise RuntimeError(f'cannot extract {path}: {kind}')
    if delete_after:
        path.unlink()
    return out_dir


def disk_report(paths) -> list[dict]:
    rows = []
    for p in paths:
        if Path(p).exists():
            u = shutil.disk_usage(p)
            rows.append(dict(path=str(p), free_gb=round(u.free / GB, 1), total_gb=round(u.total / GB, 1)))
    print('DISK', json.dumps(rows))
    return rows


# --------------------------------------------------------------------------- persistence of the verified dataset
def choose_persistence(data_bytes: int, env: str, persist_limit_gb: float | None = None) -> dict:
    """Pick where the verified data should live so later sessions never touch SciDB.

    Decision uses *measured* size and the free space we can measure. Kaggle's private-dataset quota cannot be measured
    from inside a notebook, so for Kaggle the check is against the 20 GB /kaggle/working output limit that a
    dataset-from-output has to fit in (documented Kaggle limit; confirm on your account).
    """
    need_gb = data_bytes / GB
    if env == 'colab':
        free = free_gb('/content/drive/MyDrive') if Path('/content/drive/MyDrive').exists() else 0
        ok = free >= need_gb * 1.1
        choice = dict(target='drive', ok=ok, need_gb=round(need_gb, 2), free_gb=round(free, 1))
    elif env == 'kaggle':
        limit = persist_limit_gb or 20.0
        ok = need_gb <= limit * 0.9
        choice = dict(target='kaggle_private_dataset', ok=ok, need_gb=round(need_gb, 2), limit_gb=limit)
    else:
        choice = dict(target='local_dir', ok=True, need_gb=round(need_gb, 2))
    choice['scope'] = 'all' if choice['ok'] else 'training_only'
    print('PERSISTENCE CHOICE', json.dumps(choice))
    return choice


def write_manifest(files: list[Path], out_dir: str | Path, kind: str) -> dict:
    out_dir = Path(out_dir)
    rows = [dict(name=Path(f).name, bytes=Path(f).stat().st_size, sha256=sha256_file(f)) for f in files]
    m = dict(kind=kind, files=rows, total_bytes=sum(r['bytes'] for r in rows))
    (out_dir / 'MANIFEST.json').write_text(json.dumps(m, indent=1))
    return m


def make_tar_shards(src_dir: str | Path, out_dir: str | Path, shard_gb: float = 2.0, subset: list[Path] | None = None) -> dict:
    """Used only when the verified data is an extracted tree (no original archive to keep): pack into tar shards."""
    src_dir, out_dir = Path(src_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    files = subset if subset is not None else sorted(p for p in src_dir.rglob('*') if p.is_file())
    limit, idx, cur_bytes, tf, made = int(shard_gb * GB), 0, 0, None, []
    for p in files:
        sz = p.stat().st_size
        if tf is None or (cur_bytes + sz > limit and cur_bytes > 0):
            if tf:
                tf.close()
            name = out_dir / f'msdd_shard_{idx:03d}.tar'
            made.append(name)
            tf, cur_bytes, idx = tarfile.open(name, 'w'), 0, idx + 1
        tf.add(p, arcname=str(p.relative_to(src_dir)))
        cur_bytes += sz
    if tf:
        tf.close()
    return write_manifest(made, out_dir, 'tar_shards')


def restore_from_persistent(persist_dir: str | Path, dest: str | Path, verify_hash: bool = True) -> Path:
    """Notebooks 01/02: rebuild a fast local working copy from the persistent copy (archives listed in MANIFEST.json).
    If the platform already unpacked an archive (a directory with the same stem exists) that tree is used."""
    persist_dir, dest = Path(persist_dir), Path(dest)
    man = persist_dir / 'MANIFEST.json'
    if not man.exists():
        raise FileNotFoundError(f'{man} not found. Attach the persistent dataset created by notebook 00 (see HANDOFF.md).')
    done = dest / '.restored_ok'
    if done.exists():
        return dest
    m = json.loads(man.read_text())
    need = m['total_bytes'] / GB
    print(f"restoring {need:.1f} GB from {persist_dir}; free on target {free_gb(dest.parent):.1f} GB")
    dest.mkdir(parents=True, exist_ok=True)
    for r in m['files']:
        fp = persist_dir / r['name']
        unpacked = persist_dir / Path(r['name']).stem
        if not fp.exists() and unpacked.is_dir():
            print(f"{r['name']}: platform already unpacked it; linking {unpacked}")
            os.symlink(unpacked, dest / unpacked.name)
            continue
        if verify_hash:
            if fp.stat().st_size != r['bytes'] or sha256_file(fp) != r['sha256']:
                raise RuntimeError(f'integrity check failed for {fp}')
        extract_archive(fp, dest)
        print('extracted', r['name'])
    done.write_text('ok')
    return dest


def try_kaggle_dataset_create(folder: str | Path, slug: str, title: str, private: bool = True) -> dict:
    """Best effort: needs Kaggle Secrets KAGGLE_USERNAME / KAGGLE_KEY (Add-ons > Secrets). Untested here."""
    try:
        from kaggle_secrets import UserSecretsClient  # type: ignore
        sec = UserSecretsClient()
        os.environ['KAGGLE_USERNAME'] = sec.get_secret('KAGGLE_USERNAME')
        os.environ['KAGGLE_KEY'] = sec.get_secret('KAGGLE_KEY')
    except Exception as e:  # noqa: BLE001
        return dict(done=False, reason=f'no Kaggle secrets ({type(e).__name__}); use the manual steps in HANDOFF.md')
    folder = Path(folder)
    meta = dict(title=title, id=f"{os.environ['KAGGLE_USERNAME']}/{slug}", licenses=[{'name': 'CC-BY-4.0'}])
    (folder / 'dataset-metadata.json').write_text(json.dumps(meta))
    cmd = ['kaggle', 'datasets', 'create', '-p', str(folder)] + ([] if private else ['--public'])
    rc = subprocess.call(cmd)
    return dict(done=rc == 0, slug=meta['id'], rc=rc)


# --------------------------------------------------------------------------- audit
def norm_name(s: str) -> str:
    return re.sub(r'[\s\-]+', '_', str(s).strip().lower())


def find_files(root: Path):
    for dp, dn, fns in os.walk(root):
        dn[:] = [d for d in dn if not d.startswith('.') and d != '__MACOSX']
        for f in fns:
            if not f.startswith('.') and not f.startswith('._'):
                yield Path(dp) / f


def img_header(path: Path):
    from PIL import Image
    with Image.open(path) as im:
        return im.size, im.mode, getattr(im, 'n_frames', 1)


def parse_yolo_file(path: Path):
    """returns (rows, problems); rows=[(cls, cx, cy, w, h)]"""
    rows, problems = [], []
    try:
        txt = path.read_text().strip().splitlines()
    except Exception as e:  # noqa: BLE001
        return rows, [f'unreadable: {e}']
    for i, ln in enumerate(txt):
        parts = ln.split()
        if not parts:
            continue
        try:
            vals = [float(x) for x in parts]
        except ValueError:
            problems.append(f'line {i + 1}: non-numeric')
            continue
        if len(vals) != 5:
            problems.append(f'line {i + 1}: {len(vals)} fields (polygon/conf?)')
            continue
        c = vals[0]
        if c != int(c) or c < 0:
            problems.append(f'line {i + 1}: bad class {c}')
            continue
        if not all(0 <= v <= 1 for v in vals[1:]):
            problems.append(f'line {i + 1}: coords outside [0,1]')
        rows.append((int(c), *vals[1:]))
    return rows, problems


def read_class_names(root: Path) -> tuple[list[str] | None, str | None]:
    """Look for names in dataset yaml / classes.txt / obj.names / VOC / COCO. Returns (names, source)."""
    import yaml
    for p in find_files(root):
        low = p.name.lower()
        if p.suffix in ('.yaml', '.yml'):
            try:
                d = yaml.safe_load(p.read_text())
                if isinstance(d, dict) and 'names' in d:
                    n = d['names']
                    names = [n[k] for k in sorted(n)] if isinstance(n, dict) else list(n)
                    return [str(x) for x in names], str(p.relative_to(root))
            except Exception:  # noqa: BLE001
                pass
        if low in ('classes.txt', 'obj.names', 'names.txt', 'labels.txt'):
            names = [x.strip() for x in p.read_text().splitlines() if x.strip()]
            if names:
                return names, str(p.relative_to(root))
    return None, None


def audit_dataset(root: str | Path, class_names_override: list[str] | None = None, size_sample: int = 3000,
                  licence: str = '', citation: str = '', seed: int = 0) -> tuple[dict, list[dict]]:
    """Layout-agnostic audit. Pairs images and labels by stem; treats `<capture>_<0..N>` groups as raw frames."""
    root = Path(root)
    rng = random.Random(seed)
    files = list(find_files(root))
    ext_count = Counter(p.suffix.lower() for p in files)
    dir_ext = defaultdict(Counter)
    for p in files:
        rel = p.relative_to(root).parts
        dir_ext['/'.join(rel[:-1][:2]) or '.'][p.suffix.lower()] += 1
    imgs = [p for p in files if p.suffix.lower() in IMG_EXT]
    total_bytes = sum(p.stat().st_size for p in files)

    # raw frame groups: <base>_<idx>.<ext> with >=4 contiguous indices in 0..31, where base has no standalone image
    stems = {p.stem for p in imgs}
    groups = defaultdict(set)
    for p in imgs:
        m = FRAME_RE.match(p.stem)
        if m:
            groups[(p.parent, m['base'])].add(int(m['idx']))
    frame_groups = {k: v for k, v in groups.items() if len(v) >= 4 and max(v) < 32 and min(v) in (0, 1)
                    and len(v) >= max(v) - min(v) + 1 - 1}
    frame_stems = {f'{b}_{i}' for (_, b), v in frame_groups.items() for i in v}
    frame_files = [p for p in imgs if p.stem in frame_stems]
    det_imgs = [p for p in imgs if p.stem not in frame_stems]
    channels_per_capture = Counter(len(v) for v in frame_groups.values())
    base_has_pseudo = sum(1 for (_, b) in frame_groups if b in stems)

    # image headers (sample)
    sample = det_imgs if len(det_imgs) <= size_sample else rng.sample(det_imgs, size_sample)
    sizes, modes, hdr_err = Counter(), Counter(), 0
    size_of = {}
    for p in sample:
        try:
            wh, mode, nfr = img_header(p)
            sizes[f'{wh[0]}x{wh[1]}'] += 1
            modes[mode] += 1
            size_of[p] = wh
        except Exception:  # noqa: BLE001
            hdr_err += 1
    fsample = frame_files if len(frame_files) <= 500 else rng.sample(frame_files, 500)
    fsizes, fmodes = Counter(), Counter()
    for p in fsample:
        try:
            wh, mode, _ = img_header(p)
            fsizes[f'{wh[0]}x{wh[1]}'] += 1
            fmodes[mode] += 1
        except Exception:  # noqa: BLE001
            pass

    # labels
    txt = [p for p in files if p.suffix.lower() == '.txt' and p.name.lower() not in
           ('classes.txt', 'obj.names', 'names.txt', 'labels.txt', 'train.txt', 'val.txt', 'test.txt')]
    xml = [p for p in files if p.suffix.lower() == '.xml']
    js = [p for p in files if p.suffix.lower() == '.json']
    label_formats = {k: n for k, n in (('yolo_txt', len(txt)), ('voc_xml', len(xml)), ('json(coco?)', len(js))) if n}
    names, names_src = read_class_names(root)
    if class_names_override:
        names, names_src = list(class_names_override), 'notebook override'

    warnings = []
    label_by_stem = defaultdict(list)
    for p in txt:
        label_by_stem[p.stem].append(p)
    dup_label_stems = {k: v for k, v in label_by_stem.items() if len(v) > 1}
    img_by_stem = defaultdict(list)
    for p in det_imgs:
        img_by_stem[p.stem].append(p)
    dup_img_stems = {k: len(v) for k, v in img_by_stem.items() if len(v) > 1}
    imgs_wo_label = sorted(s for s in img_by_stem if s not in label_by_stem)
    labels_wo_img = sorted(s for s in label_by_stem if s not in img_by_stem and s not in frame_stems)

    inst, small, per_cls_small, wh_px, bad_files = Counter(), 0, Counter(), [], {}
    empty_labels, items = 0, []
    imgs_with_boxes = 0
    n_boxes = 0
    for stem, plist in label_by_stem.items():
        lp = plist[0]
        rows, probs = parse_yolo_file(lp)
        if probs:
            bad_files[str(lp.relative_to(root))] = probs[:3]
        if not rows:
            empty_labels += 1
        else:
            imgs_with_boxes += 1
        ip = img_by_stem.get(stem, [None])[0]
        wh = size_of.get(ip)
        if ip is not None and wh is None:
            try:
                wh = img_header(ip)[0]
            except Exception:  # noqa: BLE001
                wh = None
        for c, cx, cy, w, h in rows:
            inst[c] += 1
            n_boxes += 1
            if wh:
                sc = 640 / max(wh)
                wp, hp = w * wh[0] * sc, h * wh[1] * sc
                wh_px.append((c, wp, hp))
                if min(wp, hp) < 16:
                    small += 1
                    per_cls_small[c] += 1
    # items for the split notebook: one row per detection image
    cls_by_stem = {}
    for stem, plist in label_by_stem.items():
        rows, _ = parse_yolo_file(plist[0])
        cls_by_stem[stem] = rows
    for p in sorted(det_imgs):
        rows = cls_by_stem.get(p.stem)
        lp = label_by_stem[p.stem][0] if p.stem in label_by_stem else None
        items.append(dict(img=str(p.relative_to(root)), label=str(lp.relative_to(root)) if lp else '',
                          n_boxes=len(rows) if rows is not None else 0,
                          classes=';'.join(str(r[0]) for r in (rows or []))))

    ids = sorted(inst)
    # box-size distribution (min side at 640 letterbox)
    import numpy as np
    mins = np.array([min(w, h) for _, w, h in wh_px]) if wh_px else np.array([])
    box_stats = {}
    if mins.size:
        box_stats = dict(n=int(mins.size), min_side_px_640_quantiles={q: round(float(np.quantile(mins, q / 100)), 1)
                                                                  for q in (1, 5, 25, 50, 75, 95, 99)},
                         frac_below_16px=round(small / mins.size, 4))
    shipped_split = {}
    for p in det_imgs:
        for part in p.relative_to(root).parts[:-1]:
            if part.lower().startswith(('train', 'val', 'test')):
                shipped_split.setdefault(re.split(r'[_\-]', part.lower())[0], 0)
                shipped_split[re.split(r'[_\-]', part.lower())[0]] += 1
                break

    class_check = check_classes(names, ids)
    audit = dict(
        root=str(root), total_files=len(files), total_bytes=total_bytes, total_gb=round(total_bytes / GB, 3),
        ext_counts=dict(ext_count), layout_top=dict((k, dict(v)) for k, v in sorted(dir_ext.items())[:60]),
        n_images_all=len(imgs), n_detection_images=len(det_imgs), n_raw_frame_files=len(frame_files),
        raw_frames=dict(n_groups=len(frame_groups), channels_per_capture=dict(channels_per_capture),
                        groups_with_standalone_pseudo_image=base_has_pseudo,
                        frame_sizes=dict(fsizes), frame_modes=dict(fmodes),
                        note='heuristic: <base>_<k>.<ext> with >=4 contiguous k in 0..31'),
        detection_image_sizes_sampled=dict(sizes), detection_image_modes_sampled=dict(modes), header_errors=hdr_err,
        label_formats=label_formats, class_names=names, class_names_source=names_src, class_ids_in_labels=ids,
        instances_per_class={str(k): inst[k] for k in ids}, n_boxes=n_boxes,
        images_without_label_file=len(imgs_wo_label), label_files_without_image=len(labels_wo_img),
        examples_images_without_label=imgs_wo_label[:10], examples_labels_without_image=labels_wo_img[:10],
        empty_label_files=empty_labels, images_with_boxes=imgs_with_boxes,
        duplicate_image_stems=len(dup_img_stems), duplicate_label_stems=len(dup_label_stems),
        label_files_with_problems=len(bad_files), label_problem_examples=dict(list(bad_files.items())[:10]),
        box_size=box_stats, small_box_frac_640=box_stats.get('frac_below_16px'),
        small_box_per_class={str(k): per_cls_small[k] for k in sorted(per_cls_small)},
        shipped_split_dirs=shipped_split, licence=licence, citation=citation, class_check=class_check,
        warnings=warnings,
    )
    if 'yolo_txt' not in label_formats:
        audit['warnings'].append('No YOLO txt labels found; box statistics are empty. Phase 2 needs a converter.')
    return audit, items


def check_classes(names, ids) -> dict:
    ref = [norm_name(n) for n in REPO_CLASSES]
    if names:
        got = [norm_name(n) for n in names]
        if set(got) == set(ref):
            return dict(status='match', order_matches=got == ref, names=names)
        return dict(status='differ', reason='names differ from the repo list', repo=REPO_CLASSES, found=names,
                    only_in_repo=sorted(set(ref) - set(got)), only_in_data=sorted(set(got) - set(ref)))
    if ids and (len(ids) != len(REPO_CLASSES) or max(ids) >= len(REPO_CLASSES)):
        return dict(status='differ', reason=f'no names found; {len(ids)} class ids {ids} vs {len(REPO_CLASSES)} in repo', repo=REPO_CLASSES)
    return dict(status='names_unknown', reason='no class names found in the data; cannot confirm against the repo list', ids=ids)


def write_audit(audit: dict, items: list[dict], out_dir: str | Path):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'audit.json').write_text(json.dumps(audit, indent=1, default=str))
    with open(out_dir / 'items.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['img', 'label', 'n_boxes', 'classes'])
        w.writeheader()
        w.writerows(items)
    a = audit
    md = [f"# MSDD audit report", '',
          f"- root: `{a['root']}`  | files: {a['total_files']}  | size: {a['total_gb']} GB",
          f"- images: {a['n_images_all']} total = {a['n_detection_images']} detection images + {a['n_raw_frame_files']} raw frame files",
          f"- raw multi-channel captures found: {a['raw_frames']['n_groups']} groups; channels per capture: {a['raw_frames']['channels_per_capture']}; groups that also have a standalone pseudo-colour image: {a['raw_frames']['groups_with_standalone_pseudo_image']}",
          f"- detection image sizes (sampled): {a['detection_image_sizes_sampled']}; modes: {a['detection_image_modes_sampled']}",
          f"- raw frame sizes (sampled): {a['raw_frames']['frame_sizes']}; modes: {a['raw_frames']['frame_modes']}",
          f"- label formats: {a['label_formats']}",
          f"- class names: {a['class_names']} (source: {a['class_names_source']}); class ids in labels: {a['class_ids_in_labels']}",
          f"- images without a label file: {a['images_without_label_file']} (legitimate if they are defect-free); label files without an image: {a['label_files_without_image']}; empty label files: {a['empty_label_files']}",
          f"- duplicate image stems: {a['duplicate_image_stems']}; duplicate label stems: {a['duplicate_label_stems']}; label files with problems: {a['label_files_with_problems']}",
          f"- boxes: {a['n_boxes']}; instances per class id: {a['instances_per_class']}",
          f"- box min-side at 640 px: {a['box_size']}; boxes under 16 px: {a['small_box_frac_640']}; per class: {a['small_box_per_class']}",
          f"- shipped split directories (image counts): {a['shipped_split_dirs']}",
          f"- licence: {a['licence'] or '(not recorded)'}", f"- citation: {a['citation'] or '(not recorded)'}",
          f"- CLASS CHECK vs repo's 10 names: **{a['class_check']['status']}** {json.dumps(a['class_check'])}", '']
    if a['warnings']:
        md += ['## Warnings'] + [f'- {w}' for w in a['warnings']]
    (out_dir / 'audit_report.md').write_text('\n'.join(md))
    return out_dir


# --------------------------------------------------------------------------- split
DEFAULT_GROUP_REGEX = r'^(\d{8}_\d{6})'


def group_key(img_rel: str, regex: str | None) -> str:
    stem = Path(img_rel).stem
    m = FRAME_RE.match(stem)
    if regex:
        mm = re.search(regex, stem)
        if mm:
            return mm.group(1) if mm.groups() else mm.group(0)
    return stem


def _features(item_classes: list[int]) -> Counter:
    c = Counter({f'c{k}': v for k, v in Counter(item_classes).items()})
    c['img'] = 1
    if not item_classes:
        c['bg'] = 1
    return c


def stratified_group_split(items: list[dict], group_regex: str | None, ratios=(0.70, 0.15, 0.15), seed=0,
                           names=('train', 'val', 'test'), fixed: dict[str, str] | None = None) -> dict:
    """Greedy multi-label stratification at group level. items: dicts with img, classes('1;2'). Deterministic.
    fixed: optional {group: split} to pin groups (used when MSDD ships a val split)."""
    rng = random.Random(seed)
    groups = defaultdict(lambda: Counter())
    members = defaultdict(list)
    for it in items:
        cl = [int(x) for x in str(it['classes']).split(';') if x != '']
        g = group_key(it['img'], group_regex)
        groups[g].update(_features(cl))
        members[g].append(it['img'])
    total = Counter()
    for g in groups.values():
        total.update(g)
    target = {s: {f: r * v for f, v in total.items()} for s, r in zip(names, ratios)}
    cur = {s: Counter() for s in names}
    assign = {}
    order = list(groups)
    rng.shuffle(order)
    # rare classes first
    def rarity(g):
        cs = [total[f] for f in groups[g] if f.startswith('c')]
        return min(cs) if cs else 10 ** 9
    order.sort(key=rarity)
    for g in order:
        if fixed and g in fixed:
            s = fixed[g]
        else:
            best, bs = None, None
            for s_, r in zip(names, ratios):
                if fixed and r == 0:
                    continue
                cost = 0.0
                for f, v in groups[g].items():
                    t = target[s_].get(f, 0.0)
                    before = (cur[s_][f] - t) ** 2
                    after = (cur[s_][f] + v - t) ** 2
                    cost += (after - before) / (t + 1.0)
                cost += rng.random() * 1e-9
                if bs is None or cost < bs:
                    best, bs = s_, cost
            s = best
        assign[g] = s
        cur[s].update(groups[g])
    out = {s: [] for s in names}
    for g, s in assign.items():
        out[s].extend(members[g])
    for s in out:
        out[s].sort()
    return dict(splits=out, group_of={i: g for g, ims in members.items() for i in ims}, assign=assign)


def split_with_shipped_val(items, group_regex, seed, test_frac=0.15):
    """If MSDD ships train/val dirs: keep its val, carve test (about test_frac of ALL images) out of its train."""
    def part(it):
        for p in Path(it['img']).parts[:-1]:
            k = re.split(r'[_\-]', p.lower())[0]
            if k in ('train', 'val', 'test'):
                return k
        return None
    parts = {it['img']: part(it) for it in items}
    val_items = [i for i in items if parts[i['img']] == 'val']
    train_items = [i for i in items if parts[i['img']] in ('train', None)]
    if not val_items:
        raise ValueError('no shipped val directory found')
    r = test_frac * len(items) / max(1, len(train_items))
    res = stratified_group_split(train_items, group_regex, ratios=(1 - r, r), seed=seed, names=('train', 'test'))
    sp = res['splits']
    val_groups = {group_key(i['img'], group_regex) for i in val_items}
    train_groups = {group_key(i, group_regex) for i in sp['train'] + sp['test']}
    if val_groups & train_groups:
        print('WARNING: shipped val shares capture groups with shipped train (capture-level leakage in the shipped split).')
    return dict(splits=dict(train=sp['train'], val=sorted(i['img'] for i in val_items), test=sp['test']),
                group_of=res['group_of'], leakage_groups=sorted(val_groups & train_groups)[:20])


def per_class_table(items, splits, names=None):
    import pandas as pd
    by_img = {it['img']: [int(x) for x in str(it['classes']).split(';') if x != ''] for it in items}
    rows = []
    for s, ims in splits.items():
        c = Counter()
        for i in ims:
            c.update(by_img[i])
        rows.append(dict(split=s, images=len(ims), background_images=sum(1 for i in ims if not by_img[i]),
                         **{(names[k] if names and k < len(names) else f'class_{k}'): v for k, v in sorted(c.items())}))
    return pd.DataFrame(rows).fillna(0)


def check_no_leak(splits, group_of):
    seen = {}
    for s, ims in splits.items():
        for i in ims:
            g = group_of[i]
            if g in seen and seen[g] != s:
                raise AssertionError(f'capture group {g} appears in {seen[g]} and {s}')
            seen[g] = s
    allimgs = [i for ims in splits.values() for i in ims]
    assert len(allimgs) == len(set(allimgs)), 'an image is in two splits'
    return True


def flat_name(rel: str) -> str:
    return rel.replace('/', '__').replace('\\', '__')


def build_yolo_farm(root: Path, items: list[dict], splits: dict, out_dir: Path, names: list[str],
                    link: str = 'symlink') -> Path:
    """Create out_dir/{images,labels}/<split>/ + <split>.txt + data.yaml for Ultralytics.
    Original files are never modified. Background images get an empty label file in the farm."""
    import yaml
    out_dir = Path(out_dir)
    by_img = {it['img']: it for it in items}
    for s, ims in splits.items():
        (out_dir / 'images' / s).mkdir(parents=True, exist_ok=True)
        (out_dir / 'labels' / s).mkdir(parents=True, exist_ok=True)
        lines = []
        for rel in ims:
            fn = flat_name(rel)
            dst = out_dir / 'images' / s / fn
            src = root / rel
            if dst.exists() or dst.is_symlink():
                dst.unlink()
            if link == 'symlink':
                os.symlink(src.resolve(), dst)
            elif link == 'hardlink':
                os.link(src, dst)
            else:
                shutil.copy2(src, dst)
            lab_dst = out_dir / 'labels' / s / (Path(fn).stem + '.txt')
            it = by_img[rel]
            if it['label']:
                shutil.copyfile(root / it['label'], lab_dst)
            else:
                lab_dst.write_text('')
            lines.append(f'./images/{s}/{fn}')
        (out_dir / f'{s}.txt').write_text('\n'.join(lines) + '\n')
    data = dict(path=str(out_dir), train='train.txt', val='val.txt', test='test.txt',
                nc=len(names), names={i: n for i, n in enumerate(names)})
    (out_dir / 'data.yaml').write_text(yaml.safe_dump(data, sort_keys=False))
    return out_dir / 'data.yaml'


def repeat_factor_oversample(train_lines: list[str], labels_dir: Path, nc: int, t: float = 0.1, seed: int = 0):
    """LVIS-style repeat factor sampling at image level: r_c = max(1, sqrt(t / f_c)), image r = max over its classes,
    stochastic rounding with a fixed seed. Returns the oversampled list and the repeat stats."""
    rng = random.Random(seed)
    img_classes = []
    for ln in train_lines:
        lab = labels_dir / (Path(ln).stem + '.txt')
        cls = set()
        if lab.exists():
            for r in lab.read_text().splitlines():
                if r.strip():
                    cls.add(int(float(r.split()[0])))
        img_classes.append(cls)
    n = len(train_lines)
    f = {c: sum(1 for cs in img_classes if c in cs) / n for c in range(nc)}
    rc = {c: max(1.0, math.sqrt(t / f[c])) if f[c] > 0 else 1.0 for c in range(nc)}
    out, extra = [], 0
    for ln, cs in zip(train_lines, img_classes):
        r = max([rc[c] for c in cs], default=1.0)
        k = int(r) + (1 if rng.random() < (r - int(r)) else 0)
        out.extend([ln] * k)
        extra += k - 1
    return out, dict(image_freq={c: round(f[c], 4) for c in f}, repeat_factor={c: round(rc[c], 2) for c in rc},
                     extra_images=extra, new_len=len(out), old_len=n)


# --------------------------------------------------------------------------- training / evaluation
def load_experiments(path: str | Path) -> dict:
    import yaml
    return yaml.safe_load(Path(path).read_text())


def valid_train_args(d: dict) -> tuple[dict, list[str]]:
    from ultralytics.cfg import DEFAULT_CFG_DICT
    ok = {k: v for k, v in d.items() if k in DEFAULT_CFG_DICT}
    return ok, sorted(set(d) - set(ok))


def resolve_experiment(exp_id: str, spec: dict, audit: dict | None, completed: dict[str, float]) -> dict:
    """Merge reference hyp + experiment overrides. `base: best` picks the best finished run by VAL mAP50-95."""
    exps = spec['experiments']
    e = dict(exps[exp_id])
    base_id = e.get('base')
    if base_id == 'best':
        if not completed:
            raise RuntimeError(f'{exp_id} needs a finished run to build on (none found); run E1 first')
        base_id = max(completed, key=completed.get)
        e['_best_of'] = {k: round(v, 4) for k, v in completed.items()}
    e['_base_id'] = base_id
    cfg = dict(spec['reference_hyp'])
    cfg.update(spec.get('common', {}))
    if base_id:
        parent = resolve_experiment(base_id, spec, audit, completed) if base_id in exps else None
        if parent:
            cfg.update(parent['train_args'])
            e.setdefault('model', parent['model'])
            e.setdefault('data_variant', parent.get('data_variant', 'default'))
            if parent.get('oversample'):
                e.setdefault('oversample', parent['oversample'])
    cfg.update(e.get('train_args', {}))
    if e.get('imgsz') == 'auto_from_audit':
        frac = (audit or {}).get('small_box_frac_640')
        cfg['imgsz'] = 1280 if (frac is not None and frac >= spec['rules']['many_small_boxes_frac']) else 960
        e['_imgsz_reason'] = f'small_box_frac_640={frac} threshold={spec["rules"]["many_small_boxes_frac"]}'
    elif e.get('imgsz'):
        cfg['imgsz'] = e['imgsz']
    if 'seed' in e:
        cfg['seed'] = e['seed']
    return dict(id=exp_id, model=e.get('model'), train_args=cfg, data_variant=e.get('data_variant', 'default'),
                oversample=e.get('oversample'), requires=e.get('requires'), meta={k: v for k, v in e.items() if k.startswith('_')},
                description=e.get('description', ''))


def val_score_from_results(results_csv: str | Path) -> float | None:
    import pandas as pd
    p = Path(results_csv)
    if not p.exists():
        return None
    df = pd.read_csv(p)
    df.columns = [c.strip() for c in df.columns]
    col = 'metrics/mAP50-95(B)'
    return float(df[col].max()) if col in df and len(df) else None


def completed_runs(persist: Path, ids: list[str]) -> dict[str, float]:
    out = {}
    for i in ids:
        done = persist / 'runs' / i / 'DONE'
        if done.exists():
            s = val_score_from_results(persist / 'runs' / i / 'results.csv')
            if s is not None:
                out[i] = s
    return out


def sync_run(run_dir: Path, persist_run: Path, final: bool = False):
    persist_run.mkdir(parents=True, exist_ok=True)
    for name in ('results.csv', 'args.yaml'):
        if (run_dir / name).exists():
            shutil.copy2(run_dir / name, persist_run / name)
    w = run_dir / 'weights'
    (persist_run / 'weights').mkdir(exist_ok=True)
    for name in ('last.pt', 'best.pt'):
        if (w / name).exists():
            tmp = persist_run / 'weights' / (name + '.tmp')
            shutil.copy2(w / name, tmp)
            os.replace(tmp, persist_run / 'weights' / name)
    if final:
        for f in run_dir.glob('*.png'):
            shutil.copy2(f, persist_run / f.name)
        for f in run_dir.glob('*.jpg'):
            shutil.copy2(f, persist_run / f.name)


def restore_run(persist_run: Path, run_dir: Path) -> bool:
    if not (persist_run / 'weights' / 'last.pt').exists():
        return False
    (run_dir / 'weights').mkdir(parents=True, exist_ok=True)
    for name in ('results.csv', 'args.yaml'):
        if (persist_run / name).exists():
            shutil.copy2(persist_run / name, run_dir / name)
    for name in ('last.pt', 'best.pt'):
        if (persist_run / 'weights' / name).exists():
            shutil.copy2(persist_run / 'weights' / name, run_dir / 'weights' / name)
    return True


def make_model(name: str):
    from ultralytics import RTDETR, YOLO
    return RTDETR(name) if 'rtdetr' in Path(name).name.lower() else YOLO(name)


def run_experiment(cfg: dict, data_yaml: str, work: Path, persist: Path, device='0', workers=4, resume=True,
                   batch: int | None = None):
    """Train (or resume) one experiment, mirroring checkpoints and results.csv to `persist` every epoch."""
    exp_id = cfg['id']
    project = work / 'runs'
    run_dir = project / exp_id
    persist_run = persist / 'runs' / exp_id
    if (persist_run / 'DONE').exists():
        print(f'{exp_id}: already DONE in persistent storage, skipping')
        return persist_run
    args, dropped = valid_train_args(cfg['train_args'])
    if dropped:
        print(f'{exp_id}: args dropped (not valid in the pinned ultralytics): {dropped}')
    args.update(data=str(data_yaml), project=str(project), name=exp_id, device=device, workers=workers, exist_ok=True)
    if batch:
        args['batch'] = batch
    restored = restore_run(persist_run, run_dir) if resume else False
    last = run_dir / 'weights' / 'last.pt'
    model = make_model(str(last) if restored and last.exists() else cfg['model'])

    def on_epoch_end(trainer):
        sync_run(Path(trainer.save_dir), persist_run)
    model.add_callback('on_fit_epoch_end', on_epoch_end)
    if restored and last.exists():
        print(f'{exp_id}: RESUMING from {last}')
        model.train(resume=True, device=device, workers=workers)
    else:
        print(f'{exp_id}: starting fresh with {cfg["model"]}')
        model.train(**args)
    sync_run(run_dir, persist_run, final=True)
    (persist_run / 'DONE').write_text(time.strftime('%Y-%m-%d %H:%M:%S'))
    (persist_run / 'resolved_config.json').write_text(json.dumps(cfg, indent=1, default=str))
    return persist_run


def evaluate_split(ckpt: str | Path, data_yaml: str, split: str, out_dir: Path, imgsz: int, device='0',
                   conf=0.001, iou=0.7, batch=16, once_guard=True) -> dict:
    """Run model.val on a split and write overall + per-class metrics. The test split is guarded to run once per run."""
    import pandas as pd
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    guard = out_dir / f'{split}_done.json'
    if split == 'test' and once_guard and guard.exists():
        raise RuntimeError(f'{guard} exists: test was already reported for this run. Delete it deliberately to re-run.')
    model = make_model(str(ckpt))
    m = model.val(data=str(data_yaml), split=split, imgsz=imgsz, device=device, conf=conf, iou=iou, batch=batch,
                  plots=True, project=str(out_dir), name=f'{split}_eval', exist_ok=True, verbose=False)
    b = m.box
    names = m.names
    per = pd.DataFrame(dict(class_id=[int(i) for i in b.ap_class_index],
                            class_name=[names[int(i)] for i in b.ap_class_index],
                            precision=b.p, recall=b.r, ap50=b.ap50, ap50_95=b.ap))
    overall = dict(split=split, precision=float(b.mp), recall=float(b.mr), map50=float(b.map50), map50_95=float(b.map),
                   ckpt=str(ckpt), imgsz=imgsz, conf=conf, iou=iou, n_per_class_rows=len(per))
    per.to_csv(out_dir / f'{split}_per_class.csv', index=False)
    (out_dir / f'{split}_metrics.json').write_text(json.dumps(overall, indent=1))
    if split == 'test':
        guard.write_text(json.dumps(overall))
    print(json.dumps(overall, indent=1))
    print(per.to_string(index=False))
    return overall


def draw_samples(root: str | Path, items: list[dict], names: list[str] | None, out_dir: str | Path, n: int = 12, seed: int = 0):
    """Draw YOLO boxes on n random labelled images so a human can eyeball label alignment."""
    from PIL import Image, ImageDraw
    root, out_dir = Path(root), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    labelled = [i for i in items if i['n_boxes'] > 0]
    random.Random(seed).shuffle(labelled)
    for k, it in enumerate(labelled[:n]):
        rows, _ = parse_yolo_file(root / it['label'])
        im = Image.open(root / it['img']).convert('RGB')
        W, H = im.size
        d = ImageDraw.Draw(im)
        lw = max(2, max(W, H) // 400)
        for c, cx, cy, w, h in rows:
            d.rectangle([(cx - w / 2) * W, (cy - h / 2) * H, (cx + w / 2) * W, (cy + h / 2) * H], outline=(255, 0, 0), width=lw)
            d.text(((cx - w / 2) * W + 3, (cy - h / 2) * H + 3), names[c] if names and c < len(names) else str(c), fill=(255, 255, 0))
        im.thumbnail((1024, 1024))
        im.save(out_dir / f'sample_{k:02d}_{Path(it["img"]).stem[:40]}.jpg', quality=85)


# --------------------------------------------------------------------------- locating the persistent copy
def locate_dataset(paths: dict, explicit: str | None = None) -> tuple[str, Path]:
    """Return ('archives', dir_with_MANIFEST) or ('tree', dir_of_extracted_data). Never touches SciDB."""
    cands = []
    if explicit:
        cands.append(Path(explicit))
    if os.environ.get('MSDD_DATASET_DIR'):
        cands.append(Path(os.environ['MSDD_DATASET_DIR']))
    cands += [paths['persist'] / 'dataset_copy']
    if paths['env'] == 'kaggle':
        cands += sorted(Path('/kaggle/input').glob('*'))
        cands += sorted(Path('/kaggle/input').glob('*/dataset_copy'))
    for c in cands:
        if (c / 'MANIFEST.json').exists():
            return 'archives', c
    for c in cands:
        if c.is_dir() and any(c.rglob('*.jpg')):
            return 'tree', c
    raise FileNotFoundError('No persistent MSDD copy found. Attach the private dataset made by notebook 00 '
                            '(or mount Drive) - see HANDOFF.md. Searched: ' + ', '.join(map(str, cands)))


def load_audit(paths: dict, data_dir: Path, dataset_copy: Path | None = None):
    """audit.json + items.csv from the persistent copy; falls back to re-running the audit on the data."""
    import pandas as pd
    for d in [paths['persist'] / 'audit', (dataset_copy / 'audit') if dataset_copy else None,
              *(Path('/kaggle/input').glob('*/audit') if paths['env'] == 'kaggle' else [])]:
        if d and (d / 'audit.json').exists() and (d / 'items.csv').exists():
            print('audit loaded from', d)
            items = pd.read_csv(d / 'items.csv', keep_default_na=False).to_dict('records')
            return json.loads((d / 'audit.json').read_text()), items
    print('no stored audit found; re-running the audit on', data_dir)
    audit, items = audit_dataset(data_dir)
    write_audit(audit, items, paths['persist'] / 'audit')
    return audit, items
