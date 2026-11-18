"""Image-level accuracy: one predicted defect class per image, compared with the filename class.

Works with detection models (detections are collapsed to one class per image) and
classification models (top-1). Writes models/<version>/metrics/image_accuracy_<split>.csv.

Usage:
    python scripts/eval_image_accuracy.py v4_yolo26s_neu_det_s1 --split val [--conf 0.05] [--tta] [--agg sum|max]
    python scripts/eval_image_accuracy.py v5_yolo26s_cls_neu --split test --data data/neu_cls
    python scripts/eval_image_accuracy.py --weights models/best_v4_yolo26s.onnx --split val
"""

import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path

import torch
from ultralytics import YOLO

REPO_ROOT = Path(__file__).resolve().parent.parent
CLASSES = ["crazing", "inclusion", "patches", "pitted_surface", "rolled-in_scale", "scratches"]
IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def true_class(path: Path) -> str:
    """crazing_107.jpg -> crazing; rolled-in_scale_12.jpg -> rolled-in_scale."""
    return re.sub(r"_\d+$", "", path.stem)


def list_images(data: Path, split: str):
    split_dir = data / "images" / split if (data / "images").exists() else data / split
    return sorted(p for p in split_dir.rglob("*") if p.suffix.lower() in IMG_EXTS)


def predict_class(result, agg: str):
    """Return the predicted class name, or None if the detector found nothing."""
    names = result.names
    if result.probs is not None:  # classification model
        return names[int(result.probs.top1)]
    if result.boxes is None or len(result.boxes) == 0:
        return None
    scores = defaultdict(float)
    for cls, conf in zip(result.boxes.cls.tolist(), result.boxes.conf.tolist()):
        key = names[int(cls)]
        scores[key] = max(scores[key], conf) if agg == "max" else scores[key] + conf
    return max(scores, key=scores.get)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("version", nargs="?")
    parser.add_argument("--weights", help="Explicit weights path (.pt/.onnx) instead of models/<version>/weights/best.pt")
    parser.add_argument("--data", default="data/neu_yolo", help="Dataset root with images/<split> or <split>/")
    parser.add_argument("--split", default="val")
    parser.add_argument("--imgsz", type=int, default=None)
    parser.add_argument("--conf", type=float, default=0.05)
    parser.add_argument("--tta", action="store_true")
    parser.add_argument("--agg", choices=["sum", "max"], default="sum")
    args = parser.parse_args()

    if args.weights:
        weights, name = Path(args.weights), Path(args.weights).stem
    else:
        weights, name = REPO_ROOT / "models" / args.version / "weights" / "best.pt", args.version
    model = YOLO(str(weights), task=None)

    images = list_images(REPO_ROOT / args.data, args.split)
    assert images, f"No images found for split {args.split!r} under {args.data}"

    kwargs = dict(conf=args.conf, verbose=False, device=0 if torch.cuda.is_available() else "cpu")
    if args.imgsz:
        kwargs["imgsz"] = args.imgsz
    if args.tta and not str(weights).endswith(".onnx"):
        kwargs["augment"] = True

    labels = CLASSES + ["(none)"]
    matrix = defaultdict(int)
    for img in images:
        pred = predict_class(model.predict(str(img), **kwargs)[0], args.agg) or "(none)"
        matrix[(true_class(img), pred)] += 1

    total = len(images)
    correct = sum(matrix[(c, c)] for c in CLASSES)
    print(f"{name} [{args.split}] image accuracy: {correct}/{total} = {correct / total:.4f}")
    print(f"{'true-pred':>16} " + " ".join(f"{c[:7]:>7}" for c in labels))
    for t in CLASSES:
        n = sum(matrix[(t, p)] for p in labels)
        acc = matrix[(t, t)] / n if n else float("nan")
        print(f"{t:>16} " + " ".join(f"{matrix[(t, p)]:>7}" for p in labels) + f"   acc={acc:.3f}")

    if args.version:
        out_dir = REPO_ROOT / "models" / args.version / "metrics"
        out_dir.mkdir(parents=True, exist_ok=True)
        with open(out_dir / f"image_accuracy_{args.split}.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["true"] + labels)
            for t in CLASSES:
                writer.writerow([t] + [matrix[(t, p)] for p in labels])
            writer.writerow(["accuracy", correct / total, f"conf={args.conf}", f"tta={args.tta}", f"agg={args.agg}"])


if __name__ == "__main__":
    main()
