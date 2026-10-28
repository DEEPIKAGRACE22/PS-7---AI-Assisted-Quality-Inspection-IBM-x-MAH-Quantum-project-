"""Measure how tightly Severstal mask-to-box conversion fits the defects, for several MERGE_KERNEL values.

For each kernel, every box is scored by its fill ratio: the share of the box area
that is actually defect pixels. A low fill ratio means the box covers mostly
background steel.

Usage:
    python scripts/analyze_severstal_boxes.py [--source <competition folder>] [--kernels 1 3 5 9 15]
"""

import argparse
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prepare_severstal as ps  # noqa: E402

COMPETITION = ps.COMPETITION


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, help="Existing competition folder (skips download)")
    parser.add_argument("--kernels", type=int, nargs="+", default=[1, 3, 5, 9, 15])
    parser.add_argument("--sample", type=int, default=500, help="Number of defect images to analyse")
    parser.add_argument("--seed", type=int, default=ps.SEED)
    args = parser.parse_args()

    if args.source:
        source = args.source
    else:
        import kagglehub
        source = Path(kagglehub.competition_download(COMPETITION))

    annotations = ps.load_annotations(source / "train.csv")
    image_ids = sorted(annotations)
    random.Random(args.seed).shuffle(image_ids)
    image_ids = image_ids[:args.sample]

    # Decode once, reuse for every kernel
    decoded = []
    for image_id in image_ids:
        for class_id, rle in annotations[image_id]:
            decoded.append((class_id, ps.rle_decode(rle)))
    print(f"Analysing {len(decoded)} defect masks from {len(image_ids)} images\n")

    header = ["kernel", "boxes", "per_mask", "median_area", "median_fill", "fill<0.3", "fill<0.5", "per_class"]
    rows = []
    for kernel in args.kernels:
        ps.MERGE_KERNEL = kernel  # mask_to_boxes reads this at call time
        fills, areas, per_class = [], [], [0] * len(ps.CLASS_NAMES)

        for class_id, mask in decoded:
            for x1, y1, x2, y2 in ps.mask_to_boxes(mask):
                box_area = (x2 - x1) * (y2 - y1)
                fills.append(mask[y1:y2, x1:x2].sum() / box_area)
                areas.append(box_area)
                per_class[class_id] += 1

        fills = np.array(fills)
        rows.append([
            kernel,
            len(fills),
            f"{len(fills) / len(decoded):.2f}",
            f"{np.median(areas):.0f}",
            f"{np.median(fills):.2f}",
            f"{(fills < 0.3).mean():.0%}",
            f"{(fills < 0.5).mean():.0%}",
            " ".join(f"{ps.CLASS_NAMES[i]}={n}" for i, n in enumerate(per_class)),
        ])

    widths = [max(len(str(x)) for x in col) for col in zip(header, *rows)]
    for row in [header] + rows:
        print("  ".join(str(x).ljust(w) for x, w in zip(row, widths)))

    print("\nfill = defect pixels / box area (1.0 = perfectly tight).")
    print("Pick the smallest kernel where median fill is high and boxes per mask stay near 1.")


if __name__ == "__main__":
    main()
