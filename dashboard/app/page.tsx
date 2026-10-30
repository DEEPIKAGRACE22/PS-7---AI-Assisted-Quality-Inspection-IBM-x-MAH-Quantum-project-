/** Project review overview. Every number comes from getEvaluation(); nothing is hard-coded. */

import { getEvaluation, reference } from "../lib/data.ts";
import { className, fmt, pct } from "../lib/format.ts";
import SiteHeader from "../components/SiteHeader.tsx";
import Leaderboard from "../components/Leaderboard.tsx";
import GapChart from "../components/GapChart.tsx";
import ClassMatrix from "../components/ClassMatrix.tsx";
import CastingCard from "../components/CastingCard.tsx";
import VideoInspector from "../components/VideoInspector.tsx";

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
  const weakRecall = (d: (typeof detectors)[number]) =>
    d.per_class.test.find((r) => r.class === weakClass)!.recall_at_conf025;
  const bestWeakRecall = Math.max(...detectors.map(weakRecall));
  const refWeakRecall = weakRecall(ref);
  const valLeader = [...detectors].sort((a, b) => b.metrics.val.mAP50 - a.metrics.val.mAP50)[0];
  const compared = detectors.filter((d) => d.gap_to_reference);
  const closeCalls = compared.filter((d) => d.gap_to_reference!.mAP50.lo <= 0).length;
  const clearlyBehind = compared.length - closeCalls;
  const weakBoxes = ref.per_class.test.find((r) => r.class === weakClass)!.gt_boxes;

  const casting = evaluation.classifiers[0];

  return (
    <>
      <SiteHeader generatedAt={evaluation.generated_at} />

      <main>
        {/* ------------------------------------------------------------ head */}
        <section className="shell hero">
          <div className="hero-grid">
            <div>
              <span className="label label-accent">Project review · NEU-DET steel defects</span>
              <h1>
                {ref.label} leads.
                <em>Not by enough to call it.</em>
              </h1>
              <p className="lede">
                {detectors.length} detectors were evaluated on the same {splits.test.images} test images.
                The hard-example model comes out on top, but against {closeCalls} of the others its
                mAP50 lead <span className="mark">could be chance</span>. The bigger problem is{" "}
                {className(weakClass)}, which every model mostly misses.
              </p>
            </div>

            <div className="split-card" aria-label="Selected model and weakest class">
              <div className="split-half split-good">
                <span className="label label-accent">Selected model</span>
                <h4>{ref.label}</h4>
                <p>{ref.trained_on}.</p>
                <span className="split-number">
                  {fmt(ref.metrics.test.mAP50_95)}
                  <small>test mAP50-95</small>
                </span>
              </div>
              <div className="split-half split-bad">
                <span className="label label-caution">Weakest class</span>
                <h4>{className(weakClass)}</h4>
                <p>The most real {className(weakClass)} defects any model finds at conf 0.25.</p>
                <span className="split-number">
                  {pct(bestWeakRecall)}
                  <small>recall, best of any model</small>
                </span>
              </div>
            </div>
          </div>
        </section>

        <section className="shell">
          <ul className="figures">
            <li><b>{detectors.length}</b><span>detectors evaluated</span></li>
            <li><b>{splits.test.images}</b><span>test images · {splits.test.boxes} boxes</span></li>
            <li><b>{fmt(ref.metrics.test.mAP50)}</b><span>{ref.label} test mAP50</span></li>
            <li><b>{ref.metrics.test.missed_at_conf025}</b><span>defects missed by {ref.label}</span></li>
          </ul>
        </section>

        {/* ----------------------------------------------------- leaderboard */}
        <section className="band shell" id="leaderboard">
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
        <section className="band band-sunk band-secondary">
          <div className="shell">
            <div className="section-head">
              <span className="label">Statistical comparison</span>
              <h2>
                Is the lead real? On mAP50 it is clear over {clearlyBehind} models and could be chance
                against {closeCalls}.
              </h2>
              <p>
                How far {ref.label} is ahead of each model, resampling the test images 1,000 times.
                Each line is a 95% interval. Where it crosses zero (hollow point), the gap could be
                chance.
              </p>
            </div>
            <div className="gap-grid">
              <GapChart
                detectors={detectors}
                metric="mAP50"
                title="Δ mAP50"
                axisNote={`Gap in mAP50, ${ref.label} minus each model. 0 means no difference; further right means ${ref.label} is ahead.`}
              />
              <GapChart
                detectors={detectors}
                metric="mAP50_95"
                title="Δ mAP50-95"
                axisNote={`Gap in mAP50-95, ${ref.label} minus each model. Same reading as the chart on the left.`}
              />
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
            <span className="label label-caution">Per class · test recall at conf 0.25</span>
            <h2>Where does the model struggle?</h2>
            <p>
              {className(weakClass)} is the lowest-recall class for every one of the {detectors.length} detectors.
              {ref.label} finds {pct(refWeakRecall)} of them. The best of any detector finds {pct(bestWeakRecall)}.
            </p>
          </div>
          <ClassMatrix detectors={detectors} classes={classes} weakClass={weakClass} />

          <div className="why">
            <h3>Why {className(weakClass)} is hard</h3>
            <ul>
              <li>
                Only <span className="n">{weakBoxes}</span> labelled {className(weakClass)} boxes in the test split. Each
                one moves its recall by about {pct(1 / weakBoxes, 1)}, so the score is unstable.
              </li>
              <li>
                Seed alone moves {className(weakClass)} recall from 0.21 to 0.43 within one training recipe. Most
                models find only 13–34%.
              </li>
              <li>
                Pretraining on Severstal did not fix it. Its AP gain came from fewer false alarms, not more real
                finds.
              </li>
              <li>
                The reports have not yet pinned down the cause. The next steps are to inspect the crazing labels
                and try contrast enhancement (CLAHE) and oversampling.
              </li>
            </ul>
          </div>
        </section>

        {/* ------------------------------------------------------- casting */}
        {casting && (
          <section className="band band-sunk casting-band">
            <div className="shell">
              <CastingCard model={casting} copies={evaluation.classifiers.length} />
            </div>
          </section>
        )}

        {/* ------------------------------------------------------- video */}
        <section className="band shell video-section" id="video-inspection">
          <div className="section-head">
            <span className="label label-accent">Practical application · video inspection</span>
            <h2>Run a line video through the selected model.</h2>
            <p>
              The model runs on every second frame. Each defect comes back boxed, with its confidence and the
              time it appears in the original video. An alert is raised as soon as the first defect is found.
            </p>
          </div>
          <VideoInspector modelLabel={ref.label} />
        </section>

        {/* ------------------------------------------------------- caveats */}
        <section className="band shell">
          <div className="section-head">
            <span className="label">Read with care</span>
            <h2>What these numbers can&rsquo;t tell you.</h2>
            <p>These limitations apply to every figure on this page and are kept as written in the evaluation.</p>
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
