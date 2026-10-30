/** Number formatting shared by server and client components. */

/** Fixed-point without the leading zero, so columns of metrics stay narrow: .433 */
export function fmt(value: number, digits = 3): string {
  return value.toFixed(digits).replace(/^(-?)0\./, "$1.");
}

export function pct(value: number, digits = 0): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export function signed(value: number, digits = 3): string {
  return `${value >= 0 ? "+" : "−"}${fmt(Math.abs(value), digits)}`;
}

export function className(name: string): string {
  return name.replace(/_/g, " ");
}

/** Video time as m:ss.s, matching the timestamp burned into the annotated video. */
export function clock(seconds: number): string {
  const m = Math.floor(seconds / 60);
  return `${m}:${(seconds - m * 60).toFixed(1).padStart(4, "0")}`;
}
