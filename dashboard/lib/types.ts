/** The evaluation payload. The backend must return exactly this shape; see docs/DASHBOARD_API.md. */

export type Split = "val" | "test";

export type DetectorStatus = "recommended" | "ok" | "do_not_use";

export type OverallMetrics = {
  precision: number;
  recall: number;
  mAP50: number;
  mAP50_95: number;
  recall_at_conf025: number;
  missed_at_conf025: number;
  false_alarms_at_conf025: number;
  image_hit_rate_at_conf025: number;
};

export type ClassMetrics = {
  class: string;
  AP50: number;
  AP50_95: number;
  recall_at_conf025: number;
  gt_boxes: number;
};

export type Interval = { mean: number; lo: number; hi: number };

export type Detector = {
  id: string;
  checkpoint: string;
  label: string;
  registered: boolean;
  status: DetectorStatus;
  trained_on: string;
  notes: string;
  cpu_ms: number;
  size_mb: number;
  metrics: Record<Split, OverallMetrics>;
  per_class: Record<Split, ClassMetrics[]>;
  /** Reference model minus this model, paired bootstrap on the test split. Null for the reference itself. */
  gap_to_reference: { mAP50: Interval; mAP50_95: Interval } | null;
};

export type Classifier = {
  id: string;
  label: string;
  dataset: string;
  test_images: number;
  reported_accuracy: number;
  accuracy: number;
  auc: number;
  defective_recall: number;
  defective_precision: number;
  ok_recall: number;
  /** Rows are true [defective, ok], columns are predicted [defective, ok]. */
  confusion_matrix: [[number, number], [number, number]];
  cpu_ms: number;
};

export type Evaluation = {
  generated_at: string;
  reference_model: string;
  splits: Record<Split, { images: number; boxes: number }>;
  classes: string[];
  detectors: Detector[];
  classifiers: Classifier[];
  caveats: string[];
};

/* Video inspection: mirrors steel-defect-backend/app/models/schemas.py. */

export type BoundingBox = { x1: number; y1: number; x2: number; y2: number; width: number; height: number; area: number };

export type DefectDetection = {
  class_id: number;
  class_name: string;
  confidence: number;
  bbox: BoundingBox;
  frame_number: number;
  /** Seconds into the source video. */
  timestamp_s: number;
};

export type QualityDecision = "APPROVED" | "REVIEW_REQUIRED" | "REJECTED" | "UNKNOWN";

export type Inspection = {
  id: string;
  file_name: string;
  status: "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED";
  quality_decision: QualityDecision;
  decision_reason: string | null;
  total_defects: number;
  max_confidence: number;
  frames_processed: number;
  total_frames: number;
  error_message: string | null;
  defects: DefectDetection[];
  annotated_url: string | null;
};

export type ProgressEvent = {
  frame_index: number;
  total_frames: number;
  progress_percent: number;
  fps: number;
  current_defects_found: number;
};

export type DefectAlertEvent = {
  frame_index: number;
  timestamp_s: number;
  detections: DefectDetection[];
};
