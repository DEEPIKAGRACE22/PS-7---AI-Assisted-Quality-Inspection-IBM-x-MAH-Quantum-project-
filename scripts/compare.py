"""Summarise test metrics across model versions, averaging seed runs (<version>_s<N>).

Usage:
    python scripts/compare.py [--output models/comparison.csv]
"""

import argparse
import csv
import re
import statistics
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FOCUS_CLASSES = ["crazing", "rolled-in_scale"]


def read_rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def fmt(values):
    if len(values) == 1:
        return f"{values[0]:.3f}"
    return f"{statistics.mean(values):.3f} ± {statistics.stdev(values):.3f}"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "models" / "comparison.csv")
    args = parser.parse_args()

    groups = defaultdict(lambda: defaultdict(list))
    for metrics_path in sorted((REPO_ROOT / "models").glob("*/metrics/test_metrics.csv")):
        version = metrics_path.parent.parent.name
        group = re.sub(r"_s\d+$", "", version)
        overall = read_rows(metrics_path)[0]
        for key in ("Precision", "Recall", "mAP50", "mAP50_95"):
            groups[group][key].append(float(overall[key]))

        per_class_path = metrics_path.with_name("test_per_class.csv")
        if per_class_path.exists():
            for row in read_rows(per_class_path):
                if row["Class"] in FOCUS_CLASSES:
                    groups[group][f"{row['Class']}_AP50"].append(float(row["mAP50"]))

    columns = ["Precision", "Recall", "mAP50", "mAP50_95"] + [f"{c}_AP50" for c in FOCUS_CLASSES]
    rows = []
    for group, metrics in groups.items():
        runs = len(metrics["mAP50_95"])
        rows.append([group, runs] + [fmt(metrics[c]) if metrics[c] else "-" for c in columns])

    rows.sort(key=lambda r: r[0])
    header = ["Version", "Runs"] + columns

    with open(args.output, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)

    widths = [max(len(str(x)) for x in col) for col in zip(header, *rows)]
    for row in [header] + rows:
        print("  ".join(str(x).ljust(w) for x, w in zip(row, widths)))
    print(f"\nWritten to {args.output}")


if __name__ == "__main__":
    main()
