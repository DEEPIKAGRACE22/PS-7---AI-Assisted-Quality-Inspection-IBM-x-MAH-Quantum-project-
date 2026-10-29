/**
 * Where the dashboard gets its numbers. With EVAL_API_URL set, the payload is
 * fetched from the backend on every request; otherwise the bundled file built
 * by scripts/export_dashboard_json.py is used.
 */

import bundled from "../data/evaluation.json" with { type: "json" };
import type { Detector, Evaluation } from "./types.ts";

export async function getEvaluation(): Promise<Evaluation> {
  const url = process.env.EVAL_API_URL;
  if (!url) return bundled as Evaluation;

  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Evaluation API returned ${response.status} for ${url}`);
  }
  return (await response.json()) as Evaluation;
}

export function reference(evaluation: Evaluation): Detector {
  const found = evaluation.detectors.find((d) => d.status === "recommended");
  if (!found) throw new Error("Evaluation payload has no detector with status 'recommended'");
  return found;
}
