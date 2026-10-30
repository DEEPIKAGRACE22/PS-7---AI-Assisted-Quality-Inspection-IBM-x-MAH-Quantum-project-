/** The casting classifier: reported versus measured, and where its errors fall. */

import type { Classifier } from "../lib/types.ts";
import { fmt, pct } from "../lib/format.ts";
export default function CastingCard({ model, copies }: { model: Classifier; copies: number }) {
  const [[defectHit, defectMissed], [okFlagged, okPassed]] = model.confusion_matrix;
  const defects = defectHit + defectMissed;

  return (
    <div className="feature">
      <div>
        <span className="kind-chip">Image classification · not NEU-DET detection</span>
        <span className="label">Casting Defect Classification – Evaluation</span>
        <h2>It lets through about one defective part in three.</h2>
        <p className="lede">
          On {model.test_images} held-out images it misses {defectMissed} of {defects} defective
          castings. When it does flag a part, it is almost always right, which is the cheaper of
          the two mistakes to make.
        </p>
        {copies > 1 && (
          <p className="caption">
            Both <code>.keras</code> files in the package give identical predictions; they are one
            model.
          </p>
        )}
      </div>

      <div className="stack">
        <div className="note" role="note">
          <span className="label label-caution">Reported accuracy differs from measured</span>
          <p className="note-figures">
            README reports <b>{pct(model.reported_accuracy, 1)}</b> · independently measured{" "}
            <b>{pct(model.accuracy, 1)}</b>
          </p>
          <p>
            The README figure comes from a notebook that read labels and predictions from a shuffled
            pipeline in two passes, so they did not line up. The measured figure is on the dataset&rsquo;s
            untouched test folder ({model.test_images} images). The two protocols differ, so this is not a
            like-for-like drop.
          </p>
        </div>

        <div className="card">
          <span className="label">Confusion matrix · {model.dataset}</span>
          <div className="cm" role="table" aria-label="Confusion matrix">
            <span />
            <span className="cm-head">Predicted defective</span>
            <span className="cm-head">Predicted ok</span>

            <span className="cm-side">Defective</span>
            <div className="cm-cell cm-right"><b>{defectHit}</b><span>caught</span></div>
            <div className="cm-cell cm-miss"><b>{defectMissed}</b><span>missed</span></div>

            <span className="cm-side">Ok</span>
            <div className="cm-cell"><b>{okFlagged}</b><span>false alarm</span></div>
            <div className="cm-cell cm-right"><b>{okPassed}</b><span>passed</span></div>
          </div>

          <dl className="kv">
            <div><dt>Defect recall</dt><dd>{fmt(model.defective_recall, 2)}</dd></div>
            <div><dt>Defect precision</dt><dd>{fmt(model.defective_precision, 2)}</dd></div>
            <div><dt>ROC AUC</dt><dd>{fmt(model.auc, 2)}</dd></div>
          </dl>
        </div>
      </div>
    </div>
  );
}
