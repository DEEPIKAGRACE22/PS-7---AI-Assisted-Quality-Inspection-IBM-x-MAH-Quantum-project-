/**
 * Dot-and-whisker chart of the paired-bootstrap gap between the reference
 * model and every other model. A whisker that crosses zero means the gap
 * could be chance, so it is drawn faint with a hollow point.
 */

import type { Detector } from "../lib/types.ts";
import { fmt } from "../lib/format.ts";

const WIDTH = 520;
const LABEL_W = 128;
const ROW_H = 30;
const TOP = 26;
const BOTTOM = 30;

export default function GapChart({
  detectors,
  metric,
  title,
  axisNote,
}: {
  detectors: Detector[];
  metric: "mAP50" | "mAP50_95";
  title: string;
  /** Plain-language reading of the x-axis, shown under the chart. */
  axisNote: string;
}) {
  const rows = detectors
    .filter((d) => d.gap_to_reference)
    .map((d) => ({ d, gap: d.gap_to_reference![metric] }))
    .sort((a, b) => a.gap.mean - b.gap.mean);

  const lo = Math.min(-0.02, ...rows.map((r) => r.gap.lo));
  const hi = Math.max(0.06, ...rows.map((r) => r.gap.hi));
  const min = Math.floor(lo * 50) / 50;
  const max = Math.ceil(hi * 50) / 50;
  const x = (v: number) => LABEL_W + ((v - min) / (max - min)) * (WIDTH - LABEL_W - 8);
  const height = TOP + rows.length * ROW_H + BOTTOM;

  const ticks: number[] = [];
  for (let t = min; t <= max + 1e-9; t += 0.02) ticks.push(Math.round(t * 100) / 100);

  return (
    <figure className="card" style={{ margin: 0, padding: "1.4rem 1.4rem 1.1rem" }}>
      <span className="label">{title}</span>
      <svg
        className="chart"
        viewBox={`0 0 ${WIDTH} ${height}`}
        role="img"
        aria-label={`${title}: gap from the reference model, with 95% intervals`}
        style={{ marginTop: "0.6rem" }}
      >
        {ticks.map((t) => (
          <g key={t}>
            <line
              className={t === 0 ? "zero-line" : "grid-line"}
              x1={x(t)} x2={x(t)} y1={TOP - 8} y2={height - BOTTOM + 4}
            />
            <text x={x(t)} y={height - 10} textAnchor="middle">
              {t === 0 ? "0" : `${t > 0 ? "+" : "−"}${fmt(Math.abs(t), 2)}`}
            </text>
          </g>
        ))}
        <text className="axis-label" x={x(0) + 6} y={TOP - 12}>REFERENCE AHEAD →</text>

        {rows.map(({ d, gap }, i) => {
          const y = TOP + i * ROW_H + ROW_H / 2;
          const noise = gap.lo <= 0;
          return (
            <g key={d.id}>
              <text className="model-label" x={0} y={y + 4}>{d.label}</text>
              <line
                className={`whisker ${noise ? "whisker-noise" : ""}`}
                x1={x(gap.lo)} x2={x(gap.hi)} y1={y} y2={y}
              />
              <circle className={noise ? "point-noise" : "point"} cx={x(gap.mean)} cy={y} r={4.2}>
                <title>{`${d.label}: ${fmt(gap.mean)} [${fmt(gap.lo)}, ${fmt(gap.hi)}]`}</title>
              </circle>
            </g>
          );
        })}
      </svg>
      <p className="caption" style={{ marginTop: "0.6rem" }}>
        {axisNote}
      </p>
      <p className="caption" style={{ marginTop: "0.2rem" }}>
        Hollow point, faint line: the interval crosses 0, so the gap could be chance.
      </p>
    </figure>
  );
}
