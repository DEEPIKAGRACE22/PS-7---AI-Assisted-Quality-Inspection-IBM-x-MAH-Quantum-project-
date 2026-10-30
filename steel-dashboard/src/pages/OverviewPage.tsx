/**
 * OverviewPage.tsx
 * Steel Quality Inspection Dashboard — Overview
 * All live metrics derived from props/data functions.
 * Real model constants (best_v2.pt test set) are pinned as specified.
 */

import {
  AreaChart, Area,
  BarChart, Bar,
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
  PieChart, Pie, Cell,
} from 'recharts';
import {
  CheckCircle2, XCircle, AlertTriangle,
  TrendingUp, TrendingDown, Target, Zap,
  BarChart3, Eye, Clock,
} from 'lucide-react';

import {
  getOverviewStats,
  getTrendData,
  getModelPerClassData,
  getDefectDistribution,
} from '../data';
import { StatCard, SectionHeader, ProgressBar, Badge, DefectPill } from '../components/UI';
import type { InspectionRecord } from '../types';
import { DEFECT_COLORS, DEFECT_LABELS } from '../types';

// ─── Real model constants (best_v2.pt — test set) ────────────────────────────
const MODEL_MAP50          = 76.8;
const MODEL_MAP50_95       = 43.3;
const MODEL_PRECISION      = 76.1;
const MODEL_RECALL         = 69.7;
const MODEL_HIT_RATE       = 90.56;
const MODEL_INFERENCE_MS   = 127;
const MODEL_TEST_IMAGES    = 180;
const MODEL_TEST_BOXES     = 416;
const MODEL_MISSED         = 117;
const MODEL_FALSE_ALARMS   = 126;

// ─── Tooltip styles ───────────────────────────────────────────────────────────
const TOOLTIP_STYLE = {
  backgroundColor: '#1a2332',
  border: '1px solid #2d3f55',
  borderRadius: 8,
  color: '#e2e8f0',
  fontSize: 12,
};

// ─── Custom Tooltip for Area chart ───────────────────────────────────────────
function TrendTooltip({ active, payload, label }: {
  active?: boolean;
  payload?: Array<{ value: number; name: string }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div style={TOOLTIP_STYLE} className="px-3 py-2 shadow-xl">
      <p className="text-steel-400 text-[11px] mb-1 font-medium">{label}</p>
      {payload.map((p) => (
        <p key={p.name} className="text-sm font-bold" style={{ color: '#00D4FF' }}>
          FPY: {p.value.toFixed(1)}%
        </p>
      ))}
    </div>
  );
}

// ─── Custom Tooltip for Pie chart ────────────────────────────────────────────
function PieTooltip({ active, payload }: {
  active?: boolean;
  payload?: Array<{ name: string; value: number; payload: { color: string; percentage: number } }>;
}) {
  if (!active || !payload?.length) return null;
  const d = payload[0];
  return (
    <div style={TOOLTIP_STYLE} className="px-3 py-2 shadow-xl">
      <p className="font-semibold text-sm mb-0.5" style={{ color: d.payload.color }}>
        {DEFECT_LABELS[d.name as keyof typeof DEFECT_LABELS] ?? d.name}
      </p>
      <p className="text-xs text-steel-300">{d.value.toLocaleString()} detections</p>
      <p className="text-xs text-steel-400">{d.payload.percentage}% of total</p>
    </div>
  );
}

// ─── Custom Tooltip for Radar chart ──────────────────────────────────────────
function RadarTooltip({ active, payload, label }: {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div style={TOOLTIP_STYLE} className="px-3 py-2 shadow-xl min-w-[140px]">
      <p className="text-steel-400 text-[11px] mb-1.5 font-medium">
        {DEFECT_LABELS[label as keyof typeof DEFECT_LABELS] ?? label}
      </p>
      {payload.map((p) => (
        <p key={p.name} className="text-xs font-semibold flex justify-between gap-4" style={{ color: p.color }}>
          <span>{p.name}</span><span>{p.value.toFixed(1)}%</span>
        </p>
      ))}
    </div>
  );
}

