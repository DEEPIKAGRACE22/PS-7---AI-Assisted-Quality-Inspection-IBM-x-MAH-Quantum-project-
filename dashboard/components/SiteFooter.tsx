/** Footer shared by every page. Only project facts that exist in the repo are listed. */

import { REPORT_URL } from "./SiteHeader.tsx";

export default function SiteFooter() {
  return (
    <footer className="shell site-footer">
      <div className="foot-grid">
        <div>
          <b className="foot-title">SteelSight</b>
          <p>AI-Powered Steel Surface Inspection System</p>
          <p className="foot-muted">Computer Vision · YOLO · Deep Learning · Video Analysis</p>
        </div>
        <div>
          <span className="label">Project</span>
          <p>PS-7 Project Review</p>
          <p>NEU-DET Steel Surface Defect Dataset</p>
        </div>
        <nav className="foot-links" aria-label="Footer">
          <span className="label">Navigate</span>
          <a href="#">Back to top</a>
          <a href={REPORT_URL} target="_blank" rel="noreferrer">Full Report</a>
        </nav>
      </div>
      <div className="foot-base">
        <span>© {new Date().getFullYear()} SteelSight · PS-7 Project Review</span>
        <span>
          Regenerate results with <code>python scripts/evaluate_all.py</code> then{" "}
          <code>python scripts/export_dashboard_json.py</code>
        </span>
      </div>
    </footer>
  );
}
