# Model Evaluation Report: All Models in the Repo

Date: 2026-10-29. Every checkpoint in `models/`, plus the casting classifier in `casting_defect_classification_package.zip`, was re-evaluated on a single machine with one script, so the numbers can be compared directly.

**Conclusion:** among the NEU-DET detectors, `models/best_v2.pt` (hard-example mining) scores highest on the test split and detects the most crazing defects. Its lead is 0.01–0.03 mAP. It does not hold on the validation split, where the original `v1_yolo11n_baseline` scores best, so no detector clearly beats the others. `best (1).pt` and `best_v1.pt` are clearly weaker. Every detector misses most crazing defects. The casting classifier misses 35% of defective parts on its held-out test set, which is far below the 99.5% accuracy its README claims.

## 1. What was evaluated

| Checkpoint | Task | Trained on | Registered version? |
|------------|------|-----------|--------------------|
| `v1_yolo11n_baseline` | NEU-DET detection | full train split, 50 epochs | yes |
| `v1r_yolo11n_baseline_long_s0/s1/s2` | NEU-DET detection | full train split, AdamW, up to 100 epochs | yes |
| `v2_yolo11n_severstal_pretrain` | Severstal detection (4 classes) | Severstal tiles | yes (intermediate only) |
| `v3_yolo11n_severstal_ft_s0/s1/s2` | NEU-DET detection | v2, then fine-tuned on NEU-DET | yes |
| `models/best_v1.pt` | NEU-DET detection | 50% of train split (`ps7_train_and_evaluate.ipynb`) | no |
| `models/best_v2.pt` | NEU-DET detection | best_v1's 50%, plus the hardest 50% of the remaining pool | no |
| `models/best (1).pt` | NEU-DET detection | fine-tuned 25 epochs from an unknown `best.pt` | no, origin undocumented |
| `casting_defect_classifier(_final).keras` | casting defect classification (`defective` / `ok`) | Kaggle casting `train/` folder | no |

`v2_yolo11n_severstal_pretrain` predicts Severstal classes, not NEU-DET classes, so it cannot be scored on NEU-DET. It is used only as the starting point for v3.

## 2. Method

- **Data:** NEU-DET, rebuilt with `scripts/prepare_neu_det.py`. The test split is 180 images and 416 boxes (seed 42, 30 images per class); the val split is 360 images and 854 boxes. The notebooks that produced `best_v1.pt` and `best_v2.pt` use the same seed-42 hold-out, so their test images were never trained on. The training data for `best (1).pt` is unknown, so its scores could be inflated.
- **Accuracy:** Ultralytics `val` reports mAP50 and mAP50-95, overall and per class, on both splits.
- **Deployment view:** predictions at conf 0.25 are matched one-to-one to ground truth (same class, IoU ≥ 0.5). From that matching come recall, missed defects, false alarms, and the share of images where at least one defect is found.
- **Uncertainty:** the 180 test images were bootstrap-resampled 1,000 times, and every model was scored on the same resamples (paired), which gives a 95% interval for each model's gap to `best_v2.pt`.
- **Latency:** median CPU time per image at 640 px on an Apple M2. All detectors are YOLO11n (about 5.5 MB), so their speed is the same apart from measurement noise.
- Everything comes from `scripts/evaluate_all.py`. Raw outputs are in `reports/eval_all/overall.csv` and `reports/eval_all/per_class.csv`.

## 3. Detector results (NEU-DET)

### Overall, sorted by test mAP50-95

| Model | Val mAP50 | Val mAP50-95 | Test mAP50 | Test mAP50-95 | Test recall @0.25 | Missed / 416 | False alarms | Images with a hit |
|-------|-----------|--------------|-----------|---------------|-------------------|--------------|--------------|-------------------|
| **best_v2.pt** | 0.740 | 0.380 | **0.768** | **0.433** | **0.719** | **117** | 126 | 90.6% |
| v3 s0 | 0.717 | 0.376 | 0.753 | **0.433** | 0.704 | 123 | 137 | 86.7% |
| v3 s1 | 0.728 | 0.378 | 0.750 | 0.420 | 0.712 | 120 | 157 | 92.2% |
| v1r s2 | 0.732 | 0.376 | 0.753 | 0.414 | 0.673 | 136 | 124 | 85.0% |
| v1_yolo11n_baseline | **0.761** | **0.390** | 0.758 | 0.413 | 0.697 | 126 | 150 | 90.6% |
| v3 s2 | 0.725 | 0.389 | 0.737 | 0.411 | 0.688 | 130 | 137 | 87.8% |
| v1r s1 | 0.712 | 0.374 | 0.735 | 0.409 | 0.707 | 122 | 155 | 92.8% |
| v1r s0 | 0.723 | 0.381 | 0.722 | 0.400 | 0.675 | 135 | 135 | 87.2% |
| best (1).pt | 0.691 | 0.343 | 0.694 | 0.389 | 0.606 | 164 | **120** | 81.7% |
| best_v1.pt | 0.719 | 0.358 | 0.689 | 0.380 | 0.615 | 160 | 149 | 82.2% |

