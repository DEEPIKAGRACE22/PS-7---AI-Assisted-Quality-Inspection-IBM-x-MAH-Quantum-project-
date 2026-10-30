import {
  LayoutDashboard, Scan, BarChart3, History, Activity,
  Brain, FileText, Settings, ChevronLeft, ChevronRight,
  Zap, Shield
} from 'lucide-react';
import type { PageId } from '../types';
import clsx from 'clsx';

interface NavItem {
  id: PageId;
  label: string;
  icon: React.ComponentType<{ className?: string; size?: number }>;
  badge?: string;
}

const NAV_ITEMS: NavItem[] = [
  { id: 'overview',     label: 'Overview',           icon: LayoutDashboard },
  { id: 'inspection',   label: 'Live Inspection',    icon: Scan,      badge: 'LIVE' },
  { id: 'analytics',    label: 'Defect Analytics',   icon: BarChart3  },
  { id: 'history',      label: 'History',            icon: History    },
  { id: 'production',   label: 'Production',         icon: Activity   },
  { id: 'intelligence', label: 'AI Intelligence',    icon: Brain      },
  { id: 'reports',      label: 'Reports',            icon: FileText   },
  { id: 'settings',     label: 'Settings',           icon: Settings   },
];

interface SidebarProps {
  currentPage: PageId;
  onNavigate: (p: PageId) => void;
  open: boolean;
  onToggle: () => void;
}

export default function Sidebar({ currentPage, onNavigate, open, onToggle }: SidebarProps) {
  return (
    <aside
      className={clsx(
        'flex flex-col bg-charcoal-900 border-r border-charcoal-700 transition-all duration-300 flex-shrink-0',
        open ? 'w-60' : 'w-16'
      )}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 py-5 border-b border-charcoal-700">
        <div className="w-8 h-8 rounded-lg bg-accent/20 border border-accent/30 flex items-center justify-center flex-shrink-0">
          <Shield size={16} className="text-accent" />
        </div>
        {open && (
          <div className="min-w-0">
            <div className="text-sm font-bold text-white leading-tight">SteelVision</div>
            <div className="text-[10px] text-steel-400 font-medium tracking-wider uppercase">AI Quality</div>
          </div>
        )}
      </div>

      {/* Live status indicator */}
      {open && (
        <div className="mx-3 mt-3 mb-1 flex items-center gap-2 px-3 py-2 rounded-lg bg-success/10 border border-success/20">
          <div className="relative flex-shrink-0">
            <div className="w-2 h-2 rounded-full bg-success"></div>
            <div className="absolute inset-0 rounded-full bg-success animate-ping opacity-75"></div>
          </div>
          <span className="text-xs text-success font-medium">System Online</span>
          <Zap size={10} className="text-success ml-auto" />
        </div>
      )}

      {/* Nav items */}
      <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const active = currentPage === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={clsx(
                'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 text-left',
                active
                  ? 'bg-accent/10 text-accent border border-accent/20'
                  : 'text-steel-400 hover:text-white hover:bg-charcoal-700'
              )}
              title={!open ? item.label : undefined}
            >
              <Icon size={16} className="flex-shrink-0" />
              {open && (
                <>
                  <span className="text-sm font-medium flex-1 truncate">{item.label}</span>
                  {item.badge && (
                    <span className="text-[9px] font-bold bg-success/20 text-success border border-success/30 px-1.5 py-0.5 rounded-full">
                      {item.badge}
                    </span>
                  )}
                </>
              )}
              {!open && item.badge && (
                <span className="absolute right-1 top-1 w-2 h-2 rounded-full bg-success"></span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Footer / collapse */}
      <div className="px-2 py-3 border-t border-charcoal-700">
        {open && (
          <div className="px-3 py-2 mb-2">
            <div className="text-[10px] text-steel-400 font-medium mb-1">NEU-DET Model v2</div>
            <div className="progress-bar">
              <div className="progress-fill bg-accent" style={{ width: '76.8%' }} />
            </div>
            <div className="flex justify-between mt-1">
              <span className="text-[10px] text-steel-400">mAP@50</span>
              <span className="text-[10px] text-accent font-mono">76.8%</span>
            </div>
          </div>
        )}
        <button
          onClick={onToggle}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-steel-400 hover:text-white hover:bg-charcoal-700 transition-all duration-200"
        >
          {open ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
          {open && <span className="text-xs">Collapse</span>}
        </button>
      </div>
    </aside>
  );
}
