# PS-7: AI-Assisted Quality Inspection — Steel Surface Defect Detection

Detects and classifies surface defects on hot-rolled steel strips. The project has three parts:

- **Detector:** an object-detection model built on [Ultralytics YOLO11](https://docs.ultralytics.com/) and trained on the NEU-DET dataset.
- **Backend:** a FastAPI service (`steel-defect-backend/`) that runs the detector on images and videos and decides whether each item is approved, needs review, or is rejected.
- **Dashboard:** a Next.js page (`dashboard/`) that shows the model evaluation and lets you upload a video for inspection.

## Contents

- [Quickstart: run the demo](#quickstart-run-the-demo)
- [Command reference](#command-reference)
- [Defect classes](#defect-classes)
- [Repository structure](#repository-structure)
- [Models](#models)
- [Dataset](#dataset)
- [Training](#training)
- [Results](#results)
- [Usage](#usage)
- [Backend](#backend)
- [Dashboard](#dashboard)
- [Documentation](#documentation)
- [Roadmap](#roadmap)

## Quickstart: run the demo

Requirements: Python 3.10 or newer and Node.js 22.18 or newer.

```bash
# 1. Backend (FastAPI + YOLO) on http://localhost:8000
cd steel-defect-backend
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python run.py

# 2. Dashboard, in another terminal, on http://localhost:3000
cd dashboard
npm install
npm run dev
```

Open the dashboard and go to **Video inspection**. Upload `data/raw/ps7_test_images_raw_upload.mp4`, a 36-second test video. You get it back with every defect boxed, its confidence, and the video timestamp burned in. The dashboard raises an alert as soon as a defect is found.

- If port 3000 is taken, Next.js uses the next free port (3001, and so on). The terminal prints the URL.
- If the backend runs somewhere other than `http://localhost:8000`, start the dashboard with `NEXT_PUBLIC_INSPECT_API_URL=http://host:port npm run dev`.
- To check the backend, open `http://localhost:8000/health`. The interactive API docs are at `http://localhost:8000/docs`.

## Command reference

Run every command from the repository root unless it starts with `cd`. Lines marked "first time only" install dependencies.

### Run the demo

```bash
# Terminal 1: backend on http://localhost:8000
cd steel-defect-backend
python -m venv .venv && .venv/bin/pip install -r requirements.txt   # first time only
.venv/bin/python run.py

# Terminal 2: dashboard on http://localhost:3000
cd dashboard
npm install                                                         # first time only
npm run dev
```

### Train, evaluate and predict

```bash
pip install -r requirements.txt                                # first time only
python scripts/prepare_neu_det.py                              # download and build the dataset
python scripts/train.py configs/train/v1_yolo11n_baseline.yaml # train a version
python scripts/evaluate.py v1_yolo11n_baseline                 # test-set metrics
python scripts/predict.py v1_yolo11n_baseline path/to/images/  # predict on images
```

Training is slow without a GPU. The original runs used a Tesla T4 on Google Colab.

### Evaluate every model and refresh the dashboard data

```bash
python scripts/evaluate_all.py           # writes reports/eval_all/
python scripts/export_dashboard_json.py  # updates dashboard/data/evaluation.json
```

### Run the tests

```bash
cd steel-defect-backend
.venv/bin/pip install pytest httpx       # first time only
.venv/bin/python -m pytest tests

cd ../dashboard
npm run typecheck
```

### Stop the servers

Press `Ctrl+C` in each terminal. If a server was started in the background, stop whatever is listening on its port:

```bash
lsof -ti tcp:8000 | xargs kill   # backend
lsof -ti tcp:3000 | xargs kill   # dashboard (use the port it printed)
```

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
├── assets/
│   ├── video_demo/               # annotated demo video and its detection CSVs
│   └── casting/                  # casting defect classifier package (separate task)
├── configs/train/                # one YAML per model version (model, data, hyperparameters)
├── dashboard/                    # Next.js dashboard: evaluation results and video inspection
├── data/
│   ├── raw/                      # raw test video for the inspection demo (tracked)
│   └── neu_yolo/                 # generated dataset (git-ignored)
├── docs/                         # evaluation report, experiment plans and results, API docs
├── models/                       # model registry, see models/README.md
│   ├── best_v2.pt                # recommended detector, used by the backend
│   └── v1_yolo11n_baseline/ ...  # registered versions: weights, config, metrics, model card
├── notebooks/                    # Colab runners and experiments
│   └── casting/                  # casting defect classifier notebook
├── reports/eval_all/             # output of scripts/evaluate_all.py
├── runs/                         # Ultralytics outputs (git-ignored)
├── scripts/                      # dataset preparation, training, evaluation, prediction
├── steel-defect-backend/         # FastAPI inspection backend, with its own README and tests
├── requirements.txt              # Python dependencies for scripts/ (training and evaluation)
└── README.md
```

### Scripts

| Script | Purpose |
|--------|---------|
| `prepare_neu_det.py` | Download NEU-DET, convert it to YOLO format, and make the fixed split |
| `prepare_severstal.py` | Convert Severstal RLE masks to boxes and cut 256×256 tiles |
| `analyze_severstal_boxes.py` | Box statistics for the Severstal tiles |
| `visualize_dataset.py` | Draw labels on sample images, as a sanity check |
| `train.py` | Train from a config and register the result under `models/<version>/` |
| `evaluate.py` | Test-set metrics for one version, overall and per class |
| `compare.py` | Compare versions, mean ± std over seeds |
| `evaluate_all.py` | Evaluate every checkpoint on val and test, writing to `reports/eval_all/` |
| `export_dashboard_json.py` | Turn `reports/eval_all/` into `dashboard/data/evaluation.json` |
| `predict.py` | Run a version on images |

## Models

Every registered version is self-contained in `models/<version>/`. See [`models/README.md`](models/README.md) for the version table and naming rules.

**Recommended detector: `models/best_v2.pt`.** It was trained with hard-example mining and is the model the backend uses. On the test split it has the highest mAP50 (0.768), ties for the highest mAP50-95 (0.433), and misses the fewest defects. Its lead over the other good models is small (0.01–0.03 mAP), and on the validation split `v1_yolo11n_baseline` scores higher. So it is the best available candidate, not a clear winner. Full comparison: [`docs/MODEL_EVALUATION_REPORT.md`](docs/MODEL_EVALUATION_REPORT.md).

Do not use `best_v1.pt` or `best (1).pt`. Both score clearly lower, and `best (1).pt` has no documented origin.

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
data/neu_yolo/
├── data.yaml
├── images/{train,val,test}/
└── labels/{train,val,test}/
```

### Preparation steps

`scripts/prepare_neu_det.py` (and the original notebook) runs these steps:

1. **Download** the dataset using `kagglehub`.
2. **Audit:** check that images and XML files pair up, that filename stems are unique, and that every class name is expected.
3. **Split and convert** to YOLO format, then generate `data.yaml`.
4. **Visual check:** draw the converted boxes on sample images and compare them with the source XML.

## Training

Baseline configuration (`v1_yolo11n_baseline`):

| Parameter | Value |
|-----------|-------|
| Model | `yolo11n.pt` (2.6M params, 6.4 GFLOPs), COCO-pretrained |
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

The other versions (longer schedule, Severstal pretraining, fine-tuning with frozen layers) each have a config in `configs/train/`.

## Results

### Recommended model, `best_v2.pt` (test split, 180 images)

| Metric | Value |
|--------|-------|
| mAP@50 | 0.768 |
| mAP@50-95 | 0.433 |
| Recall at conf 0.25 | 0.719 |
| Missed defects | 117 of 416 |

Recall per class at conf 0.25: crazing 0.41, inclusion 0.75, patches 0.83, pitted_surface 0.81, rolled-in_scale 0.64, scratches 0.93.

### Baseline, `v1_yolo11n_baseline` (test split, 180 images, 415 instances)

These are the numbers recorded for the original v1 run.

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

### Observations

- `crazing` is the weakest class for every model. Even the best models find only 41–43% of crazing defects. `rolled-in_scale` is the next weakest. Both are faint, low-contrast textures with indistinct boundaries.
- `scratches`, `pitted_surface` and `patches` are detected reliably.
- Validation and test scores are close, which suggests the models are not badly overfitted.
- **Speed:** about 7 ms per image on a T4 GPU at 640 px, and roughly 60–100 ms per image on an M2 CPU.

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

model = YOLO("models/best_v2.pt")
results = model.predict("path/to/steel_image.jpg", imgsz=640, conf=0.25, iou=0.45)

for r in results:
    for box in r.boxes:
        print(r.names[int(box.cls)], float(box.conf), box.xyxy.tolist())
    r.save(filename="prediction.jpg")
```

### Reproducing training

Use the scripts above, or open `notebooks/v1_yolo11n_baseline_colab.ipynb` in Colab with a GPU runtime. The notebook is the original record of the v1 run and uses Colab paths (`/content/...`). `notebooks/ps7_train_and_evaluate.ipynb` produced `best_v1.pt` and `best_v2.pt`.

## Backend

`steel-defect-backend/` is a FastAPI service around the detector. It loads `models/best_v2.pt`, runs on CPU or CUDA, and stores inspections in SQLite.

- **Inspections:** upload a single image, a batch, or a video (`/api/v1/inspections/upload/...`). Videos are processed in the background, and progress is streamed over a WebSocket.
- **Quality decision:** each inspection is marked `APPROVED`, `REVIEW_REQUIRED` or `REJECTED` according to configurable rules (`/api/v1/quality-rules/`).
- **Analytics and reports:** first-pass yield, defect distribution, trends (`/api/v1/analytics/...`), and a CSV export (`/api/v1/reports/csv`).

Run the tests from `steel-defect-backend/`:

```bash
.venv/bin/pip install pytest httpx
.venv/bin/python -m pytest tests
```

Architecture, endpoint examples and configuration are in [`steel-defect-backend/README.md`](steel-defect-backend/README.md).

## Dashboard

`dashboard/` is a Next.js app with two parts:

- **Evaluation results:** the leaderboard, how much of each gap could be chance, per-class recall, and the casting classifier.
- **Video inspection:** upload a video to the backend and watch the defects come back (see [Quickstart](#quickstart-run-the-demo)).

```bash
cd dashboard
npm install
npm run dev            # http://localhost:3000
npm run typecheck      # optional: TypeScript check
```

By default the results come from `dashboard/data/evaluation.json`. To read from a backend instead, set `EVAL_API_URL` to an endpoint that returns the same JSON:

```bash
EVAL_API_URL=http://localhost:8000/evaluation npm run dev
```

The response shape is documented in [`docs/DASHBOARD_API.md`](docs/DASHBOARD_API.md). After re-running the evaluation, refresh the bundled file:

```bash
python scripts/evaluate_all.py
python scripts/export_dashboard_json.py
```

## Documentation

| Document | Contents |
|----------|----------|
| [`docs/MODEL_EVALUATION_REPORT.md`](docs/MODEL_EVALUATION_REPORT.md) | Every checkpoint evaluated the same way, with significance tests and recommendations |
| [`docs/RESULTS_SEVERSTAL_TRANSFER.md`](docs/RESULTS_SEVERSTAL_TRANSFER.md) | Results of the Severstal transfer-learning experiment |
| [`docs/SEVERSTAL_TRANSFER_PLAN.md`](docs/SEVERSTAL_TRANSFER_PLAN.md) | Plan for that experiment |
| [`docs/IMPROVEMENT_PLAN.md`](docs/IMPROVEMENT_PLAN.md) | Ideas for improving the weak classes |
| [`docs/DASHBOARD_API.md`](docs/DASHBOARD_API.md) | JSON shape the dashboard reads |
| [`models/README.md`](models/README.md) | Model registry and naming rules |
| [`steel-defect-backend/README.md`](steel-defect-backend/README.md) | Backend architecture and API reference |

### Casting defect classifier

`notebooks/casting/` and `assets/casting/` hold a separate image classifier that labels cast parts as `defective` or `ok`. On held-out test data it reaches 0.764 accuracy and misses 35% of defective parts, well below the 99.5% its package README claims. See section 5 of the evaluation report.

## Roadmap

- [x] Dataset audit and YOLO conversion
- [x] Baseline detector (YOLO11n)
- [x] Repo restructured into versioned models and reusable scripts
- [x] Transfer learning from Severstal (`notebooks/v2_severstal_transfer_colab.ipynb`): small overall gain (mAP50-95 0.422 vs 0.407 control, within noise), crazing recall not improved. See [`docs/RESULTS_SEVERSTAL_TRANSFER.md`](docs/RESULTS_SEVERSTAL_TRANSFER.md)
- [x] Hard-example mining (`best_v2.pt`): best test scores so far, on fewer training images
- [x] Production-line demonstration: FastAPI backend and dashboard video inspection
- [ ] Register `best_v2.pt` as a proper version under `models/` (config, metrics, model card)
- [ ] Apply the hard-example recipe to the full training set, with 3 seeds, selecting on the validation split
- [ ] Improve `crazing` and `rolled-in_scale`: label audit, CLAHE contrast enhancement, class oversampling
