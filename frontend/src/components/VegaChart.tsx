"use client";
import { useEffect, useRef } from "react";
import embed, { Result } from "vega-embed";

interface VegaChartProps {
  spec: string;
}

export default function VegaChart({ spec }: VegaChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const resultRef = useRef<Result | null>(null);

  useEffect(() => {
    if (!containerRef.current || !spec) return;

    // Finalize previous view before creating new one
    resultRef.current?.view.finalize();
    resultRef.current = null;

    embed(containerRef.current, JSON.parse(spec) as object, { actions: false })
      .then((result) => {
        resultRef.current = result;
      })
      .catch(console.error);

    return () => {
      resultRef.current?.view.finalize();
      resultRef.current = null;
    };
  }, [spec]);

  return <div ref={containerRef} className="w-full" />;
}
