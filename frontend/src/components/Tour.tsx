import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

interface Step {
  path: string;
  target: string | null; // CSS selector, or null for a centered card
  title: string;
  body: string;
}

const STEPS: Step[] = [
  {
    path: "/",
    target: null,
    title: "Welcome to XenoPulse",
    body: "A retail & loyalty analytics platform. Every number you see is computed live from a synthetic database — nothing is hardcoded. This quick tour shows what each section does.",
  },
  {
    path: "/",
    target: '[data-tour="nav-dashboard"]',
    title: "Business Dashboard",
    body: "Headline KPIs — customers, repeat-purchase rate, 90-day retention, AOV, campaign conversion, revenue at risk — each backed by a SQL query, plus revenue and customer-segment charts.",
  },
  {
    path: "/workspace",
    target: '[data-tour="nav-workspace"]',
    title: "SQL Workspace",
    body: "Pick a reviewed analytical question or write your own read-only SQL. You get results, execution time, rows returned and the EXPLAIN plan. Queries you run are saved to this session's history.",
  },
  {
    path: "/performance",
    target: '[data-tour="nav-performance"]',
    title: "Query Performance Lab",
    body: "Real before/after benchmarks: drop an index → EXPLAIN ANALYZE → create it → run again. Covers indexing, filtering before joins, avoiding SELECT *, covering indexes and partition pruning.",
  },
  {
    path: "/customers",
    target: '[data-tour="nav-customers"]',
    title: "Customer Analytics",
    body: "RFM segmentation, cohort retention, churn / inactivity buckets and at-risk high-value customers — each with the window-function SQL behind it on screen.",
  },
  {
    path: "/ai",
    target: '[data-tour="nav-ai"]',
    title: "AI Analyst",
    body: "Ask a business question in plain English. It generates SQL, validates it against the read-only guard, runs it, then summarises the actual rows with a recommendation. It never invents numbers.",
  },
  {
    path: "/data-quality",
    target: '[data-tour="nav-dq"]',
    title: "Data Quality",
    body: "12 SQL checks — missing values, duplicate IDs, invalid dates, duplicate orders, freshness, pipeline status. A few fail on purpose so you can see the checks catching real issues.",
  },
  {
    path: "/recommendations",
    target: '[data-tour="nav-recs"]',
    title: "Recommendations",
    body: "Each item is generated from a query in that request: Finding, Evidence (real numbers), Recommendation, Expected impact, Next step.",
  },
  {
    path: "/",
    target: '[data-tour="tour-button"]',
    title: "That's the tour",
    body: "Your session remembers you've seen this, so it won't pop up again. Replay it any time from “Take a tour”. All data is synthetic — explore freely.",
  },
];

interface Rect {
  top: number;
  left: number;
  width: number;
  height: number;
}

function findTarget(selector: string, tries = 20): Promise<Element | null> {
  return new Promise((resolve) => {
    let n = 0;
    const tick = () => {
      const el = document.querySelector(selector);
      if (el || n++ >= tries) return resolve(el);
      requestAnimationFrame(tick);
    };
    tick();
  });
}

export function Tour({
  open,
  onClose,
}: {
  open: boolean;
  onClose: (completed: boolean) => void;
}) {
  const [step, setStep] = useState(0);
  const [rect, setRect] = useState<Rect | null>(null);
  const navigate = useNavigate();
  const location = useLocation();
  const cardRef = useRef<HTMLDivElement>(null);

  const current = STEPS[step];
  const last = step === STEPS.length - 1;

  useEffect(() => {
    if (open) setStep(0);
  }, [open]);

  // navigate to the step's route, then locate + measure its target
  useEffect(() => {
    if (!open) return;
    let cancelled = false;

    (async () => {
      if (location.pathname !== current.path) {
        navigate(current.path);
        await new Promise((r) => setTimeout(r, 60));
      }
      if (cancelled) return;
      if (!current.target) {
        setRect(null);
        return;
      }
      const el = await findTarget(current.target);
      if (cancelled) return;
      if (!el) {
        setRect(null);
        return;
      }
      el.scrollIntoView({ block: "center", behavior: "smooth" });
      const r = el.getBoundingClientRect();
      setRect({ top: r.top, left: r.left, width: r.width, height: r.height });
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, step]);

  // keep the spotlight glued to the element on resize / scroll
  useLayoutEffect(() => {
    if (!open || !current.target) return;
    const update = () => {
      const el = document.querySelector(current.target as string);
      if (!el) return;
      const r = el.getBoundingClientRect();
      setRect({ top: r.top, left: r.left, width: r.width, height: r.height });
    };
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    return () => {
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, step]);

  const next = useCallback(
    () => (last ? onClose(true) : setStep((s) => s + 1)),
    [last, onClose],
  );
  const prev = useCallback(() => setStep((s) => Math.max(0, s - 1)), []);
  const skip = useCallback(() => onClose(true), [onClose]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") skip();
      else if (e.key === "ArrowRight" || e.key === "Enter") next();
      else if (e.key === "ArrowLeft") prev();
    };
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", onKey);
    };
  }, [open, next, prev, skip]);

  if (!open) return null;

  const pad = 6;
  const spot: Rect | null = rect
    ? {
        top: rect.top - pad,
        left: rect.left - pad,
        width: rect.width + pad * 2,
        height: rect.height + pad * 2,
      }
    : null;

  // card placement: centered when no target, else below (or above if low), clamped
  let cardStyle: React.CSSProperties = {
    left: "50%",
    top: "50%",
    transform: "translate(-50%, -50%)",
  };
  if (spot) {
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const cardW = Math.min(380, vw - 32);
    const below = spot.top + spot.height + 12;
    const placeBelow = below + 190 < vh;
    let left = spot.left + spot.width / 2 - cardW / 2;
    left = Math.max(16, Math.min(left, vw - cardW - 16));
    cardStyle = {
      left,
      width: cardW,
      transform: "none",
      ...(placeBelow
        ? { top: below }
        : { top: Math.max(16, spot.top - 12 - 200) }),
    };
  }

  return (
    <div className="tour-root" role="dialog" aria-modal="true" aria-label="Product tour">
      {spot ? (
        <div
          className="tour-spotlight"
          style={{
            top: spot.top,
            left: spot.left,
            width: spot.width,
            height: spot.height,
          }}
        />
      ) : (
        <div className="tour-scrim" />
      )}

      <div className="tour-card" style={cardStyle} ref={cardRef}>
        <button className="tour-x" onClick={skip} aria-label="Close tour">
          ✕
        </button>
        <div className="tour-step">
          Step {step + 1} of {STEPS.length}
        </div>
        <h3>{current.title}</h3>
        <p>{current.body}</p>
        <div className="tour-dots">
          {STEPS.map((_, i) => (
            <span key={i} className={i === step ? "on" : ""} />
          ))}
        </div>
        <div className="tour-actions">
          <button className="tour-skip" onClick={skip}>
            Skip
          </button>
          <div className="row" style={{ gap: 8 }}>
            <button onClick={prev} disabled={step === 0}>
              Back
            </button>
            <button className="primary" onClick={next}>
              {last ? "Finish" : "Next"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
