/** Test-split recall at conf 0.25 for every model and class, tinted by value. */

import type { Detector } from "../lib/types.ts";
import { className, fmt } from "../lib/format.ts";

/** Paper at 0.3 recall or below, full lime wash at 0.95 and above. */
function tint(value: number): string {
  const t = Math.max(0, Math.min(1, (value - 0.3) / 0.65));
  return `color-mix(in srgb, var(--lime) ${Math.round(t * 55)}%, var(--card))`;
}

export default function ClassMatrix({
  detectors,
  classes,
  weakClass,
}: {
  detectors: Detector[];
  classes: string[];
  weakClass: string;
}) {
  const rows = [...detectors].sort(
    (a, b) => b.metrics.test.recall_at_conf025 - a.metrics.test.recall_at_conf025,
  );
  const boxes = Object.fromEntries(
    detectors[0].per_class.test.map((c) => [c.class, c.gt_boxes]),
  );

  return (
    <div className="card card-lift" style={{ padding: "1.25rem 1.25rem 0.5rem" }}>
      <div className="table-wrap">
        <table className="matrix">
          <thead>
            <tr>
              <th>Model</th>
              {classes.map((c) => (
                <th key={c} className={`num ${c === weakClass ? "weak" : ""}`}>
                  {className(c)}
                  <small>{boxes[c]} boxes</small>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((d) => (
              <tr key={d.id}>
                <td>
                  <span className={`verdict verdict-${d.status}`}>
                    <a href={`/models/${d.id}`}>{d.label}</a>
                  </span>
                </td>
                {classes.map((c) => {
                  const value = d.per_class.test.find((r) => r.class === c)!.recall_at_conf025;
                  return (
                    <td key={c} className="cell" style={{ background: tint(value) }}>
                      <span className={`n ${value < 0.3 ? "n-bad" : ""}`}>{fmt(value, 2)}</span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
