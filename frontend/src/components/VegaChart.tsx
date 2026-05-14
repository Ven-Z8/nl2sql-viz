"use client";
import { useEffect, useRef, useState } from "react";
import embed, { Result } from "vega-embed";

interface VegaChartProps {
  spec: string;
}

export default function VegaChart({ spec }: VegaChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const resultRef = useRef<Result | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!containerRef.current || !spec) return;

    // Finalize previous view before creating new one
    resultRef.current?.view.finalize();
    resultRef.current = null;
    setError(null);

    let parsedSpec: Record<string, unknown>;
    try {
      parsedSpec = JSON.parse(spec) as Record<string, unknown>;
    } catch {
      setError("Chart spec was not valid JSON.");
      return;
    }

    const width = Math.max(containerRef.current.clientWidth - 8, 320);
    const height = Math.max(containerRef.current.clientHeight - 8, 260);
    const sizedSpec = { ...parsedSpec, width, height };

    embed(containerRef.current, sizedSpec, {
      actions: false,
      renderer: "canvas",
    })
      .then((result) => {
        resultRef.current = result;
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Chart rendering failed.");
      });

    return () => {
      resultRef.current?.view.finalize();
      resultRef.current = null;
    };
  }, [spec]);

  return (
    <div ref={containerRef} style={{ width: "100%", height: "100%" }}>
      {error && (
        <div
          style={{
            border: "1px solid var(--border)",
            borderRadius: "8px",
            padding: "14px",
            color: "var(--text-secondary)",
            background: "var(--bg-panel)",
            fontSize: "13px",
          }}
        >
          {error}
        </div>
      )}
    </div>
  );
}
