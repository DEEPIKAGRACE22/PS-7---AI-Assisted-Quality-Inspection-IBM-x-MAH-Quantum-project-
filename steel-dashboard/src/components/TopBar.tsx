import { Menu, Bell, Clock, Cpu } from 'lucide-react';
import type { PageId } from '../types';

const PAGE_TITLES: Record<PageId, { title: string; subtitle: string }> = {
  overview:     { title: 'Operations Overview',     subtitle: 'Real-time quality metrics dashboard' },
  inspection:   { title: 'Live AI Inspection',      subtitle: 'Upload images or use demo video for defect detection' },
  analytics:    { title: 'Defect Analytics',        subtitle: 'Pareto, distribution & trend analysis' },
  history:      { title: 'Inspection History',      subtitle: 'Searchable inspection records & evidence gallery' },
  production:   { title: 'Production Monitoring',   subtitle: 'Line status, throughput & conveyor simulation' },
  intelligence: { title: 'AI Quality Intelligence', subtitle: 'Insights, patterns & improvement recommendations' },
  reports:      { title: 'Reports',                 subtitle: 'Generate & download PDF/CSV inspection reports' },
  settings:     { title: 'Settings',                subtitle: 'Model thresholds, categories & production config' },
};

interface TopBarProps {
  page: PageId;
  onMenuToggle: () => void;
  sidebarOpen: boolean;
}

export default function TopBar({ page, onMenuToggle }: TopBarProps) {
  const { title, subtitle } = PAGE_TITLES[page];
  const now = new Date();
  const timeStr = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
  const dateStr = now.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });

  return (
    <header className="flex-shrink-0 flex items-center gap-4 px-6 py-4 bg-charcoal-900 border-b border-charcoal-700">
      <button
        onClick={onMenuToggle}
        className="p-2 rounded-lg text-steel-400 hover:text-white hover:bg-charcoal-700 transition-all"
      >
        <Menu size={18} />
      </button>

      <div className="flex-1 min-w-0">
        <h1 className="text-base font-semibold text-white truncate">{title}</h1>
        <p className="text-xs text-steel-400 truncate">{subtitle}</p>
      </div>

      {/* Time display */}
      <div className="hidden md:flex items-center gap-2 px-3 py-2 rounded-lg bg-charcoal-800 border border-charcoal-600">
        <Clock size={14} className="text-steel-400" />
        <div className="text-right">
          <div className="text-xs font-mono text-white leading-none">{timeStr}</div>
          <div className="text-[10px] text-steel-400 leading-none mt-0.5">{dateStr}</div>
        </div>
      </div>

      {/* Model indicator */}
      <div className="hidden md:flex items-center gap-2 px-3 py-2 rounded-lg bg-charcoal-800 border border-charcoal-600">
        <Cpu size={14} className="text-accent" />
        <div>
          <div className="text-[10px] text-steel-400 leading-none">Active Model</div>
          <div className="text-xs font-mono text-accent leading-none mt-0.5">best_v2.pt</div>
        </div>
      </div>

      {/* Notifications */}
      <button className="relative p-2 rounded-lg text-steel-400 hover:text-white hover:bg-charcoal-700 transition-all">
        <Bell size={18} />
        <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-danger border-2 border-charcoal-900"></span>
      </button>
    </header>
  );
}
