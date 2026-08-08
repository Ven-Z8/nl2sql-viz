import type { NextConfig } from "next";

const nextConfig: NextConfig = {
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