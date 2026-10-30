/** Top navigation shared by every page. */

import { Mark, ArrowRight } from "../app/icons.tsx";

export const REPORT_URL =
  "https://github.com/DEEPIKAGRACE22/PS-7---AI-Assisted-Quality-Inspection-IBM-x-MAH-Quantum-project-/blob/main/docs/MODEL_EVALUATION_REPORT.md";

export default function SiteHeader({ generatedAt }: { generatedAt: string }) {
  const date = new Date(`${generatedAt}T00:00:00`).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });

  return (
    <header className="shell">
      <nav className="nav">
        <a href="/" className="brand">
          <Mark />
          PS-7 Inspection
        </a>
        <div className="nav-right">
          <a href="/#leaderboard" className="nav-link">Results</a>
          <a href="/#video-inspection" className="nav-link">Video inspection</a>
          <span className="nav-date hide-sm">Evaluated {date}</span>
          <a href={REPORT_URL} className="btn btn-ghost">
            Full report <ArrowRight className="tick" />
          </a>
        </div>
      </nav>
    </header>
  );
}
