import clsx from 'clsx';
import type { ReactNode } from 'react';

interface StatCardProps {
  label: string;
  value: string | number;
  unit?: string;
  change?: number;
  changeLabel?: string;
  icon?: ReactNode;
  color?: 'default' | 'success' | 'danger' | 'warning' | 'accent';
  glow?: boolean;
}

const COLOR_MAP = {
  default: { bg: 'bg-charcoal-800', border: 'border-charcoal-600', icon: 'bg-charcoal-700 text-steel-400', val: 'text-white' },
  success: { bg: 'bg-charcoal-800', border: 'border-success/20', icon: 'bg-success/20 text-success', val: 'text-success' },
  danger:  { bg: 'bg-charcoal-800', border: 'border-danger/20',  icon: 'bg-danger/20 text-danger',   val: 'text-danger' },
  warning: { bg: 'bg-charcoal-800', border: 'border-warning/20', icon: 'bg-warning/20 text-warning',  val: 'text-warning' },
  accent:  { bg: 'bg-charcoal-800', border: 'border-accent/20',  icon: 'bg-accent/20 text-accent',   val: 'text-accent' },
};

export function StatCard({ label, value, unit, change, changeLabel, icon, color = 'default', glow }: StatCardProps) {
  const c = COLOR_MAP[color];
  return (
    <div className={clsx(
      'card p-5 flex flex-col gap-3',
      c.bg, c.border,
      glow && color === 'success' && 'shadow-glow-success',
      glow && color === 'danger' && 'shadow-glow-danger',
      glow && color === 'accent' && 'shadow-glow',
    )}>
      <div className="flex items-start justify-between">
        <div className={clsx('w-9 h-9 rounded-lg flex items-center justify-center', c.icon)}>
          {icon}
        </div>
        {change !== undefined && (
          <span className={clsx(
            'text-xs font-medium px-2 py-0.5 rounded-full',
            change >= 0 ? 'bg-success/20 text-success' : 'bg-danger/20 text-danger'
          )}>
            {change >= 0 ? '+' : ''}{change.toFixed(1)}%
          </span>
        )}
      </div>
      <div>
        <div className={clsx('text-2xl font-bold leading-none', c.val)}>
          {value}
          {unit && <span className="text-sm font-medium text-steel-400 ml-1">{unit}</span>}
        </div>
        <div className="text-xs text-steel-400 mt-1.5 font-medium uppercase tracking-wide">{label}</div>
        {changeLabel && <div className="text-xs text-steel-400 mt-0.5">{changeLabel}</div>}
      </div>
    </div>
  );
}

interface SectionHeaderProps {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}

export function SectionHeader({ title, subtitle, actions }: SectionHeaderProps) {
  return (
    <div className="flex items-start justify-between gap-4 mb-5">
      <div>
        <h2 className="text-base font-semibold text-white">{title}</h2>
        {subtitle && <p className="text-xs text-steel-400 mt-0.5">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2 flex-shrink-0">{actions}</div>}
    </div>
  );
}

interface DefectPillProps {
  name: string;
  color: string;
  size?: 'sm' | 'md';
}

export function DefectPill({ name, color, size = 'md' }: DefectPillProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-full border font-medium',
        size === 'sm' ? 'px-2 py-0.5 text-[10px]' : 'px-2.5 py-1 text-xs'
      )}
      style={{ color, borderColor: color + '40', backgroundColor: color + '15' }}
    >
      <span
        className="w-1.5 h-1.5 rounded-full flex-shrink-0"
        style={{ backgroundColor: color }}
      />
      {name}
    </span>
  );
}

interface ProgressBarProps {
  value: number;
  max?: number;
  color?: string;
  label?: string;
  showPct?: boolean;
}

export function ProgressBar({ value, max = 100, color = '#00D4FF', label, showPct = true }: ProgressBarProps) {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div className="w-full">
      {(label || showPct) && (
        <div className="flex justify-between items-center mb-1">
          {label && <span className="text-xs text-steel-400">{label}</span>}
          {showPct && <span className="text-xs font-mono font-medium" style={{ color }}>{pct.toFixed(1)}%</span>}
        </div>
      )}
      <div className="h-1.5 rounded-full bg-charcoal-700 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
    </div>
  );
}

interface BadgeProps {
  children: ReactNode;
  variant: 'success' | 'danger' | 'warning' | 'accent' | 'neutral';
}

export function Badge({ children, variant }: BadgeProps) {
  return (
    <span className={clsx(
      'inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium border',
      variant === 'success' && 'bg-success/20 text-success border-success/30',
      variant === 'danger'  && 'bg-danger/20 text-danger border-danger/30',
      variant === 'warning' && 'bg-warning/20 text-warning border-warning/30',
      variant === 'accent'  && 'bg-accent/20 text-accent border-accent/30',
      variant === 'neutral' && 'bg-charcoal-700 text-steel-400 border-charcoal-600',
    )}>
      {children}
    </span>
  );
}

export function Divider() {
  return <div className="glow-line my-4" />;
}

export function LoadingSpinner({ size = 20 }: { size?: number }) {
  return (
    <div
      className="animate-spin rounded-full border-2 border-charcoal-600 border-t-accent"
      style={{ width: size, height: size }}
    />
  );
}
