# Plan: Transfer Learning from Severstal → NEU-DET

**Goal:** Pretrain a detector on the much larger Severstal steel dataset so that its backbone learns steel-surface textures, then fine-tune it on NEU-DET. The result should beat `v1_yolo11n_baseline` on the same NEU-DET test split, especially on `crazing` (AP50 0.39) and `rolled-in_scale` (AP50 0.70).

**Success criteria:** test mAP50-95 > 0.413 (v1), averaged over 3 seeds, with the gap bigger than the seed-to-seed spread. Crazing AP50 should also improve.

---

## 1. The Severstal dataset

| Property | Value |
|----------|-------|
| Source | Kaggle competition `severstal-steel-defect-detection` |
| Images | 12,568 training images, 1600×256 px, grayscale saved as 3-channel JPG |
| Defect images | ~6,700. The other ~5,900 have no defects. |
| Classes | 4 unnamed classes (`ClassId` 1–4) |
| Labels | **Segmentation masks** stored as run-length encoding (RLE) in `train.csv` (`ImageId, ClassId, EncodedPixels`) |
| Class imbalance | Class 3 dominates (~5,100 images); class 2 is rare (~250 images) |
| Test set | `test_images/` has no labels, so it is not used |

### Differences from NEU-DET

| | NEU-DET | Severstal |
|--|---------|-----------|
| Image size | 200×200 | 1600×256 (very wide) |
| Label type | Bounding boxes | Pixel masks |
| Classes | 6 named | 4 unnamed, which **do not map** to the NEU classes |
| Product | Hot-rolled strip | Steel sheet, different camera and lighting |

**Consequence:** we transfer only the **backbone and neck** (the learned texture features). The detection head is rebuilt for NEU's 6 classes during fine-tuning, and Ultralytics handles this automatically when `nc` changes.

---

## 2. Data preparation (`scripts/prepare_severstal.py`)

### 2.1 Download
- Join the competition on Kaggle and accept its rules first. This is required even though the competition has closed, and the rules restrict the data to non-commercial and research use, which we must respect.
- Download with `kagglehub.competition_download("severstal-steel-defect-detection")`, or with the Kaggle CLI using `~/.kaggle/kaggle.json`.

### 2.2 Convert masks to bounding boxes
1. Decode the RLE into a 256×1600 mask for each (image, class). Pixel numbering is **column-major and 1-indexed**, so a wrong decode gives transposed masks.
2. Run `cv2.connectedComponentsWithStats` on each mask, which gives one box per connected defect region.
3. **Filter noise:** drop components smaller than a minimum area (start with 40 px² and tune by eye).
4. **Merge fragments:** class 3 and 4 defects are often split into many nearby blobs. Dilate the mask before taking components (for example with a 15×15 kernel) so that one defect becomes one box. Check this visually.

### 2.3 Tile the wide images
1600×256 images squashed to 640 px would shrink defects badly, and NEU-DET uses square 200 px images. So:
- Cut each image into **6 overlapping 256×256 tiles** (stride about 269), which matches NEU's scale and aspect ratio.
- Clip boxes to each tile, and drop boxes that keep less than 30% of their area after clipping.

### 2.4 Balance and split
- Keep **all tiles containing defects**, plus a random **~15% of defect-free tiles** as negatives so the model learns what normal steel looks like.
- Split by **source image**, not by tile, so that no image leaks across splits. Use 90% train and 10% val with `seed=42`.
- Optionally oversample class 2 tiles (×3).
- Output goes to `data/severstal_yolo/` with `data.yaml` (`nc=4`).

### 2.5 Sanity checks (must pass before training)
- Overlay decoded masks and boxes on about 20 random images. Masks must line up with the visible defects.
- Report box counts per class, box-size histograms, and the number of tiles in each split.
- Expect roughly 20k–30k training tiles; record the exact numbers.

---

## 3. Experiments

All models are YOLO11n unless stated, so any gain comes from pretraining and not from model size. Each run gets a config in `configs/train/` and a version folder in `models/`.

