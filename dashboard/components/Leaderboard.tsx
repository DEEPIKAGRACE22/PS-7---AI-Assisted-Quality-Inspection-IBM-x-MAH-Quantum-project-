"use client";

/** Overall scores for every detector, switchable between splits and sortable by column. */

import { useState } from "react";
import type { Detector, OverallMetrics, Split } from "../lib/types.ts";
import { fmt, pct } from "../lib/format.ts";
import { SortDown } from "../app/icons.tsx";

type Column = {
  key: keyof OverallMetrics;
  label: string;
  /** Lower is better for counts of misses and false alarms. */
  lowerIsBetter?: boolean;
  render: (value: number) => string;
};

const COLUMNS: Column[] = [
  { key: "mAP50", label: "mAP50", render: (v) => fmt(v) },
  { key: "mAP50_95", label: "mAP50-95", render: (v) => fmt(v) },
  { key: "recall_at_conf025", label: "Recall @.25", render: (v) => fmt(v) },
  { key: "missed_at_conf025", label: "Missed", lowerIsBetter: true, render: (v) => String(v) },
  { key: "false_alarms_at_conf025", label: "False alarms", lowerIsBetter: true, render: (v) => String(v) },
  { key: "image_hit_rate_at_conf025", label: "Images hit", render: (v) => pct(v, 1) },
];

export default function Leaderboard({
  detectors,
  boxes,
}: {
  detectors: Detector[];
  boxes: Record<Split, number>;
}) {
  const [split, setSplit] = useState<Split>("test");
  const [sortKey, setSortKey] = useState<keyof OverallMetrics>("mAP50_95");

  const column = COLUMNS.find((c) => c.key === sortKey)!;
  const rows = [...detectors].sort((a, b) => {
    const diff = b.metrics[split][sortKey] - a.metrics[split][sortKey];
    // Values that print the same are a tie; fall back to mAP50 so ties read sensibly.
    if (Math.abs(diff) < 5e-4) return b.metrics[split].mAP50 - a.metrics[split].mAP50;
    return column.lowerIsBetter ? -diff : diff;
  });

  const best = Object.fromEntries(
    COLUMNS.map((c) => {
      const values = detectors.map((d) => d.metrics[split][c.key]);
      return [c.key, c.lowerIsBetter ? Math.min(...values) : Math.max(...values)];
    }),
  );

  return (
    <div className="stack">
      <div className="section-bar">
        <div className="tabs" role="tablist" aria-label="Split">
          {(["test", "val"] as const).map((s) => (
            <button key={s} role="tab" aria-selected={split === s} onClick={() => setSplit(s)}>
              {s === "test" ? "Test split" : "Validation split"}
            </button>
          ))}
        </div>
        <span className="caption" style={{ marginTop: 0 }}>
          {boxes[split]} labelled boxes. Bold marks the best value in each column.
        </span>
      </div>

      <div className="card card-lift" style={{ padding: "1.25rem 1.25rem 0.5rem" }}>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Model</th>
                {COLUMNS.map((c) => (
                  <th key={c.key} className="num">
                    <button
                      className="sort"
                      aria-pressed={sortKey === c.key}
                      onClick={() => setSortKey(c.key)}
                    >
                      {c.label}
                      {sortKey === c.key && <SortDown />}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((d) => (
                <tr key={d.id} className={d.status === "recommended" ? "row-ref" : undefined}>
                  <td>
                    <span className={`verdict verdict-${d.status}`}>
                      <a href={`/models/${d.id}`}>{d.label}</a>
                    </span>
                    {!d.registered && <span className="tag">unregistered</span>}
                  </td>
                  {COLUMNS.map((c) => {
                    const value = d.metrics[split][c.key];
                    return (
                      <td key={c.key} className="num">
                        <span className={`n ${value === best[c.key] ? "n-best" : ""}`}>
                          {c.render(value)}
                        </span>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
