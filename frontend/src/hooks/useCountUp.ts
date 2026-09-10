import { useEffect, useRef, useState } from "react";

const prefersReduced =
  typeof window !== "undefined" &&
  window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/** Animate a number from 0 → `value` once, with an ease-out curve. */
export function useCountUp(value: number | null | undefined, durationMs = 750): number {
  const [display, setDisplay] = useState(() => (prefersReduced ? value ?? 0 : 0));
  const frame = useRef<number>();
  const from = useRef(0);

  useEffect(() => {
    if (value === null || value === undefined || Number.isNaN(value)) return;
    if (prefersReduced) {
      setDisplay(value);
      return;
    }
    const start = performance.now();
    const startVal = from.current;
    const delta = value - startVal;

    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs);
      const eased = 1 - Math.pow(1 - t, 3); // easeOutCubic
      setDisplay(startVal + delta * eased);
      if (t < 1) frame.current = requestAnimationFrame(tick);
      else from.current = value;
    };
    frame.current = requestAnimationFrame(tick);
    return () => {
      if (frame.current) cancelAnimationFrame(frame.current);
      from.current = value; // so a later change animates from here
    };
  }, [value, durationMs]);

  return display;
}
