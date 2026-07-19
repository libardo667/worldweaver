import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const proxyTarget = process.env.VITE_PROXY_TARGET || "http://localhost:8000";
const worldTarget = process.env.VITE_WW_WORLD_URL || "http://localhost:9000";

type ShardRoute = { prefix?: string; target?: string };

function configuredShardTargets(): Array<{ prefix: string; target: string }> {
  const raw = process.env.VITE_WW_SHARD_ROUTES;
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw) as Record<string, ShardRoute>;
    return Object.values(parsed)
      .map((route) => ({
        prefix: String(route.prefix || "").trim(),
        target: String(route.target || "").trim(),
      }))
      .filter((route) => route.prefix.startsWith("/") && Boolean(route.target));
  } catch {
    return [];
  }
}

const shardProxyEntries = Object.fromEntries(
  configuredShardTargets().flatMap(({ prefix, target }) =>
    ["api", "health"].map((surface) => [
      `${prefix}/${surface}`,
      {
        target,
        changeOrigin: true,
        rewrite: (path: string) => path.replace(new RegExp(`^${prefix}`), ""),
      },
    ]),
  ),
);

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    allowedHosts: true,
    proxy: {
      "/api": {
        target: proxyTarget,
        changeOrigin: true,
      },
      "/health": {
        target: proxyTarget,
        changeOrigin: true,
      },
      // Federation calls stay same-origin so HTTPS pages never call HTTP directly.
      "/ww-world": {
        target: worldTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/ww-world/, ""),
      },
      ...shardProxyEntries,
    },
  },
});
