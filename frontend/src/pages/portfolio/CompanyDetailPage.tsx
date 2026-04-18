import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";
import DataTable from "@/components/shared/DataTable";
import KeyMetric from "@/components/shared/KeyMetric";
import EmptyState from "@/components/shared/EmptyState";
import StatusBadge from "@/components/shared/StatusBadge";
import type { FilingView, PortfolioHealthView } from "@/types/api";
import { formatDate } from "@/lib/format";

type TabKey = "filings" | "processed" | "health";

export default function CompanyDetailPage() {
  const { ticker } = useParams<{ ticker: string }>();
  const navigate = useNavigate();
  const [tab, setTab] = useState<TabKey>("filings");
  const [filters, setFilters] = useState({
    form_type: "",
    include_deleted: false,
  });

  if (!ticker) return <div>缺少 ticker</div>;

  const { data: filings, isLoading: filingsLoading } = useQuery({
    queryKey: ["filings", ticker, filters],
    queryFn: () =>
      api.portfolio.listFilings(ticker, {
        form_type: filters.form_type || undefined,
        include_deleted: filters.include_deleted,
      }),
  });

  const { data: health } = useQuery({
    queryKey: ["health", ticker],
    queryFn: () => api.portfolio.getPortfolioHealth(ticker),
  });

  const columns = [
    {
      key: "filing_date",
      header: "报送日期",
      render: (row: FilingView) => formatDate(row.filing_date),
    },
    { key: "form_type", header: "类型" },
    { key: "fiscal_year", header: "财年" },
    { key: "fiscal_period", header: "财季" },
    {
      key: "has_processed",
      header: "Processed",
      render: (row: FilingView) => (
        <StatusBadge state={row.has_processed ? "succeeded" : "pending"}>
          {row.has_processed ? "有" : "无"}
        </StatusBadge>
      ),
    },
    {
      key: "is_deleted",
      header: "状态",
      render: (row: FilingView) =>
        row.is_deleted ? (
          <StatusBadge state="failed">已删除</StatusBadge>
        ) : (
          <StatusBadge state="succeeded">正常</StatusBadge>
        ),
    },
  ];

  return (
    <div>
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-zinc-900">{ticker}</h2>
        {health && (
          <div className="text-sm text-zinc-500">
            {health.total_filings} filings · {health.processed_filings} processed
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-4 border-b border-zinc-200">
        {(["filings", "processed", "health"] as TabKey[]).map((key) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`px-3 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === key
                ? "border-zinc-900 text-zinc-900"
                : "border-transparent text-zinc-500 hover:text-zinc-700"
            }`}
          >
            {key === "filings" ? "Filings" : key === "processed" ? "Processed" : "健康度"}
          </button>
        ))}
      </div>

      {tab === "filings" && (
        <div>
          {/* 过滤器 */}
          <div className="mb-4 flex gap-4 items-center">
            <input
              type="text"
              placeholder="Form 类型过滤"
              value={filters.form_type}
              onChange={(e) =>
                setFilters((f) => ({ ...f, form_type: e.target.value }))
              }
              className="px-2 py-1 text-sm border border-zinc-200 rounded-md"
            />
            <label className="flex items-center gap-1 text-sm">
              <input
                type="checkbox"
                checked={filters.include_deleted}
                onChange={(e) =>
                  setFilters((f) => ({ ...f, include_deleted: e.target.checked }))
                }
              />
              包含已删除
            </label>
          </div>

          {filingsLoading ? (
            <div className="text-sm text-zinc-500">加载中...</div>
          ) : filings?.length === 0 ? (
            <EmptyState message="暂无 filings" />
          ) : (
            <DataTable
              columns={columns}
              data={filings ?? []}
              rowKey={(row) => row.document_id}
              onRowClick={(row) =>
                navigate(`/portfolio/${ticker}/filings/${row.document_id}`)
              }
            />
          )}
        </div>
      )}

      {tab === "health" && health && (
        <div className="grid grid-cols-4 gap-4">
          <KeyMetric label="Filings 总数" value={health.total_filings} />
          <KeyMetric label="已处理" value={health.processed_filings} />
          <KeyMetric label="缺失处理" value={health.missing_processed_filings} />
          <KeyMetric label="被拒绝" value={health.rejected_filings} />
        </div>
      )}

      {tab === "processed" && (
        <EmptyState message="Processed Tab 待实现" />
      )}
    </div>
  );
}