"""Generate notebooks/msdd/{00_download_and_audit,01_split,02_train}.ipynb.

The shared library (src/msdd_lib.py) and src/configs/experiments.yaml are inlined into each notebook through
%%writefile cells, so a notebook is the only file you need to upload to Kaggle/Colab.
Run:  python tools/build_notebooks.py
"""
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
LIB = (ROOT / 'src' / 'msdd_lib.py').read_text()
EXPS = (ROOT / 'src' / 'configs' / 'experiments.yaml').read_text()
OUT = ROOT / 'notebooks' / 'msdd'

PINS = "ultralytics==8.4.210 kornia==0.9.0 pytorch_msssim==1.0.0 torchsummary==1.5.1"

BOOT_LIB = "%%writefile msdd_lib.py\n" + LIB
BOOT_EXPS = "%%writefile experiments.yaml\n" + EXPS
INSTALL = f'''# Pinned dependencies (torch/torchvision are the platform's CUDA builds; tested locally with torch 2.15.0).
import os, subprocess, sys
if not os.environ.get("MSDD_SKIP_INSTALL"):
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", {", ".join(repr(p) for p in PINS.split())},
                           "gdown", "requests", "pyyaml", "pandas", "pillow", "tqdm"])
sys.path.insert(0, ".")
import msdd_lib as L
print("python", sys.version.split()[0])'''


def md(s):
    return nbf.v4.new_markdown_cell(s)


def code(s):
    return nbf.v4.new_code_cell(s)


def save(nb, name):
    OUT.mkdir(parents=True, exist_ok=True)
    nb.metadata['kernelspec'] = {'name': 'python3', 'display_name': 'Python 3', 'language': 'python'}
    nbf.write(nb, OUT / name)
    print('wrote', OUT / name)


