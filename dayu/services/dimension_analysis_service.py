"""财报维度分析服务。

对已处理的财报数据进行基础财务指标分析，生成维度分析结果。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dayu.log import Log

_MODULE = "ANALYSIS_SERVICE"


@dataclass
class FinancialMetric:
    """财务指标。"""

    name: str
    value: float | None
    unit: str
    period: str
    category: str


@dataclass
class DimensionAnalysisResult:
    """维度分析结果。"""

    ticker: str
    document_id: str
    metrics: tuple[FinancialMetric, ...]
    summary: str
    insights: tuple[str, ...]


class DimensionAnalysisService:
    """维度分析服务。

    从 processed 数据中提取财务指标，生成分析报告。
    """

    def analyze(
        self,
        ticker: str,
        document_id: str,
        processed_data: dict[str, Any],
    ) -> DimensionAnalysisResult:
        """执行维度分析。

        Args:
            ticker: 股票代码。
            document_id: 文档ID。
            processed_data: 处理后的财报数据（包含XBRL facts）。

        Returns:
            维度分析结果。
        """

        Log.info(
            f"开始维度分析: ticker={ticker}, document_id={document_id}",
            module=_MODULE,
        )

        metrics = self._extract_financial_metrics(processed_data)
        summary = self._generate_summary(metrics)
        insights = self._generate_insights(metrics)

        result = DimensionAnalysisResult(
            ticker=ticker,
            document_id=document_id,
            metrics=metrics,
            summary=summary,
            insights=insights,
        )

        Log.info(
            f"维度分析完成: ticker={ticker}, metrics_count={len(metrics)}",
            module=_MODULE,
        )

        return result

    def _extract_financial_metrics(
        self,
        processed_data: dict[str, Any],
    ) -> tuple[FinancialMetric, ...]:
        """从XBRL数据提取常用财务指标。"""

        xbrl_facts = processed_data.get("xbrl_facts", [])
        metrics: list[FinancialMetric] = []

        # 常用财务指标concept映射
        key_metrics = {
            # 盈利能力
            "Revenue": ["us-gaap:Revenue", "us-gaap:SalesRevenueNet", "us-gaap:Revenues"],
            "NetIncome": ["us-gaap:NetIncomeLoss", "us-gaap:ProfitLoss"],
            "OperatingIncome": ["us-gaap:OperatingIncomeLoss", "us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxes"],
            "GrossProfit": ["us-gaap:GrossProfit", "us-gaap:ProfitLoss"],
            # 资产负债
            "TotalAssets": ["us-gaap:Assets", "us-gaap:AssetsCurrent", "us-gaap:AssetsNoncurrent"],
            "TotalLiabilities": ["us-gaap:Liabilities", "us-gaap:LiabilitiesCurrent", "us-gaap:LiabilitiesNoncurrent"],
            "TotalEquity": ["us-gaap:StockholdersEquity", "us-gaap:Equity"],
            # 现金流
            "CashFromOperations": ["us-gaap:CashFlowFromOperatingActivities", "us-gaap:NetCashFlowFromOperatingActivities"],
            "CashFromInvesting": ["us-gaap:CashFlowFromInvestingActivities", "us-gaap:NetCashFlowFromInvestingActivities"],
            "CashFromFinancing": ["us-gaap:CashFlowFromFinancingActivities", "us-gaap:NetCashFlowFromFinancingActivities"],
            #每股指标
            "EarningsPerShare": ["us-gaap:EarningsPerShareBasic", "us-gaap:EarningsPerShareDiluted"],
        }

        categories = {
            "Revenue": "盈利能力",
            "NetIncome": "盈利能力",
            "OperatingIncome": "盈利能力",
            "GrossProfit": "盈利能力",
            "TotalAssets": "资产负债",
            "TotalLiabilities": "资产负债",
            "TotalEquity": "资产负债",
            "CashFromOperations": "现金流",
            "CashFromInvesting": "现金流",
            "CashFromFinancing": "现金流",
            "EarningsPerShare": "每股指标",
        }

        # 从XBRL提取数据
        for fact in xbrl_facts:
            concept = fact.get("concept", "")
            value_str = fact.get("value", "")
            unit = fact.get("unit", "")
            period_end = fact.get("period_end", "")

            # 尝试匹配关键指标
            for metric_name, concepts in key_metrics.items():
                for c in concepts:
                    if concept.lower() == c.lower() or concept.endswith(c.split(":")[-1]):
                        try:
                            value = float(value_str) if value_str else None
                            if value is not None:
                                metrics.append(
                                    FinancialMetric(
                                        name=metric_name,
                                        value=value,
                                        unit=unit or "USD",
                                        period=period_end,
                                        category=categories.get(metric_name, "其他"),
                                    )
                                )
                        except ValueError:
                            pass
                        break

        # 去重（按metric_name）
        seen_names: set[str] = set()
        unique_metrics: list[FinancialMetric] = []
        for m in metrics:
            if m.name not in seen_names:
                seen_names.add(m.name)
                unique_metrics.append(m)

        return tuple(unique_metrics)

    def _generate_summary(self, metrics: tuple[FinancialMetric, ...]) -> str:
        """生成分析摘要。"""

        if not metrics:
            return "未找到关键财务指标数据"

        revenue = self._find_metric(metrics, "Revenue")
        net_income = self._find_metric(metrics, "NetIncome")
        total_assets = self._find_metric(metrics, "TotalAssets")
        eps = self._find_metric(metrics, "EarningsPerShare")

        parts: list[str] = []
        if revenue:
            parts.append(f"营收{self._format_value(revenue.value)}{revenue.unit}")
        if net_income:
            parts.append(f"净利润{self._format_value(net_income.value)}{net_income.unit}")
        if total_assets:
            parts.append(f"总资产{self._format_value(total_assets.value)}{total_assets.unit}")
        if eps:
            parts.append(f"EPS{self._format_value(eps.value)}{eps.unit}")

        return "，".join(parts) if parts else "关键指标不完整"

    def _generate_insights(self, metrics: tuple[FinancialMetric, ...]) -> tuple[str, ...]:
        """生成分析洞察。"""

        insights: list[str] = []

        revenue = self._find_metric(metrics, "Revenue")
        net_income = self._find_metric(metrics, "NetIncome")
        operating_income = self._find_metric(metrics, "OperatingIncome")
        total_assets = self._find_metric(metrics, "TotalAssets")
        total_equity = self._find_metric(metrics, "TotalEquity")
        cash_ops = self._find_metric(metrics, "CashFromOperations")

        # 盈利能力分析
        if revenue and net_income:
            margin = (net_income.value / revenue.value * 100) if revenue.value and net_income.value else None
            if margin:
                insights.append(f"净利润率 {margin:.1f}%")
                if margin > 20:
                    insights.append("盈利能力强")
                elif margin < 5:
                    insights.append("盈利能力较弱")

        if revenue and operating_income:
            op_margin = (operating_income.value / revenue.value * 100) if revenue.value and operating_income.value else None
            if op_margin:
                insights.append(f"营业利润率 {op_margin:.1f}%")

        # 资产负债分析
        if total_assets and total_equity:
            leverage = (total_assets.value / total_equity.value) if total_assets.value and total_equity.value else None
            if leverage:
                insights.append(f"资产负债率 {leverage:.1f}x")
                if leverage > 3:
                    insights.append("杠杆较高")

        # 现金流分析
        if cash_ops and net_income:
            if cash_ops.value and net_income.value:
                if cash_ops.value > net_income.value:
                    insights.append("经营现金流优于净利润（现金流健康）")
                else:
                    insights.append("经营现金流低于净利润（关注应收账款）")

        return tuple(insights)

    def _find_metric(
        self,
        metrics: tuple[FinancialMetric, ...],
        name: str,
    ) -> FinancialMetric | None:
        """查找指定名称的指标。"""

        for m in metrics:
            if m.name == name:
                return m
        return None

    def _format_value(self, value: float | None) -> str:
        """格式化数值显示。"""

        if value is None:
            return "-"
        if abs(value) >= 1e9:
            return f"{value / 1e9:.1f}B"
        if abs(value) >= 1e6:
            return f"{value / 1e6:.1f}M"
        if abs(value) >= 1e3:
            return f"{value / 1e3:.1f}K"
        return f"{value:.2f}"


__all__ = ["DimensionAnalysisService", "DimensionAnalysisResult", "FinancialMetric"]