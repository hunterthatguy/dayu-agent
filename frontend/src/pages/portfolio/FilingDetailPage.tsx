import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";
import EmptyState from "@/components/shared/EmptyState";
import type { FilingDetailView, FilingSectionView, FilingTableView, XbrlFactView } from "@/types/api";
import { formatDate } from "@/lib/format";

type TabKey = "original" | "sections" | "tables" | "xbrl";

export default function FilingDetailPage() {
  const { ticker, documentId } = useParams<{ ticker: string; documentId: string }>();
  const [tab, setTab] = useState<TabKey>("original");
  const [activeSection, setActiveSection] = useState<string | null>(null);

  if (!ticker || !documentId) return <div>缺少参数</div>;

  const { data: detail, isLoading, error } = useQuery({
    queryKey: ["filing-detail", ticker, documentId],
    queryFn: () => api.portfolio.getFilingDetail(ticker, documentId),
  });

  const { data: processed } = useQuery({
    queryKey: ["filing-processed", ticker, documentId],
    queryFn: () => api.portfolio.getFilingProcessed(ticker, documentId),
    enabled: detail?.has_processed,
  });

  if (isLoading) return <div className="text-sm text-zinc-500">加载中...</div>;
  if (error) return <div className="text-sm text-rose-600">加载失败</div>;
  if (!detail) return <EmptyState message="未找到 filing" />;

  const sections = processed?.sections ?? [];

  return (
    <div className="flex gap-6">
      {/* 左侧目录 */}
      <aside className="w-48 sticky top-0 self-start">
        <div className="bg-white rounded-md border border-zinc-200 p-3">
          <div className="text-xs text-zinc-500 mb-2">Sections</div>
          {sections.length === 0 ? (
            <div className="text-xs text-zinc-400">无 sections</div>
          ) : (
            <ul className="space-y-1">
              {sections.map((section: FilingSectionView) => (
                <li key={section.section_id}>
                  <button
                    onClick={() => setActiveSection(section.section_id)}
                    className={`text-xs text-left w-full px-2 py-1 rounded ${
                      activeSection === section.section_id
                        ? "bg-zinc-100 text-zinc-900"
                        : "text-zinc-600 hover:bg-zinc-50"
                    }`}
                  >
                    {section.title}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>

      {/* 右侧主区 */}
      <div className="flex-1">
        <div className="mb-4">
          <h2 className="text-lg font-semibold text-zinc-900">
            {detail.filing.form_type} · {detail.filing.fiscal_year ?? "-"} {detail.filing.fiscal_period ?? ""}
          </h2>
          <div className="text-sm text-zinc-500">
            报送日期: {formatDate(detail.filing.filing_date)}
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-4 border-b border-zinc-200">
          {(["original", "sections", "tables", "xbrl"] as TabKey[]).map((key) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`px-3 py-2 text-sm font-medium border-b-2 transition-colors ${
                tab === key
                  ? "border-zinc-900 text-zinc-900"
                  : "border-transparent text-zinc-500 hover:text-zinc-700"
              }`}
            >
              {key === "original" ? "原文" : key === "sections" ? "Sections" : key === "tables" ? "Tables" : "XBRL"}
            </button>
          ))}
        </div>

        {tab === "original" && detail.filing.primary_document && (
          <div className="bg-white rounded-md border border-zinc-200 p-4">
            <div className="mb-2 text-sm text-zinc-500">
              预览文件: {detail.filing.primary_document}
            </div>
            <iframe
              src={`${api.portfolio.getFilingFileUrl(ticker, documentId, detail.filing.primary_document)}?preview=true`}
              className="w-full h-[600px] border-0 rounded"
              title="原文预览"
            />
            <div className="mt-2 text-xs text-zinc-400">
              如预览失败，可点击下方链接下载文件
            </div>
            <a
              href={api.portfolio.getFilingFileUrl(ticker, documentId, detail.filing.primary_document)}
              className="text-xs text-zinc-600 hover:text-zinc-900"
              download
            >
              下载原文件
            </a>
          </div>
        )}

        {tab === "sections" && (
          <div className="bg-white rounded-md border border-zinc-200 p-4">
            {processed ? (
              <ul className="space-y-2">
                {processed.sections.map((section: FilingSectionView) => (
                  <li key={section.section_id} className="text-sm">
                    <div className="font-medium text-zinc-900">{section.title}</div>
                    <div className="text-xs text-zinc-500">
                      {section.char_count} 字符
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState message="无 processed 数据" />
            )}
          </div>
        )}

        {tab === "tables" && (
          <div className="bg-white rounded-md border border-zinc-200 p-4">
            {processed ? (
              processed.tables.length === 0 ? (
                <EmptyState message="无表格数据" />
              ) : (
                <ul className="space-y-3">
                  {processed.tables.map((table: FilingTableView) => (
                    <li key={table.table_id} className="border-b border-zinc-100 pb-3 last:border-0">
                      <div className="font-medium text-zinc-900 text-sm">{table.caption || "未命名表格"}</div>
                      <div className="text-xs text-zinc-500 mt-1">
                        {table.row_count} 行 × {table.column_count} 列 · Section: {table.section_id}
                      </div>
                      <button
                        onClick={() => setActiveSection(table.section_id)}
                        className="text-xs text-zinc-400 hover:text-zinc-600 mt-1"
                      >
                        查看所属 Section
                      </button>
                    </li>
                  ))}
                </ul>
              )
            ) : (
              <EmptyState message="无 processed 数据" />
            )}
          </div>
        )}

        {tab === "xbrl" && (
          <div className="bg-white rounded-md border border-zinc-200 p-4 overflow-auto">
            {processed ? (
              processed.xbrl_facts.length === 0 ? (
                <EmptyState message="无 XBRL 数据" />
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-zinc-200">
                      <th className="px-2 py-2 text-left font-medium text-zinc-600">Concept</th>
                      <th className="px-2 py-2 text-left font-medium text-zinc-600">Value</th>
                      <th className="px-2 py-2 text-left font-medium text-zinc-600">Unit</th>
                      <th className="px-2 py-2 text-left font-medium text-zinc-600">Period</th>
                    </tr>
                  </thead>
                  <tbody>
                    {processed.xbrl_facts.map((fact: XbrlFactView, i: number) => (
                      <tr key={i} className="border-b border-zinc-100">
                        <td className="px-2 py-2 font-mono text-xs text-zinc-800">{fact.concept}</td>
                        <td className="px-2 py-2 text-zinc-900">{fact.value}</td>
                        <td className="px-2 py-2 text-zinc-500">{fact.unit}</td>
                        <td className="px-2 py-2 text-xs text-zinc-500">
                          {fact.period_end}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )
            ) : (
              <EmptyState message="无 processed 数据" />
            )}
          </div>
        )}
      </div>
    </div>
  );
}