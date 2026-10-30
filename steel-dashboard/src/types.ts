// ─── Defect Classes ──────────────────────────────────────────────────────────

export const DEFECT_CLASSES = [
  'crazing',
  'inclusion',
  'patches',
  'pitted_surface',
  'rolled-in_scale',
  'scratches',
] as const;

export type DefectClass = typeof DEFECT_CLASSES[number];

export const DEFECT_COLORS: Record<DefectClass, string> = {
  crazing:         '#FF6B6B',
  inclusion:       '#4ECDC4',
  patches:         '#45B7D1',
  pitted_surface:  '#96CEB4',
  'rolled-in_scale': '#FFEAA7',
  scratches:       '#DDA0DD',
};

export const DEFECT_LABELS: Record<DefectClass, string> = {
  crazing:         'Crazing',
  inclusion:       'Inclusion',
  patches:         'Patches',
  pitted_surface:  'Pitted Surface',
  'rolled-in_scale': 'Rolled-in Scale',
  scratches:       'Scratches',
};

export const DEFECT_DESCRIPTIONS: Record<DefectClass, string> = {
  crazing:         'Network of fine surface cracks, often faint and low-contrast',
  inclusion:       'Non-metallic particles embedded in the surface during rolling',
  patches:         'Irregular discoloured or texture-altered surface regions',
  pitted_surface:  'Small pits or cavities on the steel surface',
  'rolled-in_scale': 'Oxide scale pressed into the surface during rolling process',
  scratches:       'Linear abrasion marks from mechanical contact',
};

export const DEFECT_SEVERITY: Record<DefectClass, 'high' | 'medium' | 'low'> = {
  crazing:         'medium',
  inclusion:       'high',
  patches:         'medium',
  pitted_surface:  'high',
  'rolled-in_scale': 'medium',
  scratches:       'low',
};

// ─── Model Types ─────────────────────────────────────────────────────────────

export interface ClassMetrics {
  class: string;
  AP50: number;
  AP50_95: number;
  recall_at_conf025: number;
  gt_boxes: number;
}

export interface OverallMetrics {
  precision: number;
  recall: number;
  mAP50: number;
  mAP50_95: number;
  recall_at_conf025: number;
  missed_at_conf025: number;
  false_alarms_at_conf025: number;
  image_hit_rate_at_conf025: number;
}

export interface Detector {
  id: string;
  checkpoint: string;
  label: string;
  registered: boolean;
  status: 'recommended' | 'ok' | 'do_not_use';
  trained_on: string;
  notes: string;
  cpu_ms: number;
  size_mb: number;
  metrics: { val: OverallMetrics; test: OverallMetrics };
  per_class: { val: ClassMetrics[]; test: ClassMetrics[] };
  gap_to_reference: { mAP50: { mean: number; lo: number; hi: number }; mAP50_95: { mean: number; lo: number; hi: number } } | null;
}

// ─── Inspection Types ─────────────────────────────────────────────────────────

export type QualityStatus = 'approved' | 'rejected' | 'review';

export interface Detection {
  id: string;
  class_name: DefectClass;
  confidence: number;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  alert: boolean;
}

export interface InspectionRecord {
  id: string;
  sheet_id: string;
  timestamp: string;
  line: string;
  status: QualityStatus;
  defect_count: number;
  detections: Detection[];
  image_url?: string;
  processing_time_ms: number;
  confidence_avg: number;
}

// ─── Video Detection Types ────────────────────────────────────────────────────

export interface FrameDetection {
  frame: number;
  timestamp_seconds: number;
  class_id: number;
  class_name: string;
  confidence: number;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  alert: boolean;
}

export interface FrameSummary {
  frame: number;
  timestamp_seconds: number;
  detection_count: number;
  alert: boolean;
  max_confidence: number;
}

export interface ClassSummary {
  class_name: string;
  detection_count: number;
  mean_confidence: number;
  max_confidence: number;
  alert_count: number;
}

// ─── Analytics Types ──────────────────────────────────────────────────────────

export interface TrendPoint {
  date: string;
  total: number;
  defects: number;
  fpyRate: number;
  rejectionRate: number;
}

export interface DefectDistribution {
  name: string;
  count: number;
  percentage: number;
  color: string;
}

// ─── Production Types ────────────────────────────────────────────────────────

export type LineStatus = 'running' | 'idle' | 'maintenance' | 'alert';

export interface ProductionLine {
  id: string;
  name: string;
  status: LineStatus;
  throughput: number; // sheets/hour
  approved: number;
  rejected: number;
  uptime: number; // percentage
  speed: number; // m/min
}

// ─── Settings Types ───────────────────────────────────────────────────────────

export interface InspectionSettings {
  confidenceThreshold: number;
  alertConfidenceThreshold: number;
  enabledClasses: DefectClass[];
  qualityThreshold: number; // max defects before rejection
  imageSize: number;
  iouThreshold: number;
  autoReject: boolean;
}

// ─── Report Types ────────────────────────────────────────────────────────────

export interface ReportConfig {
  title: string;
  dateFrom: string;
  dateTo: string;
  includeCharts: boolean;
  includeImages: boolean;
  format: 'pdf' | 'csv';
  lines: string[];
  classes: DefectClass[];
}

// ─── Navigation ──────────────────────────────────────────────────────────────

export type PageId =
  | 'overview'
  | 'inspection'
  | 'analytics'
  | 'history'
  | 'production'
  | 'intelligence'
  | 'reports'
  | 'settings';
