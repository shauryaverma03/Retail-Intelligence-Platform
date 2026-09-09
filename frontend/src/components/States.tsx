interface LoadingProps {
  label?: string;
}
export function Loading({ label = "Loading…" }: LoadingProps) {
  return (
    <div className="state">
      <div className="spinner" />
      {label}
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
