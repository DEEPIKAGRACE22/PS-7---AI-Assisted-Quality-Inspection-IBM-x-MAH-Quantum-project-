import { useState, useMemo } from 'react';
import Sidebar from './components/Sidebar';
import TopBar from './components/TopBar';
import OverviewPage from './pages/OverviewPage';
import InspectionPage from './pages/InspectionPage';
import AnalyticsPage from './pages/AnalyticsPage';
import HistoryPage from './pages/HistoryPage';
import ProductionPage from './pages/ProductionPage';
import IntelligencePage from './pages/IntelligencePage';
import ReportsPage from './pages/ReportsPage';
import SettingsPage from './pages/SettingsPage';
import { generateInspectionHistory, DEFAULT_SETTINGS } from './data';
import type { PageId, InspectionSettings } from './types';

export default function App() {
  const [page, setPage] = useState<PageId>('overview');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [settings, setSettings] = useState<InspectionSettings>(DEFAULT_SETTINGS);

  // Generate inspection history once (derived from real model metrics)
  const inspectionHistory = useMemo(() => generateInspectionHistory(240), []);

  const renderPage = () => {
    switch (page) {
      case 'overview':     return <OverviewPage records={inspectionHistory} />;
      case 'inspection':   return <InspectionPage settings={settings} />;
      case 'analytics':    return <AnalyticsPage records={inspectionHistory} />;
      case 'history':      return <HistoryPage records={inspectionHistory} />;
      case 'production':   return <ProductionPage records={inspectionHistory} />;
      case 'intelligence': return <IntelligencePage records={inspectionHistory} />;
      case 'reports':      return <ReportsPage records={inspectionHistory} />;
      case 'settings':     return <SettingsPage settings={settings} onSave={setSettings} />;
      default:             return <OverviewPage records={inspectionHistory} />;
    }
  };

  return (
    <div className="flex h-screen overflow-hidden bg-charcoal-950">
      <Sidebar
        currentPage={page}
        onNavigate={setPage}
        open={sidebarOpen}
        onToggle={() => setSidebarOpen(o => !o)}
      />
      <div className={`flex-1 flex flex-col min-w-0 transition-all duration-300`}>
        <TopBar
          page={page}
          onMenuToggle={() => setSidebarOpen(o => !o)}
          sidebarOpen={sidebarOpen}
        />
        <main className="flex-1 overflow-y-auto p-6 animate-fade-in">
          {renderPage()}
        </main>
      </div>
    </div>
  );
}
