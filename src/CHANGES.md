# Changes vs reference_repo (c9aa21a)

- `train_detector.py`: rewritten as a CLI. `--config` replaces the missing `mix_8cls.yaml`; model, name, project,
  epochs, imgsz, batch, seed, device, workers and extra Ultralytics args (`--hyp`) are arguments.
- `train_tscm.py`, `train_pifm.py`: data dirs, experiment name, output dir, epochs, batch, crop size and
  weight paths are arguments (was hardcoded `exp17`, `./datasets/VAE/...`, `weights/*_exp10.pt`). Refuse to delete an existing
  experiment dir unless `--overwrite`. Removed the debug `print(quantized.size(), feature.size())` from the batch loop in `train_pifm.py`.
- Default weights are no longer loaded: the shipped `weights/*_exp10.pt` do not match the model classes the scripts build (see FEASIBILITY.md).
- `util.load_model_weights`: loads with `map_location='cpu'` and raises on shape mismatch (it used to print and continue from random init).
- `requirements.txt`: added ultralytics, pinned versions, removed unused streamlit/torchaudio/psutil/requests.
- Not changed: models/, McDataset.py (its 23-character prefix assumption is documented in FEASIBILITY.md; `export_mixed.py` will handle MSDD naming in Phase 2).
