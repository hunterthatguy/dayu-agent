import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

const SSE_URL_PATTERN = /(\/progress\/|\/events(\?|$))/;

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5175,
    proxy: {
      "/api": {
        target: "http://localhost:9000",
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on("proxyReq", (proxyReq, req) => {
            if (req.url && SSE_URL_PATTERN.test(req.url)) {
              proxyReq.setHeader("Accept", "text/event-stream");
              proxyReq.setHeader("Cache-Control", "no-cache");
              proxyReq.setHeader("Connection", "keep-alive");
            }
          });

          proxy.on("proxyRes", (proxyRes, req) => {
            if (req.url && SSE_URL_PATTERN.test(req.url)) {
              proxyRes.headers["cache-control"] = "no-cache, no-store, must-revalidate";
              proxyRes.headers["connection"] = "keep-alive";
              proxyRes.headers["x-accel-buffering"] = "no";
              proxyRes.headers["transfer-encoding"] = "chunked";
            }
          });

          proxy.on("error", (err, req) => {
            console.log("[Proxy Error]", req.url, err.message);
          });
        },
      },
    },
  },
});
