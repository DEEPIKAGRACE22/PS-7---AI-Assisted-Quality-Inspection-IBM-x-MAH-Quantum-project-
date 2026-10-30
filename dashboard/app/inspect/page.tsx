/** Video inspection: upload a line video, get it back annotated, with an alert for every defect. */

import { getEvaluation, reference } from "../../lib/data.ts";
import SiteHeader from "../../components/SiteHeader.tsx";
import VideoInspector from "../../components/VideoInspector.tsx";

export const dynamic = "force-dynamic";

export const metadata = { title: "PS-7 Inspection — Inspect a video" };

export default async function InspectPage() {
  const evaluation = await getEvaluation();
  const model = reference(evaluation);

  return (
    <>
      <SiteHeader generatedAt={evaluation.generated_at} />

      <main className="shell" style={{ paddingBottom: "var(--section)" }}>
        <div className="detail-head">
          <span className="label label-accent">Video inspection · {model.label}</span>
          <h1>Run a line video through the model.</h1>
          <p className="lede">
            Every defect comes back boxed, with its confidence and the time it appears in the video. You get an
            alert the moment the first one is found.
          </p>
        </div>

        <VideoInspector modelLabel={model.label} />
      </main>
    </>
  );
}
