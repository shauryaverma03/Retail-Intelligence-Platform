import type { ReactNode } from "react";

export function Card({
  title,
  sub,
  right,
  className = "",
  accent,
  animate = true,
  children,
}: {
  title?: ReactNode;
  sub?: ReactNode;
  right?: ReactNode;
  className?: string;
  accent?: string;
  animate?: boolean;
  children: ReactNode;
}) {
  return (
    <div
      className={`card ${animate ? "animate-in" : ""} ${className}`}
      style={accent ? ({ "--accent": accent } as React.CSSProperties) : undefined}
    >
      {(title || right) && (
        <div className="card-head">
          <h3>
            {title} {sub && <span className="sub">— {sub}</span>}
          </h3>
          {right}
        </div>
      )}
      {children}
    </div>
  );
}
