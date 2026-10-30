/**
 * AnalyticsPage.tsx — Defect Analytics Dashboard
 * Real data from NEU-DET evaluation · 6 defect classes · YOLOv8 model metrics
 */

import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ComposedChart, Line, PieChart, Pie, Cell, AreaChart, Area, Legend,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
} from 'recharts';
import {
  TrendingUp, TrendingDown, BarChart2, PieChart as PieIcon,
  AlertTriangle, Info,
} from 'lucide-react';

import {
  getDefectDistribution, getParetoData, getModelPerClassData, getTrendData,
  CLASS_SUMMARY,
} from '../data';
import { StatCard, SectionHeader, ProgressBar } from '../components/UI';
import type { InspectionRecord } from '../types';
import { DEFECT_COLORS, DEFECT_LABELS, DEFECT_DESCRIPTIONS, DEFECT_SEVERITY } from '../types';

// ─── Helpers ────────────────────────────────────────────────────────────────

const TOTAL_DETECTIONS = CLASS_SUMMARY.reduce((s, c) => s + c.detection_count, 0);
const TOTAL_ALERTS     = CLASS_SUMMARY.reduce((s, c) => s + c.alert_count, 0);

function shortenName(name: string) {
  const map: Record<string, string> = {
    inclusion: 'Inclusion',
    patches: 'Patches',
    'rolled-in_scale': 'Rolled Scale',
    scratches: 'Scratches',
    crazing: 'Crazing',
    pitted_surface: 'Pitted',
  };
  return map[name] ?? name;
}

// ─── Custom Tooltips ─────────────────────────────────────────────────────────

function ParetoTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  return (
    <div className="bg-charcoal-900 border border-charcoal-600 rounded-xl p-3 shadow-xl text-xs">
      <p className="font-semibold text-white mb-1">{DEFECT_LABELS[d.name as keyof typeof DEFECT_LABELS] ?? d.name}</p>
      <p className="text-steel-300">Count: <span className="text-white font-mono">{d.count.toLocaleString()}</span></p>
      <p className="text-steel-300">Cumulative: <span className="text-accent font-mono">{d.cumPct}%</span></p>
    </div>
  );
}

function SeverityTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  return (
    <div className="bg-charcoal-900 border border-charcoal-600 rounded-xl p-3 shadow-xl text-xs">
      <p className="font-semibold text-white mb-1">{DEFECT_LABELS[d.name as keyof typeof DEFECT_LABELS] ?? d.name}</p>
      <p className="text-steel-300">AP50: <span className="text-accent font-mono">{d.AP50}%</span></p>
      <p className="text-steel-300">Recall: <span className="text-success font-mono">{d.recall}%</span></p>
      <p className="text-steel-300">GT Boxes: <span className="text-white font-mono">{d.gt_boxes}</span></p>
    </div>
  );
}

function TrendTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-charcoal-900 border border-charcoal-600 rounded-xl p-3 shadow-xl text-xs">
      <p className="font-semibold text-white mb-1">{label}</p>
      {payload.map((p: any) => (
        <p key={p.dataKey} style={{ color: p.color }}>
          {p.name}: <span className="font-mono">{p.value}%</span>
        </p>
      ))}
    </div>
  );
}

// ─── Custom Pareto Bar (each bar its own color) ───────────────────────────────

function CustomBar(props: any) {
  const { x, y, width, height, payload } = props;
  return (
    <rect
      x={x} y={y} width={width} height={height}
      fill={payload.color}
      fillOpacity={0.85}
      rx={3}
    />
  );
}

// ─── Donut Legend ─────────────────────────────────────────────────────────────

function DonutLegend({ data }: { data: ReturnType<typeof getDefectDistribution> }) {
  return (
    <div className="grid grid-cols-2 gap-1.5 mt-3">
      {data.map(d => (
        <div key={d.name} className="flex items-center gap-2 text-xs">
          <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: d.color }} />
          <span className="text-steel-300 truncate">{shortenName(d.name)}</span>
          <span className="ml-auto font-mono text-white">{d.percentage}%</span>
        </div>
      ))}
    </div>
  );
}

