# FEASIBILITY: can the reference pipeline be reproduced on MSDD?

Status: Phase 1 verdict, written from the code only. MSDD has not been inspected yet.
Reference: `./reference_repo` @ c9aa21a (Destinyia/Metal-Surface-Defect-Detection, Apache-2.0).
Everything marked **[verified]** was run locally; **[read]** comes from reading code; **[unclear]** is not determined.

## Public metadata from the SciDB page (read without login; the data itself is NOT inspected)

Source: JSON-LD embedded in `https://www.scidb.cn/en/detail?dataSetId=3d739ddb4bdc439a9bf7ef550cae48d8` (fetched 2026-11-11).
- Total size: **9,785,811,363 bytes (about 9.8 GB)**. Version 1.0.0 (cite string says V1), published 2024-07-23, author Lin Wu (Beihang University).
- Content: **138,585 single-channel images and 9,239 mixed images**; 5,746 defect-free images and 3,493 images with defects; **eight** defect types.
- 138,585 / 9,239 = **15.0 exactly, so each capture appears to have 15 single-channel frames, not 16.** The repo's mixer is built for 16 (`conv1x1` is 16->1, `res_block` takes 16). Its sample data has 16 frames. Using the repo's mixer weights on MSDD would need padding to 16 or a retrain with `in_channels=15`. That is a change to what "Baseline B" means, so I will ask you after the audit.
- **Eight classes, not ten.** The repo yaml lists 10 names; its yaml filenames say 7cls/8cls. Notebook 00 stops if names differ, as you asked; I expect it to trigger.
- Licence: the JSON-LD says CC BY 4.0 (`https://creativecommons.org/licenses/by/4.0/`). The page's UI strings also contain CC BY-SA 4.0 boilerplate. I could not tell which applies to the files; confirm on the page. Citation (from the page):
  `@data{3d739ddb4bdc439a9bf7ef550cae48d8, title={Metal Surface Defect Dataset}, author={Lin Wu}, year={2024}, month={July}, publisher={Science Data Bank}, doi={10.57760/sciencedb.10794}, url={https://doi.org/10.57760/sciencedb.10794}, version={V1}}`
- Download needs a SciDB login (the API returns "User Not Login").
- 62% of images are defect-free. Ultralytics keeps images with empty labels as background, so labels may legitimately be missing or empty. The audit must count these separately from broken pairs.
- 9.8 GB fits in a private Kaggle dataset and on Drive; the audit notebook still measures it.

## (a) What the mixer needs

- **Input tensor**: `TaylorSeriesChannelMixer.forward(x)` takes `B x 16 x H x W`, float, values expected in [0, 1] **[read]** (`models/mixer.py`). Any H, W works (a 64x64 forward pass returned `B x 3 x H x W`) **[verified]**.
- **Output**: `B x 3 x H x W`, min-max normalised per image and per channel (`ChannleNormalize`) **[read]**. The three output channels are the same learned mix applied to the 16 channels circularly shifted by 0, 1, 2 (`channel_shift=1`) **[read]**.
  So the shift order matters: channel index = lighting/capture index, and it must be consistent with the order the mixer was trained on.
- **On disk (`McDataset`)** **[read]**: one directory with **16 single-channel JPEGs per capture**, named `<prefix>_<i>.jpg`, `i` = 0..15, opened as grayscale (`convert('L')`).
  The prefix is **the first 23 characters of every filename** (hard-coded `file[:23]`), so filenames must share a fixed-length 23-char capture prefix. This is fragile: any other file in the directory creates a bogus prefix.
- **Training-time requirements** **[read]**: `RandomResizedCrop(1024)` (output is 1024x1024 regardless of source size) and `EllipseNoise` picks centres with `randint(200, W-200)`, so images must be at least ~400 px. `ChannelReduce` and `EllipseNoise` operate on batches `B x C x H x W`.
- **Sample data in the repo** **[verified]**: `datasets/VAE/{images,test,demo}` hold 2 captures each: 16 grayscale JPEGs of 1600x1600 named `20240206_134045_Gige[0]_<i>.jpg`. The 23-char prefix is `20240206_134045_Gige[0]` (date, time, camera index). This is the authors' own capture format; whether MSDD uses it is **[unclear]** until the audit.
- **Consequence for MSDD**: Baseline B needs the **raw 16-light captures** (or at least 16 aligned grayscale frames per capture). If MSDD ships only the RGB pseudo-colour images, there is nothing to feed the mixer (see (c)).

## (b) How TSCM images and PIFM weights reach the Ultralytics detector

Short answer: **the repo contains no code that does this.** What is there:

