"use client";
import { useState, useEffect, useRef } from "react";
import { QueryWebSocket } from "@/lib/ws";
import TopBar from "@/components/TopBar";
import LeftPanel, { HistoryItem } from "@/components/LeftPanel";
import RightPanel from "@/components/RightPanel";
import { LogEntry } from "@/components/LogStream";

const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? "";
const DSN = process.env.NEXT_PUBLIC_DSN ?? "";

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
  const [sql, setSql] = useState("");
  const [sqlVisible, setSqlVisible] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [connected, setConnected] = useState(false);
  const [resultTitle, setResultTitle] = useState("");

  const wsRef = useRef<QueryWebSocket | null>(null);

  useEffect(() => {
    if (!API_KEY) return;

    const ws = new QueryWebSocket(API_KEY, (event) => {
      if (event.type === "progress") {
        const msg = event.message as string;
        setLogs((prev) => {
          const updated = prev.map((e, i) =>
            i === prev.length - 1 && e.active ? { ...e, active: false, icon: "done" as const } : e
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
            i === prev.length - 1 && e.active ? { ...e, active: false, icon: "done" as const } : e
          )
        );
        setVegaSpec(event.vega_spec as string);
        if (event.sql) setSql(event.sql as string);
        setIsLoading(false);
      }

      if (event.type === "error") {
        setLogs((prev) => {
          const updated = prev.map((e, i) =>
            i === prev.length - 1 && e.active ? { ...e, active: false, icon: "done" as const } : e
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
        wsRef.current = ws;
        setConnected(true);
      })
      .catch(() => setConnected(false));

    return () => {
      ws.disconnect();
      setConnected(false);
    };
  }, []);

  const handleSubmit = () => {
    if (!query.trim() || isLoading) return;

    if (!DSN) {
      setLogs((prev) => [
        ...prev,
        { time: now(), icon: "run", text: "Missing DSN — set NEXT_PUBLIC_DSN", active: false },
      ]);
      return;
    }

    // Reset result state
    setLogs([]);
    setVegaSpec(null);
    setSql("");
    setSqlVisible(false);
    setIsLoading(true);
    setResultTitle(query);

    // Prepend to history
    setHistory((prev) => [{ query, timestamp: now() }, ...prev]);

    wsRef.current?.sendQuery(query, DSN);
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
          logs={logs}
          history={history}
          activeHistoryIndex={history.length > 0 ? 0 : null}
          onHistoryClick={(q) => setQuery(q)}
        />
        <RightPanel
          title={resultTitle}
          vegaSpec={vegaSpec}
          sql={sql}
          sqlVisible={sqlVisible}
          onToggleSql={() => setSqlVisible((v) => !v)}
        />
      </div>
    </div>
  );
}
