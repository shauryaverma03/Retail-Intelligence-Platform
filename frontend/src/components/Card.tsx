import type { ReactNode } from "react";

export function Card({
  title,
  sub,
  right,
  className = "",
  children,
}: {
  title?: ReactNode;
  sub?: ReactNode;
  right?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={`card ${className}`}>
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
