import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const proxyTarget = process.env.VITE_PROXY_TARGET || "http://localhost:8000";
const worldTarget = process.env.VITE_WW_WORLD_URL || "http://localhost:9000";

type ShardRoute = { prefix?: string; target?: string };

function configuredShardTargets(): Array<{ prefix: string; target: string }> {
  const raw = process.env.VITE_WW_SHARD_ROUTES;
  if (raw) {
    try {
      const parsed = JSON.parse(raw) as Record<string, ShardRoute>;
      const routes = Object.values(parsed)
        .map((route) => ({
          prefix: String(route.prefix || "").trim(),
          target: String(route.target || "").trim(),
        }))
        .filter((route) => route.prefix.startsWith("/") && Boolean(route.target));
      if (routes.length > 0) return routes;
    } catch {
      // Fall through to the small legacy development topology.
    }
  }
  return [
    { prefix: "/ww-sfo", target: process.env.VITE_WW_SFO_URL || "http://localhost:8002" },
    { prefix: "/ww-pdx", target: process.env.VITE_WW_PDX_URL || "http://localhost:8003" },
  ];
}

const shardTargets = configuredShardTargets();

const shardProxyEntries = Object.fromEntries(
  shardTargets
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
