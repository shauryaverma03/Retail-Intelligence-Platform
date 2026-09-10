export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="state">
      <div className="spinner" />
      {label}
    </div>
  );
}

/** Full-screen boot splash shown until the API responds (handles free-tier cold start). */
export function BootSplash({ slow }: { slow: boolean }) {
  return (
    <div className="boot">
      <div className="boot-mark">
        <span className="dot" />
        <b>XenoPulse</b>
      </div>
      <div className="boot-bar"><span /></div>
      <p className="boot-msg">
        {slow
          ? "The free host is waking up — this first load can take up to a minute."
          : "Starting up…"}
      </p>
      <p className="boot-sub">Retail &amp; Loyalty Analytics · synthetic data</p>
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="state error">
      <p>⚠ {message}</p>
      {onRetry && (
        <button className="primary" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}

export function EmptyState({ message = "No data to show." }: { message?: string }) {
  return <div className="state">{message}</div>;
}

/** Shimmer placeholders — used while a page's data loads. */
export function Skeleton({
  className = "",
  style,
}: {
  className?: string;
  style?: React.CSSProperties;
}) {
  return <div className={`skeleton ${className}`} style={style} />;
}

export function SkeletonDashboard() {
  return (
    <div className="route-fade">
      <Skeleton className="skel-line" style={{ width: 220, height: 26, marginBottom: 4 }} />
      <Skeleton className="skel-line" style={{ width: 380 }} />
      <div className="grid cols-4" style={{ marginTop: 18 }}>
        {Array.from({ length: 8 }).map((_, i) => (
          <div className="card" key={i} style={{ padding: 18 }}>
            <Skeleton className="skel-line" style={{ width: "55%" }} />
            <Skeleton className="skel-line" style={{ width: "70%", height: 26, margin: "12px 0 6px" }} />
            <Skeleton className="skel-line" style={{ width: "45%" }} />
          </div>
        ))}
      </div>
      <div className="grid cols-2" style={{ marginTop: 16 }}>
        {Array.from({ length: 2 }).map((_, i) => (
          <div className="card" key={i}>
            <Skeleton className="skel-line" style={{ width: "40%" }} />
            <Skeleton className="skel-chart" style={{ marginTop: 12 }} />
          </div>
        ))}
      </div>
    </div>
  );
}

export function SkeletonList({ rows = 5 }: { rows?: number }) {
  return (
    <div className="route-fade">
      <Skeleton className="skel-line" style={{ width: 200, height: 24, marginBottom: 16 }} />
      <div className="grid" style={{ gap: 12 }}>
        {Array.from({ length: rows }).map((_, i) => (
          <div className="card" key={i}>
            <Skeleton className="skel-line" style={{ width: "35%" }} />
            <Skeleton className="skel-line" style={{ width: "90%", marginTop: 10 }} />
            <Skeleton className="skel-line" style={{ width: "60%" }} />
          </div>
        ))}
      </div>
    </div>
  );
}
