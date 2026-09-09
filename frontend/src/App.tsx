import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Tour } from "./components/Tour";
import { ErrorState, Loading } from "./components/States";
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

function Shell() {
  const { data: meta, loading, error, reload } = useApi(() => api.meta(), []);
  const { tourOpen, closeTour } = useSession();

  return (
    <>
      <Layout meta={meta}>
        {loading ? (
          <Loading label="Connecting to XenoPulse API…" />
        ) : error ? (
          <ErrorState message={error} onRetry={reload} />
        ) : (
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/workspace" element={<SqlWorkspace />} />
            <Route path="/performance" element={<PerformanceLab />} />
            <Route path="/customers" element={<CustomerAnalytics />} />
            <Route path="/ai" element={<AiAnalyst meta={meta} />} />
            <Route path="/data-quality" element={<DataQuality />} />
            <Route path="/recommendations" element={<Recommendations />} />
            <Route path="*" element={<div className="state">Page not found.</div>} />
          </Routes>
        )}
      </Layout>
      <Tour open={tourOpen} onClose={closeTour} />
    </>
  );
}

export default function App() {
  return (
    <SessionProvider>
      <Shell />
    </SessionProvider>
  );
}
