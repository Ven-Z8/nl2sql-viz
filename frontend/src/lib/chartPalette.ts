"use client";
import { useEffect, useMemo, useState } from "react";

/**
 * Recharts draws into SVG where `fill="var(--x)"` is unreliable (presentation
 * attributes don't participate in custom-property resolution). We therefore
 * resolve the chart tokens from globals.css to concrete color strings at
 * runtime, re-resolving whenever [data-theme] flips so the dark-mode toggle
 * restyles live charts correctly.
 */

export interface ChartPalette {
  series: string[];
  grid: string;
  axis: string;
  /** Resolved accent-dim for hover/cursor fills in SVG attributes. */
  accentDim: string;
}

const SERIES_VARS = [
  "--chart-c1",
  "--chart-c2",
  "--chart-c3",
  "--chart-c4",
  "--chart-c5",
  "--chart-c6",
  "--chart-c7",
  "--chart-c8",
];

const FALLBACK_SERIES = [
  "#3b82f6",
  "#8b5cf6",
  "#ec4899",
  "#f59e0b",
  "#10b981",
  "#06b6d4",
  "#f97316",
  "#14b8a6",
];

/** Resolve any CSS color (var()/oklch/…) to a concrete rgb() string. */
function resolveCssColor(raw: string): string {
  if (typeof document === "undefined") return raw;
  try {
    const span = document.createElement("span");
    span.style.color = raw;
    if (!span.style.color) return raw; // unsupported syntax
    document.body.appendChild(span);
    const computed = getComputedStyle(span).color;
    span.remove();
    return computed || raw;
  } catch {
    return raw;
  }
}

function readVar(name: string): string {
  if (typeof window === "undefined") return "";
  return (
    getComputedStyle(document.documentElement)
      .getPropertyValue(name)
      .trim() || ""
  );
}

/** Track the current data-theme on <html> without prop drilling. */
export function useDataTheme(): "light" | "dark" {
  const [theme, setTheme] = useState<"light" | "dark">("light");
  useEffect(() => {
    const el = document.documentElement;
    const apply = () =>
      setTheme(el.getAttribute("data-theme") === "dark" ? "dark" : "light");
    apply();
    const observer = new MutationObserver(apply);
    observer.observe(el, { attributes: true, attributeFilter: ["data-theme"] });
    return () => observer.disconnect();
  }, []);
  return theme;
}

export function useChartPalette(): ChartPalette {
  const theme = useDataTheme();
  return useMemo(() => {
    if (typeof window === "undefined") {
      // SSR prerender fallback — real values resolve from CSS vars on client.
      return {
        series: FALLBACK_SERIES,
        grid: "#c8c8c8",
        axis: "#7a7a7a",
        accentDim: "rgba(99, 102, 241, 0.12)",
      };
    }
    const series = SERIES_VARS.map((v, i) => {
      const raw = readVar(v);
      return raw ? resolveCssColor(raw) : FALLBACK_SERIES[i];
    });
    const gridRaw = readVar("--chart-grid");
    const axisRaw = readVar("--chart-axis");
    const accentDimRaw = readVar("--color-accent-dim");
    return {
      series,
      grid: gridRaw ? resolveCssColor(gridRaw) : "#c8c8c8",
      axis: axisRaw ? resolveCssColor(axisRaw) : "#7a7a7a",
      accentDim: accentDimRaw
        ? resolveCssColor(accentDimRaw)
        : "rgba(99, 102, 241, 0.12)",
    };
  }, [theme]);
}
