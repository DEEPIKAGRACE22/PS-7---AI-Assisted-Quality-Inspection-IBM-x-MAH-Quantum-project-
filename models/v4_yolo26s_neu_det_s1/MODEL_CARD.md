# v4_yolo26s_neu_det (release: seed 1)

**Base model:** `yolo26s.pt` (official Ultralytics COCO checkpoint; 9.95M params, 22.8 GFLOPs). No weights from other models in this repo were used.
**Training data:** NEU-DET, 1,260 train / 360 val images, fixed split from `scripts/prepare_neu_det.py` (seed 42)
**Config:** [`train_config.yaml`](train_config.yaml), `configs/train/v4_yolo26s_neu_det.yaml`
**Hardware:** NVIDIA RTX 3090, about 6-7 s/epoch, about 11 GB VRAM at batch 32; about 3-4 ms/image inference at 640 px
**Release copy:** [`../best_v4_yolo26s.pt`](../best_v4_yolo26s.pt)

## Training recipe
imgsz 640, batch 32, up to 150 epochs with patience 30, `optimizer=auto`, cosine LR, 3 warmup epochs, AMP, RAM cache.
Augmentation tuned for grayscale defects: no hue shift, horizontal and vertical flips, mosaic 1.0 (off for the last 15 epochs), mixup 0.05, scale 0.3, translate 0.1, rotation 5 deg.
Three seeds (0, 1, 2) were trained. **Seed 1 is released because it has the best validation mAP50-95** (0.394); the test split was not used for selection.

## Test results, released seed (180 images, 416 instances)

| Class | Precision | Recall | mAP50 | mAP50-95 |
|-------|-----------|--------|-------|----------|
| **all** | 0.790 | 0.716 | 0.779 | 0.440 |
| crazing | 0.689 | 0.329 | 0.466 | 0.167 |
| inclusion | 0.815 | 0.800 | 0.864 | 0.464 |
| patches | 0.862 | 0.838 | 0.882 | 0.543 |
| pitted_surface | 0.721 | 0.806 | 0.827 | 0.626 |
| rolled-in_scale | 0.718 | 0.628 | 0.670 | 0.318 |
| scratches | 0.933 | 0.893 | 0.967 | 0.522 |

## All seeds (test)

| Seed | Val mAP50-95 | Test P | Test R | Test mAP50 | Test mAP50-95 |
|------|--------------|--------|--------|------------|----------------|
| 0 | 0.390 | 0.699 | 0.683 | 0.727 | 0.410 |
| 1 (released) | 0.394 | 0.790 | 0.716 | 0.779 | 0.440 |
| 2 | 0.385 | 0.777 | 0.712 | 0.773 | 0.444 |
| mean ± std | | 0.755 ± 0.049 | 0.703 ± 0.018 | 0.760 ± 0.028 | 0.431 ± 0.018 |

## Notes
- Seed-to-seed spread is large (test mAP50-95 0.410 to 0.444), as with the earlier models. The test set is small, so gaps under about 0.02 are within noise. The mean (0.431) is only slightly above the YOLO11n versions (0.407 to 0.422); the released seed's 0.440 is the best of the three seeds' best-by-val pick, not a guaranteed gain.
- Labels: the "corrected" annotations in `NEU_DET_Dataset_Annotation_Audit_Report/neu_corrected_annotations.zip` are byte-identical to the Kaggle originals (1800/1800 XMLs), so the standard labels were used. `prepare_neu_det.py --annotations` is available if a genuinely different set is supplied.
- Crazing (recall 0.33) and rolled-in_scale remain the weak classes.
- Exported to ONNX and run on test images as a sanity check.
- Images are 200x200 grayscale, upscaled to 640 for training and inference.
