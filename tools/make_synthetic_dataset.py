"""Tiny synthetic MSDD-like dataset for local smoke tests (NOT real data; layout is a guess).

  <out>/mixed/<stem>.jpg          RGB pseudo-colour image
  <out>/labels/<stem>.txt         YOLO labels, only for images with defects (others = defect-free, no file)
  <out>/single/<stem>_<0..14>.jpg 15 single-channel frames (a subset of captures)
  <out>/classes.txt
Stems look like the reference repo's:  20240206_134045_Gige[0]  (timestamp + camera index; 2 cameras per timestamp)
"""
import argparse
import random
from pathlib import Path

import numpy as np
from PIL import Image

REPO10 = ['knocked', 'inclusion', 'misrun', 'burr', 'parting_line', 'dater_collapse', 'pocking_mark', 'scraped', 'cutting', 'smudge']


def make(out: Path, n_ts=40, names=REPO10, size=320, seed=0, n_frames=15, frames_for=8):
    rng = random.Random(seed)
    nrng = np.random.default_rng(seed)
    for d in ('mixed', 'labels', 'single'):
        (out / d).mkdir(parents=True, exist_ok=True)
    (out / 'classes.txt').write_text('\n'.join(names) + '\n')
    k = 0
    for t in range(n_ts):
        for cam in range(2):
            stem = f'20240206_1340{t:02d}_Gige[{cam}]'
            img = nrng.integers(60, 120, (size, size, 3), dtype=np.uint8)
            rows = []
            if rng.random() < 0.6:
                for _ in range(rng.choice([1, 1, 2, 3])):
                    c = rng.randrange(len(names)) if rng.random() < 0.5 else rng.randrange(min(3, len(names)))  # skewed classes
                    w, h = rng.randint(14, 70), rng.randint(14, 70)
                    x, y = rng.randint(0, size - w), rng.randint(0, size - h)
                    img[y:y + h, x:x + w] = (40 + 20 * c, 200 - 15 * c, 80 + 10 * c)
                    rows.append(f'{c} {(x + w / 2) / size:.6f} {(y + h / 2) / size:.6f} {w / size:.6f} {h / size:.6f}')
            Image.fromarray(img).save(out / 'mixed' / f'{stem}.jpg', quality=92)
            if rows:
                (out / 'labels' / f'{stem}.txt').write_text('\n'.join(rows) + '\n')
            if k < frames_for:
                for i in range(n_frames):
                    Image.fromarray(nrng.integers(0, 255, (64, 64), dtype=np.uint8)).save(out / 'single' / f'{stem}_{i}.jpg')
            k += 1
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--classes', type=int, default=10)
    a = ap.parse_args()
    make(Path(a.out), names=REPO10[:a.classes])
    print('wrote', a.out)
