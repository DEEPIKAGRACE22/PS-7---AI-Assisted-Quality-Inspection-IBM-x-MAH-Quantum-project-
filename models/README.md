# Model Registry

Each model version lives in its own folder:

```
models/<version>/
├── weights/best.pt        # trained weights
├── train_config.yaml      # exact config used (copy of configs/train/<version>.yaml)
├── metrics/               # test_metrics.csv, test_per_class.csv, train_results.csv
└── MODEL_CARD.md          # what changed, results, notes (where written)
```

**Naming:** `v<N>_<architecture>_<short-change>`. Runs repeated with different seeds get an `_s<seed>` suffix (for example `v3_yolo11n_severstal_ft_s0`). Never overwrite an existing version; create a new one.

`comparison.csv` is produced by `scripts/compare.py` and averages the seed runs of each version.

## Versions

All metrics are on the NEU-DET held-out test split (180 images, seed 42). Seeded versions show mean ± std over 3 seeds. Full analysis: [`docs/RESULTS_SEVERSTAL_TRANSFER.md`](../docs/RESULTS_SEVERSTAL_TRANSFER.md).

| Version | Base | Change | P | R | mAP50 | mAP50-95 | crazing AP50 | rolled-in_scale AP50 |
|---------|------|--------|---|---|-------|----------|--------------|----------------------|
| [v1_yolo11n_baseline](v1_yolo11n_baseline/MODEL_CARD.md) (1 run) | yolo11n (COCO) | Baseline | 0.748 | 0.681 | 0.758 | 0.413 | 0.391 | 0.697 |
| v1r_yolo11n_baseline_long (×3) | yolo11n (COCO) | Control: v1 augmentation, v3 schedule (AdamW, 100 epochs, patience 20) | 0.668 ± 0.025 | 0.730 ± 0.001 | 0.737 ± 0.016 | 0.407 ± 0.007 | 0.342 ± 0.016 | 0.607 ± 0.045 |
| [v2_yolo11n_severstal_pretrain](v2_yolo11n_severstal_pretrain/MODEL_CARD.md) | yolo11n (COCO) | Pretrained on Severstal tiles (4 classes, not evaluated on NEU-DET) | n/a | n/a | n/a | n/a | n/a | n/a |
| [v3_yolo11n_severstal_ft](v3_yolo11n_severstal_ft_s2/MODEL_CARD.md) (×3) | v2 | Fine-tuned on NEU-DET | 0.720 ± 0.007 | 0.704 ± 0.008 | 0.747 ± 0.008 | 0.422 ± 0.011 | 0.393 ± 0.060 | 0.636 ± 0.052 |

**Reading the table:** compare v3 against **v1r**, which has the same training schedule. The v3 gain in mAP50-95 (+0.015) is within seed-to-seed noise, and the original v1 (a single run) scores as well as either. Seed variation alone moves crazing AP50 by up to 0.12.

## Other files

`best (1).pt` in this folder is an older upload whose origin is not documented. It is not a registered version and is not used by any script.
