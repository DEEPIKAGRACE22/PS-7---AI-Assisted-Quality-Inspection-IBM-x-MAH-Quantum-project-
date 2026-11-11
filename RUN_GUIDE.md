# RUN_GUIDE

Notebooks are in `notebooks/msdd/`. Each one is self-contained (library and experiment config are inlined), so the notebook file is all you upload.
Order: `00_download_and_audit` -> `01_split` -> `02_train`.

## Platform settings

| Notebook | Kaggle settings | Needs |
|---|---|---|
| 00 | Internet **On**, accelerator **None** (no GPU needed) | direct download URL; optional Secrets `KAGGLE_USERNAME`, `KAGGLE_KEY` |
| 01 | Internet On, accelerator None; **Add Input** = the private dataset made by 00 | persistent copy |
| 02 | Internet On (downloads yolov8l.pt etc.), accelerator **GPU T4 x2 or P100**, Add Input = same private dataset | persistent copy + splits |

Colab: same notebooks; they mount Drive and keep everything under `MyDrive/msdd/` (`dataset_copy/`, `audit/`, `splits/`, `runs/`). Kaggle is the tested-first path; Colab only differs in `L.get_paths()`.

## What is persisted, where

- `dataset_copy/` = the verified original archive(s) + `MANIFEST.json` (sha256) + `audit/`. This is what you attach later. SciDB is never contacted again.
- `splits/` (`train.txt`, `val.txt`, `test.txt`, `split_manifest.json`): small. On Kaggle keep them by saving notebook 01's output (or re-run 01: it is deterministic, seed 0, and refuses to change a split once a run has used it).
- `runs/<EXP>/` (`weights/last.pt`, `best.pt`, `results.csv`, `args.yaml`, plots, `DONE`): mirrored **every epoch**. On Kaggle this folder lives in `/kaggle/working/persist/runs`, which survives only if the session survives or you save a version. Between sessions, save the notebook output as a dataset (or attach the previous version's output) and re-run the same cell: it restores `last.pt` and **resumes**. Colab writes straight to Drive.
- Test results are written once per run (`eval/test_metrics.json`, `eval/test_per_class.csv`); re-running the test cell refuses unless you delete `test_done.json`.

## Running experiments

Run the `run_one("E#")` cells from the top. `E2` prints "NOT RUN" until Phase 2 wires Baseline B; `E8c/E8d` are skipped if the best run is E1 (E8a/E8b already repeat it). Select models from the **val** table cell, then run the test cell once per chosen run. After epoch 1 the notebook prints minutes/epoch; use it to recompute the estimates below.

## GPU-hour estimates (ESTIMATES, nothing here was measured on a GPU)

Assumptions: 9,239 images in total (page metadata) -> about 6,470 train / 1,390 val / 1,390 test at 70/15/15; YOLOv8l, imgsz 640, batch 16, AMP, one T4 at roughly 25 train img/s (my assumption, not a measurement) -> about 4.5-5 min/epoch including val. Scale factors are rules of thumb: m is about 0.45x of l; imgsz 960 about 2.25x; 1280 about 4x; YOLO11l about 0.9x; RT-DETR-l about 1.2-1.5x. Kaggle's weekly GPU quota is something I recall as about 30 h; check your account.

| Exp | Setup | Estimated T4-hours |
|---|---|---|
| E1 | yolov8l 640, 80 ep | ~6.5 |
| E2 | repo pipeline (only if feasible) | ~6.5 + rendering/mixer training (not estimated) |
| E3 | E1 at 960 (or 1280) | ~14 (960) / ~26 (1280) |
| E4 | best + oversampling (about 5-10% more images per epoch) | ~7 |
| E5 | best, up to 150 ep, patience 20 | ~7 to ~12 |
| E6 | YOLO11l | ~6 |
| E7 | RT-DETR-l, 80 ep | ~8-10 |
| E8 a-d | 4 more runs (E1 and best, seeds 1 and 2) | ~26 |
| Optional m-size ablations | E1m ~3, E3m ~6.5, E4m ~3.3 | ~13 |

Everything at l size is roughly 85-95 T4-hours, i.e. several weeks of quota. If quota is tight: run E1, then the m-size ablations (E1m, E3m, E4m) to pick the winning change, rerun only the winner at l, then E8 on E1 and the winner. T4 x2 (DDP, `DEVICE="0,1"`) may give about 1.5-1.8x but is untested here.

## Local reproduction of the checks

```
python -m venv .venv-msdd && .venv-msdd/bin/pip install ultralytics==8.4.210 kornia==0.9.0 pytorch_msssim==1.0.0 torchsummary==1.5.1 pandas matplotlib pyyaml nbformat nbclient ipykernel requests tqdm
python tools/build_notebooks.py                                   # regenerates the 3 notebooks from src/
python tools/smoke_test.py <scratch_dir>                          # synthetic data, CPU, yolov8n, 1 epoch, ~30 s
```
`tools/smoke_test.py` covers: login-page detection, download/verify/extract over HTTP, class-mismatch stop, audit, split, E1/E3/E4 training and test evaluation. Also checked once with throwaway scripts (not kept in the repo): kill-and-resume after wiping the local disk, the E6 (YOLO11) and E7 (RT-DETR) code paths at 1 epoch on CPU, and the fixed `src/train_tscm.py`, `train_pifm.py`, `train_detector.py`. It does **not** cover: Kaggle/Colab specifics (Secrets API upload, `/kaggle/temp`, Drive), real GPUs/DDP, full-size weights, or the real MSDD layout.
