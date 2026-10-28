# v3_yolo11n_severstal_ft (seed 2 checkpoint)

**Base model:** [`v2_yolo11n_severstal_pretrain`](../v2_yolo11n_severstal_pretrain/MODEL_CARD.md), with the detection head rebuilt for the 6 NEU-DET classes
**Training data:** NEU-DET, 1,260 train / 360 val images
**Config:** [`train_config.yaml`](train_config.yaml) (AdamW, lr0 0.001, up to 100 epochs, patience 20)
**Inference:** about 5 ms per image on a Tesla T4 at 640 px

This card describes seed 2, the checkpoint with the best **validation** score of the three v3 seeds (val mAP50-95 0.388). It was chosen on validation, not on the test split.

## Test results, this checkpoint (180 images, 415 instances)

| Class | Precision | Recall | mAP50 | mAP50-95 |
|-------|-----------|--------|-------|----------|
| **all** | 0.725 | 0.695 | 0.737 | 0.411 |
| crazing | 0.674 | 0.257 | 0.455 | 0.158 |
| inclusion | 0.776 | 0.736 | 0.815 | 0.404 |
| patches | 0.767 | 0.838 | 0.842 | 0.520 |
| pitted_surface | 0.684 | 0.833 | 0.820 | 0.566 |
| rolled-in_scale | 0.582 | 0.594 | 0.576 | 0.302 |
| scratches | 0.865 | 0.911 | 0.916 | 0.517 |

## Across all 3 seeds (mean ± std)

| Metric | v3 | v1r control |
|--------|----|-------------|
| mAP50 | 0.747 ± 0.008 | 0.737 ± 0.016 |
| mAP50-95 | 0.422 ± 0.011 | 0.407 ± 0.007 |
| crazing AP50 | 0.393 ± 0.060 | 0.342 ± 0.016 |
| crazing recall | 0.257 ± 0.014 | 0.386 ± 0.029 |

## Notes

- Severstal pretraining made early training faster and more stable, but the final gain over the control is small and within seed noise.
- Crazing is still the weak class. v3 has higher precision on it but lower recall than the control, so it misses about three in four crazing defects.
- This checkpoint is not clearly better than the original `v1_yolo11n_baseline` on the test split.
