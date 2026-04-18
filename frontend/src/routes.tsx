// 路由表导出（供 App 使用）
import { type ReactNode } from "react";
import { Navigate } from "react-router-dom";
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

export const routes: RouteConfig[] = [
  {
    path: "/portfolio",
    label: "Portfolio",
    element: <PortfolioPage />,
    children: [
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
    element: <Navigate to="/config/scenes" replace />,
    children: [
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