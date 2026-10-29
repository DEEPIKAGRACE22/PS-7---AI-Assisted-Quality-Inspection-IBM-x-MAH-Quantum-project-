# Results: Severstal → NEU-DET Transfer Learning

Experiment described in [`SEVERSTAL_TRANSFER_PLAN.md`](SEVERSTAL_TRANSFER_PLAN.md). Run with `notebooks/v2_severstal_transfer_colab.ipynb` on a Colab T4.

**Conclusion:** pretraining on Severstal gives a small overall gain that is not statistically conclusive, and it does not fix the weak `crazing` class. The frozen-backbone variant (v3b) was not run.

## Setup

| Version | Starts from | Data | Seeds |
|---------|-------------|------|-------|
| `v1r_yolo11n_baseline_long` | COCO `yolo11n.pt` | NEU-DET | 0, 1, 2 |
| `v2_yolo11n_severstal_pretrain` | COCO `yolo11n.pt` | Severstal tiles | 1 |
| `v3_yolo11n_severstal_ft` | v2 | NEU-DET | 0, 1, 2 |

v1r and v3 share the same schedule (AdamW, lr0 0.001, up to 100 epochs, patience 20) and the same augmentation, so any difference comes from the Severstal pretraining. All scores are on the same 180-image NEU-DET test split.

## Per-seed results

| Run | Epochs | Best epoch | Val mAP50-95 | Test mAP50 | Test mAP50-95 | crazing AP50 | crazing recall | rolled-in_scale AP50 |
|-----|--------|-----------|--------------|------------|---------------|--------------|----------------|----------------------|
| v1r s0 | 70 | 50 | 0.381 | 0.722 | 0.400 | 0.329 | 0.386 | 0.556 |
| v1r s1 | 68 | 42 | 0.371 | 0.735 | 0.409 | 0.338 | 0.414 | 0.638 |
| v1r s2 | 91 | 71 | 0.376 | 0.753 | 0.414 | 0.361 | 0.357 | 0.626 |
| v3 s0 | 90 | 57 | 0.376 | 0.753 | 0.433 | 0.336 | 0.243 | 0.672 |
| v3 s1 | 100 | 81 | 0.379 | 0.750 | 0.420 | 0.387 | 0.271 | 0.658 |
| v3 s2 | 69 | 50 | 0.388 | 0.737 | 0.411 | 0.455 | 0.257 | 0.576 |

## Summary (mean ± std over 3 seeds)

| Version | P | R | mAP50 | mAP50-95 | crazing AP50 | rolled-in_scale AP50 |
|---------|---|---|-------|----------|--------------|----------------------|
| v1 (original, 1 run) | 0.748 | 0.681 | 0.758 | 0.413 | 0.391 | 0.697 |
| v1r (control) | 0.668 ± 0.025 | 0.730 ± 0.001 | 0.737 ± 0.016 | 0.407 ± 0.007 | 0.342 ± 0.016 | 0.607 ± 0.045 |
| v3 (Severstal) | 0.720 ± 0.007 | 0.704 ± 0.008 | 0.747 ± 0.008 | 0.422 ± 0.011 | 0.393 ± 0.060 | 0.636 ± 0.052 |

## Findings

1. **Overall gain is small and not conclusive.** v3 beats v1r by +0.015 mAP50-95 and +0.010 mAP50. The per-seed ranges overlap (v3: 0.411–0.433, v1r: 0.400–0.414), and on the validation split the two are almost equal (0.381 vs 0.376 mean mAP50-95).
2. **Early training is faster and more stable with pretraining.** Between epochs 5 and 16 v3 reaches higher mAP50 and fluctuates less. Both runs plateau at the same level by epoch 30–40.
3. **Crazing improved in AP but not in recall.** v3's crazing AP50 is higher on average, but its crazing recall is lower (0.24–0.27 against 0.36–0.41). The AP gain comes from fewer false positives, so most crazing defects are still missed. Crazing AP50 varies from 0.34 to 0.46 across v3 seeds, and the test split has only 70 crazing instances.
4. **rolled-in_scale:** a small gain (0.636 vs 0.607) that is inside the noise.
5. **The original v1 cannot be told apart from v3.** On mAP50 it is higher (0.758 vs 0.747 mean); on mAP50-95 v3 seeds 0 and 1 are higher (0.433 and 0.420 vs 0.413). v1 is a single run, and v1r's seeds alone span 0.722–0.753 mAP50, so its score may be a lucky draw. v1r and v3 also use a fixed-lr AdamW instead of the default optimizer, which may have cost a little.
6. **Latency is unchanged** at about 5 ms per image on a T4.

## Caveats

- 3 seeds and 180 test images give wide error bars. Differences below about 0.02 mAP should not be treated as real.
- v2 was still improving at its last epoch (best epoch 29 of 30), so the pretraining was probably undertrained.
- Severstal boxes were derived from masks with a 15 px merge dilation, and many came out much larger than the defect (see the sanity-check previews). `scripts/analyze_severstal_boxes.py` can compare other kernel sizes; it has not been run yet.
- v3b (frozen backbone) was skipped to save compute.

## Suggested next steps

1. Look at the crazing labels and the missed detections. Crazing recall is the main problem and no change so far has moved it.
2. Try cheaper crazing-focused changes (CLAHE contrast enhancement, oversampling crazing images) as fine-tunes from the existing checkpoints.
3. Only then consider redoing Severstal with tighter boxes and longer pretraining, which costs several GPU hours.
