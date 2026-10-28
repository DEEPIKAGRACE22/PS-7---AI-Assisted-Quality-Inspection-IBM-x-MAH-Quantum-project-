"""Train a model version from a config file and register it under models/<version>/.

Usage:
    python scripts/train.py configs/train/v1_yolo11n_baseline.yaml
"""

import argparse
import shutil
from pathlib import Path

import torch
import yaml
from ultralytics import YOLO

REPO_ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("config", type=Path)
    parser.add_argument("--force", action="store_true", help="Overwrite an existing model version")
    args = parser.parse_args()

    config = yaml.safe_load(args.config.read_text())
    version = config["version"]
    model_dir = REPO_ROOT / "models" / version

    if (model_dir / "weights" / "best.pt").exists() and not args.force:
        raise SystemExit(f"{model_dir} already has weights. Use a new version name or --force.")

    data_yaml = REPO_ROOT / config["data"]
    assert data_yaml.exists(), f"Dataset not found: {data_yaml}. Run the matching prepare script first."

    # Local checkpoint paths are resolved against the repo; anything else is an Ultralytics model name
    model_source = REPO_ROOT / config["model"]
    model = YOLO(str(model_source) if model_source.exists() else config["model"])

    train_args = dict(config.get("train", {}))
    train_args.setdefault("device", 0 if torch.cuda.is_available() else "cpu")

    model.train(
        data=str(data_yaml),
        project=str(REPO_ROOT / "runs"),
        name=version,
        exist_ok=True,
        plots=True,
        **train_args,
    )

    run_dir = REPO_ROOT / "runs" / version
    (model_dir / "weights").mkdir(parents=True, exist_ok=True)
    shutil.copy2(run_dir / "weights" / "best.pt", model_dir / "weights" / "best.pt")
    shutil.copy2(args.config, model_dir / "train_config.yaml")
    if (run_dir / "results.csv").exists():
        (model_dir / "metrics").mkdir(exist_ok=True)
        shutil.copy2(run_dir / "results.csv", model_dir / "metrics" / "train_results.csv")

    print(f"Registered {version} at {model_dir}")
    print(f"Next: python scripts/evaluate.py {version}")


if __name__ == "__main__":
    main()
