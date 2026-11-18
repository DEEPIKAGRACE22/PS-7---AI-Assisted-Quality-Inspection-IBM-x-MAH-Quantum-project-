"""Build an image-classification dataset (data/neu_cls/<split>/<class>/*.jpg) from the detection split.

Uses exactly the same train/val/test image assignment as data/neu_yolo, so no test image leaks into training.
The class comes from the filename prefix (crazing_107.jpg -> crazing).

Usage:
    python scripts/prepare_neu_cls.py [--src data/neu_yolo] [--dst data/neu_cls]
"""

import argparse
import re
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--src", default="data/neu_yolo")
    parser.add_argument("--dst", default="data/neu_cls")
    args = parser.parse_args()

    src, dst = REPO_ROOT / args.src, REPO_ROOT / args.dst
    for split in ("train", "val", "test"):
        files = sorted((src / "images" / split).glob("*.*"))
        assert files, f"No images in {src / 'images' / split}"
        for f in files:
            cls = re.sub(r"_\d+$", "", f.stem)
            out = dst / split / cls
            out.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, out / f.name)
        print(f"{split}: {len(files)} images")
    print(f"Classification dataset written to {dst}")


if __name__ == "__main__":
    main()
