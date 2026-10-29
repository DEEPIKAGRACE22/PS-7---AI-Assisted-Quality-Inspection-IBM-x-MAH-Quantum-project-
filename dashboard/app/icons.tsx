/** Minimal line icons. Inline SVG — no icon dependency. */

type P = { className?: string };
const base = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

/** Brand: an inspection frame with one box found. */
export const Mark = ({ className = "brand-mark" }: P) => (
  <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
    <rect x="1.6" y="1.6" width="20.8" height="20.8" rx="6.4" fill="#0D0E0A" />
    <rect x="7.2" y="7.2" width="9.6" height="9.6" rx="1.6" fill="none" stroke="#C8F04B" strokeWidth="2" />
  </svg>
);

export const ArrowRight = ({ className }: P) => (
  <svg className={className} viewBox="0 0 24 24" aria-hidden="true" {...base}>
    <path d="M4.5 12h15M14 6.5l5.5 5.5L14 17.5" />
  </svg>
);

export const ArrowLeft = ({ className }: P) => (
  <svg className={className} viewBox="0 0 24 24" aria-hidden="true" {...base}>
    <path d="M19.5 12h-15M10 6.5 4.5 12l5.5 5.5" />
  </svg>
);

export const Warning = ({ className }: P) => (
  <svg className={className} viewBox="0 0 24 24" aria-hidden="true" {...base}>
    <path d="M12 3.8 21 19.5H3L12 3.8Z" />
    <path d="M12 10v4.2M12 17h.01" />
  </svg>
);

export const SortDown = ({ className }: P) => (
  <svg className={className} viewBox="0 0 10 10" aria-hidden="true" {...base} strokeWidth={1.4}>
    <path d="M2 3.5 5 6.5l3-3" />
  </svg>
);
