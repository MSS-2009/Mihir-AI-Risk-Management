import Link from "next/link";
import { ReactNode } from "react";
import { ScrollFloat, ScrollReveal } from "./ScrollFloat";

export function Card({
  children,
  className = "",
  as: Tag = "div",
}: {
  children: ReactNode;
  className?: string;
  as?: any;
}) {
  return (
    <Tag className={`rounded-2xl border border-mist bg-surface shadow-card ${className}`}>{children}</Tag>
  );
}

export function Eyebrow({ children }: { children: ReactNode }) {
  return <div className="eyebrow">{children}</div>;
}

export function Button({
  children,
  href,
  onClick,
  variant = "primary",
  type = "button",
  disabled,
  className = "",
}: {
  children: ReactNode;
  href?: string;
  onClick?: () => void;
  variant?: "primary" | "ghost" | "outline";
  type?: "button" | "submit";
  disabled?: boolean;
  className?: string;
}) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed";
  const styles = {
    primary: "bg-bordeaux text-white hover:bg-bordeaux-deep",
    outline: "border border-mist-deep bg-surface text-ink hover:border-bordeaux hover:text-bordeaux",
    ghost: "text-ink/70 hover:bg-bordeaux/8 hover:text-bordeaux",
  }[variant];
  const cls = `${base} ${styles} ${className}`;
  if (href)
    return (
      <Link href={href} className={cls}>
        {children}
      </Link>
    );
  return (
    <button type={type} onClick={onClick} disabled={disabled} className={cls}>
      {children}
    </button>
  );
}

export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "bordeaux" | "ochre" | "muted";
}) {
  const styles = {
    neutral: "border-mist-deep bg-paper text-ink/70",
    bordeaux: "border-bordeaux/20 bg-bordeaux/8 text-bordeaux",
    ochre: "border-ochre/25 bg-ochre/10 text-ochre",
    muted: "border-mist bg-paper text-muted",
  }[tone];
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[0.66rem] uppercase tracking-wide ${styles}`}
    >
      {children}
    </span>
  );
}

/** A thin horizontal risk meter, the one place we translate magnitude to length. */
export function RiskBar({ value, max, tone = "bordeaux" }: { value: number; max: number; tone?: "bordeaux" | "ochre" }) {
  const w = max > 0 ? Math.min(100, Math.max(2, (value / max) * 100)) : 0;
  const color = tone === "ochre" ? "bg-ochre" : "bg-bordeaux";
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-mist" aria-hidden>
      <div className={`h-full rounded-full ${color}`} style={{ width: `${w}%` }} />
    </div>
  );
}

export function SectionHeading({
  eyebrow,
  title,
  accent,
  intro,
}: {
  eyebrow?: string;
  title: string;
  accent?: string;
  intro?: string;
}) {
  const segments = accent
    ? [{ text: title, className: "text-ink" }, { text: accent, className: "text-bordeaux" }]
    : [{ text: title, className: "text-ink" }];
  return (
    <div className="max-w-2xl">
      {eyebrow && <Eyebrow>{eyebrow}</Eyebrow>}
      <ScrollFloat
        segments={segments}
        as="h2"
        className="mt-2 font-display text-3xl font-bold tracking-tight sm:text-4xl"
      />
      <span className="mt-3 block h-[3px] w-12 rounded-full bg-bordeaux" />
      {intro && (
        <ScrollReveal as="p" className="mt-4 text-muted" delay={80}>
          {intro}
        </ScrollReveal>
      )}
    </div>
  );
}
