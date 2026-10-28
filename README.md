# PS-7: AI-Assisted Quality Inspection — Steel Surface Defect Detection

An object-detection model that locates and classifies surface defects on hot-rolled steel strips. It is built on [Ultralytics YOLO11](https://docs.ultralytics.com/) and trained on the NEU-DET dataset.

## Defect classes

| ID | Class | Description |
|----|-------|-------------|
| 0 | `crazing` | Network of fine surface cracks |
| 1 | `inclusion` | Non-metallic particles embedded in the surface |
| 2 | `patches` | Irregular discoloured regions |
| 3 | `pitted_surface` | Small pits or cavities |
| 4 | `rolled-in_scale` | Oxide scale pressed into the surface during rolling |
| 5 | `scratches` | Linear abrasion marks |

## Repository contents

| File | Purpose |
|------|---------|
| `Untitled15 (5).ipynb` | **Main notebook.** Covers the full pipeline: download, audit, convert, train, evaluate, predict and export. |
| `Untitled15 (4).ipynb` | Earlier version that only covers data preparation. Superseded by notebook (5). |
| `best.pt` | Trained YOLO11n weights (best epoch by validation fitness). |
| `ps7_test_metrics.csv` | Overall metrics on the held-out test set. |

## Dataset

- **Source:** [NEU Surface Defect Database (Kaggle)](https://www.kaggle.com/datasets/kaustubhdikshit/neu-surface-defect-database)
- 1,800 grayscale images, 200×200 px, 300 per class
- Pascal VOC XML bounding-box annotations; 4,189 boxes in total

### Splits

The original dataset has only train and validation splits. A class-balanced test set is held out from the original training images (30 per class, `seed=42`):

| Split | Images | Source |
|-------|--------|--------|
| train | 1,260 | Original train minus held-out test |
| val | 360 | Original validation |
| test | 180 | 30 per class, sampled from original train |

The annotations are converted from VOC (`xmin, ymin, xmax, ymax`) to YOLO format (`class xc yc w h`, normalised) and written to:

```
neu_yolo/
├── data.yaml
├── images/{train,val,test}/
└── labels/{train,val,test}/
```

## Pipeline

The notebook runs in this order:

1. **Download** the dataset using `kagglehub`.
2. **Audit:** check that images and XML files pair up, that filename stems are unique, and that every class name is expected.
3. **Split and convert** to YOLO format, then generate `data.yaml`.
4. **Visual check:** draw the converted boxes on sample images and compare them with the source XML.
5. **Train** YOLO11n from COCO-pretrained weights.
6. **Evaluate** on the held-out test split.
7. **Predict** on sample test images and export `best.pt` and the metrics CSV.

## Training configuration

| Parameter | Value |
|-----------|-------|
| Model | `yolo11n.pt` (2.6M params, 6.4 GFLOPs) |
| Epochs | 50 |
| Image size | 640 |
| Batch | 16 |
| Hardware | Tesla T4 (Google Colab) |

Augmentation is deliberately mild, so that defect textures are not distorted:

```python
hsv_h=0.015, hsv_s=0.3, hsv_v=0.2,      # illumination
degrees=3.0, translate=0.05, scale=0.15, shear=1.0,
mosaic=0.5, mixup=0.05, close_mosaic=10,
fliplr=0.5, flipud=0.0
```

## Results

### Test set (180 images, 415 instances)

| Class | Precision | Recall | mAP@50 | mAP@50-95 |
|-------|-----------|--------|--------|-----------|
| **all** | **0.748** | **0.681** | **0.758** | **0.413** |
| crazing | 0.528 | 0.257 | 0.391 | 0.147 |
| inclusion | 0.748 | 0.703 | 0.808 | 0.425 |
| patches | 0.789 | 0.807 | 0.822 | 0.498 |
| pitted_surface | 0.857 | 0.778 | 0.869 | 0.585 |
| rolled-in_scale | 0.734 | 0.594 | 0.697 | 0.309 |
| scratches | 0.831 | 0.946 | 0.963 | 0.518 |

The validation set gives similar scores: mAP@50 = 0.755 and mAP@50-95 = 0.390.

**Inference speed:** about 7 ms per image on a T4 at 640 px.

### Observations

- `crazing` is the weakest class: it detects only 26% of instances. `rolled-in_scale` is the next weakest. Both are faint, low-contrast textures with indistinct boundaries.
- `scratches`, `pitted_surface` and `patches` are detected reliably.
- Validation and test scores are close, which suggests the model is not badly overfitted.

## Usage

### Requirements

```bash
pip install ultralytics kagglehub pyyaml opencv-python matplotlib pandas
```

### Inference with the trained model

```python
from ultralytics import YOLO

model = YOLO("best.pt")
results = model.predict("path/to/steel_image.jpg", imgsz=640, conf=0.25, iou=0.45)

for r in results:
    for box in r.boxes:
        print(r.names[int(box.cls)], float(box.conf), box.xyxy.tolist())
    r.save(filename="prediction.jpg")
```

### Reproducing training

Open `Untitled15 (5).ipynb` in Google Colab with a GPU runtime and run all cells. The notebook paths assume Colab (`/content/...`), so edit them if you run it elsewhere.

## Roadmap

- [x] Dataset audit and YOLO conversion
- [x] Baseline detector (YOLO11n)
- [ ] Model-improvement experiment, compared fairly against the baseline on the same test split and focused on `crazing` and `rolled-in_scale`
- [ ] Production-line demonstration (real-time inference app)
- [ ] Refactor the notebooks into reusable scripts that do not depend on Colab
