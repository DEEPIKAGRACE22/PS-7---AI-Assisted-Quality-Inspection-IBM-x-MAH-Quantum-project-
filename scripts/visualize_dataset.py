"""Draw YOLO labels on random images from a dataset split and save a grid image.

Usage:
    python scripts/visualize_dataset.py data/severstal_yolo --split train --n 12
"""

import argparse
import random
from pathlib import Path

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import yaml

COLORS = [(255, 0, 0), (0, 200, 0), (0, 120, 255), (255, 160, 0), (200, 0, 200), (0, 200, 200)]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--split", default="train")
    parser.add_argument("--n", type=int, default=12)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--defects-only", action="store_true", help="Skip images with no labels")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    names = yaml.safe_load((args.dataset / "data.yaml").read_text())["names"]
    image_dir = args.dataset / "images" / args.split
    label_dir = args.dataset / "labels" / args.split

    images = sorted(image_dir.glob("*.jpg"))
    if args.defects_only:
        images = [p for p in images if (label_dir / f"{p.stem}.txt").read_text().strip()]
    samples = random.Random(args.seed).sample(images, min(args.n, len(images)))

    cols = 4
    rows = (len(samples) + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(4 * cols, 4 * rows))
    axes = axes.flatten()

    for ax, image_path in zip(axes, samples):
        image = cv2.cvtColor(cv2.imread(str(image_path)), cv2.COLOR_BGR2RGB)
        height, width = image.shape[:2]

        for line in (label_dir / f"{image_path.stem}.txt").read_text().split("\n"):
            if not line.strip():
                continue
            class_id, xc, yc, bw, bh = line.split()
            class_id = int(class_id)
            xc, yc, bw, bh = float(xc) * width, float(yc) * height, float(bw) * width, float(bh) * height
            p1 = (int(xc - bw / 2), int(yc - bh / 2))
            p2 = (int(xc + bw / 2), int(yc + bh / 2))
            color = COLORS[class_id % len(COLORS)]
            cv2.rectangle(image, p1, p2, color, 2)
            cv2.putText(image, names[class_id], (p1[0], max(12, p1[1] - 4)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

        ax.imshow(image)
        ax.set_title(image_path.name, fontsize=8)

    for ax in axes:
        ax.axis("off")

    output = args.output or args.dataset / f"preview_{args.split}.png"
    plt.tight_layout()
    plt.savefig(output, dpi=100)
    print(f"Saved preview to {output}")


if __name__ == "__main__":
    main()
