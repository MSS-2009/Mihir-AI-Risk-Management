"use client";
import { ElementType, ReactNode, useEffect, useRef, useState } from "react";

/**
 * Returns a class to apply. Content is visible by default; only elements that
 * start below the fold get `sf-armed` (hidden) and then `sf-in` on scroll, so
 * there is never a flash of invisible text on load.
 */
function useScrollFloat<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [cls, setCls] = useState("");
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const belowFold = rect.top > window.innerHeight * 0.9;
    if (!belowFold) return; // in or above view: stay visible, no animation
    setCls("sf-armed");

    let done = false;
    const reveal = () => {
      if (done) return;
      done = true;
      setCls("sf-armed sf-in");
      io.disconnect();
      window.removeEventListener("scroll", onScroll);
    };
    // Primary: IntersectionObserver.
    const io = new IntersectionObserver(
      ([e]) => e.isIntersecting && reveal(),
      { threshold: 0.15, rootMargin: "0px 0px -6% 0px" }
    );
    io.observe(el);
    // Failsafe: a passive scroll listener, in case IO does not fire.
    const onScroll = () => {
      if (el.getBoundingClientRect().top < window.innerHeight * 0.9) reveal();
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      io.disconnect();
      window.removeEventListener("scroll", onScroll);
    };
  }, []);
  return { ref, cls };
}

type Segment = { text: string; className?: string };

/**
 * ScrollFloat: title text whose characters float + rotate up as the element
 * scrolls into view, staggered left to right. Words never break mid-line.
 */
export function ScrollFloat({
  segments,
  as: Tag = "h2",
  className = "",
  stagger = 16,
}: {
  segments: Segment[];
  as?: ElementType;
  className?: string;
  stagger?: number;
}) {
  const { ref, cls } = useScrollFloat<HTMLElement>();
  let idx = 0;
  return (
    <Tag ref={ref as any} className={`${className} ${cls}`} aria-label={segments.map((s) => s.text).join(" ")}>
      {segments.map((seg, si) => (
        <span key={si} className={seg.className}>
          {seg.text.split(/(\s+)/).map((word, wi) => {
            if (/^\s+$/.test(word)) return <span key={wi}> </span>;
            return (
              <span key={wi} className="inline-block whitespace-nowrap" aria-hidden>
                {word.split("").map((ch, ci) => (
                  <span key={ci} className="sf-char" style={{ transitionDelay: `${Math.min(idx++, 34) * stagger}ms` }}>
                    {ch}
                  </span>
                ))}
              </span>
            );
          })}
          {si < segments.length - 1 ? <span aria-hidden> </span> : null}
        </span>
      ))}
    </Tag>
  );
}

/** A simple two-tone title (lead in ink, accent word in crimson) with ScrollFloat. */
export function FloatTitle({
  lead,
  accent,
  as = "h2",
  className = "",
}: {
  lead: string;
  accent?: string;
  as?: ElementType;
  className?: string;
}) {
  const segments: Segment[] = [{ text: lead, className: "text-ink" }];
  if (accent) segments.push({ text: accent, className: "text-bordeaux" });
  return <ScrollFloat segments={segments} as={as} className={className} />;
}

/** Block reveal for body text and cards: fade + rise on scroll into view. */
export function ScrollReveal({
  children,
  className = "",
  delay = 0,
  as: Tag = "div",
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
  as?: ElementType;
}) {
  const { ref, cls } = useScrollFloat<HTMLElement>();
  return (
    <Tag ref={ref as any} className={`sf-block ${cls} ${className}`} style={{ transitionDelay: `${delay}ms` }}>
      {children}
    </Tag>
  );
}