The registered-version scores match the numbers already recorded in `models/*/metrics/` and `docs/RESULTS_SEVERSTAL_TRANSFER.md`, which confirms that this evaluation reproduces them.

### Are the gaps real? Paired bootstrap, `best_v2.pt` minus each model (test split)

| Model | Δ mAP50 [95% CI] | Δ mAP50-95 [95% CI] |
|-------|------------------|---------------------|
| v1_yolo11n_baseline | +0.020 [−0.006, +0.047] | +0.028 [+0.009, +0.048] |
| v3 s0 | +0.029 [−0.001, +0.058] | +0.011 [−0.008, +0.029] |
| v3 s1 | +0.026 [−0.003, +0.057] | +0.024 [+0.004, +0.046] |
| v3 s2 | +0.025 [−0.005, +0.055] | +0.011 [−0.009, +0.030] |
| v1r s0 / s1 / s2 | +0.047 / +0.034 / +0.029 | +0.029 / +0.006 / +0.015 |
| best (1).pt | +0.074 [+0.036, +0.114] | +0.032 [+0.007, +0.056] |
| best_v1.pt | +0.085 [+0.053, +0.119] | +0.042 [+0.020, +0.065] |

An interval that excludes zero means `best_v2.pt` beat that model on these 180 test images. Against the v1, v1r and v3 runs, most mAP50 intervals still include zero, so the lead may not carry over to new images. Against `best (1).pt` and `best_v1.pt`, the gap is clear. The bootstrap uses its own matching code, which scores every model 0.01–0.03 lower than Ultralytics does; only the differences between models are used here.

### Per class, test split: recall at conf 0.25 (how many real defects are found)

| Model | crazing (70) | inclusion (110) | patches (75) | pitted_surface (36) | rolled-in_scale (69) | scratches (56) |
|-------|------|------|------|------|------|------|
| best_v2.pt | 0.41 | 0.75 | 0.83 | 0.81 | 0.64 | **0.93** |
| v3 s1 | **0.43** | 0.75 | **0.84** | 0.81 | **0.67** | 0.82 |
| v1r s1 | **0.43** | 0.76 | 0.80 | 0.81 | 0.61 | 0.88 |
| v1_yolo11n_baseline | 0.34 | 0.73 | 0.83 | **0.83** | 0.62 | 0.91 |
| v3 s0 | 0.31 | 0.78 | **0.84** | 0.81 | 0.64 | 0.88 |
| v3 s2 | 0.31 | 0.76 | **0.84** | 0.81 | 0.58 | 0.88 |
| v1r s0 | 0.23 | **0.84** | 0.81 | 0.78 | 0.49 | 0.89 |
| v1r s2 | 0.21 | 0.81 | 0.77 | 0.81 | 0.55 | 0.91 |
| best (1).pt | 0.16 | 0.74 | 0.69 | 0.75 | 0.45 | 0.89 |
| best_v1.pt | 0.13 | 0.70 | 0.76 | 0.81 | 0.58 | 0.79 |

Test AP50 per class follows the same pattern. For `best_v2.pt`: crazing 0.48, inclusion 0.82, patches 0.88, pitted_surface 0.87, rolled-in_scale 0.64, scratches 0.93. The full table is in `reports/eval_all/per_class.csv`.

## 4. Detector findings

