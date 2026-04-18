import { type ReactNode } from "react";
import { Routes, Route, Navigate, Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";
import PortfolioPage from "@/pages/portfolio/PortfolioPage";
import CompanyDetailPage from "@/pages/portfolio/CompanyDetailPage";
import FilingDetailPage from "@/pages/portfolio/FilingDetailPage";
import UploadPage from "@/pages/upload/UploadPage";
import SceneMatrixPage from "@/pages/config/SceneMatrixPage";
import PromptConsolePage from "@/pages/config/PromptConsolePage";
import ChatConsolePage from "@/pages/interact/ChatConsolePage";

export interface RouteConfig {
  path: string;
  label: string;
  icon?: ReactNode;
  element: ReactNode;
  children?: RouteConfig[];
}

function ConfigLayout() {
  return <Outlet />;
}

function PortfolioLayout() {
  return <Outlet />;
}

const routeConfigs: RouteConfig[] = [
  {
    path: "/portfolio",
    label: "Portfolio",
    element: <PortfolioLayout />,
    children: [
      {
        path: "",
        label: "公司列表",
        element: <PortfolioPage />,
      },
      {
        path: ":ticker",
        label: "公司详情",
        element: <CompanyDetailPage />,
        children: [
          {
            path: "filings/:documentId",
            label: "Filing 详情",
            element: <FilingDetailPage />,
          },
        ],
      },
    ],
  },
  {
    path: "/upload",
    label: "Upload",
    element: <UploadPage />,
  },
  {
    path: "/config",
    label: "Config",
    element: <ConfigLayout />,
    children: [
      {
        path: "",
        label: "默认",
        element: <Navigate to="/config/scenes" replace />,
      },
      {
        path: "scenes",
        label: "Scene 矩阵",
        element: <SceneMatrixPage />,
      },
      {
        path: "prompts",
        label: "Prompt 控制台",
        element: <PromptConsolePage />,
      },
      {
        path: "prompts/:path*",
        label: "Prompt 编辑",
        element: <PromptConsolePage />,
      },
    ],
  },
  {
    path: "/interact",
    label: "Interact",
    element: <ChatConsolePage />,
  },
];

export { routeConfigs as routes };

function renderRoutes(configs: RouteConfig[]): ReactNode {
  return configs.map((config) => (
    <Route key={config.path} path={config.path} element={config.element}>
      {config.children && renderRoutes(config.children)}
    </Route>
  ));
}

export default function AppShell() {
  return (
    <div className="flex h-screen bg-zinc-50">
      <Sidebar routes={routeConfigs} />
      <div className="flex-1 flex flex-col overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-auto p-6">
          <Routes>
            <Route path="/" element={<Navigate to="/portfolio" replace />} />
            {renderRoutes(routeConfigs)}
          </Routes>
        </main>
      </div>
    </div>
  );
}