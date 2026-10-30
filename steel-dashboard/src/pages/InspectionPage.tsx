import { useState, useRef, useEffect, useCallback } from 'react';
import {
  Upload, Play, Pause, Film, Image, AlertTriangle, CheckCircle2,
  Zap, Target, Clock, RefreshCw, Camera,
} from 'lucide-react';
import {
  BarChart, Bar, Cell, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
} from 'recharts';

import { runInference, CLASS_SUMMARY, TOTAL_VIDEO_DETECTIONS, TOTAL_VIDEO_ALERTS } from '../data';
import { SectionHeader, Badge, ProgressBar, LoadingSpinner, DefectPill } from '../components/UI';
import type { InspectionSettings } from '../types';
import { DEFECT_COLORS, DEFECT_LABELS, DEFECT_CLASSES } from '../types';

// ─── Types ────────────────────────────────────────────────────────────────────

interface DetectionResult {
  class_name: string;
  confidence: number;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

interface InferenceResult {
  detections: DetectionResult[];
  processing_time_ms: number;
  image_size: [number, number];
}

interface FeedItem {
  id: string;
  timestamp: string;
  class_name: string;
  confidence: number;
  alert: boolean;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const TOTAL_FRAMES = 3240; // 216 s × 15 fps

// Cumulative weight thresholds for weighted random class selection
const CLASS_WEIGHTS = (() => {
  const total = CLASS_SUMMARY.reduce((s, c) => s + c.detection_count, 0);
  let cum = 0;
  return CLASS_SUMMARY.map(c => {
    cum += c.detection_count / total;
    return { class_name: c.class_name, mean_confidence: c.mean_confidence, cum };
  });
})();

function pickWeightedClass() {
  const r = Math.random();
  for (const w of CLASS_WEIGHTS) {
    if (r <= w.cum) return w;
  }
  return CLASS_WEIGHTS[CLASS_WEIGHTS.length - 1];
}

function formatTime(d: Date) {
  return d.toLocaleTimeString('en-US', { hour12: false });
}

// ─── Custom Tooltip ───────────────────────────────────────────────────────────

function CustomBarTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: { class_name: string; detection_count: number; mean_confidence: number; alert_count: number } }> }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  const color = DEFECT_COLORS[d.class_name as keyof typeof DEFECT_COLORS] ?? '#8BA7C7';
  const label = DEFECT_LABELS[d.class_name as keyof typeof DEFECT_LABELS] ?? d.class_name;
  return (
    <div className="bg-charcoal-800 border border-charcoal-600 rounded-lg p-3 text-xs shadow-xl">
      <p className="font-semibold mb-1" style={{ color }}>{label}</p>
      <p className="text-steel-300">Detections: <span className="text-white font-mono">{d.detection_count.toLocaleString()}</span></p>
      <p className="text-steel-300">Alerts: <span className="text-danger font-mono">{d.alert_count}</span></p>
      <p className="text-steel-300">Mean Conf: <span className="text-accent font-mono">{(d.mean_confidence * 100).toFixed(1)}%</span></p>
    </div>
  );
}

// ─── Component ────────────────────────────────────────────────────────────────

interface Props {
  settings: InspectionSettings;
}

