/**
 * Browser client for the inspection backend (steel-defect-backend/). Set
 * NEXT_PUBLIC_INSPECT_API_URL when it isn't on localhost:8000.
 */

import type { DefectAlertEvent, Inspection, ProgressEvent } from "./types.ts";

export const API_URL = (process.env.NEXT_PUBLIC_INSPECT_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

/** Every Nth frame goes through the model; the frames between reuse its boxes. */
export const STRIDE = 2;

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Backend returned ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function uploadVideo(file: File, conf: number): Promise<Inspection> {
  const form = new FormData();
  form.append("file", file);
  form.append("conf_threshold", String(conf));
  form.append("stride", String(STRIDE));
  return json(await fetch(`${API_URL}/api/v1/inspections/upload/video`, { method: "POST", body: form }));
}

export async function getInspection(id: string): Promise<Inspection> {
  return json(await fetch(`${API_URL}/api/v1/inspections/${id}`, { cache: "no-store" }));
}

export function mediaUrl(path: string): string {
  return `${API_URL}${path}`;
}

type Handlers = {
  progress: (event: ProgressEvent) => void;
  alert: (event: DefectAlertEvent) => void;
  done: () => void;
  error: (message: string) => void;
};

/** Live events for one inspection. Returns a function that closes the socket. */
export function watchInspection(id: string, on: Handlers): () => void {
  const socket = new WebSocket(`${API_URL.replace(/^http/, "ws")}/ws/inspections/${id}`);
  socket.onmessage = (message) => {
    const { event, data } = JSON.parse(message.data);
    if (event === "progress") on.progress(data);
    else if (event === "defect_alert") on.alert(data);
    else if (event === "completed") on.done();
    else if (event === "error") on.error(data.error);
  };
  socket.onerror = () => on.error(`Lost connection to ${API_URL}`);
  return () => socket.close();
}

/** The model file the backend actually loaded, from GET /health. */
export async function getLoadedModel(): Promise<string | null> {
  try {
    const health = await json<{ yolo_model?: string }>(await fetch(`${API_URL}/health`, { cache: "no-store" }));
    return health.yolo_model ?? null;
  } catch {
    return null;
  }
}

/** Save the annotated video as a file. Cross-origin links ignore the download attribute, so fetch the bytes first. */
export async function saveVideo(url: string, filename: string): Promise<void> {
  const blob = await (await fetch(url)).blob();
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(objectUrl);
}

/** One row per saved detection, with its time in the original video. */
export function inspectionReportCsv(inspection: Inspection, meta: { model: string; threshold: number }): string {
  const header = ["file", "model", "confidence_threshold", "frames_processed", "total_frames", "decision", "class", "confidence", "frame", "timestamp_s", "x1", "y1", "x2", "y2"];
  const rows = [...inspection.defects]
    .sort((a, b) => a.frame_number - b.frame_number)
    .map((d) => [
      inspection.file_name,
      meta.model,
      meta.threshold,
      inspection.frames_processed,
      inspection.total_frames,
      inspection.quality_decision,
      d.class_name,
      d.confidence.toFixed(4),
      d.frame_number,
      d.timestamp_s.toFixed(3),
      d.bbox.x1,
      d.bbox.y1,
      d.bbox.x2,
      d.bbox.y2,
    ]);
  return [header, ...rows].map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(",")).join("\n") + "\n";
}

export function downloadText(content: string, filename: string): void {
  const url = URL.createObjectURL(new Blob([content], { type: "text/csv" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
