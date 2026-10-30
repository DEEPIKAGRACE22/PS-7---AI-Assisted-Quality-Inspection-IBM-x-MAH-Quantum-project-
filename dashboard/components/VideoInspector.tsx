"use client";

/**
 * Upload a video, follow the backend as it runs the model frame by frame, raise
 * an alert on the first defect, then play the annotated video next to a
 * clickable list of every defect found.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import type { DefectDetection, Inspection, ProgressEvent } from "../lib/types.ts";
import { API_URL, getInspection, mediaUrl, uploadVideo, watchInspection } from "../lib/api.ts";
import { className, fmt } from "../lib/format.ts";
import UploadDropzone from "./UploadDropzone.tsx";
import AlertBanner from "./AlertBanner.tsx";
import DefectTimeline, { CLASS_COLOR, groupDefectEvents } from "./DefectTimeline.tsx";

type Phase = "idle" | "uploading" | "running" | "done" | "failed";

const DECISION = {
  APPROVED: { label: "Approved", className: "label-accent" },
  REVIEW_REQUIRED: { label: "Review required", className: "" },
  REJECTED: { label: "Rejected", className: "label-fail" },
  UNKNOWN: { label: "Undecided", className: "" },
} as const;

function beep() {
  const audio = new AudioContext();
  const tone = audio.createOscillator();
  const gain = audio.createGain();
  tone.frequency.value = 880;
  gain.gain.setValueAtTime(0.15, audio.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, audio.currentTime + 0.25);
  tone.connect(gain).connect(audio.destination);
  tone.start();
  tone.stop(audio.currentTime + 0.25);
  tone.onended = () => audio.close();
}

export default function VideoInspector({ modelLabel }: { modelLabel: string }) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [file, setFile] = useState<File | null>(null);
  const [conf, setConf] = useState(0.25);
  const [error, setError] = useState<string | null>(null);
  const [id, setId] = useState<string | null>(null);
  const [progress, setProgress] = useState<ProgressEvent | null>(null);
  const [live, setLive] = useState<DefectDetection[]>([]);
  const [result, setResult] = useState<Inspection | null>(null);
  const [sound, setSound] = useState(false);
  const [currentTime, setCurrentTime] = useState<number | null>(null);
  const [duration, setDuration] = useState<number | null>(null);
  const video = useRef<HTMLVideoElement>(null);

  // Follow a running inspection. The socket gives live alerts; polling covers
  // events sent before it connected and a socket that never connects.
  useEffect(() => {
    if (!id || phase !== "running") return;
    let finished = false;
    const finish = async () => {
      if (finished) return;
      const inspection = await getInspection(id);
      if (inspection.status === "COMPLETED") {
        finished = true;
        setResult(inspection);
        setPhase("done");
      } else if (inspection.status === "FAILED") {
        finished = true;
        setError(inspection.error_message ?? "Inspection failed.");
        setPhase("failed");
      }
    };
    const close = watchInspection(id, {
      progress: setProgress,
      alert: (event) => setLive((seen) => [...seen, ...event.detections]),
      done: finish,
      error: () => {},
    });
    const poll = setInterval(() => finish().catch(() => {}), 2000);
    return () => {
      close();
      clearInterval(poll);
    };
  }, [id, phase]);

  // The saved detections are complete; the live list can miss the first frames.
  const events = useMemo(() => groupDefectEvents(result ? result.defects : live), [result, live]);

  const heard = useRef(0);
  useEffect(() => {
    if (sound && phase === "running" && events.length > heard.current) beep();
    heard.current = events.length;
  }, [events.length, sound, phase]);

  async function start() {
    if (!file) return;
    setError(null);
    setPhase("uploading");
    try {
      const inspection = await uploadVideo(file, conf);
      setLive([]);
      setProgress(null);
      setResult(null);
      setId(inspection.id);
      setPhase("running");
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      setError(message === "Failed to fetch" ? `Can't reach the inspection backend at ${API_URL}. Is it running?` : message);
      setPhase("failed");
    }
  }

  function reset() {
    setPhase("idle");
    setId(null);
    setResult(null);
    setLive([]);
    setProgress(null);
    setError(null);
    setCurrentTime(null);
    setDuration(null);
  }

  function seek(seconds: number) {
    if (!video.current) return;
    video.current.currentTime = seconds;
    video.current.pause();
  }

  // ------------------------------------------------------------ upload form
  if (phase === "idle" || phase === "uploading" || (phase === "failed" && !id)) {
    return (
      <div className="card card-lift inspect-form">
        <UploadDropzone file={file} onFile={setFile} />
        <div className="inspect-controls">
          <label className="slider">
            <span>
              Confidence threshold <b className="n">{fmt(conf, 2)}</b>
            </span>
            <input type="range" min={0.05} max={0.9} step={0.05} value={conf} onChange={(e) => setConf(Number(e.target.value))} />
          </label>
          <button type="button" className="btn" disabled={!file || phase === "uploading"} onClick={start}>
            {phase === "uploading" ? "Uploading…" : "Run inspection"}
          </button>
        </div>
        <p className="caption">
          Runs {modelLabel} on every second frame. Boxes below the threshold are dropped; 0.25 is the threshold the
          evaluation used.
        </p>
        {error && (
          <div className="banner banner-bad">
            <div>
              <h3>Upload failed</h3>
              <p>{error}</p>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ------------------------------------------------------- run and result
  const total = result?.total_frames ?? progress?.total_frames ?? 0;
  const perClass = Object.entries(
    events.reduce<Record<string, number>>((acc, e) => ({ ...acc, [e.class_name]: (acc[e.class_name] ?? 0) + 1 }), {}),
  ).sort((a, b) => b[1] - a[1]);
  const decision = result ? DECISION[result.quality_decision] : null;
  const reasons = result?.decision_reason?.split(" | ") ?? [];

  return (
    <div className="stack inspect-run">
      <AlertBanner events={events} running={phase === "running"} sound={sound} onSound={setSound} />

      <div className="detail-grid">
        <div className="stack">
          {phase === "done" && result?.annotated_url ? (
            <video
              ref={video}
              className="player"
              src={mediaUrl(result.annotated_url)}
              controls
              playsInline
              onLoadedMetadata={(e) => setDuration(e.currentTarget.duration)}
              onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
            />
          ) : (
            <div className="player player-wait">
              {phase === "failed" ? (
                <p>{error}</p>
              ) : (
                <>
                  <span className="label">Running the model</span>
                  <b className="split-number">
                    {Math.round(progress?.progress_percent ?? 0)}
                    <small>%</small>
                  </b>
                  <div className="bar-track">
                    <div className="bar-fill" style={{ width: `${progress?.progress_percent ?? 0}%` }} />
                  </div>
                  <p className="n n-faint">
                    {progress ? `frame ${progress.frame_index} / ${progress.total_frames} · ${progress.fps} fps` : "starting…"}
                  </p>
                </>
              )}
            </div>
          )}

          <DefectTimeline
            events={events}
            totalFrames={total}
            currentTime={currentTime}
            duration={duration}
            onSeek={phase === "done" ? seek : null}
          />
        </div>

        <aside className="aside">
          <div className="aside-card">
            <span className={`label ${decision?.className ?? ""}`}>{decision?.label ?? "Inspecting"}</span>
            <h3 style={{ marginTop: "0.6rem" }}>{file?.name}</h3>
            {reasons.length > 0 && (
              <p>
                {reasons[0]}
                {reasons.length > 1 && ` (+${reasons.length - 1} more)`}
              </p>
            )}
            <dl className="kv kv-2">
              <div>
                <dt>Defect events</dt>
                <dd>{events.length}</dd>
              </div>
              <div>
                <dt>Frames</dt>
                <dd>{total || "–"}</dd>
              </div>
            </dl>
          </div>

          {perClass.length > 0 && (
            <div className="aside-card">
              <h3>By class</h3>
              <ul className="class-counts">
                {perClass.map(([name, count]) => (
                  <li key={name}>
                    <span className="swatch" style={{ background: CLASS_COLOR[name] ?? "var(--danger)" }} />
                    {className(name)}
                    <span className="n">{count}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="inspect-actions">
            {phase === "done" && result?.annotated_url && (
              <a className="btn" href={mediaUrl(result.annotated_url)} target="_blank" rel="noreferrer">
                Open annotated video
              </a>
            )}
            {phase !== "running" && (
              <button type="button" className="btn btn-ghost" onClick={reset}>
                Inspect another video
              </button>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