export default function InspectionPage({ settings }: Props) {
  // ── State ──────────────────────────────────────────────────────────────────
  const [activeTab, setActiveTab] = useState<'upload' | 'demo'>('demo');
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [fileType, setFileType] = useState<'image' | 'video' | null>(null);
  const [detecting, setDetecting] = useState(false);
  const [detectionResult, setDetectionResult] = useState<InferenceResult | null>(null);
  const [detectError, setDetectError] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [videoDuration, setVideoDuration] = useState(0);
  const [videoCurrentTime, setVideoCurrentTime] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const [feedItems, setFeedItems] = useState<FeedItem[]>([]);

  // ── Refs ───────────────────────────────────────────────────────────────────
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const previewImgRef = useRef<HTMLImageElement>(null);
  const feedRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── Live feed simulation ───────────────────────────────────────────────────
  useEffect(() => {
    const id = setInterval(() => {
      const cls = pickWeightedClass();
      const conf = Math.max(0.15, Math.min(0.99,
        cls.mean_confidence + (Math.random() - 0.5) * 0.35
      ));
      const alert = conf >= settings.alertConfidenceThreshold;
      const item: FeedItem = {
        id: `feed-${Date.now()}-${Math.random()}`,
        timestamp: formatTime(new Date()),
        class_name: cls.class_name,
        confidence: conf,
        alert,
      };
      setFeedItems(prev => [...prev.slice(-99), item]);
    }, 2000);
    return () => clearInterval(id);
  }, [settings.alertConfidenceThreshold]);

  // Auto-scroll feed to bottom
  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [feedItems]);

  // ── Draw bounding boxes on canvas ─────────────────────────────────────────
  const drawBoxes = useCallback(() => {
    const canvas = canvasRef.current;
    const img = previewImgRef.current;
    if (!canvas || !img || !detectionResult) return;

    const { naturalWidth, naturalHeight } = img;
    const { width: dispW, height: dispH } = img.getBoundingClientRect();

    canvas.width = dispW;
    canvas.height = dispH;

    const scaleX = dispW / (detectionResult.image_size[0] || naturalWidth || 200);
    const scaleY = dispH / (detectionResult.image_size[1] || naturalHeight || 200);

    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.clearRect(0, 0, dispW, dispH);

    for (const det of detectionResult.detections) {
      const color = DEFECT_COLORS[det.class_name as keyof typeof DEFECT_COLORS] ?? '#8BA7C7';
      const x = det.x1 * scaleX;
      const y = det.y1 * scaleY;
      const w = (det.x2 - det.x1) * scaleX;
      const h = (det.y2 - det.y1) * scaleY;

      // Box
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.strokeRect(x, y, w, h);

      // Label background
      const label = `${DEFECT_LABELS[det.class_name as keyof typeof DEFECT_LABELS] ?? det.class_name} ${(det.confidence * 100).toFixed(0)}%`;
      ctx.font = 'bold 11px monospace';
      const tw = ctx.measureText(label).width;
      const lh = 16;
      ctx.fillStyle = color + 'CC';
      ctx.fillRect(x, y - lh - 2, tw + 8, lh + 2);

      // Label text
      ctx.fillStyle = '#fff';
      ctx.fillText(label, x + 4, y - 4);
    }
  }, [detectionResult]);

  useEffect(() => {
    if (detectionResult && fileType === 'image') {
      // Wait for image to render
      const t = setTimeout(drawBoxes, 100);
      return () => clearTimeout(t);
    }
  }, [detectionResult, fileType, drawBoxes]);

  // ── File handling ──────────────────────────────────────────────────────────
  const handleFile = (file: File) => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setDetectionResult(null);
    setDetectError(null);
    setUploadedFile(file);
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    setFileType(file.type.startsWith('video') ? 'video' : 'image');
  };

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  };

  // ── Run Detection ──────────────────────────────────────────────────────────
  const runDetection = async () => {
    if (!uploadedFile) return;
    setDetecting(true);
    setDetectError(null);
    setDetectionResult(null);
    try {
      const result = await runInference(uploadedFile);
      setDetectionResult(result);
    } catch (err: unknown) {
      setDetectError(err instanceof Error ? err.message : 'Detection failed');
    } finally {
      setDetecting(false);
    }
  };

  // ── Video controls ─────────────────────────────────────────────────────────
  const togglePlay = () => {
    const v = videoRef.current;
    if (!v) return;
    if (v.paused) { v.play(); setIsPlaying(true); }
    else { v.pause(); setIsPlaying(false); }
  };

  const onVideoTimeUpdate = () => {
    if (videoRef.current) setVideoCurrentTime(videoRef.current.currentTime);
  };

  const onVideoLoaded = () => {
    if (videoRef.current) setVideoDuration(videoRef.current.duration);
  };

  const onSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = videoRef.current;
    if (!v) return;
    v.currentTime = Number(e.target.value);
    setVideoCurrentTime(v.currentTime);
  };

  const fmtSec = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, '0')}`;
  };

  // ── Bar chart data ─────────────────────────────────────────────────────────
  const chartData = CLASS_SUMMARY.map(c => ({
    class_name: c.class_name,
    name: (DEFECT_LABELS[c.class_name as keyof typeof DEFECT_LABELS] ?? c.class_name).replace('Rolled-in Scale', 'Rolled Scale'),
    detection_count: c.detection_count,
    mean_confidence: c.mean_confidence,
    alert_count: c.alert_count,
  }));

  // ── Upload results summary ─────────────────────────────────────────────────
  const alertDetections = detectionResult?.detections.filter(
    d => d.confidence >= settings.alertConfidenceThreshold
  ) ?? [];

  // ─── Render ──────────────────────────────────────────────────────────────
  return (
    <div className="space-y-6">

      {/* ── Page Header ──────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Camera size={20} className="text-accent" />
            Live AI Inspection
          </h1>
          <p className="text-xs text-steel-400 mt-0.5">
            Real-time defect detection · YOLOv8 model · conf ≥ {settings.confidenceThreshold}
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-steel-400 border border-charcoal-600 rounded-lg px-3 py-1.5 bg-charcoal-800">
          <span className="w-2 h-2 rounded-full bg-success animate-pulse" />
          Model Active
        </div>
      </div>

      {/* ── SECTION 1: Mode Tabs ─────────────────────────────────────────── */}
      <div className="card p-0 overflow-hidden">
        <div className="flex border-b border-charcoal-700">
          {(['upload', 'demo'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`flex-1 flex items-center justify-center gap-2 py-3.5 text-sm font-medium transition-colors ${
                activeTab === tab
                  ? 'bg-charcoal-700 text-accent border-b-2 border-accent -mb-px'
                  : 'text-steel-400 hover:text-white hover:bg-charcoal-800'
              }`}
            >
              {tab === 'upload' ? <Image size={15} /> : <Film size={15} />}
              {tab === 'upload' ? 'Upload Image / Video' : 'Demo Video'}
            </button>
          ))}
        </div>

        {/* ── SECTION 2A: Upload Mode ──────────────────────────────────── */}
        {activeTab === 'upload' && (
          <div className="p-5 space-y-5">

            {/* Drag-and-drop zone */}
            {!uploadedFile && (
              <div
                className={`relative border-2 border-dashed rounded-xl flex flex-col items-center justify-center gap-3 py-14 cursor-pointer transition-colors ${
                  isDragging
                    ? 'border-accent bg-accent/5'
                    : 'border-charcoal-600 hover:border-accent/60 hover:bg-charcoal-800/40'
                }`}
                onDragOver={e => { e.preventDefault(); setIsDragging(true); }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={onDrop}
                onClick={() => fileInputRef.current?.click()}
              >
                <div className="w-14 h-14 rounded-2xl bg-charcoal-700 flex items-center justify-center">
                  <Upload size={24} className="text-accent" />
                </div>
                <div className="text-center">
                  <p className="text-white font-medium">Drop image or video here</p>
                  <p className="text-steel-400 text-sm mt-1">or click to browse · JPG, PNG, MP4, AVI</p>
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*,video/*"
                  className="hidden"
                  onChange={onFileChange}
                />
              </div>
            )}

            {/* Preview + controls */}
            {uploadedFile && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <p className="text-sm text-white font-medium flex items-center gap-2">
                    {fileType === 'video' ? <Film size={14} className="text-accent" /> : <Image size={14} className="text-accent" />}
                    {uploadedFile.name}
                  </p>
                  <button
                    onClick={() => {
                      setUploadedFile(null);
                      setPreviewUrl(null);
                      setDetectionResult(null);
                      setDetectError(null);
                      if (fileInputRef.current) fileInputRef.current.value = '';
                    }}
                    className="text-xs text-steel-400 hover:text-white flex items-center gap-1"
                  >
                    <RefreshCw size={12} /> Clear
                  </button>
                </div>

                {/* Image preview with canvas overlay */}
                {fileType === 'image' && previewUrl && (
                  <div className="relative inline-block w-full max-w-xl mx-auto">
                    <img
                      ref={previewImgRef}
                      src={previewUrl}
                      alt="Preview"
                      className="w-full rounded-lg border border-charcoal-600 block"
                      onLoad={drawBoxes}
                    />
                    <canvas
                      ref={canvasRef}
                      className="absolute inset-0 w-full h-full pointer-events-none rounded-lg"
                    />
                  </div>
                )}

                {/* Video preview */}
                {fileType === 'video' && previewUrl && (
                  <video
                    src={previewUrl}
                    controls
                    className="w-full max-w-xl mx-auto rounded-lg border border-charcoal-600 block"
                  />
                )}

                {/* Run detection */}
                <div className="flex items-center gap-3">
                  <button
                    onClick={runDetection}
                    disabled={detecting}
                    className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-accent text-charcoal-900 font-semibold text-sm hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    {detecting ? (
                      <><LoadingSpinner size={16} /> Processing…</>
                    ) : (
                      <><Zap size={15} /> Run Detection</>
                    )}
                  </button>
                  {detectionResult && !detecting && (
                    <span className="text-xs text-steel-400 flex items-center gap-1">
                      <Clock size={12} />
                      {detectionResult.processing_time_ms} ms
                    </span>
                  )}
                </div>

                {/* Error */}
                {detectError && (
                  <div className="text-danger text-sm flex items-center gap-2 p-3 bg-danger/10 border border-danger/30 rounded-lg">
                    <AlertTriangle size={14} /> {detectError}
                  </div>
                )}

                {/* Detection results */}
                {detectionResult && !detecting && (
                  <div className="card p-4 border-charcoal-600 space-y-4">
                    <div className="flex items-center gap-4 flex-wrap">
                      <div className="flex items-center gap-2">
                        <Target size={15} className="text-accent" />
                        <span className="text-sm text-white font-semibold">
                          {detectionResult.detections.length} detection{detectionResult.detections.length !== 1 ? 's' : ''}
                        </span>
                      </div>
                      {alertDetections.length > 0 ? (
                        <Badge variant="danger">
                          <AlertTriangle size={10} className="mr-1" />
                          {alertDetections.length} alert
                        </Badge>
                      ) : (
                        <Badge variant="success">
                          <CheckCircle2 size={10} className="mr-1" />
                          No alerts
                        </Badge>
                      )}
                      <span className="text-xs text-steel-400 ml-auto">
                        {detectionResult.image_size[0]}×{detectionResult.image_size[1]} px
                      </span>
                    </div>

                    {detectionResult.detections.length === 0 ? (
                      <p className="text-sm text-steel-400 flex items-center gap-2">
                        <CheckCircle2 size={14} className="text-success" /> No defects detected above threshold.
                      </p>
                    ) : (
                      <div className="space-y-2">
                        {detectionResult.detections.map((det, i) => {
                          const color = DEFECT_COLORS[det.class_name as keyof typeof DEFECT_COLORS] ?? '#8BA7C7';
                          const label = DEFECT_LABELS[det.class_name as keyof typeof DEFECT_LABELS] ?? det.class_name;
                          const isAlert = det.confidence >= settings.alertConfidenceThreshold;
                          return (
                            <div key={i} className="flex items-center gap-3 bg-charcoal-800 rounded-lg px-3 py-2">
                              <DefectPill name={label} color={color} size="sm" />
                              <div className="flex-1 min-w-0">
                                <ProgressBar
                                  value={det.confidence * 100}
                                  max={100}
                                  color={color}
                                  showPct
                                />
                              </div>
                              {isAlert && <Badge variant="danger">ALERT</Badge>}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ── SECTION 2B: Demo Video Mode ──────────────────────────────── */}
        {activeTab === 'demo' && (
          <div className="p-5 space-y-5">
            <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">

              {/* Video player */}
              <div className="lg:col-span-3 space-y-3">
                <div className="relative bg-black rounded-xl overflow-hidden border border-charcoal-600">
                  <video
                    ref={videoRef}
                    src="/videos/ps7_continuous_inspection_annotated.mp4"
                    className="w-full block"
                    onTimeUpdate={onVideoTimeUpdate}
                    onLoadedMetadata={onVideoLoaded}
                    onEnded={() => setIsPlaying(false)}
                    playsInline
                  />
                  {/* Overlay badge */}
                  <div className="absolute top-3 left-3 flex items-center gap-1.5 bg-black/70 backdrop-blur-sm text-xs text-white px-2 py-1 rounded-full">
                    <span className={`w-2 h-2 rounded-full ${isPlaying ? 'bg-danger animate-pulse' : 'bg-steel-500'}`} />
                    {isPlaying ? 'LIVE' : 'PAUSED'}
                  </div>
                </div>

                {/* Controls */}
                <div className="flex items-center gap-3">
                  <button
                    onClick={togglePlay}
                    className="w-9 h-9 rounded-lg bg-accent flex items-center justify-center text-charcoal-900 hover:bg-accent/90 transition-colors flex-shrink-0"
                  >
                    {isPlaying ? <Pause size={16} /> : <Play size={16} />}
                  </button>
                  <span className="text-xs text-steel-400 font-mono w-20 flex-shrink-0">
                    {fmtSec(videoCurrentTime)} / {fmtSec(videoDuration)}
                  </span>
                  <input
                    type="range"
                    min={0}
                    max={videoDuration || 100}
                    step={0.1}
                    value={videoCurrentTime}
                    onChange={onSeek}
                    className="flex-1 accent-accent h-1.5 rounded-full cursor-pointer"
                  />
                </div>
              </div>

              {/* Stats panel */}
              <div className="lg:col-span-2 space-y-3">
                <p className="text-xs font-semibold text-steel-400 uppercase tracking-wider">Video Analysis Stats</p>

                {/* Summary cards */}
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { label: 'Frames Analyzed', value: TOTAL_FRAMES.toLocaleString(), icon: <Film size={13} />, color: 'text-accent' },
                    { label: 'Total Detections', value: TOTAL_VIDEO_DETECTIONS.toLocaleString(), icon: <Target size={13} />, color: 'text-accent' },
                    { label: 'Alert Detections', value: TOTAL_VIDEO_ALERTS.toLocaleString(), icon: <AlertTriangle size={13} />, color: 'text-danger' },
                    { label: 'Alert Rate', value: `${((TOTAL_VIDEO_ALERTS / TOTAL_VIDEO_DETECTIONS) * 100).toFixed(1)}%`, icon: <Zap size={13} />, color: 'text-warning' },
                  ].map(stat => (
                    <div key={stat.label} className="bg-charcoal-800 border border-charcoal-700 rounded-lg p-3">
                      <div className={`flex items-center gap-1 mb-1 ${stat.color}`}>
                        {stat.icon}
                        <span className="text-[10px] font-medium uppercase tracking-wide text-steel-400">{stat.label}</span>
                      </div>
                      <p className={`text-lg font-bold font-mono ${stat.color}`}>{stat.value}</p>
                    </div>
                  ))}
                </div>

                {/* Per-class breakdown */}
                <div className="bg-charcoal-800 border border-charcoal-700 rounded-lg p-3 space-y-2.5">
                  <p className="text-xs font-semibold text-steel-400 uppercase tracking-wider">Per-Class Detections</p>
                  {CLASS_SUMMARY.map(c => {
                    const color = DEFECT_COLORS[c.class_name as keyof typeof DEFECT_COLORS] ?? '#8BA7C7';
                    const label = DEFECT_LABELS[c.class_name as keyof typeof DEFECT_LABELS] ?? c.class_name;
                    const pct = (c.detection_count / TOTAL_VIDEO_DETECTIONS) * 100;
                    return (
                      <div key={c.class_name} className="space-y-1">
                        <div className="flex items-center justify-between text-xs">
                          <DefectPill name={label} color={color} size="sm" />
                          <span className="font-mono text-white">{c.detection_count.toLocaleString()}</span>
                        </div>
                        <ProgressBar value={pct} max={100} color={color} showPct={false} />
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── SECTION 3 + 4: Feed and Chart ──────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">

        {/* ── SECTION 3: Live Detection Feed ─────────────────────────────── */}
        <div className="card p-5 flex flex-col" style={{ minHeight: 420 }}>
          <SectionHeader
            title="Live Detection Feed"
            subtitle="Simulated real-time detections weighted by class distribution"
            actions={
              <button
                onClick={() => setFeedItems([])}
                className="flex items-center gap-1.5 text-xs text-steel-400 hover:text-white border border-charcoal-600 rounded-lg px-3 py-1.5 hover:border-charcoal-500 transition-colors"
              >
                <RefreshCw size={12} /> Clear
              </button>
            }
          />

          {/* Feed entries */}
          <div
            ref={feedRef}
            className="flex-1 overflow-y-auto space-y-1.5 pr-1 scrollbar-thin scrollbar-track-charcoal-900 scrollbar-thumb-charcoal-600"
            style={{ maxHeight: 340 }}
          >
            {feedItems.length === 0 && (
              <div className="flex flex-col items-center justify-center h-32 text-steel-500 text-sm gap-2">
                <Zap size={20} className="opacity-40" />
                Awaiting detections…
              </div>
            )}
            {feedItems.map(item => {
              const color = DEFECT_COLORS[item.class_name as keyof typeof DEFECT_COLORS] ?? '#8BA7C7';
              const label = DEFECT_LABELS[item.class_name as keyof typeof DEFECT_LABELS] ?? item.class_name;
              return (
                <div
                  key={item.id}
                  className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-charcoal-800 border border-charcoal-700 hover:border-charcoal-600 transition-colors group"
                >
                  <span className="text-[10px] font-mono text-steel-500 w-16 flex-shrink-0">
                    {item.timestamp}
                  </span>
                  <DefectPill name={label} color={color} size="sm" />
                  <div className="flex-1 min-w-0">
                    <div className="h-1 rounded-full bg-charcoal-700 overflow-hidden">
                      <div
                        className="h-full rounded-full"
                        style={{ width: `${item.confidence * 100}%`, backgroundColor: color }}
                      />
                    </div>
                  </div>
                  <span className="text-[10px] font-mono text-steel-400 w-10 text-right flex-shrink-0">
                    {(item.confidence * 100).toFixed(0)}%
                  </span>
                  {item.alert ? (
                    <Badge variant="danger">⚠</Badge>
                  ) : (
                    <Badge variant="neutral">OK</Badge>
                  )}
                </div>
              );
            })}
          </div>

          {/* Feed footer */}
          <div className="mt-3 pt-3 border-t border-charcoal-700 flex items-center justify-between text-xs text-steel-500">
            <span>{feedItems.length} events logged</span>
            <span className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
              Updating every 2s
            </span>
          </div>
        </div>

        {/* ── SECTION 4: Detection Stats Chart ──────────────────────────── */}
        <div className="card p-5 flex flex-col" style={{ minHeight: 420 }}>
          <SectionHeader
            title="Detection Distribution"
            subtitle={`${TOTAL_VIDEO_DETECTIONS.toLocaleString()} total detections across ${TOTAL_FRAMES.toLocaleString()} frames`}
          />

          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={chartData} margin={{ top: 4, right: 8, left: -10, bottom: 40 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a3441" vertical={false} />
              <XAxis
                dataKey="name"
                tick={{ fill: '#8BA7C7', fontSize: 10 }}
                angle={-35}
                textAnchor="end"
                interval={0}
                tickLine={false}
                axisLine={{ stroke: '#2a3441' }}
              />
              <YAxis tick={{ fill: '#8BA7C7', fontSize: 10 }} tickLine={false} axisLine={false} />
              <Tooltip content={<CustomBarTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
              <Bar dataKey="detection_count" radius={[3, 3, 0, 0]} maxBarSize={48}>
                {chartData.map(entry => (
                  <Cell
                    key={entry.class_name}
                    fill={DEFECT_COLORS[entry.class_name as keyof typeof DEFECT_COLORS] ?? '#8BA7C7'}
                    fillOpacity={0.85}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>

          {/* Mean confidence per class */}
          <div className="mt-4 space-y-2">
            <p className="text-xs font-semibold text-steel-400 uppercase tracking-wider">Mean Confidence per Class</p>
            {CLASS_SUMMARY.map(c => {
              const color = DEFECT_COLORS[c.class_name as keyof typeof DEFECT_COLORS] ?? '#8BA7C7';
              const label = DEFECT_LABELS[c.class_name as keyof typeof DEFECT_LABELS] ?? c.class_name;
              return (
                <div key={c.class_name} className="flex items-center gap-2 text-xs">
                  <span className="w-28 text-steel-400 truncate flex-shrink-0">{label}</span>
                  <div className="flex-1">
                    <ProgressBar
                      value={c.mean_confidence * 100}
                      max={100}
                      color={color}
                      showPct
                    />
                  </div>
                  {c.alert_count > 0 && (
                    <span className="text-danger font-mono text-[10px] flex-shrink-0">
                      {c.alert_count} ⚠
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* ── Quick class reference ───────────────────────────────────────────── */}
      <div className="card p-5">
        <SectionHeader
          title="Defect Class Reference"
          subtitle="All 6 defect classes detected by the YOLOv8 model"
        />
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {DEFECT_CLASSES.map(cls => {
            const color = DEFECT_COLORS[cls];
            const label = DEFECT_LABELS[cls];
            const summary = CLASS_SUMMARY.find(c => c.class_name === cls);
            const enabled = settings.enabledClasses.includes(cls);
            return (
              <div
                key={cls}
                className={`rounded-xl p-3 border transition-opacity ${enabled ? 'opacity-100' : 'opacity-40'}`}
                style={{ borderColor: color + '30', backgroundColor: color + '08' }}
              >
                <div className="flex items-center gap-1.5 mb-2">
                  <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
                  <span className="text-xs font-semibold text-white leading-tight">{label}</span>
                </div>
                {summary && (
                  <div className="space-y-0.5">
                    <p className="text-[10px] text-steel-400">
                      <span className="text-white font-mono">{summary.detection_count.toLocaleString()}</span> dets
                    </p>
                    <p className="text-[10px] text-steel-400">
                      Conf <span className="font-mono" style={{ color }}>{(summary.mean_confidence * 100).toFixed(1)}%</span>
                    </p>
                    <p className="text-[10px] text-danger">
                      {summary.alert_count} alerts
                    </p>
                  </div>
                )}
                {!enabled && (
                  <p className="text-[10px] text-steel-500 mt-1 italic">Disabled</p>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