# ----------------------------------------------------------------------------------------------- 00
nb0 = nbf.v4.new_notebook()
nb0.cells = [
    md("# 00 - Download MSDD once, verify, audit, persist\n"
       "Run on **Kaggle** (GPU not needed, Internet ON) or Colab. Edit only the cell marked `EDIT HERE`.\n\n"
       "Order: probe URL (few MB) -> download with resume -> verify -> unzip -> audit -> persist a verified copy so "
       "notebooks 01 and 02 never touch SciDB again. The audit is saved **before** the class check can stop the run."),
    code(BOOT_LIB),
    code(INSTALL),
    code('''# ============================== EDIT HERE ==============================
SOURCE_MODE = "url"            # "url" | "gdown" | "kaggle_input" | "local_dir"

# --- SOURCE_MODE = "url": paste the DIRECT download link(s) copied from the SciDB downloads list (one per file).
#     Links can expire: run this notebook right after copying. Leave the list empty to stop at the check below.
DOWNLOAD_URLS = [
    # "PASTE_DIRECT_DOWNLOAD_URL_HERE",
]
GDOWN_IDS_OR_URLS = []                          # SOURCE_MODE = "gdown"
KAGGLE_INPUT_DIR = "/kaggle/input/CHANGE-ME"    # SOURCE_MODE = "kaggle_input" (dataset attached via Add Input)
LOCAL_DIR = ""                                  # SOURCE_MODE = "local_dir" (already-extracted tree, e.g. a sample)

EXPECTED_TOTAL_BYTES = 9_785_811_363   # total file size stated on the SciDB page metadata (checked, only warns)
KAGGLE_DATASET_SLUG = "msdd-verified"  # name of the private Kaggle dataset that will hold the persistent copy
CREATE_KAGGLE_DATASET = True           # try the Kaggle API (needs Secrets KAGGLE_USERNAME / KAGGLE_KEY); else manual steps
STOP_ON_CLASS_MISMATCH = True
CLASS_NAMES_OVERRIDE = None            # only if the data has no names file; otherwise leave None

# Recorded from the SciDB page JSON-LD on 2026-11-11. Confirm against the page (its UI text also mentions CC BY-SA 4.0).
LICENCE = "CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/) per SciDB page metadata; confirm on the page"
CITATION = ("@data{3d739ddb4bdc439a9bf7ef550cae48d8, title={Metal Surface Defect Dataset}, author={Lin Wu}, year={2024}, "
            "month={July}, publisher={Science Data Bank}, doi={10.57760/sciencedb.10794}, "
            "url={https://doi.org/10.57760/sciencedb.10794}, version={V1}}")
# =======================================================================
'''),
    code('''import json, shutil
from pathlib import Path
GB = L.GB
P = L.get_paths()
print(P)
DS_COPY = P["persist"] / "dataset_copy"      # <- this folder is the persistent, SciDB-free copy
DS_COPY.mkdir(parents=True, exist_ok=True)
SCRATCH = [p for p in ("/kaggle/temp", "/tmp", str(P["work"])) if Path(p).exists()]
rows = L.disk_report([P["work"], P["persist"], *SCRATCH])
# extraction goes to the volume with the most free space
EXTRACT_ROOT = Path(max(SCRATCH, key=lambda p: L.free_gb(p))) / "msdd_data"
print("extract target:", EXTRACT_ROOT)'''),
    code('''ARCHIVES, DATA_DIR = [], None
EXT = {"zip": ".zip", "7z": ".7z", "tar": ".tar", "gzip": ".tar.gz", "bzip2": ".tar.bz2", "xz": ".tar.xz"}

def fetch_archives():
    global ARCHIVES
    if SOURCE_MODE == "url":
        assert DOWNLOAD_URLS, "DOWNLOAD_URLS is empty: paste the direct link(s) as described in HANDOFF.md, then re-run."
        probes = [L.probe_url(u) for u in DOWNLOAD_URLS]          # a few MB only; raises on a login page
        total = sum(p["total_bytes"] or 0 for p in probes)
        print(f"servers report {total/GB:.2f} GB total; free in persist dir {L.free_gb(DS_COPY):.1f} GB, "
              f"free in extract dir {L.free_gb(EXTRACT_ROOT.parent):.1f} GB")
        if total and total/GB*1.05 > L.free_gb(DS_COPY): raise RuntimeError("not enough free disk for the archive(s)")
        for i, (u, p) in enumerate(zip(DOWNLOAD_URLS, probes)):
            ext = EXT.get(p["sniffed"].split("(")[0], ".bin")
            ARCHIVES.append(L.download_url(u, DS_COPY / f"msdd_part{i:02d}{ext}"))
    elif SOURCE_MODE == "gdown":
        for i, g in enumerate(GDOWN_IDS_OR_URLS):
            ARCHIVES.append(L.download_gdown(g, DS_COPY / f"msdd_part{i:02d}.bin"))
    return ARCHIVES

if SOURCE_MODE in ("url", "gdown"):
    fetch_archives()
    got = sum(a.stat().st_size for a in ARCHIVES)
    if EXPECTED_TOTAL_BYTES and abs(got - EXPECTED_TOTAL_BYTES) / EXPECTED_TOTAL_BYTES > 0.05:
        print(f"WARNING: archives total {got} bytes vs {EXPECTED_TOTAL_BYTES} stated on the page (archives may differ legitimately)")
    for a in ARCHIVES: L.verify_archive(a)
    for a in ARCHIVES: L.extract_archive(a, EXTRACT_ROOT)
    DATA_DIR = EXTRACT_ROOT
elif SOURCE_MODE == "kaggle_input":
    DATA_DIR = Path(KAGGLE_INPUT_DIR)
    assert DATA_DIR.exists(), f"{DATA_DIR} not found: attach the dataset via Add Input"
    arcs = [p for p in DATA_DIR.iterdir() if p.suffix in (".zip", ".7z", ".tar", ".gz")]
    if arcs and not any(DATA_DIR.rglob("*.jpg")):
        for a in arcs: L.verify_archive(a); L.extract_archive(a, EXTRACT_ROOT)
        DATA_DIR = EXTRACT_ROOT
elif SOURCE_MODE == "local_dir":
    DATA_DIR = Path(LOCAL_DIR); assert DATA_DIR.exists(), LOCAL_DIR
else:
    raise ValueError(SOURCE_MODE)

DATA_BYTES = L.dir_size(DATA_DIR)
print(f"DATA_DIR={DATA_DIR}  total {DATA_BYTES/GB:.2f} GB ({DATA_BYTES} bytes)")
L.disk_report([P["work"], EXTRACT_ROOT.parent])'''),
    code('''# ---- audit (saved before anything can stop the notebook) ----
audit, items = L.audit_dataset(DATA_DIR, class_names_override=CLASS_NAMES_OVERRIDE, licence=LICENCE, citation=CITATION)
audit["source_mode"] = SOURCE_MODE
audit["archives"] = [a.name for a in ARCHIVES]
AUDIT_OUT = P["persist"] / "audit"
L.write_audit(audit, items, AUDIT_OUT)
L.draw_samples(DATA_DIR, items, audit["class_names"], AUDIT_OUT / "sample_boxes", n=12)
print((AUDIT_OUT / "audit_report.md").read_text())
if P["env"] == "kaggle":   # also visible as notebook output files for easy download
    shutil.copytree(AUDIT_OUT, Path("/kaggle/working/audit_out"), dirs_exist_ok=True)'''),
    code('''# ---- persist a verified copy so later sessions never need SciDB ----
choice = L.choose_persistence(DATA_BYTES, P["env"])
if SOURCE_MODE == "kaggle_input" and DATA_DIR == Path(KAGGLE_INPUT_DIR):
    print("Data came from an attached Kaggle dataset: it is already the persistent copy. Nothing to upload.")
    manifest = None
elif choice["scope"] == "all" and ARCHIVES:
    manifest = L.write_manifest(ARCHIVES, DS_COPY, "archives")          # keep the verified originals + sha256
elif choice["scope"] == "all":
    manifest = L.make_tar_shards(DATA_DIR, DS_COPY)
else:
    keep = []
    for it in items:                                                      # training needs images + labels only
        keep += [DATA_DIR / it["img"]] + ([DATA_DIR / it["label"]] if it["label"] else [])
    for a in ARCHIVES: a.unlink()
    manifest = L.make_tar_shards(DATA_DIR, DS_COPY, subset=keep)
    print("LEFT OUT of the persistent copy (raw frame files):", audit["n_raw_frame_files"], "files")
shutil.copytree(AUDIT_OUT, DS_COPY / "audit", dirs_exist_ok=True)
print("persistent copy at:", DS_COPY, "| size GB:", round(L.dir_size(DS_COPY)/GB, 2))

if P["env"] == "kaggle" and manifest is not None:
    if CREATE_KAGGLE_DATASET:
        r = L.try_kaggle_dataset_create(DS_COPY, KAGGLE_DATASET_SLUG, "MSDD verified copy"); print(r)
        if not r["done"]: print("MANUAL STEP (HANDOFF.md): Save Version (Save & Run All), then Output tab > New Dataset > select the dataset_copy folder, private.")
    else:
        print("MANUAL STEP (HANDOFF.md): Save Version (Save & Run All), then Output tab > New Dataset, private.")
elif P["env"] == "colab":
    print("Persistent copy is on Drive:", DS_COPY)'''),
    code('''# ---- class check against the repo's 10 names (outputs are already saved above) ----
cc = audit["class_check"]; print(json.dumps(cc, indent=1))
if cc["status"] != "match" and STOP_ON_CLASS_MISMATCH:
    raise SystemExit("STOP: the data's classes do not match the repo's 10 names (details above). "
                     "audit.json / audit_report.md are saved; bring them back (HANDOFF.md). Do not change the class list without deciding it with the user.")
print("classes match the repo list")'''),
]
save(nb0, '00_download_and_audit.ipynb')

