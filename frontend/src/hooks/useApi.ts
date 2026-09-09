import { useCallback, useEffect, useRef, useState } from "react";

interface State<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

/** Run an async loader on mount (and when `deps` change). */
export function useApi<T>(loader: () => Promise<T>, deps: unknown[] = []) {
  const [state, setState] = useState<State<T>>({
    data: null,
    loading: true,
    error: null,
  });
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  const reload = useCallback(() => {
    let alive = true;
    setState((s) => ({ ...s, loading: true, error: null }));
    loaderRef
      .current()
      .then((data) => alive && setState({ data, loading: false, error: null }))
      .catch(
        (e) =>
          alive &&
          setState({ data: null, loading: false, error: e.message ?? String(e) }),
      );
    return () => {
      alive = false;
    };
  }, []);

  useEffect(reload, deps); // eslint-disable-line react-hooks/exhaustive-deps

  return { ...state, reload };
}

/** Imperative async action with loading/error tracking. */
export function useAction<TArgs extends unknown[], TResult>(
  fn: (...args: TArgs) => Promise<TResult>,
) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<TResult | null>(null);

  const run = useCallback(
    async (...args: TArgs) => {
      setLoading(true);
      setError(null);
      try {
        const result = await fn(...args);
        setData(result);
        return result;
      } catch (e: any) {
        setError(e?.message ?? String(e));
        return null;
      } finally {
        setLoading(false);
      }
    },
    [fn],
  );

  return { run, loading, error, data, setData };
}
