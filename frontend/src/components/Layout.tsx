import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";

const NAV = [
  { to: "/", label: "Dashboard", icon: "▚", end: true },
  { to: "/workspace", label: "SQL Workspace", icon: "⌘" },
  { to: "/performance", label: "Performance Lab", icon: "⚡" },
  { to: "/customers", label: "Customer Analytics", icon: "◵" },
  { to: "/ai", label: "AI Analyst", icon: "✦" },
  { to: "/data-quality", label: "Data Quality", icon: "✓" },
  { to: "/recommendations", label: "Recommendations", icon: "➤" },
];

export function Layout({ children, meta }: { children: ReactNode; meta: any }) {
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="dot" />
          <b>XenoPulse</b>
        </div>
        <nav>
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => (isActive ? "active" : "")}>
              <span aria-hidden>{n.icon}</span>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="foot">
          v{meta?.version ?? "—"} · AI:{" "}
          {meta?.ai_enabled ? `on (${meta.ai_model})` : "rule-based fallback"}
          <br />
          Synthetic data only.
        </div>
      </aside>
      <div className="main">
        <div className="topbar">
          <div className="row">
            <strong>Retail &amp; Loyalty Analytics</strong>
          </div>
          <span className="synthetic">SYNTHETIC DATA · DEMO</span>
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
