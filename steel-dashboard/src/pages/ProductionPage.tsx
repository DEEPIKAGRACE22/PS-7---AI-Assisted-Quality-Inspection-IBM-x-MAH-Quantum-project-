import { useState, useEffect, useRef } from 'react';
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell,
} from 'recharts';
import {
  Activity, Gauge, AlertTriangle, CheckCircle2, XCircle, Clock,
  Play, Pause, ChevronRight,
} from 'lucide-react';
import { getProductionLines, getTrendData } from '../data';
import { StatCard, SectionHeader, Badge, ProgressBar } from '../components/UI';
import type { InspectionRecord, ProductionLine, LineStatus } from '../types';

// ─── Types ────────────────────────────────────────────────────────────────────

interface Props {
  records: InspectionRecord[];
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function statusBadgeVariant(s: LineStatus): 'success' | 'warning' | 'neutral' | 'danger' {
  if (s === 'running') return 'success';
  if (s === 'maintenance') return 'warning';
  if (s === 'alert') return 'danger';
  return 'neutral';
}

function statusLabel(s: LineStatus) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function StatusDot({ status }: { status: LineStatus }) {
  const base = 'relative inline-flex w-2.5 h-2.5 rounded-full flex-shrink-0';
  if (status === 'running') {
    return (
      <span className={`${base} bg-success`}>
        <span className="absolute inset-0 rounded-full bg-success animate-ping opacity-75" />
      </span>
    );
  }
  if (status === 'maintenance') return <span className={`${base} bg-warning`} />;
  if (status === 'alert') return <span className={`${base} bg-danger animate-pulse`} />;
  return <span className={`${base} bg-steel-400`} />;
}

// ─── Mini Ratio Bar ────────────────────────────────────────────────────────────

function MiniRatioBar({ approved, rejected }: { approved: number; rejected: number }) {
  const total = approved + rejected || 1;
  const approvedPct = (approved / total) * 100;
  return (
    <div className="flex gap-0.5 h-2 rounded-full overflow-hidden w-full">
      <div className="h-full rounded-l-full bg-success/70 transition-all" style={{ width: `${approvedPct}%` }} />
      <div className="h-full rounded-r-full bg-danger/60 flex-1" />
    </div>
  );
}

// ─── Line Card ────────────────────────────────────────────────────────────────

function LineCard({ line }: { line: ProductionLine }) {
  const total = line.approved + line.rejected || 1;
  const approvedPct = Math.round((line.approved / total) * 100);
  const ratioData = [
    { name: 'Approved', value: line.approved, fill: '#22C55E' },
    { name: 'Rejected', value: line.rejected, fill: '#EF4444' },
  ];
  return (
    <div className="card p-5 flex flex-col gap-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <StatusDot status={line.status} />
          <span className="font-semibold text-white text-sm">{line.name}</span>
        </div>
        <Badge variant={statusBadgeVariant(line.status)}>{statusLabel(line.status)}</Badge>
      </div>

      {/* Metrics row */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
        <div>
          <div className="text-steel-400 uppercase tracking-wide">Throughput</div>
          <div className="font-mono text-accent font-semibold">{line.throughput} <span className="text-steel-400 font-normal">sheets/hr</span></div>
        </div>
        <div>
          <div className="text-steel-400 uppercase tracking-wide">Speed</div>
          <div className="font-mono text-white font-semibold">
            {line.status === 'maintenance' ? '—' : `${line.speed} m/min`}
          </div>
        </div>
        <div>
          <div className="text-steel-400 uppercase tracking-wide">Approved</div>
          <div className="font-mono text-success font-semibold">{line.approved.toLocaleString()}</div>
        </div>
        <div>
          <div className="text-steel-400 uppercase tracking-wide">Rejected</div>
          <div className="font-mono text-danger font-semibold">{line.rejected.toLocaleString()}</div>
        </div>
      </div>

      {/* Uptime */}
      {line.status !== 'maintenance' ? (
        <ProgressBar value={line.uptime} max={100} color="#00D4FF" label="Uptime" />
      ) : (
        <div className="text-xs text-warning flex items-center gap-1.5">
          <AlertTriangle size={12} /> Under scheduled maintenance
        </div>
      )}

      {/* Mini ratio bar */}
      <div>
        <div className="flex justify-between text-[10px] text-steel-400 mb-1">
          <span>Approved {approvedPct}%</span>
          <span>Rejected {100 - approvedPct}%</span>
        </div>
        <div className="h-20">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={ratioData} barCategoryGap="20%">
              <XAxis dataKey="name" tick={{ fontSize: 9, fill: '#8BA7C7' }} axisLine={false} tickLine={false} />
              <YAxis hide />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {ratioData.map((entry, i) => <Cell key={i} fill={entry.fill} fillOpacity={0.8} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <MiniRatioBar approved={line.approved} rejected={line.rejected} />
      </div>
    </div>
  );
}

// ─── Conveyor Simulation ──────────────────────────────────────────────────────

const DEFECT_COLORS_SIM = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFEAA7', '#DDA0DD'];
const DEFECT_NAMES_SIM = ['Crazing', 'Inclusion', 'Patches', 'Scale', 'Scratch'];

interface Sheet {
  id: number;
  x: number;
  defectIdx: number | null; // null = pass
  color: string;
}

function seededRng(seed: number) {
  const x = Math.sin(seed + 1) * 10000;
  return x - Math.floor(x);
}

function generateSheets(): Sheet[] {
  return Array.from({ length: 7 }, (_, i) => ({
    id: i,
    x: i * 160 - 80,
    defectIdx: seededRng(i * 31) < 0.38 ? Math.floor(seededRng(i * 31 + 5) * DEFECT_NAMES_SIM.length) : null,
    color: `hsl(${200 + i * 10}, 30%, ${25 + i * 2}%)`,
  }));
}

function ConveyorSimulation() {
  const [running, setRunning] = useState(true);
  const [sheets, setSheets] = useState<Sheet[]>(generateSheets);
  const [scanX, setScanX] = useState(50); // percent
  const [scanDir, setScanDir] = useState(1);
  const frameRef = useRef<number | null>(null);
  const lastRef = useRef<number>(0);
  const sheetCountRef = useRef(7);

  useEffect(() => {
    if (!running) {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
      return;
    }
    const animate = (ts: number) => {
      const dt = ts - lastRef.current;
      lastRef.current = ts;
      const speed = 0.04; // px per ms
      setScanX(prev => {
        let next = prev + scanDir * 0.08;
        if (next >= 95) { setScanDir(-1); next = 95; }
        if (next <= 5)  { setScanDir(1);  next = 5; }
        return next;
      });
      setSheets(prev =>
        prev.map(s => {
          let nx = s.x + speed * dt;
          if (nx > 1200) {
            const newId = ++sheetCountRef.current;
            return {
              id: newId,
              x: -80,
              defectIdx: seededRng(newId * 31) < 0.38 ? Math.floor(seededRng(newId * 31 + 5) * DEFECT_NAMES_SIM.length) : null,
              color: `hsl(${200 + (newId % 6) * 10}, 30%, ${25 + (newId % 5) * 2}%)`,
            };
          }
          return { ...s, x: nx };
        })
      );
      frameRef.current = requestAnimationFrame(animate);
    };
    frameRef.current = requestAnimationFrame(animate);
    return () => { if (frameRef.current) cancelAnimationFrame(frameRef.current); };
  }, [running, scanDir]);

  const throughput = 18;
  const defectRate = 38;

  return (
    <div className="card p-5">
      <SectionHeader
        title="Conveyor Belt Simulation"
        subtitle="Live AI inspection simulation — defects flagged in real-time"
        actions={
          <button
            onClick={() => setRunning(r => !r)}
            className={running ? 'btn-danger' : 'btn-primary'}
          >
            {running ? <><Pause size={14} /> Stop</> : <><Play size={14} /> Start</>}
          </button>
        }
      />

      {/* Belt wrapper */}
      <div className="relative rounded-xl overflow-hidden border border-charcoal-600" style={{ height: 140 }}>
        {/* Belt background */}
        <div className="absolute inset-0 conveyor-belt opacity-60" />
        {/* Dark overlay top/bottom rails */}
        <div className="absolute top-0 left-0 right-0 h-5 bg-charcoal-900/80" />
        <div className="absolute bottom-0 left-0 right-0 h-5 bg-charcoal-900/80" />

        {/* Steel sheets */}
        {sheets.map(sheet => (
          <div
            key={sheet.id}
            className="absolute top-1/2 -translate-y-1/2 rounded-md border border-steel-400/20 flex items-center justify-center text-[9px] font-bold overflow-hidden"
            style={{
              left: sheet.x,
              width: 120,
              height: 70,
              background: `linear-gradient(135deg, #1E2D45, #2A3F5F)`,
              boxShadow: '0 2px 8px rgba(0,0,0,0.4)',
            }}
          >
            {/* Metallic sheen */}
            <div className="absolute inset-0 opacity-10" style={{
              background: 'linear-gradient(45deg, rgba(255,255,255,0.3) 0%, transparent 60%)',
            }} />
            {sheet.defectIdx !== null ? (
              <div className="flex flex-col items-center gap-1 z-10">
                <div
                  className="w-4 h-4 rounded-full animate-pulse"
                  style={{ backgroundColor: DEFECT_COLORS_SIM[sheet.defectIdx] }}
                />
                <span style={{ color: DEFECT_COLORS_SIM[sheet.defectIdx], fontSize: 9 }}>
                  {DEFECT_NAMES_SIM[sheet.defectIdx]}
                </span>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-0.5 z-10">
                <CheckCircle2 size={14} className="text-success" />
                <span className="text-success" style={{ fontSize: 9 }}>PASS</span>
              </div>
            )}
          </div>
        ))}

        {/* Scanner vertical line */}
        <div
          className="absolute top-0 bottom-0 w-0.5 z-20 transition-none"
          style={{
            left: `${scanX}%`,
            background: 'linear-gradient(180deg, transparent, rgba(0,212,255,0.9), transparent)',
            boxShadow: '0 0 12px rgba(0,212,255,0.6)',
          }}
        >
          {/* Scanner head */}
          <div className="absolute -top-0 left-1/2 -translate-x-1/2 w-3 h-2 bg-accent rounded-b" />
          <div className="absolute -bottom-0 left-1/2 -translate-x-1/2 w-3 h-2 bg-accent rounded-t" />
        </div>

        {/* AI label */}
        <div className="absolute top-2 left-3 z-20 flex items-center gap-1.5">
          <div className={`w-2 h-2 rounded-full ${running ? 'bg-success animate-ping' : 'bg-steel-400'}`} />
          <span className="text-[10px] text-steel-400 font-medium">AI SCANNER</span>
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-4 mt-4">
        <div className="card p-3 text-center">
          <div className="text-accent text-lg font-bold font-mono">{throughput}</div>
          <div className="text-[10px] text-steel-400 uppercase tracking-wide">Sheets / hr</div>
        </div>
        <div className="card p-3 text-center">
          <div className="text-warning text-lg font-bold font-mono">{defectRate}%</div>
          <div className="text-[10px] text-steel-400 uppercase tracking-wide">Defect Rate</div>
        </div>
        <div className="card p-3 text-center">
          <div className={`text-lg font-bold font-mono ${running ? 'text-success' : 'text-steel-400'}`}>
            {running ? 'LIVE' : 'PAUSED'}
          </div>
          <div className="text-[10px] text-steel-400 uppercase tracking-wide">Sim Status</div>
        </div>
      </div>
    </div>
  );
}

// ─── Throughput Chart ──────────────────────────────────────────────────────────

function ThroughputChart({ records }: { records: InspectionRecord[] }) {
  const trend = getTrendData(records);
  return (
    <div className="card p-5">
      <SectionHeader
        title="Inspection Throughput Over Time"
        subtitle="Daily inspections, defect detections, and FPY rate"
      />
      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={trend} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
          <defs>
            <linearGradient id="gradTotal" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#00D4FF" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#00D4FF" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="gradDefects" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#FF6B6B" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#FF6B6B" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="gradFpy" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#22C55E" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#22C55E" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(139,167,199,0.08)" />
          <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#8BA7C7' }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 10, fill: '#8BA7C7' }} axisLine={false} tickLine={false} />
          <Tooltip
            contentStyle={{ background: '#131C2E', border: '1px solid rgba(0,212,255,0.2)', borderRadius: 8 }}
            labelStyle={{ color: '#C4D3E3' }}
          />
          <Area type="monotone" dataKey="total" stroke="#00D4FF" strokeWidth={2} fill="url(#gradTotal)" name="Total" />
          <Area type="monotone" dataKey="defects" stroke="#FF6B6B" strokeWidth={2} fill="url(#gradDefects)" name="With Defects" />
        </AreaChart>
      </ResponsiveContainer>
      <div className="flex gap-4 mt-2 flex-wrap">
        {[
          { color: '#00D4FF', label: 'Total Inspections' },
          { color: '#FF6B6B', label: 'With Defects' },
        ].map(({ color, label }) => (
          <div key={label} className="flex items-center gap-1.5">
            <div className="w-3 h-1.5 rounded-full" style={{ backgroundColor: color }} />
            <span className="text-[10px] text-steel-400">{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Alert Feed ────────────────────────────────────────────────────────────────

function AlertFeed({ records }: { records: InspectionRecord[] }) {
  const alerts = [...records]
    .filter(r => r.status === 'rejected' || r.status === 'review')
    .sort((a, b) => b.timestamp.localeCompare(a.timestamp))
    .slice(0, 10);

  function timeAgo(ts: string) {
    const diffMs = Date.now() - new Date(ts).getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 60) return `${diffMin}m ago`;
    return `${Math.floor(diffMin / 60)}h ${diffMin % 60}m ago`;
  }

  return (
    <div className="card p-5">
      <SectionHeader
        title="Alert Feed"
        subtitle="Last 10 flagged inspections (rejected + review)"
        actions={
          <Badge variant="danger">{alerts.length} alerts</Badge>
        }
      />
      <div className="flex flex-col gap-1 max-h-72 overflow-y-auto pr-1">
        {alerts.map(r => (
          <div
            key={r.id}
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-charcoal-900/60 hover:bg-charcoal-700/40 transition-colors group"
          >
            {r.status === 'rejected'
              ? <XCircle size={14} className="text-danger flex-shrink-0" />
              : <AlertTriangle size={14} className="text-warning flex-shrink-0" />
            }
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-mono text-xs text-white font-medium">{r.sheet_id}</span>
                <span className="text-[10px] text-steel-500">{r.line}</span>
                <Badge variant={r.status === 'rejected' ? 'danger' : 'warning'}>
                  {r.status}
                </Badge>
              </div>
              <div className="text-[10px] text-steel-400 mt-0.5">
                {r.defect_count} defect{r.defect_count !== 1 ? 's' : ''} detected
              </div>
            </div>
            <div className="flex items-center gap-1 text-steel-500 text-[10px] flex-shrink-0">
              <Clock size={10} />
              {timeAgo(r.timestamp)}
            </div>
            <ChevronRight size={12} className="text-steel-600 group-hover:text-steel-400 transition-colors" />
          </div>
        ))}
        {alerts.length === 0 && (
          <div className="text-center py-8 text-steel-500 text-sm">
            <CheckCircle2 size={24} className="mx-auto mb-2 text-success" />
            No alerts — all lines running clean
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function ProductionPage({ records }: Props) {
  const lines = getProductionLines(records);
  const running = lines.filter(l => l.status === 'running').length;
  const totalThroughput = lines.filter(l => l.status === 'running').reduce((s, l) => s + l.throughput, 0);
  const avgUptime = lines.filter(l => l.uptime > 0).reduce((s, l) => s + l.uptime, 0) /
    (lines.filter(l => l.uptime > 0).length || 1);

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Activity size={20} className="text-accent" />
            Production Monitor
          </h1>
          <p className="text-xs text-steel-400 mt-0.5">Real-time line status, throughput & simulation</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-steel-400">
          <div className="w-2 h-2 rounded-full bg-success animate-ping" />
          {running}/{lines.length} lines running
        </div>
      </div>

      {/* Top KPI row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Active Lines"
          value={running}
          unit={`/ ${lines.length}`}
          icon={<Activity size={16} />}
          color="success"
        />
        <StatCard
          label="Total Throughput"
          value={totalThroughput}
          unit="sheets/hr"
          icon={<Gauge size={16} />}
          color="accent"
        />
        <StatCard
          label="Avg Uptime"
          value={avgUptime.toFixed(1)}
          unit="%"
          icon={<CheckCircle2 size={16} />}
          color="success"
        />
        <StatCard
          label="Inspected Today"
          value={records.length.toLocaleString()}
          unit="sheets"
          icon={<Clock size={16} />}
          color="default"
        />
      </div>

      {/* Line Status Grid */}
      <div>
        <h2 className="text-sm font-semibold text-white mb-3">Line Status Grid</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          {lines.map(line => <LineCard key={line.id} line={line} />)}
        </div>
      </div>

      {/* Conveyor simulation */}
      <ConveyorSimulation />

      {/* Charts row */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <ThroughputChart records={records} />
        <AlertFeed records={records} />
      </div>
    </div>
  );
}
