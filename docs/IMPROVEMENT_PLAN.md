# Model Improvement Plan

**Baseline:** YOLO11n, 50 epochs, imgsz 640. On the test set it scores **mAP@50 = 0.758** and **mAP@50-95 = 0.413**.
**Weak classes:** `crazing` (recall 0.26, mAP@50 0.39) and `rolled-in_scale` (mAP@50 0.70).
**Goal:** raise overall mAP@50-95 and lift crazing and rolled-in_scale, while keeping inference fast enough for a production line (< 20 ms per image on a GPU).

---

## Phase 0: Fair evaluation protocol (do this first)

Without this, no comparison between runs means anything.

1. **Freeze the splits.** Keep the same `seed=42` train/val/test split for every experiment. Never tune on the test set.
2. **Change one variable per experiment** relative to the baseline, unless the run is a planned combination.
3. **Run 3 seeds per configuration** (`seed=0,1,2`) and report the mean ± standard deviation. With only 180 test images, a single run can easily move by ±0.01–0.02 mAP from noise alone.
4. **Log every run** in `experiments.csv` with these columns: run name, config diff, seed, val mAP50/50-95, test P/R/mAP50/mAP50-95, crazing AP, rolled-in_scale AP, ms/img, params.
5. **Primary metric:** test mAP@50-95, with per-class AP for the weak classes. **Secondary metrics:** recall at the operating confidence (missing a defect usually costs more than a false alarm), and latency.

---

## Phase 1: Cheap, high-value levers (SKIPPED)

> The team tried these earlier without a useful gain, so the work moves straight to Phase 3.

Each experiment is about 15–40 minutes on a Colab T4.

| # | Experiment | Change | Why |
|---|-----------|--------|-----|
| 1.1 | Longer training | `epochs=150, patience=30` | 50 epochs is short for 1,260 images; the curves had probably not plateaued. |
| 1.2 | Bigger model | `yolo11s`, then `yolo11m` | `n` has limited capacity for subtle textures. `s` is about 3× the cost and usually a clear gain. |
| 1.3 | Vertical flip and rotation | `flipud=0.5`, `degrees=0→90-multiples` (via custom aug) | Steel defects have no "up" direction, so this effectively quadruples orientation diversity. |
| 1.4 | Image size | Compare `imgsz=320`, `640`, `800` | The native size is 200 px. Upscaling to 640 may add nothing; 320 would be about 4× faster. |
| 1.5 | Less mosaic and mixup | `mosaic=0.0` or `1.0`, `mixup=0` | Mosaic tiles 200 px textures together and can create misleading context. This needs testing either way. |

**Expected outcome:** the best combination of 1.1–1.5 should give a meaningful gain, most likely from model size and training length.

---

## Phase 2: Targeting crazing and rolled-in_scale

| # | Experiment | Details |
|---|-----------|---------|
| 2.1 | **Error analysis first** | Look at the confusion matrix and false negatives for crazing. Are the defects being *missed* (background) or *confused* with rolled-in_scale? Are the ground-truth boxes inconsistent? Some crazing annotations cover the whole image, others cover strips. |
| 2.2 | **Label audit** | Spot-check about 50 crazing and rolled-in_scale annotations. If the labels are inconsistent, the model can't learn a consistent target, and fixing them can help more than any model change. |
| 2.3 | **CLAHE contrast enhancement** | Apply CLAHE as a preprocessing step (to both training and inference images). Crazing is low-contrast, so local contrast equalisation should make its texture more visible. |
| 2.4 | **Class-aware sampling** | Oversample crazing and rolled-in_scale images, or duplicate them in the train list. |
| 2.5 | **Loss tuning** | Raise `cls` gain, or try `box`/`dfl` weights. This is lower priority. |

---

## Phase 3: Transfer learning from other steel datasets (your question)

**Short answer:** yes, it's worth trying, but **after Phases 1–2**. It costs much more to set up, and the gain is uncertain.

The idea is to pretrain on a larger steel-defect dataset so the backbone learns metal-surface textures instead of COCO's everyday objects, then fine-tune on NEU-DET.

| Dataset | Size | Format | Fit |
|---------|------|--------|-----|
| **GC10-DET** | ~2,300 images, 10 classes | Bounding boxes (VOC) | **Best fit.** Steel surface, detection format; some classes overlap with NEU (e.g. crease, inclusion, scratch-like). |
| **Severstal Steel Defect (Kaggle)** | ~12,500 images (1600×256), 4 classes | Segmentation masks (RLE) | Large, but the masks have to be converted to boxes. It's a different domain (cold-rolled, different camera). |
| **X-SDD / other steel datasets** | Small | Varies | Less useful. |

### Transfer learning strategy

1. **Stage A:** train YOLO11s on GC10-DET (optionally combined with Severstal converted to boxes), starting from COCO weights.
2. **Stage B:** fine-tune on NEU-DET from the Stage A weights.
   - Variant B1: full fine-tune with a lower learning rate (`lr0=0.001`).
   - Variant B2: freeze the backbone for the first N epochs (`freeze=10`), then unfreeze it.
3. **Compare** against the best Phase 1–2 config trained from COCO weights. Use the same split and the same seeds.

**Risks:** domain shift between datasets (camera, lighting, resolution), extra preparation work (especially converting Severstal's masks), and the possibility of no gain. COCO pretraining already provides strong low-level features.

**Alternative:** use a domain-specific or self-supervised backbone, for example a model pretrained on industrial imagery. This is more research effort and is optional.

---

## Phase 4: Architecture and inference tricks (if time allows)

| # | Experiment | Notes |
|---|-----------|-------|
| 4.1 | **RT-DETR-L** (transformer detector, available in Ultralytics) | Often better on texture-like or global defects such as crazing, but slower. |
| 4.2 | **YOLO with a P2 head** (`yolo11-p2.yaml`) | Better on small defects (inclusion, pitted). |
| 4.3 | **Test-time augmentation** (`augment=True`) | A free gain at inference time in exchange for about 2–3× the latency. |
| 4.4 | **Confidence-threshold tuning** | Pick the confidence threshold from the F1 or recall curve to suit what the production line needs (for example ≥ 90% recall). |
| 4.5 | **Ensemble or WBF** of the 2–3 best models | Use only if latency allows. |

---

## Suggested order and timeline

```
Week 1: Phase 0 (protocol + experiment logging)
        Phase 1.1–1.5  → pick best config ("Baseline v2")
Week 2: Phase 2.1–2.3  (error analysis, label audit, CLAHE)
        Phase 2.4 if crazing still weak
Week 3: Phase 3 (GC10-DET pretrain → NEU fine-tune) vs Baseline v2
Week 4: Phase 4 selections, final 3-seed comparison, write-up
```

## Deliverables

- `experiments.csv` with every run
- A final comparison table: baseline vs the best model, with per-class AP and mean ± std over 3 seeds
- The best `best.pt` and its config
- A short write-up on which levers helped, which didn't, and why
