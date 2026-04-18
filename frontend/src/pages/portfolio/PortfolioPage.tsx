import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import DataTable from "@/components/shared/DataTable";
import EmptyState from "@/components/shared/EmptyState";
import type { CompanyView } from "@/types/api";
import { formatDate } from "@/lib/format";

export default function PortfolioPage() {
  const navigate = useNavigate();
  const { data, isLoading, error } = useQuery({
    queryKey: ["companies"],
    queryFn: api.portfolio.listCompanies,
  });

  if (isLoading) return <div className="text-sm text-zinc-500">加载中...</div>;
  if (error) return <div className="text-sm text-rose-600">加载失败</div>;

  // 过滤掉 ticker 为空的异常条目
  const companies = (data ?? []).filter((c) => c.ticker && c.ticker.trim() !== "");

  const columns = [
    {
      key: "ticker",
      header: "Ticker",
      render: (row: CompanyView) => (
        <span className="font-semibold text-zinc-900">{row.ticker}</span>
      ),
    },
    { key: "company_name", header: "公司名称" },
    { key: "market", header: "市场" },
    {
      key: "filing_count",
      header: "Filings",
      render: (row: CompanyView) => (
        <span className="tabular-nums">{row.filing_count}</span>
      ),
    },
    {
      key: "processed_count",
      header: "Processed",
      render: (row: CompanyView) => (
        <span className="tabular-nums">{row.processed_count}</span>
      ),
    },
    {
      key: "updated_at",
      header: "更新时间",
      render: (row: CompanyView) => formatDate(row.updated_at),
    },
  ];

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-zinc-900">Portfolio</h2>
        <button
          onClick={() => navigate("/upload")}
          className="px-3 py-1.5 text-sm bg-zinc-900 text-white rounded-md hover:bg-zinc-800"
        >
          新建分析
        </button>
      </div>

      {companies.length === 0 ? (
        <EmptyState message="暂无公司数据" />
      ) : (
        <DataTable
          columns={columns}
          data={companies}
          rowKey={(row) => row.ticker}
          onRowClick={(row) => navigate(`/portfolio/${row.ticker}`)}
        />
      )}
    </div>
  );
}