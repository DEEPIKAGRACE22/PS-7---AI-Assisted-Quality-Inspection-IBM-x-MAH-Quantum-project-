# v5_yolo26s_cls_neu

**Base model:** `yolo26s-cls.pt` (official Ultralytics ImageNet classification checkpoint, YOLO26s family). No weights from other models in this repo were used.
**Task:** image classification, one defect class per image (6 classes). It does not output boxes; use v4 for localization.
**Baseline:** [`v4_yolo26s_neu_det_s1`](../v4_yolo26s_neu_det_s1/MODEL_CARD.md), a detector whose detections are collapsed to one class per image (`scripts/eval_image_accuracy.py`).
**Training data:** NEU-DET, 1,260 train / 360 val images, the same image assignment as v4 (built by `scripts/prepare_neu_cls.py`; class = filename prefix). Test images were not used for training or selection.
**Config:** [`train_config.yaml`](train_config.yaml), `configs/train/v5_yolo26s_cls_neu.yaml`
**Hardware:** NVIDIA RTX 3090, about 5 s/epoch.

## Training recipe
imgsz 224, batch 64, up to 60 epochs with patience 20 (stopped at epoch 41), `optimizer=auto`, cosine LR, 3 warmup epochs, AMP, seed 0. Augmentation for grayscale defects: no hue shift, horizontal and vertical flips, scale 0.3, translate 0.1, rotation 5 deg. One run, one seed.

## Results (image-level accuracy)

| Model | Val (360) | Test (180) |
|-------|-----------|------------|
| v5_yolo26s_cls_neu (classifier) | 360/360 = 1.000 | 180/180 = 1.000 |
| v4_yolo26s_neu_det_s1 (detector, conf 0.05) | 357/360 = 0.992 | 180/180 = 1.000 |

Every class is 1.000 precision and recall on both splits. Metrics: `metrics/val_metrics.csv`, `metrics/test_metrics.csv`, confusion matrices in `metrics/image_accuracy_{val,test}.csv`, training curve in `metrics/train_results.csv`. The test split was evaluated once, after training.

## Notes
- **No measured gain over v4 on test.** Both score 180/180. The only difference is on val, where v4 misses 3 `pitted_surface` images; val was also used to choose v5's checkpoint (best val top-1, which reached 1.000 from epoch 21), so val is slightly optimistic for both.
- Test has 30 images per class, so 180/180 means the true accuracy is probably at least about 98%, not exactly 100%. A perfect score on a test set this small cannot separate the two models.
- Single seed; seed-to-seed variation was not measured.
- Classification only: for box quality (crazing recall 0.33 in v4) this model does not help.
- Images are 200x200 grayscale, upscaled to 224 for training and inference.
