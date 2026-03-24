"use client";
import { useEffect, useRef } from "react";
import embed from "vega-embed";

interface VegaChartProps {
  spec: string;
}

export default function VegaChart({ spec }: VegaChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || !spec) return;
    embed(containerRef.current, JSON.parse(spec), { actions: false }).catch(console.error);
  }, [spec]);

  return <div ref={containerRef} className="w-full" />;
}
