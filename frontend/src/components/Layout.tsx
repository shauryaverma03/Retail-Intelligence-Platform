import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { useSession } from "../session";

const NAV = [
  { to: "/", label: "Dashboard", icon: "▚", end: true, tour: "nav-dashboard" },
  { to: "/workspace", label: "SQL Workspace", icon: "⌘", tour: "nav-workspace" },
  { to: "/performance", label: "Performance Lab", icon: "⚡", tour: "nav-performance" },
  { to: "/customers", label: "Customer Analytics", icon: "◵", tour: "nav-customers" },
  { to: "/ai", label: "AI Analyst", icon: "✦", tour: "nav-ai" },
  { to: "/data-quality", label: "Data Quality", icon: "✓", tour: "nav-dq" },
  { to: "/recommendations", label: "Recommendations", icon: "➤", tour: "nav-recs" },
];

export function Layout({ children, meta }: { children: ReactNode; meta: any }) {
  const { session, openTour } = useSession();

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="dot" />
          <b>XenoPulse</b>
        </div>
        <nav>
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              data-tour={n.tour}
              className={({ isActive }) => (isActive ? "active" : "")}
            >
              <span aria-hidden>{n.icon}</span>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="foot">
          v{meta?.version ?? "—"} · AI:{" "}
          {meta?.ai_enabled ? `on (${meta.ai_model})` : "rule-based fallback"}
          <br />
          {session && (
            <span className="session-badge" title={`Anonymous session ${session.short_id} · ${session.request_count} requests`}>
              <span className="swatch" />
              session {session.short_id}
            </span>
          )}
          <br />
          Synthetic data only.
        </div>
      </aside>
      <div className="main">
        <div className="topbar">
          <div className="row">
            <strong>Retail &amp; Loyalty Analytics</strong>
          </div>
          <div className="row">
            <button className="tourbtn" data-tour="tour-button" onClick={openTour}>
              <span aria-hidden>🧭</span> Take a tour
            </button>
            <span className="synthetic">SYNTHETIC DATA · DEMO</span>
          </div>
        </div>
        <div className="content">{children}</div>
      </div>
    </div>
  );
}

export function PageHeader({
  title,
  children,
  right,
}: {
  title: string;
  children?: ReactNode;
  right?: ReactNode;
}) {
  return (
    <div className="section-title">
      <div>
        <h1>{title}</h1>
        {children && <p className="muted">{children}</p>}
      </div>
      {right}
    </div>
  );
}
