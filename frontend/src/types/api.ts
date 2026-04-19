/** 前端类型定义（与后端 dayu/services/contracts.py 一一对应）。 */

// === Portfolio ===

export interface CompanyView {
  ticker: string;
  company_name: string;
  market: string;
  company_id: string;
  updated_at: string;
  ticker_aliases: string[];
  directory_name: string;
  status: string;
  detail: string;
  filing_count: number;
  processed_count: number;
}

export interface FilingFileView {
  name: string;
  size: number | null;
  content_type: string | null;
  sha256: string | null;
}

export interface FilingView {
  ticker: string;
  document_id: string;
  form_type: string | null;
  fiscal_year: number | null;
  fiscal_period: string | null;
  report_date: string | null;
  filing_date: string | null;
  amended: boolean;
  ingest_complete: boolean;
  is_deleted: boolean;
  has_xbrl: boolean | null;
  has_processed: boolean;
  primary_document: string;
}

export interface ProcessedArtifactView {
  ticker: string;
  document_id: string;
  source_kind: string;
  form_type: string | null;
  fiscal_year: number | null;
  fiscal_period: string | null;
  report_date: string | null;
  filing_date: string | null;
  amended: boolean;
  is_deleted: boolean;
  document_version: string;
  quality: string;
  has_financials: boolean;
  section_count: number;
  table_count: number;
}

export interface FilingDetailView {
  filing: FilingView;
  files: FilingFileView[];
  processed_summary: ProcessedArtifactView | null;
  section_count: number;
  table_count: number;
  has_financials: boolean;
}

export interface FilingSectionView {
  section_id: string;
  title: string;
  depth: number;
  order: number;
  char_count: number;
}

export interface FilingTableView {
  table_id: string;
  caption: string;
  section_id: string;
  row_count: number;
  column_count: number;
}

export interface XbrlFactView {
  concept: string;
  unit: string;
  value: string;
  period_start: string;
  period_end: string;
  decimals: string;
  context_id: string;
}

export interface FilingProcessedView {
  artifact: ProcessedArtifactView;
  sections: FilingSectionView[];
  tables: FilingTableView[];
  xbrl_facts: XbrlFactView[];
}

export interface RejectedFilingView {
  ticker: string;
  document_id: string;
  accession_number: string;
  form_type: string;
  filing_date: string;
  rejection_reason: string;
  rejection_category: string;
  rejected_at: string;
}

export interface PortfolioHealthView {
  ticker: string;
  total_filings: number;
  ingest_incomplete_filings: number;
  deleted_filings: number;
  processed_filings: number;
  missing_processed_filings: number;
  rejected_filings: number;
  rejected_samples: RejectedFilingView[];
}

// === Config ===

export interface SceneModelOptionView {
  model_name: string;
  is_default: boolean;
}

export interface SceneMatrixRowView {
  scene_name: string;
  default_model: string;
  allowed_models: SceneModelOptionView[];
}

export interface SceneMatrixView {
  all_models: string[];
  rows: SceneMatrixRowView[];
}

export interface PromptDocumentView {
  category: string;
  name: string;
  relative_path: string;
  size: number;
  updated_at: string;
}

export interface PromptDocumentDetailView {
  document: PromptDocumentView;
  content: string;
}

export interface ScenePromptCompositionView {
  scene_name: string;
  composed_text: string;
  fragments: string[];
}

// === Upload ===

export type PipelineStageState =
  | "pending"
  | "running"
  | "succeeded"
  | "failed"
  | "skipped";

export interface PipelineStageView {
  key: string;
  title: string;
  state: PipelineStageState;
  message: string;
  started_at: string;
  finished_at: string;
}

export interface PipelineProgressView {
  ticker: string;
  run_id: string;
  session_id: string;
  stages: PipelineStageView[];
  active_stage_key: string;
  terminal_state: "running" | "succeeded" | "failed" | "cancelled";
  updated_at: string;
}

export interface ManualUploadResponse {
  run_id: string;
  session_id: string;
  ticker: string;
}

export interface FileUploadResponse {
  run_id: string;
  session_id: string;
  ticker: string;
  files_received: number;
}

// === Chat ===

export interface ChatTurnSubmission {
  user_text: string;
  ticker?: string;
  scene_name?: string;
  session_id?: string;
}

export interface ChatTurnResponse {
  session_id: string;
  run_id: string;
}

export interface AgentEvent {
  type: string;
  payload: Record<string, unknown>;
  run_id?: string;
}

// === Settings ===

export interface ApiKeyStatusResponse {
  key_name: string;
  display_name: string;
  is_configured: boolean;
  source: string;
  url: string;
}

export interface ModelRequirementResponse {
  model_name: string;
  required_key: string;
  key_display_name: string;
  is_available: boolean;
}

export interface SceneModelUpdateResponse {
  scene_name: string;
  old_model: string;
  new_model: string;
}