"use client";
import { useState, useEffect, useRef } from "react";
import { QueryWebSocket } from "@/lib/ws";
import QueryInput from "@/components/QueryInput";
import VegaChart from "@/components/VegaChart";

const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? "";
const DSN = process.env.NEXT_PUBLIC_DSN ?? "";

export default function Home() {
  const [status, setStatus] = useState<string>("Connecting...");
  const [loading, setLoading] = useState(false);
  const [vegaSpec, setVegaSpec] = useState<string | null>(null);
  const wsRef = useRef<QueryWebSocket | null>(null);

  useEffect(() => {
    if (!API_KEY) {
      setStatus("Missing API key — set NEXT_PUBLIC_API_KEY in .env.local");
      return;
    }

    const ws = new QueryWebSocket(API_KEY, (event) => {
      if (event.type === "progress") setStatus(event.message as string);
      if (event.type === "result") {
        setVegaSpec(event.vega_spec as string);
        setLoading(false);
        setStatus("Done");
      }
      if (event.type === "error") {
        setStatus(`Error: ${event.message}`);
        setLoading(false);
      }
    });

    ws.connect()
      .then(() => setStatus("Connected — ask a question"))
      .catch(() => setStatus("Failed to connect — is the backend running?"));

    wsRef.current = ws;
    return () => ws.disconnect();
  }, []);

  const handleQuery = (query: string) => {
    setLoading(true);
    setVegaSpec(null);
    wsRef.current?.sendQuery(query, DSN);
  };

  return (
    <main className="max-w-3xl mx-auto p-8">
      <h1 className="text-2xl font-bold mb-2">DataLens AI</h1>
      <p className="text-gray-500 text-sm mb-6">{status}</p>
      <QueryInput onSubmit={handleQuery} disabled={loading} />
      {vegaSpec && (
        <div className="mt-8">
          <VegaChart spec={vegaSpec} />
        </div>
      )}
    </main>
  );
}
