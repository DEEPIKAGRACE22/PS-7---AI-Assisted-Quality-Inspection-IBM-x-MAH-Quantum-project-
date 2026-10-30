/** Top navigation shared by every page. */

import { Mark, ArrowRight } from "../app/icons.tsx";
import HeaderNav, { type NavItem } from "./HeaderNav.tsx";

export const REPORT_URL =
  "https://github.com/DEEPIKAGRACE22/PS-7---AI-Assisted-Quality-Inspection-IBM-x-MAH-Quantum-project-/blob/main/docs/MODEL_EVALUATION_REPORT.md";

const NAV: NavItem[] = [
  { label: "Overview", href: "/#overview", section: "overview" },
  { label: "Model Evaluation", href: "/#leaderboard", section: "leaderboard" },
  { label: "Video Inspection", href: "/#video-inspection", section: "video-inspection" },
  { label: "Full Report", href: REPORT_URL, external: true },
];

export default function SiteHeader({ generatedAt }: { generatedAt: string }) {
  const date = new Date(`${generatedAt}T00:00:00`).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });

  return (
    <header className="shell site-header">
      <div className="nav">
        <a href="/" className="brand" aria-label="SteelSight home">
          <Mark />
          <span className="brand-text">
            <b>SteelSight</b>
            <small>Steel Surface Inspection</small>
          </span>
        </a>
        <div className="nav-right">
          <span className="nav-date hide-sm">Evaluated {date}</span>
        </div>
      </div>
      <div className="nav-bar">
        <HeaderNav items={NAV} />
      </div>
    </header>
  );
}
