import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Static export for GitHub Pages hosting
  output: "export",
  images: { unoptimized: true },
  // Set NEXT_PUBLIC_BASE_PATH=/nl2sql-viz when hosting under a repo path on
  // GitHub Pages (project site). Empty for a custom domain or local dev.
  basePath: process.env.NEXT_PUBLIC_BASE_PATH || "",
  turbopack: {
    root: __dirname,
  },
  webpack: (config) => {
    // vega-canvas tries to import the Node-only `canvas` package; it's not
    // needed in the browser and its failed resolution breaks the RSC boundary.
    config.resolve.alias.canvas = false;
    return config;
  },
};

export default nextConfig;