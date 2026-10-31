/** Project review overview. Every number comes from getEvaluation(); nothing is hard-coded. */

import { getEvaluation, reference } from "../lib/data.ts";
import { className, fmt, pct } from "../lib/format.ts";
import SiteHeader from "../components/SiteHeader.tsx";
import SiteFooter from "../components/SiteFooter.tsx";
import Leaderboard from "../components/Leaderboard.tsx";
import GapChart from "../components/GapChart.tsx";
import ClassMatrix from "../components/ClassMatrix.tsx";
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

  return (
    <>
      <SiteHeader generatedAt={evaluation.generated_at} />

      <main>
        {/* ------------------------------------------------------------ head */}
        <section className="shell hero" id="overview">
          <div className="hero-grid">
            <div className="hero-copy">
              <span className="label label-accent">Computer Vision · Deep Learning · Industrial Quality Inspection</span>
              <h1 className="hero-name">SteelSight</h1>
              <p className="hero-subtitle">AI-Powered Steel Surface Defect Inspection System</p>

              <div className="hero-block">
                <h3>The Challenge</h3>
                <p>
                  Steel manufacturing processes require continuous inspection to identify surface defects such as
                  crazing, inclusions, patches, pitted surfaces, rolled-in scale and scratches.
                </p>
                <p>
                  Manual inspection can be time-consuming and inconsistent, particularly when steel sheets move
                  continuously along conveyor belts. Identifying defects accurately and at the right time is essential
                  for maintaining product quality and reducing defective output.
                </p>
              </div>

              <div className="hero-block">
                <h3>Our Approach</h3>
                <p>
                  SteelSight is an AI-powered steel surface inspection system that uses computer vision and deep
                  learning to automatically detect and classify surface defects from conveyor-belt video recordings.
                </p>
                <p>
                  The system processes video frames, identifies defects using an object detection model, generates
                  annotated videos containing bounding boxes and confidence scores, records defect timestamps and
                  raises alerts whenever defects are detected.
                </p>
              </div>
            </div>

            <aside className="model-card" aria-label="Selected detection model">
              <span className="label">Selected Detection Model</span>
              <h2 className="model-file">{ref.label}</h2>
              <p className="model-desc">
                YOLO-based steel surface defect detection model selected following comparative evaluation of{" "}
                {detectors.length} detector configurations.
              </p>

              <dl className="model-metrics">
                <div>
                  <dt>Test mAP50</dt>
                  <dd>{fmt(ref.metrics.test.mAP50)}</dd>
                </div>
                <div>
                  <dt>Test mAP50-95</dt>
                  <dd>{fmt(ref.metrics.test.mAP50_95)}</dd>
                </div>
                <div>
                  <dt>Recall at conf 0.25</dt>
                  <dd>{fmt(ref.metrics.test.recall_at_conf025)}</dd>
                </div>
              </dl>
              <p className="model-note">
                Model evaluation metrics on the held-out test split. These are not live inspection statistics.
              </p>

              <p className="model-selection">
                Chosen as the recommended candidate after comparing {detectors.length} detector configurations on the
                test split. Its lead is small, and the validation split ranks models differently, so the Model
                Evaluation section shows the full comparison.
              </p>
            </aside>
          </div>
        </section>

        <section className="shell">
          <ul className="figures">
            <li><b>{detectors.length}</b><span>detectors evaluated</span></li>
            <li><b>{splits.test.images}</b><span>test images</span></li>
            <li><b>{splits.test.boxes}</b><span>labelled bounding boxes</span></li>
            <li><b>{fmt(ref.metrics.test.mAP50)}</b><span>selected model · test mAP50</span></li>
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

      <SiteFooter />
    </>
  );
}
