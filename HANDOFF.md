# HANDOFF 1  (actions only you can do, in order)

## Step 1 - Get a direct download URL for MSDD (needs your SciDB login)
Unblocks: notebook 00, then everything else.
1. Open https://www.scidb.cn/en/detail?dataSetId=3d739ddb4bdc439a9bf7ef550cae48d8 and log in.
2. Write down the **file names and sizes** listed under the dataset files (the page metadata I could read says about 9.79 GB total, but not how many files or their names).
3. Click download on each file. In the browser's downloads list (Chrome: `chrome://downloads`), right-click the item > **Copy link address**. Then **cancel** the browser download so nothing large lands on your laptop.
4. Links may expire: do Step 2 straight after this.
Bring back: the file names and sizes from item 2, typed into `./returned/1/scidb_files.txt`.

## Step 2 - Run notebook 00 on Kaggle
Unblocks: Phase 2 (everything depends on the audit).
1. Kaggle > Create > Notebook > File > **Import Notebook** > `notebooks/msdd/00_download_and_audit.ipynb`.
2. Settings: **Internet On**, Accelerator **None**.
3. Recommended so the persistent copy is made automatically: Kaggle > Settings > API > *Create New Token*; then in the notebook Add-ons > **Secrets** add `KAGGLE_USERNAME` and `KAGGLE_KEY` (values from the downloaded `kaggle.json`) and tick both for this notebook.
4. In the cell marked `EDIT HERE`, paste the URL(s) into `DOWNLOAD_URLS = [ "..." ]` (one string per file).
5. Run with **Run All in the interactive editor (not Save Version)**: the data is large and Save Version would download it again.
6. Expected: the last cell stops with `STOP: the data's classes do not match the repo's 10 names`. That is the designed check (the SciDB page says MSDD has **eight** defect types, the repo lists ten) and is not a failure; the audit files are already saved before it.
7. If cell "persist" printed `MANUAL STEP` (no Secrets set, or the API call failed): set `STOP_ON_CLASS_MISMATCH = False`, **Save Version > Save & Run All** (this downloads again once; use a fresh link), then Output tab > **New Dataset** > select the `persist/dataset_copy` folder, name it `msdd-verified`, **Private**.
8. If the first cell of the probe stops with `URL did not return archive bytes`, the link was a login page or has expired: repeat Step 1 for a fresh link.

## Step 3 - Bring back the audit
Put under `./returned/1/`:
- `audit.json`, `audit_report.md`, `items.csv` (Kaggle file browser: `/kaggle/working/audit_out/`, or Output tab after Save Version)
- the `sample_boxes/` images (12 jpg) from the same folder
- the console lines starting `DISK`, `PERSISTENCE CHOICE`, `PROBE` and `VERIFY` (paste into `./returned/1/console.txt`)
- the name of the private dataset that now holds the persistent copy (in `console.txt`)
Then tell me **continue**.

## Deferred to HANDOFF 2 (needs the real data and a GPU; not done, not skipped silently)
Notebooks 01 and 02 on the real data; a GPU/Kaggle run of notebook 02 (T4 x2 / DDP and full-size yolov8l, yolo11l, rtdetr-l weight downloads were not exercised locally, only CPU with n-size models); Baseline B wiring (E2), which depends on the audit and on your decision about 15 vs 16 channels.
