import type {
  CompanyView,
  FilingView,
  FilingDetailView,
  FilingProcessedView,
  ProcessedArtifactView,
  PortfolioHealthView,
  SceneMatrixView,
  PromptDocumentView,
  PromptDocumentDetailView,
  ScenePromptCompositionView,
  ManualUploadResponse,
  FileUploadResponse,
  ChatTurnSubmission,
  ChatTurnResponse,
} from "@/types/api";

const BASE = ""; // 同源；dev 由 vite proxy 转发

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

function formatErrorDetail(detail: unknown): string {
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    // FastAPI validation errors: [{type, loc, msg, input}]
    return detail.map((e) => e.msg || String(e)).join("; ");
  }
  return String(detail);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const isFormData = init?.body instanceof FormData;
  const headers = isFormData
    ? (init?.headers ?? {})
    : { "Content-Type": "application/json", ...(init?.headers ?? {}) };

  const resp = await fetch(`${BASE}${path}`, {
    ...init,
    headers,
  });
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({ detail: resp.statusText }));
    const detail = (data as { detail?: unknown }).detail ?? resp.statusText;
    throw new ApiError(resp.status, formatErrorDetail(detail));
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

function qs(params: Record<string, unknown>): string {
  const pairs: string[] = [];
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      pairs.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`);
    }
  }
  return pairs.length > 0 ? `?${pairs.join("&")}` : "";
}

export const api = {
  portfolio: {
    listCompanies: () => request<CompanyView[]>("/api/portfolio/companies"),

    listFilings: (
      ticker: string,
      params?: {
        form_type?: string;
        fiscal_year?: number;
        fiscal_period?: string;
        include_deleted?: boolean;
      },
    ) => request<FilingView[]>(`/api/portfolio/companies/${ticker}/filings${qs(params ?? {})}`),

    getFilingDetail: (ticker: string, documentId: string) =>
      request<FilingDetailView>(`/api/portfolio/companies/${ticker}/filings/${documentId}`),

    getFilingProcessed: (ticker: string, documentId: string) =>
      request<FilingProcessedView>(`/api/portfolio/companies/${ticker}/filings/${documentId}/processed`),

    listProcessedArtifacts: (
      ticker: string,
      params?: {
        form_type?: string;
        fiscal_year?: number;
        fiscal_period?: string;
        include_deleted?: boolean;
      },
    ) =>
      request<ProcessedArtifactView[]>(
        `/api/portfolio/companies/${ticker}/processed${qs(params ?? {})}`,
      ),

    getPortfolioHealth: (ticker: string) =>
      request<PortfolioHealthView>(`/api/portfolio/companies/${ticker}/health`),

    getFilingFileUrl: (ticker: string, documentId: string, filename: string) =>
      `${BASE}/api/portfolio/companies/${ticker}/filings/${documentId}/files/${filename}`,
  },

  config: {
    getSceneMatrix: () => request<SceneMatrixView>("/api/config/scenes/matrix"),

    listPromptDocuments: () => request<PromptDocumentView[]>("/api/config/prompts"),

    getPromptDocument: (relativePath: string) =>
      request<PromptDocumentDetailView>(`/api/config/prompts/${relativePath}`),

    updatePromptDocument: (relativePath: string, content: string) =>
      request<PromptDocumentDetailView>(`/api/config/prompts/${relativePath}`, {
        method: "PUT",
        body: JSON.stringify({ content }),
      }),

    getScenePromptComposition: (sceneName: string) =>
      request<ScenePromptCompositionView>(`/api/config/scenes/${sceneName}/composition`),
  },

  upload: {
    manualUpload: (body: {
      ticker: string;
      market?: string;
      form_types?: string[];
      start_date?: string;
      end_date?: string;
      overwrite?: boolean;
    }) =>
      request<ManualUploadResponse>("/api/upload/manual", {
        method: "POST",
        body: JSON.stringify(body),
      }),

    uploadFiles: async (ticker: string, files: FileList) => {
      const formData = new FormData();
      for (let i = 0; i < files.length; i++) {
        formData.append("files", files[i]);
      }
      // FormData 不需要手动设置 Content-Type
      const resp = await fetch(
        `${BASE}/api/upload/files?ticker=${encodeURIComponent(ticker)}`,
        {
          method: "POST",
          body: formData,
        },
      );
      if (!resp.ok) {
        const detail = await resp.json().catch(() => ({ detail: resp.statusText }));
        throw new ApiError(
          resp.status,
          (detail as { detail?: string }).detail ?? resp.statusText,
        );
      }
      return (await resp.json()) as FileUploadResponse;
    },

    getProgressUrl: (runId: string, ticker: string, sessionId: string) =>
      `${BASE}/api/upload/progress/${runId}?ticker=${encodeURIComponent(ticker)}&session_id=${encodeURIComponent(sessionId)}`,
  },

  chat: {
    submitTurn: (body: ChatTurnSubmission) =>
      request<ChatTurnResponse>("/api/chat", {
        method: "POST",
        body: JSON.stringify(body),
      }),

    getRunEventsUrl: (runId: string) =>
      `${BASE}/api/runs/${runId}/events`,
  },
};