# ----------------------------------------------------------------------------------------------- 01
nb1 = nbf.v4.new_notebook()
nb1.cells = [
    md("# 01 - Stratified capture-level split (train/val/test ~ 70/15/15)\n"
       "Loads the persistent copy made by notebook 00 (never SciDB), splits at **capture level**, writes the split lists + a dataset yaml.\n"
       "The split is saved once. If any experiment has already used it, this notebook refuses to change it (ask the user first)."),
    code(BOOT_LIB),
    code(INSTALL),
    code('''# ============================== EDIT HERE ==============================
SEED = 0
RATIOS = (0.70, 0.15, 0.15)
DATASET_DIR = None                    # None = auto-locate (Drive / attached Kaggle dataset / local persist dir)
GROUP_REGEX = r"^(\\d{8}_\\d{6})"       # capture id from a filename stem; images sharing it never cross splits. Set None to treat each image as a capture.
USE_SHIPPED_VAL = "auto"              # "auto": if the data ships train/val dirs keep its val and carve test from train
LINK = "symlink"                      # "symlink" | "hardlink" | "copy" for the YOLO folder built on local disk
FORCE_NEW_SPLIT = False               # only after agreeing with the user: split already used by a run
# =======================================================================
'''),
    code('''import json, hashlib, shutil
from pathlib import Path
P = L.get_paths(); print(P)
kind, ds = L.locate_dataset(P, DATASET_DIR); print(kind, ds)
DATA = L.restore_from_persistent(ds, P["work"] / "msdd_data") if kind == "archives" else ds
audit, items = L.load_audit(P, DATA, ds if kind == "archives" else None)
names = audit["class_names"]; assert names, "no class names in the audit; resolve this before splitting (see HANDOFF.md)"
if audit["class_check"]["status"] != "match":
    print("NOTE: classes differ from the repo list:", audit["class_check"].get("reason", audit["class_check"]["status"]))
print(len(items), "detection images;", len(names), "classes")'''),
    code('''# group diagnostics: how images collapse into captures
from collections import Counter
gk = [L.group_key(i["img"], GROUP_REGEX) for i in items]
sizes = Counter(Counter(gk).values())
hit = sum(1 for i in items if GROUP_REGEX and __import__("re").search(GROUP_REGEX, Path(i["img"]).stem)) / max(1, len(items))
print(f"{len(set(gk))} capture groups for {len(items)} images; regex matches {hit:.1%} of filenames; group-size histogram {dict(sizes)}")
print("example filenames:", [Path(i["img"]).name for i in items[:3]])
if GROUP_REGEX and hit < 0.9:
    print("WARNING: GROUP_REGEX matches few filenames, so most images are their own group. Check the example names above.")'''),
    code('''SPL = P["persist"] / "splits"
runs_dir = P["persist"] / "runs"
used = runs_dir.exists() and any(runs_dir.iterdir())
if (SPL / "split_manifest.json").exists() and not FORCE_NEW_SPLIT:
    print("Split already exists - loading it unchanged:", SPL)
    splits = {s: (SPL / f"{s}.txt").read_text().split() for s in ("train", "val", "test")}
    group_of = {i["img"]: L.group_key(i["img"], GROUP_REGEX) for i in items}
else:
    if used and not FORCE_NEW_SPLIT:
        raise RuntimeError("A run already used the split; ask the user before changing it.")
    shipped = audit["shipped_split_dirs"].get("val", 0) > 0
    if USE_SHIPPED_VAL is True or (USE_SHIPPED_VAL == "auto" and shipped):
        print("Using the dataset's own val; carving test from its train")
        res = L.split_with_shipped_val(items, GROUP_REGEX, SEED, test_frac=RATIOS[2])
    else:
        res = L.stratified_group_split(items, GROUP_REGEX, RATIOS, SEED)
    splits, group_of = res["splits"], res["group_of"]
    SPL.mkdir(parents=True, exist_ok=True)
    for s, ims in splits.items(): (SPL / f"{s}.txt").write_text("\\n".join(ims) + "\\n")
L.check_no_leak(splits, group_of)
print("no capture group spans two splits; no image in two splits")
tab = L.per_class_table(items, splits, names); print(tab.to_string(index=False))
low = [(r["split"], c) for _, r in tab.iterrows() for c in names if c in tab and r.get(c, 0) < 5]
if low: print("WARNING: very few instances (<5) in", low)
man = dict(seed=SEED, ratios=RATIOS, group_regex=GROUP_REGEX, n_items=len(items),
           sha256={s: hashlib.sha256((SPL / f"{s}.txt").read_bytes()).hexdigest() for s in splits},
           counts={s: len(v) for s, v in splits.items()}, per_class=tab.to_dict("records"))
old = SPL / "split_manifest.json"
if old.exists() and json.loads(old.read_text())["sha256"] != man["sha256"] and not FORCE_NEW_SPLIT:
    raise RuntimeError("split lists differ from the stored manifest")
old.write_text(json.dumps(man, indent=1, default=str))'''),
    code('''# YOLO folder on local disk + dataset yaml that uses the split lists
FARM = P["work"] / "msdd_yolo"
if FARM.exists(): shutil.rmtree(FARM)
YAML = L.build_yolo_farm(DATA, items, splits, FARM, names, link=LINK)
print(Path(YAML).read_text())
print({s: len((FARM / f"{s}.txt").read_text().split()) for s in splits})'''),
]
save(nb1, '01_split.ipynb')

