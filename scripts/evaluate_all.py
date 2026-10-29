"""Evaluate every NEU-DET detector checkpoint in models/ on the same splits.

For each checkpoint, writes overall and per-class mAP on the val and test
splits, plus what an operator would see at the deployment threshold
(conf 0.25): per-class recall, missed defects, false alarms, and the share of
images where at least one defect is found. Also measures CPU latency.

Usage:
    python scripts/evaluate_all.py [--data data/neu_yolo/data.yaml] [--out reports/eval_all]
"""

import argparse
import csv
import time
from pathlib import Path

import numpy as np
import torch
from ultralytics import YOLO
from ultralytics.utils.metrics import box_iou

REPO_ROOT = Path(__file__).resolve().parent.parent
LATENCY_IMAGES = 50
DEPLOY_CONF = 0.25
MATCH_IOU = 0.5


def find_checkpoints():
    checkpoints = {}
    for path in sorted((REPO_ROOT / "models").glob("*/weights/best.pt")):
        checkpoints[path.parent.parent.name] = path
    for path in sorted((REPO_ROOT / "models").glob("*.pt")):
        checkpoints[f"loose:{path.name}"] = path
    return checkpoints


def device():
    if torch.cuda.is_available():
        return 0
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def load_labels(image_path, width, height):
    label_path = image_path.parent.parent.parent / "labels" / image_path.parent.name / f"{image_path.stem}.txt"
    rows = np.loadtxt(label_path, ndmin=2)
    classes = rows[:, 0].astype(int)
    cx, cy, w, h = rows[:, 1] * width, rows[:, 2] * height, rows[:, 3] * width, rows[:, 4] * height
    boxes = np.stack([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], axis=1)
    return classes, torch.tensor(boxes, dtype=torch.float32)


def deployment_counts(model, images, num_classes):
    """Greedy one-to-one matching of predictions to ground truth at DEPLOY_CONF."""
    hits = np.zeros(num_classes, int)
    gt_count = np.zeros(num_classes, int)
    false_alarms = np.zeros(num_classes, int)
    images_with_hit = 0

    for image in images:
        result = model.predict(str(image), imgsz=640, conf=DEPLOY_CONF, device=device(), verbose=False)[0]
        height, width = result.orig_shape
        gt_classes, gt_boxes = load_labels(image, width, height)
        np.add.at(gt_count, gt_classes, 1)

        pred_classes = result.boxes.cls.cpu().numpy().astype(int)
        pred_boxes = result.boxes.xyxy.cpu()
        matched_gt = set()
        if len(pred_classes):
            iou = box_iou(pred_boxes, gt_boxes).numpy()
            for p in np.argsort(-result.boxes.conf.cpu().numpy()):
                candidates = [
                    g for g in np.argsort(-iou[p])
                    if iou[p, g] >= MATCH_IOU and g not in matched_gt and gt_classes[g] == pred_classes[p]
                ]
                if candidates:
                    matched_gt.add(candidates[0])
                    hits[pred_classes[p]] += 1
                else:
                    false_alarms[pred_classes[p]] += 1
        images_with_hit += bool(matched_gt)

    return hits, gt_count, false_alarms, images_with_hit / len(images)


def measure_latency(model, images):
    model.predict(str(images[0]), imgsz=640, device="cpu", verbose=False)
    start = time.perf_counter()
    for image in images:
        model.predict(str(image), imgsz=640, device="cpu", verbose=False)
    return (time.perf_counter() - start) / len(images) * 1000


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", default="data/neu_yolo/data.yaml")
    parser.add_argument("--out", default="reports/eval_all")
    args = parser.parse_args()

    out_dir = REPO_ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    data_root = (REPO_ROOT / args.data).parent

    overall_rows, class_rows = [], []
    for name, path in find_checkpoints().items():
        model = YOLO(str(path))
        if len(model.names) != 6:
            print(f"skip {name}: {len(model.names)} classes, not a NEU-DET model")
            continue

        latency = measure_latency(model, sorted(data_root.glob("images/test/*.jpg"))[:LATENCY_IMAGES])
        for split in ["val", "test"]:
            results = model.val(
                data=str(REPO_ROOT / args.data),
                split=split,
                imgsz=640,
                batch=16,
                device=device(),
                project=str(REPO_ROOT / "runs" / "eval_all"),
                name=f"{name.replace(':', '_')}_{split}",
                exist_ok=True,
                plots=True,
                verbose=False,
            )
            box = results.box
            images = sorted(data_root.glob(f"images/{split}/*.jpg"))
            hits, gt_count, false_alarms, image_hit_rate = deployment_counts(model, images, len(model.names))

            overall_rows.append({
                "model": name, "split": split,
                "precision": box.mp, "recall": box.mr, "mAP50": box.map50, "mAP50_95": box.map,
                "recall_at_conf025": hits.sum() / gt_count.sum(),
                "missed_at_conf025": gt_count.sum() - hits.sum(),
                "false_alarms_at_conf025": false_alarms.sum(),
                "image_hit_rate_at_conf025": image_hit_rate,
                "gt_boxes": gt_count.sum(), "images": len(images),
                "cpu_ms_per_image": latency, "size_mb": path.stat().st_size / 1e6,
            })
            ap_by_class = {int(c): box.class_result(i) for i, c in enumerate(box.ap_class_index)}
            for class_id, class_name in model.names.items():
                p, r, ap50, ap = ap_by_class[class_id]
                class_rows.append({
                    "model": name, "split": split, "class": class_name,
                    "precision": p, "recall": r, "AP50": ap50, "AP50_95": ap,
                    "recall_at_conf025": hits[class_id] / gt_count[class_id],
                    "missed_at_conf025": gt_count[class_id] - hits[class_id],
                    "false_alarms_at_conf025": false_alarms[class_id],
                    "gt_boxes": gt_count[class_id],
                })
        print(f"done {name}")

    for filename, rows in [("overall.csv", overall_rows), ("per_class.csv", class_rows)]:
        with open(out_dir / filename, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    print(f"Metrics written to {out_dir}")


if __name__ == "__main__":
    main()