| Version | Stage | Starts from | Data | Key settings |
|---------|-------|-------------|------|--------------|
| `v2_yolo11n_severstal_pretrain` | Pretrain | `yolo11n.pt` (COCO) | Severstal tiles | 30 epochs, imgsz 256, batch 64, `flipud=0.5`, `fliplr=0.5`, `patience=10` |
| `v3_yolo11n_severstal_ft` | Fine-tune | v2 `best.pt` | NEU-DET | Same as v1, but `lr0=0.001` and 100 epochs with `patience=20` |
| `v3b_yolo11n_severstal_ft_freeze` | Fine-tune | v2 `best.pt` | NEU-DET | As v3, plus `freeze=10` (frozen backbone) |
| `v1r_yolo11n_baseline_long` | **Control** | `yolo11n.pt` | NEU-DET | v1 config with the **same epochs, patience and learning rate as v3**, so the comparison is fair |

**Why the control run (v1r) matters:** v3 trains longer than v1, which used `patience=10`. Without v1r, any gain could come from the longer training and not from Severstal.

### Optional follow-ups (only if v3 beats v1r)
- `v4`: repeat with YOLO11s.
- `v5`: imgsz 320 for both stages, since NEU images are 200 px and this could be faster with no loss.
- Combine with CLAHE preprocessing (plan Phase 2.3).

### Evaluation
- Use `scripts/evaluate.py` on the **NEU-DET test split** (180 images, seed 42), the same split as v1.
- Run v1r, v3 and v3b with 3 seeds each (`seed=0,1,2`) and report the mean ± std.
- Add every result to `models/README.md`. For each version, report overall P, R, mAP50 and mAP50-95, plus crazing and rolled-in_scale AP.
- Also report Severstal val mAP for v2. That number isn't the goal, but it shows whether pretraining learned anything.

---

## 4. Code changes

| File | Change |
|------|--------|
| `scripts/prepare_severstal.py` | **New:** download, RLE decode, masks to boxes, tiling, balancing, splitting, `data.yaml` |
| `scripts/visualize_dataset.py` | **New:** draws labels on random samples for any YOLO dataset (used for the sanity checks) |
| `configs/train/v2_*.yaml`, `v3_*.yaml`, `v3b_*.yaml`, `v1r_*.yaml` | **New** configs |
| `scripts/train.py` | Add a `--seed` override, and append the seed to the version folder so that 3-seed runs don't collide |
| `notebooks/v2_severstal_transfer_colab.ipynb` | **New:** a thin Colab runner that clones the repo and calls the scripts, because training needs a GPU |
| `requirements.txt` | No change (`opencv-python` is already listed) |

---

## 5. Compute and logistics

- **Hardware:** Colab T4 (free tier sessions last about 12 hours and can disconnect).
- **Rough time estimate:** Severstal pretraining is about 25k tiles × 30 epochs at 256 px, roughly 3–5 hours on a T4. Each NEU fine-tune takes about 15–30 minutes.
- **Disconnects:** set `save_period=5` and resume with `resume=True`. Copy `runs/` to Google Drive after each stage.
- **Storage:** the Severstal download is about 1.6 GB and the tiles about 2 GB. Both are git-ignored; only the weights (about 5 MB each) go into `models/`.

---

## 6. Risks

| Risk | Mitigation |
|------|-----------|
| The domain gap is too large and gives no gain, or makes results worse | The v3b frozen variant and the v1r control show this clearly. A negative result is still a valid finding. |
| Boxes made from masks are noisy (fragments, huge merged regions) | Do the visual sanity check, and tune the dilation and area threshold before training. |
| RLE decoding bugs (transposed masks) | Overlay check on known images before going further. |
| Colab time limits | Checkpoints and resume, plus backups to Drive. |
| Competition data license | Use it for research and education only, and don't commit the images. |

---

## 7. Order of work

1. Write `prepare_severstal.py` and `visualize_dataset.py`, then run them in Colab and check the overlays. **This is the main checkpoint: stop and review the overlays before continuing.**
2. Train the v1r control (3 seeds). This gives the real baseline.
3. Pretrain v2 on Severstal.
4. Fine-tune v3 and v3b from v2 (3 seeds each).
5. Compare and update `models/README.md` and the model cards. Decide on the follow-ups.
