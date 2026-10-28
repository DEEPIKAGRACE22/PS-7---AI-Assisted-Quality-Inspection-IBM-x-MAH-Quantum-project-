# Model Registry

Each model version lives in its own folder:

```
models/<version>/
├── weights/best.pt        # trained weights
├── train_config.yaml      # exact config used (copy of configs/train/<version>.yaml)
├── metrics/               # test_metrics.csv, test_per_class.csv, train_results.csv
└── MODEL_CARD.md          # what changed, results, notes
```

**Naming:** `v<N>_<architecture>_<short-change>`, for example `v2_yolo11s_gc10_pretrain`. Never overwrite an existing version; create a new one.

## Versions

All metrics are on the NEU-DET held-out test split (180 images, seed 42).

| Version | Base | Change vs previous | P | R | mAP50 | mAP50-95 | crazing AP50 |
|---------|------|--------------------|---|---|-------|----------|--------------|
| [v1_yolo11n_baseline](v1_yolo11n_baseline/MODEL_CARD.md) | yolo11n (COCO) | Baseline | 0.748 | 0.681 | 0.758 | 0.413 | 0.391 |
