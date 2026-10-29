# Dashboard API contract

The dashboard (`dashboard/`) makes one request and renders everything from the response. A backend only has to serve this one endpoint.

```
GET <EVAL_API_URL>
200 OK
Content-Type: application/json
```

The dashboard fetches it on the server for every page load (`cache: "no-store"`), so CORS does not matter. A non-200 response shows Next.js's error page.

`dashboard/data/evaluation.json` is a complete, valid example, built by `scripts/export_dashboard_json.py`. The TypeScript types in `dashboard/lib/types.ts` are the source of truth; this page explains them.

## Top level

| Field | Type | Meaning |
|-------|------|---------|
| `generated_at` | string, `YYYY-MM-DD` | Date the evaluation was run. Shown in the nav. |
| `reference_model` | string | Label of the model the others are compared against. |
| `splits` | `{ val, test }`, each `{ images, boxes }` | Size of each NEU-DET split. |
| `classes` | string[] | Class names, in display order. |
| `detectors` | Detector[] | Every NEU-DET detector. |
| `classifiers` | Classifier[] | Casting classifiers. An empty array hides that section. |
| `caveats` | string[] | Plain-text notes shown at the bottom of the page. |

## Detector

| Field | Type | Meaning |
|-------|------|---------|
| `id` | string | URL-safe id, used in `/models/<id>`. |
| `checkpoint` | string | Registered version name (for example `v1_yolo11n_baseline`), or `loose:<file>.pt` for a file directly in `models/`. |
| `label` | string | Display name. |
| `registered` | boolean | Whether it is a registered version under `models/<version>/`. |
| `status` | `"recommended"` \| `"ok"` \| `"do_not_use"` | Exactly one detector must be `recommended`; it becomes the reference model. |
| `trained_on` | string | One sentence on the training data. |
| `notes` | string | One sentence on what to make of the model. |
| `cpu_ms` | number | CPU milliseconds per image. |
| `size_mb` | number | Weight file size. |
| `metrics` | `{ val, test }` of OverallMetrics | See below. |
| `per_class` | `{ val, test }` of ClassMetrics[] | One entry per class. |
| `gap_to_reference` | `{ mAP50, mAP50_95 }` of `{ mean, lo, hi }`, or `null` | Reference minus this model on the test split (paired bootstrap, 95% interval). `null` for the reference itself. |

**OverallMetrics:** `precision`, `recall`, `mAP50`, `mAP50_95` (Ultralytics `val`, values from 0 to 1); `recall_at_conf025` (0–1), `missed_at_conf025` and `false_alarms_at_conf025` (integer counts), and `image_hit_rate_at_conf025` (0–1). The last four come from one-to-one matching at conf 0.25 and IoU 0.5.

**ClassMetrics:** `class`, `AP50`, `AP50_95`, `recall_at_conf025` (0–1), and `gt_boxes` (integer).

## Classifier

| Field | Type | Meaning |
|-------|------|---------|
| `id`, `label` | string | Identifier and display name. |
| `dataset` | string | Where the test images came from. |
| `test_images` | integer | Number of test images. |
| `reported_accuracy` | number | Accuracy the model's own package claims. |
| `accuracy`, `auc` | number | Measured on the test images. |
| `defective_recall`, `defective_precision`, `ok_recall` | number | Per-class results. |
| `confusion_matrix` | `[[number, number], [number, number]]` | Rows are true `[defective, ok]`; columns are predicted `[defective, ok]`. |
| `cpu_ms` | number | CPU milliseconds per image. |