1. **`best_v2.pt` is the best candidate on test, but it is not the clear winner.** It has the highest test mAP50, ties for the highest test mAP50-95, misses the fewest defects, and has the best crazing AP50 (0.48). On the validation split, though, `v1_yolo11n_baseline` leads (0.761 vs 0.740 mAP50), and several v3 and v1r runs equal `best_v2.pt` on mAP50-95. Picking a model because it tops the test split makes its test score look better than it will be on new images.
2. **Hard-example mining worked.** `best_v2.pt` was trained on fewer images than the full train split, yet it matches or beats every full-data model. It gains +0.079 test mAP50 over `best_v1.pt`, the same recipe without the hard images. This is the most promising direction found so far, and it has not been tried on the full training set.
3. **Severstal pretraining (v3) did not beat the long-schedule control (v1r)** by more than the seed-to-seed variation, which matches `docs/RESULTS_SEVERSTAL_TRANSFER.md`.
4. **Crazing is the main weakness of every model.** At conf 0.25, the best models find 41–43% of crazing defects, and most models find only 13–34%. Seed alone moves crazing recall from 0.21 to 0.43 within v1r. rolled-in_scale is the second-weakest class (0.45–0.67).
5. **`best (1).pt` and `best_v1.pt` should not be used.** They score lowest on both splits, and `best (1).pt` has no documented origin.
6. **In operation,** a typical top model at conf 0.25 finds about 70% of defect boxes, raises about 130 false alarms over 180 test images (about 0.7 per image), and finds at least one defect on about 90% of defective images.
7. **Speed is not a differentiator.** All detectors share the same architecture and weight size (5.5 MB) and run at roughly 60–100 ms per image on an M2 CPU, depending on load. The earlier reported figure was about 5 ms on a T4 GPU.

## 5. Casting defect classifier

Evaluated on the Kaggle dataset's official `casting_data/test` folder: 715 images (453 defective, 262 ok) that were not used in training. The notebook trained only on the `train/` folder.

| File | Accuracy | ROC AUC | Defective recall | Defective precision | OK recall | CPU latency |
|------|----------|---------|------------------|---------------------|-----------|-------------|
| `casting_defect_classifier.keras` | 0.764 | 0.899 | **0.647** | 0.970 | 0.966 | about 22 ms |
| `casting_defect_classifier_final.keras` | 0.764 | 0.899 | 0.647 | 0.970 | 0.966 | about 23 ms |

Confusion matrix (rows are true labels, columns are predictions): defective → [293 defective, 160 ok]; ok → [9 defective, 253 ok].

1. **The package's reported metrics are wrong.** The README says 0.9947 validation accuracy. `evaluation_metrics.json` says 0.786, and its own classification report says 0.504. The 0.504 comes from a known bug in the notebook: the labels are read from a shuffled `tf.data` pipeline in one pass and the predictions in another, so they do not line up. On real held-out data the model scores 0.764.
2. **It misses 35% of defective castings** (160 of 453), which is the costly error in inspection. When it does flag a part as defective, it is almost always right (97% precision).
3. **The model separates the classes reasonably well** (AUC 0.90), but its 0.5 threshold leans toward predicting `ok`. Tuning the threshold on a validation split would trade some false alarms for fewer missed defects. It should not be tuned on this test set.
4. **The two `.keras` files are different files but give identical predictions,** so they are effectively the same model.

## 6. Recommendations

1. **Detector to use now:** `models/best_v2.pt`, as the best available candidate, with the caveat from finding 1. Register it properly first: create a `models/v4_...` folder with its config, metrics and a model card, as `models/README.md` requires.
2. **Next experiment:** apply the `best_v2` hard-example recipe to the full training set, with 3 seeds and the same v1r schedule. Then select the model on the validation split, not on test.
3. **Crazing:** inspect the crazing labels and the missed detections, and try contrast enhancement (CLAHE) and oversampling crazing images. The earlier results doc already listed these.
4. **Casting classifier:** fix the evaluation bug in the notebook and correct the README. Then tune the decision threshold for defect recall on a validation split, or switch to a pretrained backbone such as MobileNet or EfficientNet.
5. **Cleanup:** delete `best (1).pt`, or document where it came from. Deduplicate the two casting `.keras` files.

## 7. Caveats

- 180 test images give intervals of about ±0.04 on mAP50, so differences below about 0.03 should not be treated as real.
- The training data for `best (1).pt` is unknown, so its test scores could be inflated.
- `best_v1.pt` and `best_v2.pt` each come from a single training run with no seed repeats.
- `v2_yolo11n_severstal_pretrain` was not scored on Severstal itself, because that dataset is not available locally.
- CPU latency on a laptop is noisy, so only its order of magnitude is reliable.

## Reproduce

```bash
python scripts/prepare_neu_det.py
python scripts/evaluate_all.py   # writes reports/eval_all/{overall,per_class}.csv
```
