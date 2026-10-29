/** One metric per class as paired bars: validation (light) above test (ink). */

import type { ClassMetrics, Split } from "../lib/types.ts";
import { className, fmt } from "../lib/format.ts";

export default function ClassBars({
  perClass,
  metric,
}: {
  perClass: Record<Split, ClassMetrics[]>;
  metric: "AP50" | "recall_at_conf025";
}) {
  return (
    <div className="bars">
      {perClass.test.map((test) => {
        const val = perClass.val.find((v) => v.class === test.class)!;
        return (
          <div className="bar-row" key={test.class}>
            <span className="bar-name">{className(test.class)}</span>
            <div className="bar-pair">
              {[
                { split: "val", value: val[metric] },
                { split: "test", value: test[metric] },
              ].map(({ split, value }) => (
                <div className={`bar bar-${split}`} key={split}>
                  <div className="bar-track">
                    <div className="bar-fill" style={{ width: `${value * 100}%` }} />
                  </div>
                  <span className="n">{fmt(value)}</span>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
