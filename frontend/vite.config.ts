import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

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
        // SSE 代理配置：禁用所有缓冲
        configure: (proxy) => {
          // 设置代理选项
          proxy.on("proxyReq", (proxyReq, req) => {
            // SSE 端点特殊处理
            if (req.url?.includes("/progress/")) {
              proxyReq.setHeader("Accept", "text/event-stream");
              proxyReq.setHeader("Cache-Control", "no-cache");
              proxyReq.setHeader("Connection", "keep-alive");
            }
          });

          // 响应头处理
          proxy.on("proxyRes", (proxyRes, req) => {
            if (req.url?.includes("/progress/")) {
              // 关键：禁用所有缓冲
              proxyRes.headers["cache-control"] = "no-cache, no-store, must-revalidate";
              proxyRes.headers["connection"] = "keep-alive";
              proxyRes.headers["x-accel-buffering"] = "no";
              proxyRes.headers["transfer-encoding"] = "chunked";
            }
          });

          // 错误处理
          proxy.on("error", (err, req) => {
            console.log("[Proxy Error]", req.url, err.message);
          });
        },
      },
    },
  },
});