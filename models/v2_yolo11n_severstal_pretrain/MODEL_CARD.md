# v2_yolo11n_severstal_pretrain

**Purpose:** pretraining stage for transfer learning. It is not a defect detector for NEU-DET: its 4 output classes are Severstal's unnamed defect types.

**Base model:** `yolo11n.pt` (COCO)
**Training data:** Severstal Steel Defect Detection, converted to YOLO boxes and cut into 256×256 tiles (`scripts/prepare_severstal.py`), split 90/10 by source image
**Config:** [`train_config.yaml`](train_config.yaml)
**Training:** 30 epochs, imgsz 256, batch 64, vertical and horizontal flips on

## Results (Severstal validation split)

| Best epoch | mAP50 | mAP50-95 |
|------------|-------|----------|
| 29 of 30 | 0.620 | 0.348 |

## Notes

- The best epoch is the second-to-last one, so training was still improving when it stopped. A longer pretraining run might transfer better.
- Boxes were derived from masks with a 15 px merge dilation. Visual checks showed many boxes much larger than the defect itself. `scripts/analyze_severstal_boxes.py` measures this for other kernel sizes.
- Used as the starting point for `v3_yolo11n_severstal_ft_s{0,1,2}`.
