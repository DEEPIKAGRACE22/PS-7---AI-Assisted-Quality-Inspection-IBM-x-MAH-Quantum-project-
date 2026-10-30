"use client";

/** Defects found in a video, merged into events and laid out along the video's length. Clicking one seeks the player. */

import type { DefectDetection } from "../lib/types.ts";
import { STRIDE } from "../lib/api.ts";
import { className, clock, pct } from "../lib/format.ts";

/** Box colours drawn by the backend (steel-defect-backend/app/config.py CLASS_COLORS), as RGB. */
export const CLASS_COLOR: Record<string, string> = {
  crazing: "rgb(255 144 30)",
  inclusion: "rgb(230 0 0)",
  patches: "rgb(0 140 255)",
  pitted_surface: "rgb(255 165 0)",
  "rolled-in_scale": "rgb(180 0 0)",
  scratches: "rgb(255 215 0)",
};

export type DefectEvent = {
  class_name: string;
  start_frame: number;
  end_frame: number;
  start_s: number;
  end_s: number;
  peak: number;
};

/** One event per run of frames where a class keeps being detected, allowing for frames the stride skips. */
export function groupDefectEvents(detections: DefectDetection[]): DefectEvent[] {
  const open = new Map<string, DefectEvent>();
  const events: DefectEvent[] = [];
  for (const d of [...detections].sort((a, b) => a.frame_number - b.frame_number)) {
    const current = open.get(d.class_name);
    if (current && d.frame_number - current.end_frame <= STRIDE) {
      current.end_frame = d.frame_number;
      current.end_s = d.timestamp_s;
      current.peak = Math.max(current.peak, d.confidence);
    } else {
      const event = {
        class_name: d.class_name,
        start_frame: d.frame_number,
        end_frame: d.frame_number,
        start_s: d.timestamp_s,
        end_s: d.timestamp_s,
        peak: d.confidence,
      };
      open.set(d.class_name, event);
      events.push(event);
    }
  }
  return events.sort((a, b) => a.start_frame - b.start_frame);
}

export default function DefectTimeline({
  events,
  totalFrames,
  currentTime,
  duration,
  onSeek,
}: {
  events: DefectEvent[];
  totalFrames: number;
  /** Player position in seconds, or null before the video is ready. */
  currentTime: number | null;
  /** Video length in seconds, once the player knows it. */
  duration: number | null;
  onSeek: ((seconds: number) => void) | null;
}) {
  const isActive = (e: DefectEvent) => currentTime !== null && currentTime >= e.start_s - 0.05 && currentTime <= e.end_s + 0.15;
  const at = (frame: number) => `${((frame - 1) / Math.max(1, totalFrames)) * 100}%`;

  return (
    <div className="timeline">
      <div className="timeline-strip" aria-hidden="true">
        {events.map((e, i) => (
          <i
            key={i}
            style={{
              left: at(e.start_frame),
              width: `max(3px, calc(${at(e.end_frame + 1)} - ${at(e.start_frame)}))`,
              background: CLASS_COLOR[e.class_name] ?? "var(--danger)",
            }}
          />
        ))}
        {currentTime !== null && duration ? <b style={{ left: `${Math.min(100, (currentTime / duration) * 100)}%` }} /> : null}
      </div>

      <ol className="events">
        {events.map((e, i) => (
          <li key={i} className={isActive(e) ? "is-active" : undefined}>
            <button type="button" disabled={!onSeek} onClick={() => onSeek?.(e.start_s)}>
              <span className="n">{clock(e.start_s)}</span>
              <span className="swatch" style={{ background: CLASS_COLOR[e.class_name] ?? "var(--danger)" }} />
              <span className="event-name">{className(e.class_name)}</span>
              <span className="n n-faint">{pct(e.peak)}</span>
            </button>
          </li>
        ))}
      </ol>
    </div>
  );
}