# ----------------------------------------------------------------------------------------------- 02
runcells = []
for e in ["E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8a", "E8b", "E8c", "E8d"]:
    runcells.append(code(f'run_one("{e}")   # {e}'))
nb2 = nbf.v4.new_notebook()
nb2.cells = [
    md("# 02 - Train experiments and evaluate on test\n"
       "Run the experiment cells from the top as far as GPU quota allows. Every epoch the checkpoint + `results.csv` are mirrored to persistent storage; "
       "re-running a cell after a disconnect **resumes** it, and a finished run is skipped.\n"
       "Val is evaluated during training. Test is evaluated only in the separate evaluation cell, once per run."),
    code(BOOT_LIB),
    code(BOOT_EXPS),
    code(INSTALL),
    code('''# ============================== EDIT HERE ==============================
DATASET_DIR = None          # None = auto-locate the persistent copy
DEVICE = "0"                # "0", "0,1" (Kaggle T4 x2), or "cpu"
WORKERS = 4
BATCH = None                # None = batch from the config (16). Lower it on out-of-memory.
OVERRIDES = {}              # applied to every experiment, e.g. {"epochs": 1}. Leave {} for real runs.
MODEL_OVERRIDE = None       # e.g. "yolov8n.pt" for a smoke test only
# =======================================================================
'''),
    code('''import json, time, shutil
from pathlib import Path
import pandas as pd
P = L.get_paths(); print(P)
SPEC = L.load_experiments("experiments.yaml")
kind, ds = L.locate_dataset(P, DATASET_DIR)
DATA = L.restore_from_persistent(ds, P["work"] / "msdd_data") if kind == "archives" else ds
audit, items = L.load_audit(P, DATA, ds if kind == "archives" else None)
names = audit["class_names"]
SPL = P["persist"] / "splits"
assert (SPL / "split_manifest.json").exists(), "run notebook 01 first (splits not found in persistent storage)"
splits = {s: (SPL / f"{s}.txt").read_text().split() for s in ("train", "val", "test")}
FARM = P["work"] / "msdd_yolo"
if not (FARM / "data.yaml").exists():                      # new session: rebuild the local folder from the saved lists
    L.build_yolo_farm(DATA, items, splits, FARM, names)
BASE_YAML = FARM / "data.yaml"
DATA_YAMLS = {"baseline_a": BASE_YAML, "baseline_b": None}  # baseline_b is wired in Phase 2 (see HANDOFF.md)
ALL_IDS = [i for i in SPEC["order"]] + SPEC["optional"]

def oversampled_yaml(nc):
    import yaml
    lines = (FARM / "train.txt").read_text().split()
    freq = {}
    for ln in lines:
        lab = FARM / "labels" / "train" / (Path(ln).stem + ".txt")
        cs = {int(float(r.split()[0])) for r in lab.read_text().splitlines() if r.strip()} if lab.exists() else set()
        for c in cs: freq[c] = freq.get(c, 0) + 1
    present = sorted(freq.values()); t = present[len(present)//2] / len(lines)    # median class image-frequency
    out, stats = L.repeat_factor_oversample(lines, FARM / "labels" / "train", nc, t=t)
    (FARM / "train_os.txt").write_text("\\n".join(out) + "\\n")
    d = yaml.safe_load(BASE_YAML.read_text()); d["train"] = "train_os.txt"
    (FARM / "data_os.yaml").write_text(yaml.safe_dump(d, sort_keys=False))
    print("oversampling threshold t =", round(t, 4), json.dumps(stats))
    return FARM / "data_os.yaml"

def run_one(exp_id):
    done = L.completed_runs(P["persist"], ALL_IDS)
    cfg = L.resolve_experiment(exp_id, SPEC, audit, done)
    cfg["train_args"].update(OVERRIDES)
    if MODEL_OVERRIDE: cfg["model"] = MODEL_OVERRIDE
    if cfg["requires"] == "baseline_b_ready" and DATA_YAMLS.get("baseline_b") is None:
        print(f"{exp_id} NOT RUN: Baseline B is not set up yet (needs the Phase 2 audit decision; see FEASIBILITY.md / HANDOFF.md).")
        return None
    if exp_id in ("E8c", "E8d") and cfg["meta"].get("_base_id") == "E1":
        print(f"{exp_id} SKIPPED: the best run so far is E1, already repeated by E8a/E8b."); return None
    data = DATA_YAMLS[cfg["data_variant"]]
    if cfg["oversample"]: data = oversampled_yaml(len(names))
    print(f"=== {exp_id}: {cfg['description']}\\n    model={cfg['model']} data_variant={cfg['data_variant']} meta={cfg['meta']}")
    t0 = time.time()
    run = L.run_experiment(cfg, data, P["work"], P["persist"], device=DEVICE, workers=WORKERS, batch=BATCH)
    s = L.val_score_from_results(Path(run) / "results.csv")
    print(f"{exp_id}: best val mAP50-95 = {s}  ({(time.time()-t0)/60:.1f} min this session)")
    return run'''),
    *runcells,
    md("## Optional quota savers (yolov8m ablations)\nRun `E1m`, then `E3m`/`E4m`; rerun the winner at l size."),
    code('# for e in SPEC["optional"]: run_one(e)'),
    md("## Evaluate a chosen checkpoint on TEST (once per run) - choose it from VAL results only"),
    code('''EVAL_RUN = "E1"          # experiment id
EVAL_WEIGHTS = "best"    # "best" or "last"
run = P["persist"] / "runs" / EVAL_RUN
cfg = json.loads((run / "resolved_config.json").read_text())
test = L.evaluate_split(run / "weights" / f"{EVAL_WEIGHTS}.pt", FARM / "data.yaml", "test", run / "eval",
                        imgsz=int(cfg["train_args"]["imgsz"]), device=DEVICE, batch=BATCH or 16)'''),
    md("## Val summary of all finished runs (for model selection)"),
    code('''rows = []
for i in ALL_IDS:
    r = P["persist"] / "runs" / i
    if (r / "DONE").exists():
        df = pd.read_csv(r / "results.csv"); df.columns = [c.strip() for c in df.columns]
        b = df.loc[df["metrics/mAP50-95(B)"].idxmax()]
        rows.append(dict(run=i, best_epoch=int(b["epoch"]), P=b["metrics/precision(B)"], R=b["metrics/recall(B)"],
                         mAP50=b["metrics/mAP50(B)"], mAP50_95=b["metrics/mAP50-95(B)"]))
print(pd.DataFrame(rows).to_string(index=False) if rows else "no finished runs yet")'''),
]
save(nb2, '02_train.ipynb')