1. `train_detector.py` is plain Ultralytics: `YOLO('yolov8m.pt').train(data='./datasets/mix_8cls.yaml', ...)`. It consumes ordinary RGB image files and YOLO txt labels. It never imports the mixer, VQ-VAE or PIFM.
2. `mix_8cls.yaml` **does not exist** in the repo (only `mix_7cls.yaml` and `gray_7cls.yaml`) **[verified]**.
3. `args.yaml` of the reported run says `model: yolov8l.pt` (stock pretrained weights), `data: ./datasets/gray_7cls.yaml` **[read]**. No PIFM or custom backbone weights are referenced.
4. `train_pifm.py` saves `pifm_epoch*.pt` (a small YOLOv8-style student `YOLOv8Backbone`, stride 8, 128 ch) but **nothing loads it** anywhere (grep for `pifm` in `*.py` finds only `train_pifm.py`) **[verified]**.

So the only mechanism by which TSCM/PIFM can influence the YOLO result is **offline rendering**: run the trained mixer over each 16-channel capture, save the 3-channel result as an ordinary image, and train stock YOLOv8l on those images. PIFM then only acts as an auxiliary loss that shapes the mixer during `train_pifm.py`; the student network itself is discarded **[inference, not stated in the repo]**.
The image-export step is missing from the repo, so it has to be written (in `src/export_mixed.py`, Phase 2) if Baseline B is feasible.

Other unclear points:
- **[unclear]** `gray_7cls.yaml` points at `defectDetection/gray/*_7cls`; `mix_7cls.yaml` points at `MSDD/images/*_7cls`. The `*_static` runs use `mix_7cls.yaml` and the `*_tscm*` runs use `gray_7cls.yaml`, i.e. the names look swapped relative to what a reader would expect. I cannot tell from the repo what "gray" contains (it may not be MSDD, as you suspected).
- **[unclear]** `*_end2end` runs: no code for joint mixer+detector training is in the repo.
- **[unclear]** `train_detector.py` hyperparameters (`hsv_h=0.06, hsv_s=0.4, hsv_v=0.5, close_mosaic=10`) differ from the reported run's `args.yaml` (`hsv_h=0.07, hsv_s=0.5, hsv_v=0.4, close_mosaic=8`). Configs follow `args.yaml` as instructed.
- **[unclear]** the split: `val` doubles as `test` in both yamls, so the reported numbers are val-on-val-selected, not held-out test.

### Defects in the repo that affect reproducing Baseline B **[verified]**

- **The shipped `weights/*_exp10.pt` do not load into the models the scripts build.**
  - `mixer_exp10.pt` matches `models.vqvae.ChannelMixer` (7x7 conv in `res_block.2`, no `coeff`), not `TaylorSeriesChannelMixer` (1x1 conv, has `coeff`).
  - `vqvae_exp10.pt` has `embedding_dim=64` and does not load into `models.fpn_vae.VQVAE` at either 64 or 128 (shape mismatches).
  - `util.load_model_weights` wraps `load_state_dict` in `try/except` and only prints, so both `train_tscm.py` and `train_pifm.py` **silently start from random init** (the load also fails on CPU because there is no `map_location`).
- Mixer checkpoints that **do** match `TaylorSeriesChannelMixer`: `runs/tscm/exp14|15|17/mixer_epoch*.pt` and `runs/pifm/exp16/mixer_epoch0-49.pt` (have `coeff`, 1x1 `res_block`). Which one produced the reported run is **[unclear]**.
- `train_tscm.py` builds the VQ-VAE with `embedding_dim=64` and `train_pifm.py` with `128`; PIFM's student output is 128 ch at stride 8, which matches the VQ latent (stride 8) **[read]**.
- `train_pifm.py` has a debug `print` inside the batch loop (removed in `src/`).

Fixes applied in `src/` are listed in `src/CHANGES.md`.

## (c) What to check in MSDD to confirm Baseline B is possible

Baseline B is possible only if all of these hold (the audit notebook records each one):
1. **Raw multi-channel captures exist**: per capture there are N aligned grayscale frames (ideally 16, matching `in_channels=16`), not only RGB pseudo-colour images. If the number of lights is not 16, the mixer's `conv1x1` and `res_block` input size must change and the repo's trained mixer weights cannot be reused (it would be a retrain, not a reproduction).
2. **Capture grouping is recoverable from filenames** (capture id + light index), and the light index order is meaningful and consistent.
3. **Labels exist per capture** (one label set applicable to all its frames and to the pseudo-colour image) and the box coordinates refer to an image size we can map to the exported mixed image.
4. **Size and licence permit** storing the raw 16-channel data (it is ~16x the pseudo-colour size) on Kaggle/Drive. If not, Baseline B may need to be restricted to a subset; that needs the user's decision.
5. Whether the dataset's own pseudo-colour images were made by a channel mixer (the dataset description says so) which would make "YOLO on the shipped pseudo-colour images" a different baseline from "repo's mixer output".

Verdict for now: **undetermined**, but the public metadata says raw single-channel frames AND mixed images both ship (so (1) likely holds), with 15 frames per capture (so the repo's 16-channel mixer does not fit as is). Reproducible in principle only if (1)-(3) hold. Even then, "reproducing" the reference means training our own mixer (the shipped exp10 weights do not load, and the reference's training data and 16-light layout are unconfirmed for MSDD).
