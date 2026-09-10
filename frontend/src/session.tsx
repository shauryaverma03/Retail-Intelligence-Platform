import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api } from "./api";

export interface RecentQuery {
  id: number;
  sql: string;
  source: string;
  row_count: number | null;
  execution_ms: number | null;
  ok: boolean;
  created_at: string;
}

export interface SessionInfo {
  session_id: string;
  short_id: string;
  created_at: string;
  last_seen_at: string;
  tour_completed: boolean;
  preferences: Record<string, unknown>;
  request_count: number;
  is_new: boolean;
  recent_queries: RecentQuery[];
  cookie: Record<string, unknown>;
}

interface SessionCtx {
  session: SessionInfo | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  completeTour: () => Promise<void>;
  setPreference: (patch: Record<string, unknown>) => Promise<void>;
  clearSession: () => Promise<void>;
  tourOpen: boolean;
  openTour: () => void;
  closeTour: (completed: boolean) => void;
  markBooted: () => void;
}

const Ctx = createContext<SessionCtx | null>(null);

const TOUR_SEEN_KEY = "xeno_tour_seen";
const tourSeenLocally = () => {
  try {
    return localStorage.getItem(TOUR_SEEN_KEY) === "1";
  } catch {
    return false;
  }
};
const rememberTourSeen = () => {
  try {
    localStorage.setItem(TOUR_SEEN_KEY, "1");
  } catch {
    /* private mode / storage disabled */
  }
};

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tourOpen, setTourOpen] = useState(false);
  const [autoChecked, setAutoChecked] = useState(false);
  const [booted, setBooted] = useState(false);

  const markBooted = useCallback(() => setBooted(true), []);

  const refresh = useCallback(async () => {
    try {
      const s = await api.session();
      setSession(s);
      setError(null);
    } catch (e: any) {
      setError(e?.message ?? String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Auto-open the tour once — only after the app has actually booted, only if
  // neither the server session nor this browser has seen it, and after a short
  // beat so it never pops over a still-loading page.
  useEffect(() => {
    if (autoChecked || loading || !session || !booted) return;
    setAutoChecked(true);
    if (session.tour_completed || tourSeenLocally()) return;
    const t = setTimeout(() => setTourOpen(true), 1100);
    return () => clearTimeout(t);
  }, [autoChecked, loading, session, booted]);

  const completeTour = useCallback(async () => {
    rememberTourSeen(); // survives even if the session cookie doesn't persist
    try {
      await api.setTour(true);
    } catch {
      /* non-fatal */
    }
    setSession((s) => (s ? { ...s, tour_completed: true } : s));
  }, []);

  const setPreference = useCallback(async (patch: Record<string, unknown>) => {
    try {
      const { preferences } = await api.setPreferences(patch);
      setSession((s) => (s ? { ...s, preferences } : s));
    } catch {
      /* non-fatal */
    }
  }, []);

  const clearSession = useCallback(async () => {
    try {
      await api.clearSession();
    } catch {
      /* non-fatal */
    }
    await refresh();
  }, [refresh]);

  const openTour = useCallback(() => setTourOpen(true), []);
  const closeTour = useCallback(
    (completed: boolean) => {
      setTourOpen(false);
      if (completed) completeTour();
    },
    [completeTour],
  );

  const value = useMemo<SessionCtx>(
    () => ({
      session,
      loading,
      error,
      refresh,
      completeTour,
      setPreference,
      clearSession,
      tourOpen,
      openTour,
      closeTour,
      markBooted,
    }),
    [session, loading, error, refresh, completeTour, setPreference, clearSession, tourOpen, openTour, closeTour, markBooted],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSession(): SessionCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useSession must be used within <SessionProvider>");
  return ctx;
}
