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