// ─── Model metric mini-block ──────────────────────────────────────────────────
function ModelMetric({ label, value, unit = '%', color = '#00D4FF' }: {
  label: string; value: number; unit?: string; color?: string;
}) {
  return (
    <div className="flex flex-col items-center gap-0.5 px-4 py-3 rounded-xl bg-charcoal-900/50 border border-charcoal-600 min-w-[90px]">
      <span className="text-xl font-bold font-mono" style={{ color }}>
        {value}{unit}
      </span>
      <span className="text-[10px] text-steel-400 uppercase tracking-wider text-center leading-tight">{label}</span>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────
interface OverviewPageProps {
  records: InspectionRecord[];
}

export default function OverviewPage({ records }: OverviewPageProps) {
  const stats      = getOverviewStats(records);
  const trendData  = getTrendData(records);
  const perClass   = getModelPerClassData();
  const distData   = getDefectDistribution();

  // Radar subject keys
  const radarData = perClass.map((c) => ({
    class: DEFECT_LABELS[c.name as keyof typeof DEFECT_LABELS] ?? c.name,
    AP50: c.AP50,
    Recall: c.recall,
    fullName: c.name,
  }));

  // Trend direction badge
  const lastTwo = trendData.slice(-2);
  const fpyTrend = lastTwo.length === 2
    ? lastTwo[1].fpyRate - lastTwo[0].fpyRate
    : 0;

  return (
    <div className="space-y-6 p-6">

      {/* ─── Row 1: Stat Cards ─────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-4">
        <StatCard
          label="Total Inspections"
          value={stats.total.toLocaleString()}
          icon={<Eye size={16} />}
          color="default"
          change={fpyTrend}
          changeLabel="vs yesterday"
        />
        <StatCard
          label="Defects Detected"
          value={stats.totalDefects.toLocaleString()}
          icon={<AlertTriangle size={16} />}
          color="warning"
        />
        <StatCard
          label="First-Pass Yield"
          value={stats.fpyPct.toFixed(1)}
          unit="%"
          icon={<TrendingUp size={16} />}
          color="success"
          glow
          change={fpyTrend}
        />
        <StatCard
          label="Rejection Rate"
          value={stats.rejectionRate.toFixed(1)}
          unit="%"
          icon={<TrendingDown size={16} />}
          color="danger"
        />
        <StatCard
          label="Approved Sheets"
          value={stats.approved.toLocaleString()}
          icon={<CheckCircle2 size={16} />}
          color="success"
        />
        <StatCard
          label="Rejected Sheets"
          value={stats.rejected.toLocaleString()}
          icon={<XCircle size={16} />}
          color="danger"
        />
      </div>

      {/* ─── Row 2: Model Performance Banner ──────────────────────────────── */}
      <div className="card p-5 border-accent/20 bg-charcoal-800">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-accent/20 flex items-center justify-center text-accent">
              <Zap size={18} />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">Active Model Performance</h3>
              <p className="text-xs text-steel-400 mt-0.5">Evaluated on {MODEL_TEST_IMAGES} test images · {MODEL_TEST_BOXES} ground-truth boxes</p>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant="accent">✦ Recommended Model: best_v2.pt</Badge>
            <Badge variant="neutral">{MODEL_INFERENCE_MS}ms CPU inference</Badge>
          </div>
        </div>

        {/* Metric pills */}
        <div className="flex flex-wrap gap-3">
          <ModelMetric label="mAP50" value={MODEL_MAP50} color="#00D4FF" />
          <ModelMetric label="mAP50-95" value={MODEL_MAP50_95} color="#818CF8" />
          <ModelMetric label="Precision" value={MODEL_PRECISION} color="#22C55E" />
          <ModelMetric label="Recall" value={MODEL_RECALL} color="#F59E0B" />
          <ModelMetric label="Image Hit Rate @0.25" value={MODEL_HIT_RATE} color="#22C55E" />
          <ModelMetric label="Missed Defects" value={MODEL_MISSED} unit="" color="#EF4444" />
          <ModelMetric label="False Alarms" value={MODEL_FALSE_ALARMS} unit="" color="#F59E0B" />
        </div>

        {/* Progress bars row */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-5">
          <ProgressBar label="mAP50" value={MODEL_MAP50} max={100} color="#00D4FF" />
          <ProgressBar label="Precision" value={MODEL_PRECISION} max={100} color="#22C55E" />
          <ProgressBar label="Recall" value={MODEL_RECALL} max={100} color="#F59E0B" />
          <ProgressBar label="Image Hit Rate" value={MODEL_HIT_RATE} max={100} color="#22C55E" />
        </div>
      </div>

      {/* ─── Row 3: Trend + Donut ──────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">

        {/* Area Chart: 30-day FPY Trend */}
        <div className="card p-5 lg:col-span-3 bg-charcoal-800 border-charcoal-600">
          <SectionHeader
            title="First-Pass Yield Trend"
            subtitle={`${trendData.length}-day rolling window`}
            actions={
              fpyTrend >= 0
                ? <Badge variant="success"><TrendingUp size={10} className="inline mr-1" />{fpyTrend > 0 ? '+' : ''}{fpyTrend.toFixed(1)}%</Badge>
                : <Badge variant="danger"><TrendingDown size={10} className="inline mr-1" />{fpyTrend.toFixed(1)}%</Badge>
            }
          />
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={trendData} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
              <defs>
                <linearGradient id="fpyGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#00D4FF" stopOpacity={0.28} />
                  <stop offset="95%" stopColor="#00D4FF" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#2d3f55" vertical={false} />
              <XAxis
                dataKey="date"
                tick={{ fill: '#64748b', fontSize: 10 }}
                axisLine={{ stroke: '#2d3f55' }}
                tickLine={false}
                interval="preserveStartEnd"
              />
              <YAxis
                domain={[0, 100]}
                tick={{ fill: '#64748b', fontSize: 10 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => `${v}%`}
              />
              <Tooltip content={<TrendTooltip />} />
              <Area
                type="monotone"
                dataKey="fpyRate"
                stroke="#00D4FF"
                strokeWidth={2}
                fill="url(#fpyGrad)"
                dot={false}
                activeDot={{ r: 4, fill: '#00D4FF', stroke: '#0f172a', strokeWidth: 2 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Pie / Donut: Defect Distribution */}
        <div className="card p-5 lg:col-span-2 bg-charcoal-800 border-charcoal-600">
          <SectionHeader
            title="Defect Distribution"
            subtitle="Video stream detections by class"
          />
          <div className="flex flex-col items-center gap-4">
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie
                  data={distData}
                  dataKey="count"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  innerRadius={52}
                  outerRadius={80}
                  paddingAngle={2}
                  strokeWidth={0}
                >
                  {distData.map((entry) => (
                    <Cell key={entry.name} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip content={<PieTooltip />} />
              </PieChart>
            </ResponsiveContainer>

            {/* Legend */}
            <div className="w-full space-y-1.5">
              {distData.map((d) => (
                <div key={d.name} className="flex items-center justify-between gap-2">
                  <DefectPill
                    name={DEFECT_LABELS[d.name as keyof typeof DEFECT_LABELS] ?? d.name}
                    color={d.color}
                    size="sm"
                  />
                  <div className="flex items-center gap-2 text-xs">
                    <span className="text-steel-400">{d.count.toLocaleString()}</span>
                    <span className="text-steel-500 w-9 text-right font-mono">{d.percentage}%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ─── Row 4: Radar + Bar chart ─────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Radar: AP50 & Recall per class */}
        <div className="card p-5 bg-charcoal-800 border-charcoal-600">
          <SectionHeader
            title="Per-Class Model Performance"
            subtitle="AP50 & Recall @ conf 0.25 from test set"
            actions={<Badge variant="accent"><Target size={10} className="inline mr-1" />best_v2.pt</Badge>}
          />
          <ResponsiveContainer width="100%" height={260}>
            <RadarChart data={radarData} margin={{ top: 8, right: 24, bottom: 8, left: 24 }}>
              <PolarGrid stroke="#2d3f55" />
              <PolarAngleAxis
                dataKey="class"
                tick={{ fill: '#64748b', fontSize: 10 }}
              />
              <Radar
                name="AP50"
                dataKey="AP50"
                stroke="#00D4FF"
                fill="#00D4FF"
                fillOpacity={0.15}
                strokeWidth={2}
              />
              <Radar
                name="Recall"
                dataKey="Recall"
                stroke="#F59E0B"
                fill="#F59E0B"
                fillOpacity={0.12}
                strokeWidth={2}
              />
              <Tooltip content={<RadarTooltip />} />
            </RadarChart>
          </ResponsiveContainer>
          <div className="flex justify-center gap-6 mt-1">
            <span className="flex items-center gap-1.5 text-xs text-steel-400">
              <span className="w-3 h-0.5 rounded-full bg-accent inline-block" /> AP50
            </span>
            <span className="flex items-center gap-1.5 text-xs text-steel-400">
              <span className="w-3 h-0.5 rounded-full bg-warning inline-block" /> Recall
            </span>
          </div>
        </div>

        {/* Bar chart: AP50 per class */}
        <div className="card p-5 bg-charcoal-800 border-charcoal-600">
          <SectionHeader
            title="AP50 by Defect Class"
            subtitle="Test-set average precision at IoU 0.50"
            actions={<Badge variant="neutral"><BarChart3 size={10} className="inline mr-1" />Test Set</Badge>}
          />
          <ResponsiveContainer width="100%" height={260}>
            <BarChart
              data={perClass}
              margin={{ top: 4, right: 4, left: -20, bottom: 40 }}
              barSize={28}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#2d3f55" vertical={false} />
              <XAxis
                dataKey="name"
                tick={{ fill: '#64748b', fontSize: 9 }}
                axisLine={{ stroke: '#2d3f55' }}
                tickLine={false}
                angle={-30}
                textAnchor="end"
                interval={0}
              />
              <YAxis
                domain={[0, 100]}
                tick={{ fill: '#64748b', fontSize: 10 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => `${v}%`}
              />
              <Tooltip
                contentStyle={TOOLTIP_STYLE}
                formatter={(v: number, name: string) => [`${v.toFixed(1)}%`, name === 'AP50' ? 'AP50' : 'Recall']}
                labelFormatter={(l) => DEFECT_LABELS[l as keyof typeof DEFECT_LABELS] ?? l}
              />
              <Bar dataKey="AP50" radius={[4, 4, 0, 0]} name="AP50">
                {perClass.map((c) => (
                  <Cell key={c.name} fill={c.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ─── Row 5: Per-class detail cards ────────────────────────────────── */}
      <div>
        <SectionHeader
          title="Per-Class Detail"
          subtitle="Real metrics from best_v2.pt test evaluation"
          actions={
            <div className="flex items-center gap-2">
              <Badge variant="accent"><Clock size={10} className="inline mr-1" />Live</Badge>
              <Badge variant="neutral">6 classes</Badge>
            </div>
          }
        />
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {perClass.map((cls) => {
            const label = DEFECT_LABELS[cls.name as keyof typeof DEFECT_LABELS] ?? cls.name;
            const color = DEFECT_COLORS[cls.name as keyof typeof DEFECT_COLORS] ?? '#8BA7C7';
            const ap50Good = cls.AP50 >= 70;
            const recallGood = cls.recall >= 65;

            return (
              <div
                key={cls.name}
                className="card p-4 bg-charcoal-800 border-charcoal-600 hover:border-charcoal-500 transition-colors"
              >
                {/* Header */}
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span
                      className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                      style={{ backgroundColor: color }}
                    />
                    <span className="text-sm font-semibold text-white">{label}</span>
                  </div>
                  <Badge variant={ap50Good ? 'success' : 'warning'}>
                    {ap50Good ? 'Good' : 'Fair'}
                  </Badge>
                </div>

                {/* AP50 bar */}
                <div className="space-y-2.5">
                  <ProgressBar
                    label="AP50"
                    value={cls.AP50}
                    max={100}
                    color={color}
                    showPct
                  />
                  <ProgressBar
                    label="AP50-95"
                    value={cls.AP50_95}
                    max={100}
                    color={color + 'AA'}
                    showPct
                  />
                  <ProgressBar
                    label="Recall @0.25"
                    value={cls.recall}
                    max={100}
                    color={recallGood ? '#22C55E' : '#F59E0B'}
                    showPct
                  />
                </div>

                {/* Footer stats */}
                <div className="flex items-center justify-between mt-3 pt-3 border-t border-charcoal-700">
                  <span className="text-[11px] text-steel-500">
                    GT Boxes: <span className="text-steel-300 font-medium">{cls.gt_boxes}</span>
                  </span>
                  <div className="flex gap-1.5">
                    {ap50Good && (
                      <CheckCircle2 size={13} className="text-success" />
                    )}
                    {!recallGood && (
                      <AlertTriangle size={13} className="text-warning" />
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

    </div>
  );
}
