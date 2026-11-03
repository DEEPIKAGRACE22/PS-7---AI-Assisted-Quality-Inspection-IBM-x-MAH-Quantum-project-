# Improvement Plan v2: Closing the Gap After Review

Date: 2026-11-03. This plan follows the interim review (high failure rate against an 83% success target). It builds on `docs/MODEL_EVALUATION_REPORT.md` and replaces the ordering in `docs/IMPROVEMENT_PLAN.md`, whose Phase 1 was marked "skipped" without recorded results.

> **Team of 6:** work is split into streams A–F in [section 13](#13-team-split-6-members). Fill in the owner names there.

## 1. Where we are

Numbers are from `reports/eval_all/overall.csv` (NEU-DET test split, 180 images, 416 boxes, conf 0.25).

| Metric | `best_v2.pt` | Target |
|--------|--------------|--------|
| Box recall | 0.72 (117 missed of 416) | ≥ 0.90 |
| False alarms | 126 over 180 images (0.7 per image) | ≤ 0.1 per image |
| mAP50 / mAP50-95 | 0.768 / 0.433 | ≥ 0.85 / ≥ 0.55 |
| Crazing recall | 0.41 | ≥ 0.80 |
| rolled-in_scale recall | 0.64 | ≥ 0.80 |

The 83% target has no agreed definition yet. Step 0 below fixes that before any training.

Known weaknesses, in order of impact:
1. Crazing and rolled-in_scale are barely detected.
2. Localisation is loose (mAP50 0.77 vs mAP50-95 0.43).
3. False alarms are frequent.
4. The only model ever trained is YOLO11n (2.6M params). Larger models and higher resolution were never tested.
5. The data is 1,800 small lab images, and the test split was cut from the training pool.
6. The casting classifier misses 35% of defects and its documented accuracy is wrong.

## 2. Step 0: Define "success" and the failure taxonomy (1–2 days, no training)

Everything else depends on this.

1. Ask the organiser for the evaluation schema and a sample of failed cases. Record what counts as a pass (per image, per box, class-correct, IoU threshold, false alarms allowed).
2. Write `scripts/score_cases.py` that implements that rule and report the pass rate for `best_v2.pt` on val and test. This is the number we optimise.
3. Bucket every failure on the test set into: missed (background), wrong class, loose box (IoU < threshold), false alarm, duplicate. Save as `reports/error_analysis/`.
4. Check the integration path separately: start the backend from a clean clone, run `/health`, and upload one image and one video. Any crash here fails every case regardless of model quality.

**Exit criterion:** one pass-rate number and a table of failure buckets. Plan priorities below are re-ranked if one bucket dominates.

## 3. Phase A: Fix the evaluation (before more training)

| # | Action | Why |
|---|--------|-----|
| A1 | Re-split: hold out a test set from a source never used for selection, and select models on val only | Current `best_v2` choice used test; val disagrees |
| A2 | Run 3 seeds per configuration, report mean ± std | `best_v1`/`best_v2` are single runs |
| A3 | Register `best_v2.pt` as `models/v4_...` with config, metrics and model card; delete or document `best (1).pt` | Reproducibility and provenance |
| A4 | Log every run in `experiments.csv` | Already specified in the old plan, never created |

## 4. Phase B: Cheap, high-value levers (the old Phase 1, now actually run)

One change per run, 3 seeds each, Colab T4, about 15–40 minutes per run.

| # | Experiment | Expectation |
|---|-----------|-------------|
| B1 | `yolo11s`, then `yolo11m` | Most likely largest single gain; `n` has little capacity for faint textures |
| B2 | `imgsz` 320 vs 640 vs 800 | Native size is 200 px; upscaling may add nothing |
| B3 | Longer training with patience (`epochs=150, patience=30`) | Old curves may not have plateaued |
| B4 | `flipud=0.5` and 90° rotations | Defects have no "up"; effectively 4× orientation diversity |
| B5 | Mosaic and mixup off/on | Mosaic of 200 px textures may create misleading context |

Keep the best combination as "Baseline v3".

## 5. Phase C: Target crazing and rolled-in_scale

| # | Action | Detail |
|---|--------|--------|
| C1 | Label audit | Review about 50 crazing and 50 rolled-in_scale annotations. Some crazing boxes cover the whole image, others strips. Inconsistent labels cap recall for every model. Fix or define a rule, then retrain. |
| C2 | CLAHE preprocessing | Apply at train and inference time. Crazing is low contrast. The backend must apply the same step. |
| C3 | Class-aware oversampling | Duplicate crazing and rolled-in_scale images in the train list |
| C4 | Hard-example mining on the full training set | `best_v2` gained +0.079 mAP50 over `best_v1` with this recipe on half the data. Apply it to all data with 3 seeds. |
| C5 | Loss weights | Raise `cls` gain if confusion with other classes shows up in the error analysis |

## 6. Phase D: Data

1. Add GC10-DET (about 2,300 boxes-labelled steel images) as extra data or for pretraining, then fine-tune on NEU-DET. Severstal transfer (v3) gave no gain beyond seed noise, so do this only after B and C.
2. Collect or simulate production-like input: varied lighting, noise, motion blur, camera angle. Add these augmentations and a separate "robustness" test set.
3. Add negative images (clean steel) so false alarms are measured and reduced. The current sets are almost all defective.

## 7. Phase E: Inference and decision layer

| # | Action |
|---|--------|
| E1 | Choose the confidence threshold from the validation F1/recall curve, not the default 0.25. Set it per class if curves differ. |
| E2 | Test-time augmentation (`augment=True`) and a WBF ensemble of the 2–3 best models, if latency allows |
| E3 | Validate the quality-rule thresholds in `steel-defect-backend/app/config.py` (reject, review, critical classes) against labelled outcomes instead of hand-picked values |
| E4 | Try RT-DETR-L or a P2-head YOLO if crazing is still below 0.7 recall |

## 8. Phase F: Casting classifier (fix or remove)

1. Fix the shuffled-label bug in `notebooks/casting/casting_defect_classification.ipynb` and correct the package README (0.764 accuracy, not 99.47%).
2. Retrain on a pretrained backbone (MobileNetV3 or EfficientNet). Tune the threshold on a validation split for defective recall ≥ 0.95.
3. If this cannot be done before the next review, state clearly that the casting classifier is out of scope rather than shipping unverified claims.

## 9. Phase G: Deployment and load (Level 2 readiness)

1. Export to ONNX or TensorRT and measure latency on the intended hardware. Report p50/p95, not a single median.
2. Run a load test on the backend (concurrent uploads, a long video) and record throughput.
3. Add a CI check: backend tests plus a smoke test that loads the registered weights from a clean clone.
4. Keep large binaries out of git history going forward (Git LFS for `.pt`).

## 10. Schedule

```
Days 1-2   Step 0: success definition, failure taxonomy, clean-clone integration check
Week 1     Phase A + Phase B (B1 and B2 first)
Week 2     Phase C (C1 label audit first, then C2-C4)
Week 3     Phase D (negatives and robustness first), Phase E
Week 4     Phase F, Phase G, final 3-seed comparison and write-up
```

## 11. Decision gates

- After Step 0: if one failure bucket is over 50%, work that bucket first and skip phases that do not address it.
- After Phase B: if `yolo11s/m` reaches recall ≥ 0.85, defer Phase D.
- After Phase C: if crazing recall is still below 0.6, escalate to Phase D1 and E4.
- Stop when val and test pass rates both reach the agreed target with seed std below 0.02.

## 12. Deliverables

- `scripts/score_cases.py` and `reports/error_analysis/`
- `experiments.csv` with every run
- Final table: `best_v2` vs the new model, per-class recall and AP, mean ± std over 3 seeds, on val and test
- Registered model folder with config, metrics and model card
- Corrected casting documentation (or an explicit out-of-scope note)
- Updated `docs/MODEL_EVALUATION_REPORT.md`

## 13. Team split (6 members)

Each stream owns its phases, branches and outputs. Branch names: `<stream>/<topic>` (for example `b/yolo11s-sweep`). One PR per experiment or change, reviewed by someone from another stream.

| Stream | Owner | Scope | Plan sections | Main outputs |
|--------|-------|-------|---------------|--------------|
| **A. Evaluation and integration** | _name_ | Success definition, scoring script, failure taxonomy, re-split, seeds protocol, `experiments.csv`, model registration, clean-clone check | Step 0, Phase A | `scripts/score_cases.py`, `reports/error_analysis/`, frozen split, `experiments.csv`, registered `models/v4_...` |
| **B. Model capacity and training** | _name_ | `yolo11s/m`, image size, schedule, flips and rotations, mosaic/mixup | Phase B | Baseline v3 config, 3-seed results table |
| **C. Weak classes** | _name_ | Label audit, CLAHE, oversampling, hard-example mining on full data, loss weights | Phase C | Corrected labels, crazing and rolled-in_scale recall results |
| **D. Data and robustness** | _name_ | GC10-DET, negative (clean) images, production-like augmentation, robustness test set | Phase D | New dataset builds under `data/`, robustness test split |
| **E. Inference, backend and dashboard** | _name_ | Threshold tuning, TTA and ensemble, quality-rule validation, ONNX export, latency and load tests, CI smoke test, Git LFS | Phase E, Phase G | Per-class thresholds, latency/throughput report, CI workflow |
| **F. Casting classifier and documentation** | _name_ | Notebook bug fix, README correction, retrain or mark out of scope; keep README, evaluation report and model cards in sync; final write-up | Phase F, Deliverables | Corrected casting package, updated `MODEL_EVALUATION_REPORT.md`, final report |

### Dependencies and order

```
Day 1-2    A: Step 0 (blocks everyone: split, scoring rule, experiments.csv format)
           B, C, D, E, F can read code and prepare while waiting, but do not report numbers yet
Week 1     A: Phase A       B: B1, B2 first       F: casting fix       E: clean-clone check, latency baseline
Week 2     C: label audit first (C1), then C2-C4   D: negatives and robustness set   B: remaining sweeps
Week 3     C and B merge best settings into one config (A reviews)   E: thresholds, TTA, quality rules on that model
Week 4     A: final 3-seed comparison   E: load test and CI   F: final report
```

### Shared rules

1. **One frozen split and one scoring script (from A).** Nobody reports results from their own metric or split.
2. **Every run goes into `experiments.csv`** with stream, config diff, seed, val and test scores.
3. **Change one variable per run, 3 seeds.** Select on val, never on test.
4. **Handoffs:** B's best config and C's label fixes and CLAHE setting are combined into a single "Baseline v4" config, owned by A. D's new data and E's thresholds are evaluated on that config only.
5. **CLAHE and any preprocessing must be added to the backend** (stream E) in the same PR cycle that C adopts it, or the deployed model will not match the evaluated one.
6. **Weekly 30-minute sync:** each stream reports its numbers against the agreed pass rate and any blocker.
7. **Pull `origin/main` and branch from it before starting any change.**

### Load balance note

A and E carry the most integration work. If either falls behind, F (documentation is lighter in weeks 1–2) picks up the clean-clone and CI tasks.
