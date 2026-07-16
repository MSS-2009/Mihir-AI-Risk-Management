"use client";
import { useCallback, useEffect, useRef } from "react";

/** Debounce a callback, used to throttle the backend-debounced live re-runs so
 * a dragging finger doesn't fire a Monte Carlo per frame. */
export function useDebouncedCallback<A extends any[]>(fn: (...args: A) => void, delay: number) {
  const timer = useRef<ReturnType<typeof setTimeout>>();
  const saved = useRef(fn);
  useEffect(() => {
    saved.current = fn;
  }, [fn]);
  useEffect(() => () => clearTimeout(timer.current), []);
  return useCallback(
    (...args: A) => {
      clearTimeout(timer.current);
      timer.current = setTimeout(() => saved.current(...args), delay);
    },
    [delay]
  );
}
