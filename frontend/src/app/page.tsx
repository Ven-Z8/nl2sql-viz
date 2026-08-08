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

  const wsRef = useRef<QueryWebSocket | null>(null);

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

  const handleSubmit = () => {
    if (!query.trim() || isLoading) return;

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
    setResultTitle(query);

    // Prepend to history
    setHistory((prev) => [{ query, timestamp: now() }, ...prev]);

    wsRef.current?.sendQuery(query, runtimeDsn);
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
          onSuggestedQuestionClick={(q) => setQuery(q)}
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
        />
      </div>
    </div>
  );
}
