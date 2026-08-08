"use client";
import { useState, useEffect, useRef } from "react";
import { QueryWebSocket } from "@/lib/ws";
import TopBar from "@/components/TopBar";
import LeftPanel, { HistoryItem, SuggestedQuestion } from "@/components/LeftPanel";
import RightPanel from "@/components/RightPanel";
import { LogEntry } from "@/components/LogStream";

const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? "";
const DSN = process.env.NEXT_PUBLIC_DSN ?? "";
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function now(): string {
  return new Date().toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export default function Home() {
  const [query, setQuery] = useState("");
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [vegaSpec, setVegaSpec] = useState<string | null>(null);
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [sql, setSql] = useState("");
  const [sqlVisible, setSqlVisible] = useState(false);
  const [queryType, setQueryType] = useState<string | null>(null);
  const [answer, setAnswer] = useState<{
    text: string;
    metrics: { label: string; value: number; unit: string }[];
    sub_queries: { id: string; question: string }[];
  } | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [connected, setConnected] = useState(false);
  const [resultTitle, setResultTitle] = useState("");
  const [runtimeDsn, setRuntimeDsn] = useState(DSN);
  const [datasetName, setDatasetName] = useState("Postgres Workspace");
  const [connectionLabel, setConnectionLabel] = useState("Waiting for connection");
  const [suggestedQuestions, setSuggestedQuestions] = useState<SuggestedQuestion[]>([]);
  const [domains, setDomains] = useState<{ id: string; name: string }[]>([]);
  const [samples, setSamples] = useState<
    { id: string; name: string; domain: string; description: string }[]
  >([]);
  const [activeDomain, setActiveDomain] = useState("general");
  const [uploading, setUploading] = useState(false);
  const [uploadedDataset, setUploadedDataset] = useState<{
    table_name: string;
    row_count: number;
    columns: string[];
    domain: string;
  } | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const wsRef = useRef<QueryWebSocket | null>(null);
  const apiKeyRef = useRef<string>(API_KEY);

  useEffect(() => {
    let cancelled = false;

    const start = async () => {
      let apiKey = API_KEY;
      let dsn = DSN;

      try {
        const questionsResp = await fetch(`${API_URL}/api/demo/questions`);
        if (questionsResp.ok) {
          const body = (await questionsResp.json()) as {
            dataset: string;
            questions: SuggestedQuestion[];
          };
          if (!cancelled) {
            setDatasetName(body.dataset);
            setSuggestedQuestions(body.questions);
          }
        }

        const domainsResp = await fetch(`${API_URL}/api/domains`);
        if (domainsResp.ok) {
          const body = (await domainsResp.json()) as {
            domains: { id: string; name: string }[];
          };
          if (!cancelled) setDomains(body.domains);
        }

        const samplesResp = await fetch(`${API_URL}/api/samples`);
        if (samplesResp.ok) {
          const body = (await samplesResp.json()) as {
            samples: { id: string; name: string; domain: string; description: string }[];
          };
          if (!cancelled) setSamples(body.samples);
        }

        if (!apiKey || !dsn) {
          const sessionResp = await fetch(`${API_URL}/api/demo/session`, {
            method: "POST",
          });
          if (!sessionResp.ok) {
            throw new Error("Could not create demo session");
          }
          const session = (await sessionResp.json()) as {
            username: string;
            api_key: string;
            dsn: string;
            dataset: string;
          };
          apiKey = session.api_key;
          dsn = session.dsn;
          if (!cancelled) {
            setDatasetName(session.dataset);
          }
        }
      } catch {
        if (!apiKey || !dsn) {
          if (!cancelled) {
            setConnectionLabel("Set NEXT_PUBLIC_API_KEY and NEXT_PUBLIC_DSN");
          }
          return;
        }
      }

      if (cancelled) return;
      apiKeyRef.current = apiKey;
      setRuntimeDsn(dsn);
      setConnectionLabel(new URL(API_URL).host);

      const ws = new QueryWebSocket(apiKey, (event) => {
      if (event.type === "progress") {
        const msg = event.message as string;
        setLogs((prev) => {
          const updated = prev.map((e, i) =>
            e.active ? { ...e, active: false, icon: "done" as const } : e
          );
          return [...updated, { time: now(), icon: "run" as const, text: msg, active: true }];
        });
      }

      if (event.type === "sql") {
        const rawSql = event.sql as string;
        setSql(rawSql);
        setLogs((prev) => [
          ...prev,
          {
            time: now(),
            icon: "sql" as const,
            text: rawSql.slice(0, 40) + (rawSql.length > 40 ? "…" : ""),
            active: false,
          },
        ]);
      }

      if (event.type === "result") {
        setLogs((prev) =>
          prev.map((e, i) =>
            e.active ? { ...e, active: false, icon: "done" as const } : e
          )
        );
        const chartSpec = event.chart_spec as
          | { spec?: Record<string, unknown> }
          | undefined;
        setVegaSpec(chartSpec?.spec ? JSON.stringify(chartSpec.spec) : null);
        setRows((event.rows as Record<string, unknown>[] | undefined) ?? []);
        if (event.sql) setSql(event.sql as string);
        setQueryType((event.query_type as string | undefined) ?? null);
        setAnswer(
          (event.answer as {
            text: string;
            metrics: { label: string; value: number; unit: string }[];
            sub_queries: { id: string; question: string }[];
          } | undefined) ?? null
        );
        setIsLoading(false);
      }

      if (event.type === "error") {
        setLogs((prev) => {
          const updated = prev.map((e, i) =>
            e.active ? { ...e, active: false, icon: "done" as const } : e
          );
          return [
            ...updated,
            {
              time: now(),
              icon: "run" as const,
              text: `Error: ${event.message as string}`,
              active: false,
            },
          ];
        });
        setIsLoading(false);
      }
      });

      ws.connect()
        .then(() => {
          if (cancelled) {
            ws.disconnect();
            return;
          }
          wsRef.current = ws;
          setConnected(true);
        })
        .catch(() => {
          if (!cancelled) setConnected(false);
        });
    };

    void start();

    return () => {
      cancelled = true;
      wsRef.current?.disconnect();
      setConnected(false);
    };
  }, []);

  const handleSubmit = (q?: string) => {
    const question = (typeof q === "string" ? q : query).trim();
    if (!question || isLoading) return;

    if (!wsRef.current) {
      setLogs((prev) => [
        ...prev,
        { time: now(), icon: "run" as const, text: "Not connected — check NEXT_PUBLIC_API_KEY", active: false },
      ]);
      return;
    }

    if (!runtimeDsn) {
      setLogs((prev) => [
        ...prev,
        { time: now(), icon: "run", text: "Missing DSN — set NEXT_PUBLIC_DSN", active: false },
      ]);
      return;
    }

    // Reset result state
    setLogs([]);
    setVegaSpec(null);
    setRows([]);
    setSql("");
    setSqlVisible(false);
    setQueryType(null);
    setAnswer(null);
    setIsLoading(true);
    setResultTitle(question);

    // Prepend to history
    setHistory((prev) => [{ query: question, timestamp: now() }, ...prev]);

    wsRef.current?.sendQuery(question, runtimeDsn, activeDomain);
  };

  const handleUpload = async (file: File, domain: string) => {
    if (!file || uploading) return;
    if (!apiKeyRef.current) {
      setUploadError("Not connected — register or start a demo session first.");
      return;
    }
    setUploading(true);
    setUploadError(null);
    try {
      const form = new FormData();
      form.append("api_key", apiKeyRef.current);
      form.append("domain", domain);
      form.append("file", file);
      const resp = await fetch(`${API_URL}/api/upload`, {
        method: "POST",
        body: form,
      });
      const body = (await resp.json()) as {
        table_name: string;
        row_count: number;
        columns: string[];
        domain: string;
        dsn: string;
        detail?: string;
      };
      if (!resp.ok) {
        throw new Error(body.detail ?? "Upload failed");
      }
      setUploadedDataset({
        table_name: body.table_name,
        row_count: body.row_count,
        columns: body.columns,
        domain: body.domain,
      });
      setActiveDomain(body.domain);
      setRuntimeDsn(body.dsn);
      setDatasetName(body.table_name.replace(/^upload_/, ""));
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const handleLoadSample = async (sampleId: string) => {
    if (uploading) return;
    if (!apiKeyRef.current) {
      setUploadError("Not connected — register or start a demo session first.");
      return;
    }
    setUploading(true);
    setUploadError(null);
    try {
      const form = new FormData();
      form.append("api_key", apiKeyRef.current);
      const resp = await fetch(`${API_URL}/api/samples/${sampleId}/load`, {
        method: "POST",
        body: form,
      });
      const body = (await resp.json()) as {
        table_name: string;
        row_count: number;
        columns: string[];
        domain: string;
        dsn: string;
        questions?: string[];
        detail?: string;
      };
      if (!resp.ok) {
        throw new Error(body.detail ?? "Failed to load sample");
      }
      setUploadedDataset({
        table_name: body.table_name,
        row_count: body.row_count,
        columns: body.columns,
        domain: body.domain,
      });
      setActiveDomain(body.domain);
      setRuntimeDsn(body.dsn);
      setDatasetName(body.table_name.replace(/^upload_/, ""));
      // Show the dataset's suggested questions
      if (body.questions && body.questions.length > 0) {
        setSuggestedQuestions(
          body.questions.map((q, i) => ({
            id: `sample-q-${i}`,
            question: q,
            category: body.domain,
          }))
        );
      }
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : "Failed to load sample");
    } finally {
      setUploading(false);
    }
  };

  const handleConnect = async (dsn: string) => {
    if (!apiKeyRef.current) {
      setUploadError("Not connected — register or start a demo session first.");
      return;
    }
    setUploading(true);
    setUploadError(null);
    try {
      const resp = await fetch(`${API_URL}/api/connections`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: apiKeyRef.current, dsn }),
      });
      const body = (await resp.json()) as { connection_id?: string; detail?: string };
      if (!resp.ok) {
        throw new Error(body.detail ?? "Connection failed");
      }
      setRuntimeDsn(dsn);
      setDatasetName("Connected Database");
      setConnectionLabel(new URL(dsn).host);
      setUploadedDataset(null);
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : "Connection failed");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <TopBar connected={connected} />
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        <LeftPanel
          query={query}
          onQueryChange={setQuery}
          onSubmit={handleSubmit}
          isLoading={isLoading}
          datasetName={datasetName}
          connectionLabel={connectionLabel}
          suggestedQuestions={suggestedQuestions}
          logs={logs}
          history={history}
          activeHistoryIndex={history.length > 0 ? 0 : null}
          onHistoryClick={(q) => setQuery(q)}
          onSuggestedQuestionClick={(q) => {
            setQuery(q);
            handleSubmit(q);
          }}
          domains={domains}
          activeDomain={activeDomain}
          onDomainChange={setActiveDomain}
          uploading={uploading}
          uploadedDataset={uploadedDataset}
          uploadError={uploadError}
          onUpload={handleUpload}
          samples={samples}
          onLoadSample={handleLoadSample}
          onConnect={handleConnect}
        />
        <RightPanel
          title={resultTitle}
          vegaSpec={vegaSpec}
          rows={rows}
          sql={sql}
          sqlVisible={sqlVisible}
          onToggleSql={() => setSqlVisible((v) => !v)}
          queryType={queryType}
          answer={answer}
          isLoading={isLoading}
        />
      </div>
    </div>
  );
}
