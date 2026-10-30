"use client";

/** Raised as soon as the model finds a defect; stays up with the latest one and a running count. */

import type { DefectEvent } from "./DefectTimeline.tsx";
import { className, clock, pct } from "../lib/format.ts";
import { Warning } from "../app/icons.tsx";

export default function AlertBanner({
  events,
  running,
  sound,
  onSound,
}: {
  events: DefectEvent[];
  running: boolean;
  sound: boolean;
  onSound: (on: boolean) => void;
}) {
  if (events.length === 0) {
    return (
      <div className="banner alert-bar" role="status">
        <div>
          <h3>{running ? "No defects so far." : "No defects found."}</h3>
          <p>{running ? "An alert appears here the moment the model finds one." : "Nothing crossed the confidence threshold."}</p>
        </div>
      </div>
    );
  }

  const latest = events.reduce((a, b) => (b.start_frame >= a.start_frame ? b : a));
  return (
    <div className="banner banner-bad alert-bar" role="alert">
      <Warning className="banner-icon" />
      <div>
        <h3>
          Defect detected: {className(latest.class_name)} {pct(latest.peak)} at {clock(latest.start_s)}
        </h3>
        <p>
          {events.length} defect {events.length === 1 ? "event" : "events"} {running ? "so far" : "in this video"}.
        </p>
      </div>
      <label className="alert-sound">
        <input type="checkbox" checked={sound} onChange={(e) => onSound(e.target.checked)} /> Sound
      </label>
    </div>
  );
}
