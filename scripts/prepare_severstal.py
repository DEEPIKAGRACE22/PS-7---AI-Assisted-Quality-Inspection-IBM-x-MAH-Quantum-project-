"""Download Severstal, convert RLE masks to boxes, and tile images into a YOLO dataset.

Each 1600x256 image is cut into 6 overlapping 256x256 tiles (close to NEU-DET's
200x200 scale). All defect tiles are kept, plus a sample of defect-free tiles as
negatives. Train/val are split by source image so tiles never leak across splits.

Requires accepting the competition rules on Kaggle first:
https://www.kaggle.com/competitions/severstal-steel-defect-detection/rules

Usage:
    python scripts/prepare_severstal.py [--output data/severstal_yolo]
"""

import argparse
import csv
import random
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np

COMPETITION = "severstal-steel-defect-detection"
CLASS_NAMES = ["defect_1", "defect_2", "defect_3", "defect_4"]

IMAGE_HEIGHT = 256
IMAGE_WIDTH = 1600
TILE = 256
TILES_PER_IMAGE = 6
TILE_STARTS = [
    round(i * (IMAGE_WIDTH - TILE) / (TILES_PER_IMAGE - 1))
    for i in range(TILES_PER_IMAGE)
]

SEED = 42
VAL_FRACTION = 0.1
NEGATIVE_FRACTION = 0.15
MIN_AREA = 40        # px; smaller components are treated as noise
MERGE_KERNEL = 15    # px; dilation used to merge nearby fragments into one box


def rle_decode(rle):
    """Decode Severstal RLE (1-indexed, column-major) into a HxW uint8 mask."""
    mask = np.zeros(IMAGE_HEIGHT * IMAGE_WIDTH, dtype=np.uint8)
    values = list(map(int, rle.split()))
    for start, length in zip(values[0::2], values[1::2]):
        mask[start - 1:start - 1 + length] = 1
    return mask.reshape((IMAGE_HEIGHT, IMAGE_WIDTH), order="F")


def mask_to_boxes(mask):
    """Return (x1, y1, x2, y2) boxes, merging fragments closer than MERGE_KERNEL."""
    kernel = np.ones((MERGE_KERNEL, MERGE_KERNEL), dtype=np.uint8)
    merged = cv2.dilate(mask, kernel)
    count, labels = cv2.connectedComponents(merged)

    boxes = []
    for label in range(1, count):
        # Box the original pixels, not the dilated region
        ys, xs = np.nonzero((labels == label) & (mask > 0))
        if len(xs) < MIN_AREA:
            continue
        boxes.append((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    return boxes


def load_annotations(csv_path):
    annotations = defaultdict(list)
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        assert {"ImageId", "ClassId", "EncodedPixels"} <= set(reader.fieldnames), (
            f"Unexpected train.csv columns: {reader.fieldnames}"
        )
        for row in reader:
            if row["EncodedPixels"].strip():
                annotations[row["ImageId"]].append(
                    (int(row["ClassId"]) - 1, row["EncodedPixels"])
                )
    return annotations


def tile_labels(class_masks, x0):
    lines = []
    for class_id, mask in class_masks:
        for x1, y1, x2, y2 in mask_to_boxes(mask[:, x0:x0 + TILE]):
            lines.append(
                f"{class_id} {(x1 + x2) / 2 / TILE:.6f} {(y1 + y2) / 2 / TILE:.6f} "
                f"{(x2 - x1) / TILE:.6f} {(y2 - y1) / TILE:.6f}"
            )
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=Path("data/severstal_yolo"))
    parser.add_argument("--source", type=Path, help="Existing competition folder (skips download)")
    parser.add_argument("--limit", type=int, help="Only process this many images (for quick tests)")
    args = parser.parse_args()

    if args.source:
        source = args.source
    else:
        import kagglehub
        source = Path(kagglehub.competition_download(COMPETITION))

    annotations = load_annotations(source / "train.csv")
    image_ids = sorted(p.name for p in (source / "train_images").glob("*.jpg"))
    assert image_ids, f"No images found in {source / 'train_images'}"

    rng = random.Random(SEED)
    rng.shuffle(image_ids)
    if args.limit:
        image_ids = image_ids[:args.limit]

    val_count = round(len(image_ids) * VAL_FRACTION)
    split_of = {image_id: ("val" if i < val_count else "train") for i, image_id in enumerate(image_ids)}

    output = args.output.resolve()
    if output.exists():
        shutil.rmtree(output)
    for split in ("train", "val"):
        (output / "images" / split).mkdir(parents=True)
        (output / "labels" / split).mkdir(parents=True)

    tile_counts = Counter()
    box_counts = Counter()

    for n, image_id in enumerate(image_ids, 1):
        split = split_of[image_id]
        image = cv2.imread(str(source / "train_images" / image_id))
        assert image.shape[:2] == (IMAGE_HEIGHT, IMAGE_WIDTH), f"Unexpected size: {image_id}"

        class_masks = [(c, rle_decode(rle)) for c, rle in annotations.get(image_id, [])]

        for i, x0 in enumerate(TILE_STARTS):
            lines = tile_labels(class_masks, x0)
            if not lines and rng.random() > NEGATIVE_FRACTION:
                continue

            stem = f"{Path(image_id).stem}_t{i}"
            cv2.imwrite(str(output / "images" / split / f"{stem}.jpg"), image[:, x0:x0 + TILE])
            (output / "labels" / split / f"{stem}.txt").write_text(
                "\n".join(lines) + "\n" if lines else ""
            )

            tile_counts[(split, "defect" if lines else "negative")] += 1
            for line in lines:
                box_counts[(split, CLASS_NAMES[int(line.split()[0])])] += 1

        if n % 1000 == 0:
            print(f"Processed {n}/{len(image_ids)} images")

    names = "\n".join(f"  {i}: {name}" for i, name in enumerate(CLASS_NAMES))
    (output / "data.yaml").write_text(
        f"path: {output}\n"
        "train: images/train\n"
        "val: images/val\n"
        f"names:\n{names}\n"
    )

    for split in ("train", "val"):
        print(
            f"{split}: {tile_counts[(split, 'defect')]} defect tiles, "
            f"{tile_counts[(split, 'negative')]} negative tiles"
        )
        print("  boxes: " + ", ".join(f"{c}={box_counts[(split, c)]}" for c in CLASS_NAMES))
    print(f"Dataset written to {output}")


if __name__ == "__main__":
    main()
