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

## Repository structure

```
├── configs/train/            # one YAML per model version (model, data, hyperparameters)
├── scripts/
│   ├── prepare_neu_det.py    # download NEU-DET, convert to YOLO, fixed split
│   ├── train.py              # train from a config, register under models/<version>/
│   ├── prepare_severstal.py  # Severstal RLE masks -> boxes, 256x256 tiles
│   ├── visualize_dataset.py  # draw labels on samples (sanity check)
│   ├── evaluate.py           # test-set metrics (overall + per class)
│   ├── compare.py            # compare versions, mean ± std over seeds
│   ├── evaluate_all.py       # every checkpoint on val + test -> reports/eval_all/
│   ├── export_dashboard_json.py  # reports/eval_all/ -> dashboard/data/evaluation.json
│   └── predict.py            # run a version on images
├── dashboard/                # results dashboard (Next.js), see "Dashboard" below
├── steel-defect-backend/     # FastAPI + YOLO inspection backend, see "Video inspection"
├── models/                   # model registry (see models/README.md)
│   └── v1_yolo11n_baseline/  # weights, config, metrics, model card
├── notebooks/                # Colab runners and experiments (casting/ = casting classifier)
├── assets/                   # test video, annotated video demo, casting classifier package
├── docs/IMPROVEMENT_PLAN.md
├── data/                     # generated datasets (git-ignored)
└── runs/                     # Ultralytics outputs (git-ignored)
```

Every model version is self-contained in `models/<version>/`. See [`models/README.md`](models/README.md) for the version table and naming rules.

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
pip install -r requirements.txt
```

### Workflow

```bash
# 1. Build the dataset (data/neu_yolo)
python scripts/prepare_neu_det.py

# 2. Train a version from its config
python scripts/train.py configs/train/v1_yolo11n_baseline.yaml

# 3. Evaluate on the test split
python scripts/evaluate.py v1_yolo11n_baseline

# 4. Predict
python scripts/predict.py v1_yolo11n_baseline path/to/images/
```

### Adding a new model version

1. Copy a config in `configs/train/` and give it a new `version` name.
2. To fine-tune from an existing version, set `model: models/<version>/weights/best.pt`.
3. Train, evaluate, write `models/<new_version>/MODEL_CARD.md`, and add a row to `models/README.md`.

### Inference from Python

```python
from ultralytics import YOLO

model = YOLO("models/v1_yolo11n_baseline/weights/best.pt")
results = model.predict("path/to/steel_image.jpg", imgsz=640, conf=0.25, iou=0.45)

for r in results:
    for box in r.boxes:
        print(r.names[int(box.cls)], float(box.conf), box.xyxy.tolist())
    r.save(filename="prediction.jpg")
```

### Reproducing training

Use the scripts above, or open `notebooks/v1_yolo11n_baseline_colab.ipynb` in Colab with a GPU runtime. The notebook is the original record of the v1 run and uses Colab paths (`/content/...`).

## Dashboard

`dashboard/` is a Next.js page that shows the evaluation results: the leaderboard, how much of each gap could be chance, per-class recall, and the casting classifier. It needs Node.js 22.18 or newer.

```bash
cd dashboard
npm install
npm run dev            # http://localhost:3000
```

By default it reads `dashboard/data/evaluation.json`. To read from a backend instead, set `EVAL_API_URL` to an endpoint that returns the same JSON:

```bash
EVAL_API_URL=http://localhost:8000/evaluation npm run dev
```

The response shape is documented in [`docs/DASHBOARD_API.md`](docs/DASHBOARD_API.md). After re-running the evaluation, refresh the bundled file:

```bash
python scripts/evaluate_all.py
python scripts/export_dashboard_json.py
```

## Roadmap

- [x] Dataset audit and YOLO conversion
- [x] Baseline detector (YOLO11n)
- [x] Repo restructured into versioned models and reusable scripts
- [x] Transfer learning from Severstal (`notebooks/v2_severstal_transfer_colab.ipynb`): small overall gain (mAP50-95 0.422 vs 0.407 control, within noise), crazing recall not improved. See [`docs/RESULTS_SEVERSTAL_TRANSFER.md`](docs/RESULTS_SEVERSTAL_TRANSFER.md)
- [ ] Improve `crazing` and `rolled-in_scale`: label audit, CLAHE contrast enhancement, class oversampling
- [ ] Production-line demonstration (real-time inference app)

## Video inspection

Upload a conveyor video and get it back with every defect boxed, its confidence, and the video timestamp burned in. The dashboard raises an alert as soon as a defect is found. It uses the recommended model, `models/best_v2.pt`.

```bash
# 1. Backend (FastAPI + YOLO), port 8000
cd steel-defect-backend
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python run.py

# 2. Dashboard, in another terminal
cd dashboard
npm install
npm run dev            # then open http://localhost:3000 and go to "Video inspection"
```

If the backend runs somewhere other than `http://localhost:8000`, start the dashboard with `NEXT_PUBLIC_INSPECT_API_URL=http://host:port npm run dev`. `assets/videos/ps7_test_images_raw_upload.mp4` is a 36-second test video.
