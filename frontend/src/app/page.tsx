"use client";
import { useCallback, useState } from "react";
import TopBar from "@/components/TopBar";
import LeftPanel from "@/components/LeftPanel";
import RightPanel from "@/components/RightPanel";
import ArchitecturePanel from "@/components/ArchitecturePanel";
import Banner from "@/components/Banner";
import SetupRequired from "@/components/SetupRequired";
import { useBackendSession } from "@/hooks/useBackendSession";
import { useWorkspace } from "@/hooks/useWorkspace";
import { useQueryStream } from "@/hooks/useQueryStream";
import { isApiConfigured } from "@/lib/config";

/**
 * DataLens AI — workbench shell.
 *
 * Composition:
 *   useBackendSession → demo credentials (api_key + connection_id)
 *   useWorkspace      → catalogs, suggested questions, dataset flows
 *   useQueryStream    → WS lifecycle, pipeline/log/result state
 *
 * All backend URLs come from lib/config.ts. When NEXT_PUBLIC_API_URL is
 * missing, the app renders a setup-required card instead of silently
 * targeting localhost.
 */
export default function Home() {
  const configured = isApiConfigured();

  // Local UI-only state (kept out of hooks deliberately).
  const [query, setQuery] = useState("");
  const [sqlVisible, setSqlVisible] = useState(false);

  const backend = useBackendSession(configured);
  const workspace = useWorkspace({
    enabled: configured,
    apiKey: backend.session?.apiKey ?? null,
    onConnectionId: backend.adoptConnection,
    initialFocusTable: backend.session?.focusTable,
  });

  const stream = useQueryStream({
    apiKey: backend.session?.apiKey ?? null,
    connectionId: backend.session?.connectionId ?? null,
    domain: workspace.activeDomain,
    focusTable: workspace.uploadedDataset?.table_name ?? workspace.focusTable,
  });

  const runFromHistory = useCallback(
    (q: string) => {
      setQuery(q);
      // History reruns are deliberate replays, not conversation — always a
      // fresh topic (contract v3).
      stream.runQuestion(q, { continueThread: false });
    },
    [stream]
  );

  const askSuggested = useCallback(
    (q: string) => {
      setQuery(q);
      stream.runQuestion(q);
    },
    [stream]
  );

  if (!configured) {
    return <SetupRequired />;
  }

  const retryingNotice =
    stream.status === "retrying" ? (
      <Banner
        tone="info"
        message="Connecting to backend… Render free tier can take ~60s to wake"
      />
    ) : null;

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <TopBar status={stream.status} />
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        <LeftPanel
          query={query}
          onQueryChange={setQuery}
          onSubmit={() => stream.runQuestion(query)}
          // Composer disabled while paused on a clarify too — answer the
          // question first; runQuestion guards against it regardless.
          isLoading={stream.isLoading || stream.pendingClarify != null}
          canRun={stream.status === "open"}
          composerPlaceholder={
            stream.activeThreadId ? "Ask a follow-up…" : undefined
          }
          datasetName={workspace.datasetName}
          connectionLabel={backend.connectionLabel}
          suggestedQuestions={workspace.suggestedQuestions}
          logs={stream.logs}
          history={stream.history}
          onHistoryRerun={runFromHistory}
          onAsk={askSuggested}
          domains={workspace.domains}
          activeDomain={workspace.activeDomain}
          onDomainChange={workspace.setActiveDomain}
          uploading={workspace.uploading}
          uploadedDataset={workspace.uploadedDataset}
          uploadError={workspace.uploadError}
          onUpload={workspace.uploadCsv}
          samples={workspace.samples}
          onLoadSample={workspace.loadSample}
          datasets={workspace.datasets}
          onLoadDataset={workspace.loadDataset}
          onConnect={workspace.connectDsn}
        />
        <RightPanel
          slots={stream.slots}
          activeThreadId={stream.activeThreadId}
          loadingThreadId={stream.loadingThreadId}
          pendingTitle={stream.pendingTitle}
          draftSql={stream.draftSql}
          pendingClarify={stream.pendingClarify}
          onRespondClarify={stream.respondClarify}
          sqlVisible={sqlVisible}
          onToggleSql={() => setSqlVisible((v) => !v)}
          isLoading={stream.isLoading}
          phase={stream.phase}
          error={stream.error}
          onDismissError={stream.dismissError}
          onNewTopic={stream.startNewTopic}
          notice={retryingNotice}
        />
        <ArchitecturePanel
          pipeline={stream.pipeline}
          isLoading={stream.isLoading}
          hasRun={stream.pipelineEverFired}
        />
      </div>
    </div>
  );
}
