# v1_yolo11n_baseline

**Base model:** `yolo11n.pt` (COCO-pretrained, 2.6M params)
**Training data:** NEU-DET, 1,260 train / 360 val images
**Config:** [`train_config.yaml`](train_config.yaml)
**Source notebook:** [`notebooks/v1_yolo11n_baseline_colab.ipynb`](../../notebooks/v1_yolo11n_baseline_colab.ipynb)
**Hardware:** Tesla T4 (Colab), about 7 ms per image inference at 640 px

## Test results (180 images, 415 instances)

| Class | Precision | Recall | mAP50 | mAP50-95 |
|-------|-----------|--------|-------|----------|
| **all** | 0.748 | 0.681 | 0.758 | 0.413 |
| crazing | 0.528 | 0.257 | 0.391 | 0.147 |
| inclusion | 0.748 | 0.703 | 0.808 | 0.425 |
| patches | 0.789 | 0.807 | 0.822 | 0.498 |
| pitted_surface | 0.857 | 0.778 | 0.869 | 0.585 |
| rolled-in_scale | 0.734 | 0.594 | 0.697 | 0.309 |
| scratches | 0.831 | 0.946 | 0.963 | 0.518 |

## Notes

- Trained with `patience=10`, so training may have stopped before 50 epochs.
- Crazing and rolled-in_scale are the weak classes.
