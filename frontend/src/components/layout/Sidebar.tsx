import { NavLink, useLocation } from "react-router-dom";
import { type ReactNode } from "react";
import { LayoutDashboard, Upload, Settings, MessageSquare, Key } from "lucide-react";
import type { RouteConfig } from "./AppShell";
import { cn } from "@/lib/cn";

const NAV_ITEMS: { path: string; label: string; icon: ReactNode }[] = [
  { path: "/portfolio", label: "Portfolio", icon: <LayoutDashboard className="w-5 h-5" /> },
  { path: "/upload", label: "Upload", icon: <Upload className="w-5 h-5" /> },
  { path: "/config/scenes", label: "Config", icon: <Settings className="w-5 h-5" /> },
  { path: "/settings/api-keys", label: "API Keys", icon: <Key className="w-5 h-5" /> },
  { path: "/interact", label: "Interact", icon: <MessageSquare className="w-5 h-5" /> },
];

// 检查路径是否匹配（支持子路径匹配）
function matchPath(currentPath: string, navPath: string): boolean {
  if (navPath === "/config/scenes") {
    return currentPath.startsWith("/config");
  }
  if (navPath === "/settings/api-keys") {
    return currentPath.startsWith("/settings");
  }
  return currentPath === navPath || currentPath.startsWith(navPath + "/");
}

export default function Sidebar({ routes }: { routes: RouteConfig[] }) {
  const location = useLocation();

  return (
    <aside className="w-64 border-r border-zinc-200 bg-white flex flex-col">
      <div className="px-4 py-4 border-b border-zinc-200">
        <h1 className="text-lg font-semibold text-zinc-900">Dayu Web</h1>
        <p className="text-xs text-zinc-500">财报分析可视化</p>
      </div>
      <nav className="flex-1 px-2 py-4 space-y-1">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                isActive || matchPath(location.pathname, item.path)
                  ? "bg-zinc-100 text-zinc-900"
                  : "text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900",
              )
            }
          >
            {item.icon}
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="px-4 py-4 border-t border-zinc-200 text-xs text-zinc-400">
        v0.1.0
      </div>
    </aside>
  );
}