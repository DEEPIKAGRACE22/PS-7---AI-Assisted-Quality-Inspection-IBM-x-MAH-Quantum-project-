"""Run a registered model version on images and save annotated predictions.

Usage:
    python scripts/predict.py v1_yolo11n_baseline path/to/image_or_folder [--conf 0.25]
"""

import argparse
from pathlib import Path

from ultralytics import YOLO

REPO_ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("version")
    parser.add_argument("source")
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--iou", type=float, default=0.45)
    parser.add_argument("--imgsz", type=int, default=640)
    args = parser.parse_args()

    model = YOLO(str(REPO_ROOT / "models" / args.version / "weights" / "best.pt"))
    results = model.predict(
        source=args.source,
        imgsz=args.imgsz,
        conf=args.conf,
        iou=args.iou,
        save=True,
        project=str(REPO_ROOT / "runs"),
        name=f"{args.version}_predict",
        exist_ok=True,
    )

    for r in results:
        detections = [f"{r.names[int(b.cls)]} ({float(b.conf):.2f})" for b in r.boxes]
        print(f"{Path(r.path).name}: {', '.join(detections) or 'no defects'}")
    print(f"Annotated images saved to {results[0].save_dir}")


if __name__ == "__main__":
    main()
