"""Build the dashboard's data file from the evaluation outputs in reports/eval_all/.

The output follows the contract in docs/DASHBOARD_API.md, so the same JSON
can be served by a backend later.

Usage:
    python scripts/export_dashboard_json.py [--out dashboard/data/evaluation.json]
"""

import argparse
import csv
import json
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = REPO_ROOT / "reports" / "eval_all"
REFERENCE = "loose:best_v2.pt"

# Facts about each checkpoint that are not in the metrics, taken from the
# notebooks and docs/MODEL_EVALUATION_REPORT.md.
DETECTORS = {
    "loose:best_v2.pt": ("best_v2.pt", False, "recommended",
                         "Half of the train split plus the hardest half of the rest (hard-example mining)",
                         "Highest test score, but its lead over v1, v1r and v3 is mostly within noise. Needs registering as a version."),
    "v1_yolo11n_baseline": ("v1 baseline", True, "ok", "Full train split, 50 epochs",
                            "Highest score on the validation split."),
    "v1r_yolo11n_baseline_long_s0": ("v1r · seed 0", True, "ok", "Full train split, AdamW, up to 100 epochs",
                                     "Control for v3: same schedule, no Severstal pretraining."),
    "v1r_yolo11n_baseline_long_s1": ("v1r · seed 1", True, "ok", "Full train split, AdamW, up to 100 epochs",
                                     "Control for v3: same schedule, no Severstal pretraining."),
    "v1r_yolo11n_baseline_long_s2": ("v1r · seed 2", True, "ok", "Full train split, AdamW, up to 100 epochs",
                                     "Control for v3: same schedule, no Severstal pretraining."),
    "v3_yolo11n_severstal_ft_s0": ("v3 · seed 0", True, "ok", "Severstal pretrain (v2), then fine-tuned on NEU-DET",
                                   "Not better than v1r beyond seed-to-seed variation."),
    "v3_yolo11n_severstal_ft_s1": ("v3 · seed 1", True, "ok", "Severstal pretrain (v2), then fine-tuned on NEU-DET",
                                   "Not better than v1r beyond seed-to-seed variation."),
    "v3_yolo11n_severstal_ft_s2": ("v3 · seed 2", True, "ok", "Severstal pretrain (v2), then fine-tuned on NEU-DET",
                                   "Picked by the model card on validation score; mid-table on both splits."),
    "loose:best_v1.pt": ("best_v1.pt", False, "do_not_use", "Half of the train split",
                         "Clearly weaker than every full-data model."),
    "loose:best (1).pt": ("best (1).pt", False, "do_not_use", "Unknown: fine-tuned 25 epochs from an undocumented checkpoint",
                          "Weakest model, origin undocumented; its test score could be inflated."),
}

CAVEATS = [
    "180 test images give intervals of about ±0.04 on mAP50, so gaps below about 0.03 should not be treated as real.",
    "best_v2.pt tops the test split, which makes its test score look better than it will be on new images.",
    "The training data for best (1).pt is unknown.",
    "best_v1.pt and best_v2.pt are single runs with no seed repeats.",
    "v2_yolo11n_severstal_pretrain predicts Severstal classes and was not scored.",
    "CPU latency was measured on a busy laptop; only its order of magnitude is reliable.",
]

OVERALL_FIELDS = ["precision", "recall", "mAP50", "mAP50_95", "recall_at_conf025",
                  "missed_at_conf025", "false_alarms_at_conf025", "image_hit_rate_at_conf025"]
CLASS_FIELDS = ["AP50", "AP50_95", "recall_at_conf025", "gt_boxes"]
INT_FIELDS = {"missed_at_conf025", "false_alarms_at_conf025", "gt_boxes"}


def number(field, value):
    return int(float(value)) if field in INT_FIELDS else round(float(value), 4)


def read_csv(name):
    with open(EVAL_DIR / name, newline="") as f:
        return list(csv.DictReader(f))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="dashboard/data/evaluation.json")
    args = parser.parse_args()

    overall = read_csv("overall.csv")
    per_class = read_csv("per_class.csv")
    gaps = read_csv("bootstrap_gap.csv")
    casting = json.loads((EVAL_DIR / "casting.json").read_text())

    classes = list(dict.fromkeys(row["class"] for row in per_class))
    splits = {}
    for row in overall:
        if row["model"] == REFERENCE:
            splits[row["split"]] = {"images": int(row["images"]), "boxes": int(float(row["gt_boxes"]))}

    detectors = []
    for model_id, (label, registered, status, trained_on, notes) in DETECTORS.items():
        rows = [r for r in overall if r["model"] == model_id]
        gap = {
            r["metric"]: {k: float(r[k]) for k in ["mean", "lo", "hi"]}
            for r in gaps if r["model"] == model_id
        }
        detectors.append({
            "id": model_id.replace("loose:", "").replace(" ", "_").replace("(", "").replace(")", "").replace(".pt", ""),
            "checkpoint": model_id,
            "label": label,
            "registered": registered,
            "status": status,
            "trained_on": trained_on,
            "notes": notes,
            "cpu_ms": round(float(rows[0]["cpu_ms_per_image"]), 1),
            "size_mb": round(float(rows[0]["size_mb"]), 2),
            "metrics": {r["split"]: {f: number(f, r[f]) for f in OVERALL_FIELDS} for r in rows},
            "per_class": {
                split: [
                    {"class": r["class"], **{f: number(f, r[f]) for f in CLASS_FIELDS}}
                    for r in per_class if r["model"] == model_id and r["split"] == split
                ]
                for split in ["val", "test"]
            },
            "gap_to_reference": gap or None,
        })

    classifiers = [{
        "id": m["id"].replace(".keras", ""),
        "label": m["id"],
        "dataset": casting["dataset"],
        "test_images": casting["test_images"],
        "reported_accuracy": casting["reported_accuracy"],
        **{k: m[k] for k in ["accuracy", "auc", "defective_recall", "defective_precision", "ok_recall",
                             "confusion_matrix", "cpu_ms"]},
    } for m in casting["models"]]

    evaluation = {
        "generated_at": date.today().isoformat(),
        "reference_model": DETECTORS[REFERENCE][0],
        "splits": splits,
        "classes": classes,
        "detectors": detectors,
        "classifiers": classifiers,
        "caveats": CAVEATS,
    }
    out = REPO_ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evaluation, indent=2) + "\n")
    print(f"Wrote {len(detectors)} detectors and {len(classifiers)} classifiers to {out}")


if __name__ == "__main__":
    main()
