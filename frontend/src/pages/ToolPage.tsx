import { lazy, Suspense, useEffect, useMemo, useState, type ReactNode } from "react";
import { useParams } from "react-router-dom";
import NavBar from "../components/layout/NavBar";
import { get } from "../lib/api";
import { createToolClient } from "../lib/toolClient";
import { pluginLoaderFor } from "../tool_plugins/registry";
import type { ToolManifest } from "../types";
import PluginMissing from "./PluginMissing";
import SchemaTool from "./schema/SchemaTool";

/**
 * The single `/tools/:toolId` route. It resolves the tool manifest, then
 * dispatches to the generic schema renderer or lazily-loaded custom plugin UI
 * based on `manifest.ui.kind`, and wraps standard-layout tools in the site
 * chrome while leaving fullscreen tools untouched.
 */
export default function ToolPage() {
  const { toolId = "" } = useParams();
  const [manifest, setManifest] = useState<ToolManifest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setManifest(null);
    setError(null);
    get<{ tool: ToolManifest }>(`/tools/${toolId}`)
      .then((res) => {
        if (cancelled) return;
        if (res.success && res.data) setManifest(res.data.tool);
        else setError(res.error?.message ?? "Tool not found");
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [toolId]);

  const client = useMemo(() => createToolClient(toolId), [toolId]);

  if (loading) return <StandardLayout><p className="status-text">Loading tool…</p></StandardLayout>;
  if (error || !manifest) {
    return (
      <StandardLayout>
        <div className="tool-page">
          <p className="error-text">{error ?? "Tool not found"}</p>
        </div>
      </StandardLayout>
    );
  }

  if (manifest.ui.kind === "schema") {
    return (
      <StandardLayout>
        <SchemaTool client={client} manifest={manifest} />
      </StandardLayout>
    );
  }

  const loader = pluginLoaderFor(toolId);
  if (!loader) {
    return (
      <StandardLayout>
        <PluginMissing manifest={manifest} />
      </StandardLayout>
    );
  }

  const Component = lazy(loader);
  const body = (
    <Suspense fallback={<p className="status-text">Loading plugin…</p>}>
      <Component client={client} manifest={manifest} />
    </Suspense>
  );

  if (manifest.ui.layout === "fullscreen") return body;
  return <StandardLayout>{body}</StandardLayout>;
}

function StandardLayout({ children }: { children: ReactNode }) {
  return (
    <div className="layout">
      <NavBar />
      <main className="main-content">{children}</main>
    </div>
  );
}
