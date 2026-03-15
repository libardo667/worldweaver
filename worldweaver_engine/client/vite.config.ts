import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const proxyTarget = process.env.VITE_PROXY_TARGET || "http://localhost:8000";
const worldTarget = process.env.VITE_WW_WORLD_URL || "http://localhost:9000";
const shardTargets: Array<{ prefix: string; target: string | undefined }> = [
  { prefix: "/ww-sfo", target: process.env.VITE_WW_SFO_URL || "http://localhost:8002" },
  { prefix: "/ww-pdx", target: process.env.VITE_WW_PDX_URL || "http://localhost:8003" },
];

const shardProxyEntries = Object.fromEntries(
  shardTargets
    .filter((entry) => Boolean(entry.target))
    .map(({ prefix, target }) => [
      prefix,
      {
        target,
        changeOrigin: true,
        rewrite: (path: string) => path.replace(new RegExp(`^${prefix}`), ""),
      },
    ]),
);

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    allowedHosts: true,
    proxy: {
      "/api": {
        target: proxyTarget,
        changeOrigin: true,
      },
      "/author": {
        target: proxyTarget,
        changeOrigin: true,
      },
      "/health": {
        target: proxyTarget,
        changeOrigin: true,
      },
      // Proxy federation calls through Vite so browsers on HTTPS (world-weaver.org)
      // never make direct HTTP requests to the world server.
      "/ww-world": {
        target: worldTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/ww-world/, ""),
      },
      ...shardProxyEntries,
    },
  },
});
