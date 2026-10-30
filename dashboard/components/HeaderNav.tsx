"use client";

/** Section links in the header. The link for the section currently in view is marked active. */

import { useEffect, useState } from "react";

export type NavItem = { label: string; href: string; section?: string; external?: boolean };

export default function HeaderNav({ items }: { items: NavItem[] }) {
  const [active, setActive] = useState<string | null>(null);

  useEffect(() => {
    const ids = items.flatMap((i) => (i.section ? [i.section] : []));
    const targets = ids.map((id) => document.getElementById(id)).filter((el): el is HTMLElement => el !== null);
    if (targets.length === 0) return;

    // A section counts as current while it crosses the upper part of the viewport.
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible.length > 0) setActive(visible[0].target.id);
      },
      { rootMargin: "-30% 0px -60% 0px" },
    );
    targets.forEach((t) => observer.observe(t));
    return () => observer.disconnect();
  }, [items]);

  return (
    <nav className="nav-links" aria-label="Sections">
      {items.map((item) => {
        const isActive = item.section !== undefined && item.section === active;
        return (
          <a
            key={item.label}
            href={item.href}
            className={`nav-link${isActive ? " is-active" : ""}`}
            aria-current={isActive ? "location" : undefined}
            {...(item.external ? { target: "_blank", rel: "noreferrer" } : {})}
          >
            {item.label}
          </a>
        );
      })}
    </nav>
  );
}
