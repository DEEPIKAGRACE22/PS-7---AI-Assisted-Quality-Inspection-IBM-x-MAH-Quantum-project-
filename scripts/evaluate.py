"""Evaluate a registered model version on the held-out test split.

Writes overall and per-class metrics to models/<version>/metrics/.

Usage:
    python scripts/evaluate.py v1_yolo11n_baseline [--data data/neu_yolo/data.yaml]
"""

import argparse
import csv
from pathlib import Path

import torch
from ultralytics import YOLO

REPO_ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("version")
    parser.add_argument("--data", default="data/neu_yolo/data.yaml")
    parser.add_argument("--split", default="test")
    parser.add_argument("--imgsz", type=int, default=640)
    args = parser.parse_args()

    model_dir = REPO_ROOT / "models" / args.version
    model = YOLO(str(model_dir / "weights" / "best.pt"))

    results = model.val(
        data=str(REPO_ROOT / args.data),
        split=args.split,
        imgsz=args.imgsz,
        device=0 if torch.cuda.is_available() else "cpu",
        project=str(REPO_ROOT / "runs"),
        name=f"{args.version}_{args.split}",
        exist_ok=True,
        plots=True,
    )
    box = results.box

    metrics_dir = model_dir / "metrics"
    metrics_dir.mkdir(exist_ok=True)

    with open(metrics_dir / f"{args.split}_metrics.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Model", "Dataset", "Precision", "Recall", "mAP50", "mAP50_95"])
        writer.writerow([args.version, args.data, box.mp, box.mr, box.map50, box.map])

    with open(metrics_dir / f"{args.split}_per_class.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Class", "Precision", "Recall", "mAP50", "mAP50_95"])
        for i, class_id in enumerate(box.ap_class_index):
            p, r, ap50, ap = box.class_result(i)
            writer.writerow([results.names[int(class_id)], p, r, ap50, ap])

    print(f"{args.split}: P={box.mp:.4f} R={box.mr:.4f} mAP50={box.map50:.4f} mAP50-95={box.map:.4f}")
    print(f"Metrics written to {metrics_dir}")


if __name__ == "__main__":
    main()
