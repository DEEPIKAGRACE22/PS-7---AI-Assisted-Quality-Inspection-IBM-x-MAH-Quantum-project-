/** One detector: scores on both splits, per-class bars and what training produced it. */

import { notFound } from "next/navigation.js";
import { getEvaluation } from "../../../lib/data.ts";
import { fmt, pct, signed } from "../../../lib/format.ts";
import type { Split } from "../../../lib/types.ts";
import SiteHeader from "../../../components/SiteHeader.tsx";
import SiteFooter from "../../../components/SiteFooter.tsx";
import ClassBars from "../../../components/ClassBars.tsx";
import { ArrowLeft } from "../../icons.tsx";

export const dynamic = "force-dynamic";

const STATUS = {
  recommended: { label: "Use for now", className: "label-accent" },
  ok: { label: "Comparable", className: "" },
  do_not_use: { label: "Do not use", className: "label-fail" },
} as const;

export default async function ModelPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const evaluation = await getEvaluation();
  const d = evaluation.detectors.find((x) => x.id === id) ?? notFound();

  const status = STATUS[d.status];
  const rows: { label: string; render: (s: Split) => string }[] = [
    { label: "mAP50", render: (s) => fmt(d.metrics[s].mAP50) },
    { label: "mAP50-95", render: (s) => fmt(d.metrics[s].mAP50_95) },
    { label: "Precision", render: (s) => fmt(d.metrics[s].precision) },
    { label: "Recall", render: (s) => fmt(d.metrics[s].recall) },
    { label: "Recall @ conf 0.25", render: (s) => fmt(d.metrics[s].recall_at_conf025) },
    { label: "Missed defects", render: (s) => `${d.metrics[s].missed_at_conf025} / ${evaluation.splits[s].boxes}` },
    { label: "False alarms", render: (s) => String(d.metrics[s].false_alarms_at_conf025) },
    { label: "Images with a hit", render: (s) => pct(d.metrics[s].image_hit_rate_at_conf025, 1) },
  ];

  return (
    <>
      <SiteHeader generatedAt={evaluation.generated_at} />

      <main className="shell" style={{ paddingBottom: "var(--section)" }}>
        <div className="detail-head">
          <a href="/" className="btn btn-ghost" style={{ width: "fit-content" }}>
            <ArrowLeft className="tick" /> All models
          </a>
          <span className={`label ${status.className}`} style={{ marginTop: "1rem" }}>
            {status.label}
            {!d.registered && " · unregistered checkpoint"}
          </span>
          <h1>{d.label}</h1>
          <p className="lede">{d.notes}</p>
        </div>

        <div className="detail-grid">
          <div className="stack" style={{ gap: "1.5rem" }}>
            <div className="card card-lift" style={{ padding: "1.25rem 1.25rem 0.5rem" }}>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr><th>Metric</th><th className="num">Validation</th><th className="num">Test</th></tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr key={r.label}>
                        <td>{r.label}</td>
                        <td className="num"><span className="n">{r.render("val")}</span></td>
                        <td className="num"><span className="n">{r.render("test")}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {(["AP50", "recall_at_conf025"] as const).map((metric) => (
              <div className="card" key={metric}>
                <div className="section-bar">
                  <span className="label">
                    {metric === "AP50" ? "AP50 per class" : "Recall per class at conf 0.25"}
                  </span>
                  <span className="legend">
                    <span><i style={{ background: "var(--line-firm)" }} />Validation</span>
                    <span><i style={{ background: "var(--ink)" }} />Test</span>
                  </span>
                </div>
                <ClassBars perClass={d.per_class} metric={metric} />
              </div>
            ))}
          </div>

          <aside className="aside">
            <div className="aside-card">
              <h3>Trained on</h3>
              <p>{d.trained_on}.</p>
            </div>
            <div className="aside-card">
              <h3>Against {evaluation.reference_model}</h3>
              {d.gap_to_reference ? (
                <p>
                  The reference is ahead by{" "}
                  <span className="n">{signed(d.gap_to_reference.mAP50.mean)}</span> mAP50 (95%
                  interval <span className="n">{fmt(d.gap_to_reference.mAP50.lo)}</span> to{" "}
                  <span className="n">{fmt(d.gap_to_reference.mAP50.hi)}</span>).{" "}
                  {d.gap_to_reference.mAP50.lo <= 0
                    ? "The interval crosses zero, so the gap could be chance."
                    : "The interval excludes zero, so the gap is real on this test set."}
                </p>
              ) : (
                <p>This is the reference model the others are compared against.</p>
              )}
            </div>
            <div className="aside-card">
              <h3>Checkpoint</h3>
              <p>
                <code>
                  {d.registered ? `models/${d.checkpoint}/weights/best.pt` : d.checkpoint.replace("loose:", "models/")}
                </code>
              </p>
              <p style={{ marginTop: "0.5rem" }}>
                {d.size_mb} MB · about {Math.round(d.cpu_ms)} ms per image on an M2 CPU
              </p>
            </div>
          </aside>
        </div>
      </main>

      <SiteFooter />
    </>
  );
}
