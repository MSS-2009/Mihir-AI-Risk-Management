"use client";
import { useEffect, useState } from "react";

/**
 * Light is the default and the canonical artifact: it matches the board deck
 * this output gets pasted into. Dark is for the dim demo room.
 */
export function ThemeToggle() {
  const [dark, setDark] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const saved = window.localStorage.getItem("avenoir.theme");
    const isDark = saved === "dark";
    setDark(isDark);
    document.documentElement.classList.toggle("dark", isDark);
    setMounted(true);
  }, []);

  const toggle = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    window.localStorage.setItem("avenoir.theme", next ? "dark" : "light");
  };

  return (
    <button
      onClick={toggle}
      aria-label={mounted ? `Switch to ${dark ? "light" : "dark"} mode` : "Toggle colour mode"}
      aria-pressed={dark}
      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-rule text-muted transition-colors hover:border-brand hover:text-brand"
    >
      <span aria-hidden className="text-[0.85rem] leading-none">{mounted && dark ? "☀" : "☾"}</span>
    </button>
  );
}
