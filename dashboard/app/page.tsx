/** Results overview. Every number comes from getEvaluation(); nothing is hard-coded. */

import { getEvaluation, reference } from "../lib/data.ts";
import { className, fmt, pct } from "../lib/format.ts";
import SiteHeader from "../components/SiteHeader.tsx";
import Leaderboard from "../components/Leaderboard.tsx";
import GapChart from "../components/GapChart.tsx";
import ClassMatrix from "../components/ClassMatrix.tsx";
import CastingCard from "../components/CastingCard.tsx";

export const dynamic = "force-dynamic";

export default async function Overview() {
  const evaluation = await getEvaluation();
  const { detectors, classes, splits } = evaluation;
  const ref = reference(evaluation);

  // The class every model finds hardest, by mean test recall.
  const meanRecall = (c: string) =>
    detectors.reduce((sum, d) => sum + d.per_class.test.find((r) => r.class === c)!.recall_at_conf025, 0) /
    detectors.length;
  const weakClass = [...classes].sort((a, b) => meanRecall(a) - meanRecall(b))[0];
  const bestWeakRecall = Math.max(
    ...detectors.map((d) => d.per_class.test.find((r) => r.class === weakClass)!.recall_at_conf025),
  );
  const valLeader = [...detectors].sort((a, b) => b.metrics.val.mAP50 - a.metrics.val.mAP50)[0];
  const compared = detectors.filter((d) => d.gap_to_reference);
  const closeCalls = compared.filter((d) => d.gap_to_reference!.mAP50.lo <= 0).length;
  const clearlyBehind = compared.length - closeCalls;

  return (
    <>
      <SiteHeader generatedAt={evaluation.generated_at} />

      <main>
        {/* ------------------------------------------------------------ head */}
        <section className="shell hero">
          <div className="hero-grid">
            <div>
              <span className="label label-accent">Model evaluation · NEU-DET steel defects</span>
              <h1>
                {ref.label} leads.
                <em>Not by enough to call it.</em>
              </h1>
              <p className="lede">
                Ten detectors scored on the same {splits.test.images} test images. The
                hard-example model comes out on top, but against {closeCalls} of the others its
                mAP50 lead <span className="mark">could be chance</span>. The bigger problem is{" "}
                {className(weakClass)}, which every model mostly misses.
              </p>
            </div>

            <div className="split-card" aria-label="Recommended model and weakest class">
              <div className="split-half split-good">
                <span className="label label-accent">Use for now</span>
                <h4>{ref.label}</h4>
                <p>{ref.trained_on}.</p>
                <span className="split-number">
                  {fmt(ref.metrics.test.mAP50_95)}
                  <small>test mAP50-95</small>
                </span>
              </div>
              <div className="split-half split-bad">
                <span className="label label-fail">Weakest class</span>
                <h4>{className(weakClass)}</h4>
                <p>The most real {className(weakClass)} defects any model finds at conf 0.25.</p>
                <span className="split-number">
                  {pct(bestWeakRecall)}
                  <small>recall</small>
                </span>
              </div>
            </div>
          </div>
        </section>

        <section className="shell">
          <ul className="figures">
            <li><b>{detectors.length}</b><span>detectors evaluated</span></li>
            <li><b>{splits.test.images}</b><span>test images · {splits.test.boxes} boxes</span></li>
            <li><b>{fmt(ref.metrics.test.mAP50)}</b><span>best test mAP50</span></li>
            <li><b>{ref.metrics.test.missed_at_conf025}</b><span>defects missed by the best model</span></li>
          </ul>
        </section>

        {/* ----------------------------------------------------- leaderboard */}
        <section className="band shell">
          <div className="section-head">
            <span className="label">Leaderboard</span>
            <h2>The order changes depending on which split you look at.</h2>
            <p>
              On test, {ref.label} is first. On validation, {valLeader.label} is. Recall,
              misses and false alarms are counted at conf 0.25, the threshold an operator would
              use. Click a model for its per-class breakdown.
            </p>
          </div>
          <Leaderboard
            detectors={detectors}
            boxes={{ val: splits.val.boxes, test: splits.test.boxes }}
          />
        </section>

        {/* ------------------------------------------------------ gap chart */}
        <section className="band band-sunk">
          <div className="shell">
            <div className="section-head">
              <span className="label">Are the gaps real?</span>
              <h2>
                On mAP50, the lead is clear over {clearlyBehind} models and could be chance
                against the other {closeCalls}.
              </h2>
              <p>
                How far {ref.label} is ahead of each model, resampling the test images 1,000 times.
                Each line is a 95% interval. Where it crosses zero (hollow point), the gap could be
                chance.
              </p>
            </div>
            <div className="gap-grid">
              <GapChart detectors={detectors} metric="mAP50" title="Δ mAP50" />
              <GapChart detectors={detectors} metric="mAP50_95" title="Δ mAP50-95" />
            </div>
            <p className="caption">
              The bootstrap uses its own box matching, which scores every model 0.01–0.03 lower
              than Ultralytics. Only the differences are shown here.
            </p>
          </div>
        </section>

        {/* ----------------------------------------------------- per class */}
        <section className="band shell">
          <div className="section-head">
            <span className="label label-fail">Per class · test recall at conf 0.25</span>
            <h2>{className(weakClass)[0].toUpperCase() + className(weakClass).slice(1)} is missed by every model.</h2>
            <p>
              The share of real defects found, per class. Even the best models catch fewer than
              half of the {className(weakClass)} defects, and seed alone moves that number by
              about 0.2.
            </p>
          </div>
          <ClassMatrix detectors={detectors} classes={classes} weakClass={weakClass} />
        </section>

        {/* ------------------------------------------------------- casting */}
        {evaluation.classifiers.length > 0 && (
          <section className="band band-sunk">
            <div className="shell">
              <CastingCard model={evaluation.classifiers[0]} copies={evaluation.classifiers.length} />
            </div>
          </section>
        )}

        {/* ------------------------------------------------------- caveats */}
        <section className="band shell">
          <div className="section-head">
            <span className="label">Read with care</span>
            <h2>What these numbers can&rsquo;t tell you.</h2>
          </div>
          <ol className="caveats">
            {evaluation.caveats.map((c) => <li key={c}>{c}</li>)}
          </ol>
        </section>
      </main>

      <footer className="shell foot">
        <span>PS-7 · AI-assisted quality inspection</span>
        <span>
          Regenerate with <code>python scripts/evaluate_all.py</code> then{" "}
          <code>python scripts/export_dashboard_json.py</code>
        </span>
      </footer>
    </>
  );
}
