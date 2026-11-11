"""Local smoke test: run notebooks 00/01/02 end to end on a tiny SYNTHETIC dataset (CPU, yolov8n, 1 epoch).

Notebooks are copied and only their config cells are edited (string replace); all other cells run unchanged.
usage: python tools/smoke_test.py <scratch_dir> [--rtdetr]
"""
import copy
import http.server
import json
import os
import re
import shutil
import socketserver
import sys
import threading
import zipfile
from pathlib import Path

import nbformat
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from make_synthetic_dataset import make, REPO10  # noqa: E402

S = Path(sys.argv[1]).resolve()
NBDIR = ROOT / 'notebooks' / 'msdd'


def run_nb(name, replacements=(), work=None, keep_cells=None, timeout=1800):
    nb = nbformat.read(NBDIR / name, 4)
    for c in nb.cells:
        if c.cell_type == 'code':
            for a, b in replacements:
                if a in c.source:
                    c.source = c.source.replace(a, b)
    if keep_cells is not None:
        nb.cells = [c for c in nb.cells if keep_cells(c)]
    os.environ['MSDD_WORK'] = str(work)
    os.environ['MSDD_SKIP_INSTALL'] = '1'
    cwd = work / ('cwd_' + name.split('.')[0])
    cwd.mkdir(parents=True, exist_ok=True)
    client = NotebookClient(nb, timeout=timeout, kernel_name='python3', resources={'metadata': {'path': str(cwd)}})
    try:
        client.execute()
        err = None
    except CellExecutionError as e:
        err = str(e)
    out = nb
    (work / (name + '.executed.ipynb')).write_text(nbformat.writes(out))
    text = '\n'.join(o.get('text', '') for c in out.cells if c.cell_type == 'code' for o in c.get('outputs', []) if o.output_type == 'stream')
    return err, text


def main():
    if S.exists():
        shutil.rmtree(S)
    S.mkdir(parents=True)
    s10, s8 = make(S / 'synth10', names=REPO10), make(S / 'synth8', names=REPO10[:8])
    # local web server: a login page and a zip of the dataset
    serve = S / 'serve'
    serve.mkdir()
    (serve / 'login.html').write_text('<!DOCTYPE html><html><body>Please log in</body></html>')
    with zipfile.ZipFile(serve / 'synth.zip', 'w') as z:
        for p in s10.rglob('*'):
            if p.is_file():
                z.write(p, p.relative_to(s10))
    handler = lambda *a, **k: http.server.SimpleHTTPRequestHandler(*a, directory=str(serve), **k)  # noqa: E731
    httpd = socketserver.TCPServer(('127.0.0.1', 0), handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    results = {}

    # A. login page must be caught by the probe
    w = S / 'workA'
    err, _ = run_nb('00_download_and_audit.ipynb', [('DOWNLOAD_URLS = [', f'DOWNLOAD_URLS = ["http://127.0.0.1:{port}/login.html"] + [')], w)
    results['A_login_page_caught'] = bool(err and 'did not return archive bytes' in err)

    # B. zip over http -> verify -> extract -> audit -> persist; 10 classes -> continues
    w = S / 'workB'
    err, txt = run_nb('00_download_and_audit.ipynb', [('DOWNLOAD_URLS = [', f'DOWNLOAD_URLS = ["http://127.0.0.1:{port}/synth.zip"] + ['),
                                                       ('EXPECTED_TOTAL_BYTES = 9_785_811_363', 'EXPECTED_TOTAL_BYTES = 0'),
                                                       ('CREATE_KAGGLE_DATASET = True', 'CREATE_KAGGLE_DATASET = False')], w)
    results['B_nb00_ok'] = err is None
    results['B_files'] = sorted(p.name for p in (w / 'persist' / 'dataset_copy').iterdir()) if (w / 'persist').exists() else None
    if err:
        print('B ERROR:', err[-1500:])
    print(txt[-1800:])

    # C. 8-class data must stop the notebook AFTER saving the audit
    wC = S / 'workC'
    err, _ = run_nb('00_download_and_audit.ipynb', [('SOURCE_MODE = "url"', 'SOURCE_MODE = "local_dir"'), ('LOCAL_DIR = ""', f'LOCAL_DIR = "{s8}"')], wC)
    results['C_stops_on_8_classes'] = bool(err and 'STOP' in err)
    results['C_audit_saved_before_stop'] = (wC / 'persist' / 'audit' / 'audit.json').exists()

    # D. split (workB persistent copy)
    err, txt = run_nb('01_split.ipynb', [], S / 'workB')
    results['D_nb01_ok'] = err is None
    if err:
        print('D ERROR:', err[-1500:])
    print(txt[-1800:])

    # E. train: E1, E3 (imgsz rule), E4 (best + oversampling), then test evaluation + summary
    ov = '{"epochs": 1, "imgsz": 160, "batch": 8, "workers": 0, "patience": 100}'
    keep = lambda c: not (c.cell_type == 'code' and re.match(r'run_one\("(E2|E5|E6|E7|E8[a-d])"\)', c.source.strip()))  # noqa: E731
    reps = [('DEVICE = "0"', 'DEVICE = "cpu"'), ('WORKERS = 4', 'WORKERS = 0'), ('OVERRIDES = {}', f'OVERRIDES = {ov}'),
            ('MODEL_OVERRIDE = None', 'MODEL_OVERRIDE = "yolov8n.pt"')]
    err, txt = run_nb('02_train.ipynb', reps, S / 'workB', keep_cells=keep, timeout=3000)
    results['E_nb02_ok'] = err is None
    if err:
        print('E ERROR:', err[-2500:])
    print(txt[-3500:])
    print(json.dumps(results, indent=1))
    httpd.shutdown()


main()
