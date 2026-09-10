import { useEffect, useState } from "react";
import { Route, Routes, useLocation } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Tour } from "./components/Tour";
import { BootSplash, ErrorState } from "./components/States";
import { useApi } from "./hooks/useApi";
import { api } from "./api";
import { SessionProvider, useSession } from "./session";
import { Dashboard } from "./pages/Dashboard";
import { SqlWorkspace } from "./pages/SqlWorkspace";
import { PerformanceLab } from "./pages/PerformanceLab";
import { CustomerAnalytics } from "./pages/CustomerAnalytics";
import { AiAnalyst } from "./pages/AiAnalyst";
import { DataQuality } from "./pages/DataQuality";
import { Recommendations } from "./pages/Recommendations";

function Shell({ meta }: { meta: any }) {
  const { tourOpen, closeTour } = useSession();
  const location = useLocation();

  return (
    <>
      <Layout meta={meta}>
        <div className="route-fade" key={location.pathname}>
          <Routes location={location}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/workspace" element={<SqlWorkspace />} />
            <Route path="/performance" element={<PerformanceLab />} />
            <Route path="/customers" element={<CustomerAnalytics />} />
            <Route path="/ai" element={<AiAnalyst meta={meta} />} />
            <Route path="/data-quality" element={<DataQuality />} />
            <Route path="/recommendations" element={<Recommendations />} />
            <Route path="*" element={<div className="state">Page not found.</div>} />
          </Routes>
        </div>
      </Layout>
      <Tour open={tourOpen} onClose={closeTour} />
    </>
  );
}

/** Hold the app behind a splash until /api/meta + the session have loaded. */
function Boot() {
  const { data: meta, loading, error, reload } = useApi(() => api.meta(), []);
  const { loading: sessionLoading, markBooted } = useSession();
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setSlow(true), 5000);
    return () => clearTimeout(t);
  }, []);

  const ready = !loading && !sessionLoading && meta;

  useEffect(() => {
    if (ready) markBooted();
  }, [ready, markBooted]);

  if (error && !loading) {
    return (
      <div className="boot">
        <ErrorState message={error} onRetry={reload} />
      </div>
    );
  }
  if (!ready) return <BootSplash slow={slow} />;
  return <Shell meta={meta} />;
}

export default function App() {
  return (
    <SessionProvider>
      <Boot />
    </SessionProvider>
  );
}