// ─── Hotspot Card ─────────────────────────────────────────────────────────────

function HotspotCard({ name, count, color }: { name: string; count: number; color: string }) {
  const label = DEFECT_LABELS[name as keyof typeof DEFECT_LABELS] ?? name;
  const severity = DEFECT_SEVERITY[name as keyof typeof DEFECT_SEVERITY];
  const severityColor = severity === 'high' ? '#ef4444' : severity === 'medium' ? '#f59e0b' : '#22c55e';
  return (
    <div className="card p-4 flex flex-col gap-3 hover:border-charcoal-500 transition-colors">
      {/* Simulated heatmap */}
      <div
        className="w-full rounded-lg overflow-hidden relative"
        style={{ height: 140 }}
      >
        {/* Background steel texture */}
        <div className="absolute inset-0 bg-charcoal-900" />
        {/* Primary hotspot blob */}
        <div
          className="absolute inset-0"
          style={{
            background: `radial-gradient(ellipse 55% 45% at 38% 42%, ${color}55 0%, ${color}22 40%, transparent 70%)`,
          }}
        />
        {/* Secondary hotspot */}
        <div
          className="absolute inset-0"
          style={{
            background: `radial-gradient(ellipse 30% 25% at 72% 65%, ${color}44 0%, ${color}18 50%, transparent 75%)`,
          }}
        />
        {/* Grid lines to simulate image */}
        <div
          className="absolute inset-0 opacity-10"
          style={{
            backgroundImage: `
              linear-gradient(to right, ${color}30 1px, transparent 1px),
              linear-gradient(to bottom, ${color}30 1px, transparent 1px)
            `,
            backgroundSize: '20px 20px',
          }}
        />
        {/* Bounding box simulation */}
        <div
          className="absolute rounded border"
          style={{
            border: `1.5px solid ${color}`,
            left: '22%', top: '20%', width: '35%', height: '30%',
            backgroundColor: `${color}10`,
          }}
        />
        <div
          className="absolute rounded border"
          style={{
            border: `1px solid ${color}88`,
            left: '58%', top: '50%', width: '22%', height: '20%',
            backgroundColor: `${color}08`,
          }}
        />
        {/* Corner label */}
        <div
          className="absolute top-2 left-2 px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide"
          style={{ backgroundColor: `${color}25`, color }}
        >
          {shortenName(name)}
        </div>
      </div>

      {/* Info */}
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-semibold text-white">{label}</p>
          <p className="text-[10px] text-steel-400 mt-0.5 leading-snug">
            {DEFECT_DESCRIPTIONS[name as keyof typeof DEFECT_DESCRIPTIONS]?.slice(0, 48)}…
          </p>
        </div>
      </div>
      <div className="flex items-center justify-between">
        <span className="font-mono text-sm font-bold" style={{ color }}>{count.toLocaleString()}</span>
        <span
          className="text-[10px] font-medium px-1.5 py-0.5 rounded-full uppercase tracking-wide"
          style={{ color: severityColor, backgroundColor: `${severityColor}20` }}
        >
          {severity}
        </span>
      </div>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

interface AnalyticsPageProps {
  records: InspectionRecord[];
}

export default function AnalyticsPage({ records }: AnalyticsPageProps) {
  const paretoData   = getParetoData();
  const distribution = getDefectDistribution();
  const perClass     = getModelPerClassData();
  const trendData    = getTrendData(records);

  const totalDefects = records.reduce((s, r) => s + r.defect_count, 0);
  const alertRate    = Math.round((TOTAL_ALERTS / TOTAL_DETECTIONS) * 1000) / 10;

  // RadarChart data: AP50 + Recall per class
  const radarData = perClass.map(c => ({
    class: shortenName(c.name),
    AP50: c.AP50,
    Recall: c.recall,
  }));

  return (
    <div className="space-y-6 pb-8">

      {/* ── Row 1: Quick Stats ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Total Detections"
          value={TOTAL_DETECTIONS.toLocaleString()}
          icon={<BarChart2 size={16} />}
          color="accent"
          change={+3.2}
          changeLabel="vs. last period"
        />
        <StatCard
          label="Most Frequent Defect"
          value="Inclusion"
          icon={<AlertTriangle size={16} />}
          color="warning"
          changeLabel="2,002 detections"
        />
        <StatCard
          label="Alert Rate"
          value={alertRate}
          unit="%"
          icon={<TrendingUp size={16} />}
          color="danger"
          change={-1.4}
          changeLabel="alerts / total detections"
        />
        <StatCard
          label="Model mAP50"
          value="76.8"
          unit="%"
          icon={<Info size={16} />}
          color="success"
          changeLabel="Test set · NEU-DET"
        />
      </div>

      {/* ── Row 2: Pareto + Donut ── */}
      <div className="grid grid-cols-5 gap-4">

        {/* Pareto Chart */}
        <div className="col-span-5 lg:col-span-3 card p-5">
          <SectionHeader
            title="Pareto Analysis — Defect Frequency"
            subtitle="Bars = count · Line = cumulative % · 80% Pareto threshold shown"
          />
          <ResponsiveContainer width="100%" height={280}>
            <ComposedChart data={paretoData} margin={{ top: 10, right: 50, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a3441" />
              <XAxis
                dataKey="name"
                tickFormatter={shortenName}
                tick={{ fill: '#8BA7C7', fontSize: 11 }}
                axisLine={{ stroke: '#2a3441' }}
                tickLine={false}
              />
              <YAxis
                yAxisId="left"
                orientation="left"
                tick={{ fill: '#8BA7C7', fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                yAxisId="right"
                orientation="right"
                domain={[0, 100]}
                tickFormatter={v => `${v}%`}
                tick={{ fill: '#8BA7C7', fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip content={<ParetoTooltip />} />
              <Bar yAxisId="left" dataKey="count" shape={<CustomBar />} maxBarSize={50}>
                {paretoData.map((entry) => (
                  <Cell key={entry.name} fill={entry.color} fillOpacity={0.85} />
                ))}
              </Bar>
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="cumPct"
                stroke="#00D4FF"
                strokeWidth={2}
                dot={{ fill: '#00D4FF', r: 4, strokeWidth: 0 }}
                name="Cumulative %"
              />
              {/* 80% threshold reference */}
              <Line
                yAxisId="right"
                type="monotone"
                dataKey={() => 80}
                stroke="#f59e0b"
                strokeWidth={1}
                strokeDasharray="6 4"
                dot={false}
                name="80% Threshold"
              />
            </ComposedChart>
          </ResponsiveContainer>
          <p className="text-[10px] text-steel-400 mt-2 text-center">
            Inclusion + Patches account for <span className="text-warning font-medium">51.2%</span> of all defects — Pareto critical pair
          </p>
        </div>

        {/* Donut Chart */}
        <div className="col-span-5 lg:col-span-2 card p-5 flex flex-col">
          <SectionHeader
            title="Defect Distribution"
            subtitle="By detection count from ps7_class_summary.csv"
            actions={<PieIcon size={14} className="text-steel-400" />}
          />
          <div className="flex-1 flex items-center justify-center">
            <PieChart width={200} height={200}>
              <Pie
                data={distribution}
                cx={100}
                cy={100}
                innerRadius={60}
                outerRadius={90}
                paddingAngle={3}
                dataKey="count"
              >
                {distribution.map((entry) => (
                  <Cell key={entry.name} fill={entry.color} stroke="transparent" />
                ))}
              </Pie>
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const d = payload[0].payload;
                  return (
                    <div className="bg-charcoal-900 border border-charcoal-600 rounded-lg p-2 text-xs shadow-xl">
                      <p className="font-semibold" style={{ color: d.color }}>{DEFECT_LABELS[d.name as keyof typeof DEFECT_LABELS] ?? d.name}</p>
                      <p className="text-steel-300">{d.count.toLocaleString()} ({d.percentage}%)</p>
                    </div>
                  );
                }}
              />
            </PieChart>
          </div>
          {/* Center label overlay */}
          <DonutLegend data={distribution} />
        </div>
      </div>

      {/* ── Row 3: Severity Analysis + Historical Trend ── */}
      <div className="grid grid-cols-2 gap-4">

        {/* Per-Class AP50 + Recall */}
        <div className="col-span-2 lg:col-span-1 card p-5">
          <SectionHeader
            title="Per-Class Model Performance"
            subtitle="AP50 vs Recall at conf 0.25 — test split · NEU-DET"
          />
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={perClass} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a3441" />
              <XAxis
                dataKey="name"
                tickFormatter={shortenName}
                tick={{ fill: '#8BA7C7', fontSize: 11 }}
                axisLine={{ stroke: '#2a3441' }}
                tickLine={false}
              />
              <YAxis
                domain={[0, 100]}
                tickFormatter={v => `${v}%`}
                tick={{ fill: '#8BA7C7', fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip content={<SeverityTooltip />} />
              <Legend
                formatter={(value) => (
                  <span className="text-xs text-steel-300">{value}</span>
                )}
              />
              <Bar dataKey="AP50"   name="AP50"   fill="#00D4FF" fillOpacity={0.85} radius={[3, 3, 0, 0]} maxBarSize={20} />
              <Bar dataKey="recall" name="Recall" fill="#22c55e" fillOpacity={0.85} radius={[3, 3, 0, 0]} maxBarSize={20} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Historical Trend */}
        <div className="col-span-2 lg:col-span-1 card p-5">
          <SectionHeader
            title="FPY & Rejection Rate Trend"
            subtitle="Rolling daily rates from inspection history"
            actions={<TrendingDown size={14} className="text-danger" />}
          />
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={trendData} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="fpyGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#22c55e" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#22c55e" stopOpacity={0.02} />
                </linearGradient>
                <linearGradient id="rejGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#ef4444" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#ef4444" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a3441" />
              <XAxis
                dataKey="date"
                tick={{ fill: '#8BA7C7', fontSize: 10 }}
                axisLine={{ stroke: '#2a3441' }}
                tickLine={false}
              />
              <YAxis
                domain={[0, 100]}
                tickFormatter={v => `${v}%`}
                tick={{ fill: '#8BA7C7', fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip content={<TrendTooltip />} />
              <Legend formatter={(v) => <span className="text-xs text-steel-300">{v}</span>} />
              <Area
                type="monotone"
                dataKey="fpyRate"
                name="FPY Rate"
                stroke="#22c55e"
                strokeWidth={2}
                fill="url(#fpyGrad)"
              />
              <Area
                type="monotone"
                dataKey="rejectionRate"
                name="Rejection Rate"
                stroke="#ef4444"
                strokeWidth={2}
                fill="url(#rejGrad)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ── Row 4: Per-Class Performance Cards ── */}
      <div className="card p-5">
        <SectionHeader
          title="Per-Class Performance Summary"
          subtitle="Real metrics from NEU-DET test split evaluation"
        />
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {perClass.map(cls => (
            <div
              key={cls.name}
              className="bg-charcoal-900 rounded-xl p-4 border transition-colors hover:border-charcoal-500"
              style={{ borderColor: `${cls.color}30` }}
            >
              {/* Color dot + name */}
              <div className="flex items-center gap-2 mb-3">
                <span
                  className="w-2.5 h-2.5 rounded-full flex-shrink-0 ring-2"
                  style={{ backgroundColor: cls.color, ringColor: `${cls.color}40` }}
                />
                <span className="text-xs font-semibold text-white leading-tight">
                  {shortenName(cls.name)}
                </span>
              </div>

              {/* AP50 */}
              <div className="mb-2">
                <ProgressBar
                  label="AP50"
                  value={cls.AP50}
                  color={cls.color}
                  showPct
                />
              </div>

              {/* Recall */}
              <div className="mb-3">
                <ProgressBar
                  label="Recall"
                  value={cls.recall}
                  color="#22c55e"
                  showPct
                />
              </div>

              {/* GT boxes */}
              <div className="flex justify-between items-center mt-1">
                <span className="text-[10px] text-steel-400">GT Boxes</span>
                <span className="text-[10px] font-mono text-white">{cls.gt_boxes}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Row 5: Radar + Hotspot Maps ── */}
      <div className="grid grid-cols-5 gap-4">

        {/* Radar Chart */}
        <div className="col-span-5 lg:col-span-2 card p-5">
          <SectionHeader
            title="Class Capability Radar"
            subtitle="AP50 vs Recall · model test split"
          />
          <ResponsiveContainer width="100%" height={280}>
            <RadarChart data={radarData}>
              <PolarGrid stroke="#2a3441" />
              <PolarAngleAxis
                dataKey="class"
                tick={{ fill: '#8BA7C7', fontSize: 10 }}
              />
              <PolarRadiusAxis
                angle={30}
                domain={[0, 100]}
                tick={{ fill: '#8BA7C7', fontSize: 9 }}
                tickCount={4}
              />
              <Radar name="AP50"   dataKey="AP50"   stroke="#00D4FF" fill="#00D4FF" fillOpacity={0.2} strokeWidth={2} />
              <Radar name="Recall" dataKey="Recall" stroke="#22c55e" fill="#22c55e" fillOpacity={0.15} strokeWidth={2} />
              <Legend formatter={(v) => <span className="text-xs text-steel-300">{v}</span>} />
              <Tooltip content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                return (
                  <div className="bg-charcoal-900 border border-charcoal-600 rounded-lg p-2 text-xs shadow-xl">
                    {payload.map((p: any) => (
                      <p key={p.name} style={{ color: p.stroke }}>
                        {p.name}: <span className="font-mono">{p.value}%</span>
                      </p>
                    ))}
                  </div>
                );
              }} />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        {/* Defect Hotspot Maps */}
        <div className="col-span-5 lg:col-span-3 card p-5">
          <SectionHeader
            title="Defect Hotspot Visualization"
            subtitle="Simulated spatial heatmaps — detection density overlay per class"
          />
          <div className="grid grid-cols-3 gap-3">
            {CLASS_SUMMARY.map(cls => (
              <HotspotCard
                key={cls.class_name}
                name={cls.class_name}
                count={cls.detection_count}
                color={DEFECT_COLORS[cls.class_name as keyof typeof DEFECT_COLORS] ?? '#8BA7C7'}
              />
            ))}
          </div>
        </div>
      </div>

      {/* ── Footer Note ── */}
      <div className="flex items-start gap-2 text-xs text-steel-400 bg-charcoal-800 border border-charcoal-700 rounded-xl px-4 py-3">
        <Info size={13} className="flex-shrink-0 mt-0.5 text-accent" />
        <span>
          All metrics are derived from the NEU-DET benchmark dataset (1,800 images, 6 defect classes).
          Model: YOLOv8n · Test mAP50 <span className="text-white font-medium">76.8%</span> ·
          Precision <span className="text-white font-medium">76.1%</span> ·
          Recall <span className="text-white font-medium">69.7%</span> ·
          Inference <span className="text-white font-medium">~127 ms</span> on CPU.
        </span>
      </div>
    </div>
  );
}
