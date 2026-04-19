"""Portfolio 浏览 REST 端点。

该路由聚合 ``PortfolioBrowsingService`` 能力，向 UI 暴露 portfolio 只读浏览 API：
- 公司列表
- filings 列表与详情
- processed 产物浏览
- 健康度摘要
- filing 文件下载
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.responses import Response
from pydantic import BaseModel

from dayu.services.protocols import PortfolioBrowsingServiceProtocol


def create_portfolio_router(service: PortfolioBrowsingServiceProtocol) -> Any:
    """创建 portfolio 浏览路由。

    Args:
        service: portfolio 浏览服务实例。

    Returns:
        FastAPI 路由对象。

    Raises:
        无。
    """

    router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

    # === 响应模型 ===

    class CompanyResponse(BaseModel):
        """公司列表条目响应。"""

        ticker: str
        company_name: str
        market: str
        company_id: str
        updated_at: str
        ticker_aliases: list[str]
        directory_name: str
        status: str
        detail: str
        filing_count: int
        processed_count: int

    class FilingFileResponse(BaseModel):
        """filing 文件条目响应。"""

        name: str
        size: int | None = None
        content_type: str | None = None
        sha256: str | None = None

    class FilingResponse(BaseModel):
        """filing 列表条目响应。"""

        ticker: str
        document_id: str
        form_type: str | None = None
        fiscal_year: int | None = None
        fiscal_period: str | None = None
        report_date: str | None = None
        filing_date: str | None = None
        amended: bool
        ingest_complete: bool
        is_deleted: bool
        has_xbrl: bool | None = None
        has_processed: bool
        primary_document: str

    class ProcessedSummaryResponse(BaseModel):
        """processed 摘要响应。"""

        ticker: str
        document_id: str
        source_kind: str
        form_type: str | None = None
        fiscal_year: int | None = None
        fiscal_period: str | None = None
        report_date: str | None = None
        filing_date: str | None = None
        amended: bool
        is_deleted: bool
        document_version: str
        quality: str
        has_financials: bool
        section_count: int
        table_count: int

    class FilingDetailResponse(BaseModel):
        """filing 详情响应。"""

        filing: FilingResponse
        files: list[FilingFileResponse]
        processed_summary: ProcessedSummaryResponse | None = None
        section_count: int
        table_count: int
        has_financials: bool

    class FilingSectionResponse(BaseModel):
        """section 条目响应。"""

        section_id: str
        title: str
        depth: int
        order: int
        char_count: int

    class FilingTableResponse(BaseModel):
        """table 条目响应。"""

        table_id: str
        caption: str
        section_id: str
        row_count: int
        column_count: int

    class XbrlFactResponse(BaseModel):
        """XBRL fact 条目响应。"""

        concept: str
        unit: str
        value: str
        period_start: str
        period_end: str
        decimals: str
        context_id: str

    class FilingProcessedResponse(BaseModel):
        """filing processed 详情响应。"""

        artifact: ProcessedSummaryResponse
        sections: list[FilingSectionResponse]
        tables: list[FilingTableResponse]
        xbrl_facts: list[XbrlFactResponse]

    class RejectedFilingResponse(BaseModel):
        """被拒绝 filing 响应。"""

        ticker: str
        document_id: str
        accession_number: str
        form_type: str
        filing_date: str
        rejection_reason: str
        rejection_category: str
        rejected_at: str

    class PortfolioHealthResponse(BaseModel):
        """健康度响应。"""

        ticker: str
        total_filings: int
        ingest_incomplete_filings: int
        deleted_filings: int
        processed_filings: int
        missing_processed_filings: int
        rejected_filings: int
        rejected_samples: list[RejectedFilingResponse]

    # === 转换函数 ===

    def _company_to_response(view: Any) -> CompanyResponse:
        """公司视图转响应。"""

        return CompanyResponse(
            ticker=view.ticker,
            company_name=view.company_name,
            market=view.market,
            company_id=view.company_id,
            updated_at=view.updated_at,
            ticker_aliases=list(view.ticker_aliases),
            directory_name=view.directory_name,
            status=view.status,
            detail=view.detail,
            filing_count=view.filing_count,
            processed_count=view.processed_count,
        )

    def _filing_to_response(view: Any) -> FilingResponse:
        """filing 视图转响应。"""

        return FilingResponse(
            ticker=view.ticker,
            document_id=view.document_id,
            form_type=view.form_type,
            fiscal_year=view.fiscal_year,
            fiscal_period=view.fiscal_period,
            report_date=view.report_date,
            filing_date=view.filing_date,
            amended=view.amended,
            ingest_complete=view.ingest_complete,
            is_deleted=view.is_deleted,
            has_xbrl=view.has_xbrl,
            has_processed=view.has_processed,
            primary_document=view.primary_document,
        )

    def _file_to_response(view: Any) -> FilingFileResponse:
        """文件视图转响应。"""

        return FilingFileResponse(
            name=view.name,
            size=view.size,
            content_type=view.content_type,
            sha256=view.sha256,
        )

    def _processed_to_response(view: Any) -> ProcessedSummaryResponse:
        """processed 视图转响应。"""

        return ProcessedSummaryResponse(
            ticker=view.ticker,
            document_id=view.document_id,
            source_kind=view.source_kind,
            form_type=view.form_type,
            fiscal_year=view.fiscal_year,
            fiscal_period=view.fiscal_period,
            report_date=view.report_date,
            filing_date=view.filing_date,
            amended=view.amended,
            is_deleted=view.is_deleted,
            document_version=view.document_version,
            quality=view.quality,
            has_financials=view.has_financials,
            section_count=view.section_count,
            table_count=view.table_count,
        )

    def _section_to_response(view: Any) -> FilingSectionResponse:
        """section 视图转响应。"""

        return FilingSectionResponse(
            section_id=view.section_id,
            title=view.title,
            depth=view.depth,
            order=view.order,
            char_count=view.char_count,
        )

    def _table_to_response(view: Any) -> FilingTableResponse:
        """table 视图转响应。"""

        return FilingTableResponse(
            table_id=view.table_id,
            caption=view.caption,
            section_id=view.section_id,
            row_count=view.row_count,
            column_count=view.column_count,
        )

    def _xbrl_to_response(view: Any) -> XbrlFactResponse:
        """XBRL fact 视图转响应。"""

        return XbrlFactResponse(
            concept=view.concept,
            unit=view.unit,
            value=view.value,
            period_start=view.period_start,
            period_end=view.period_end,
            decimals=view.decimals,
            context_id=view.context_id,
        )

    def _rejected_to_response(view: Any) -> RejectedFilingResponse:
        """被拒绝 filing 视图转响应。"""

        return RejectedFilingResponse(
            ticker=view.ticker,
            document_id=view.document_id,
            accession_number=view.accession_number,
            form_type=view.form_type,
            filing_date=view.filing_date,
            rejection_reason=view.rejection_reason,
            rejection_category=view.rejection_category,
            rejected_at=view.rejected_at,
        )

    def _health_to_response(view: Any) -> PortfolioHealthResponse:
        """健康度视图转响应。"""

        return PortfolioHealthResponse(
            ticker=view.ticker,
            total_filings=view.total_filings,
            ingest_incomplete_filings=view.ingest_incomplete_filings,
            deleted_filings=view.deleted_filings,
            processed_filings=view.processed_filings,
            missing_processed_filings=view.missing_processed_filings,
            rejected_filings=view.rejected_filings,
            rejected_samples=[_rejected_to_response(s) for s in view.rejected_samples],
        )

    # === 路由端点 ===

    @router.get("/companies", response_model=list[CompanyResponse])
    async def list_companies() -> list[CompanyResponse]:
        """列出所有公司。"""

        views = service.list_companies()
        return [_company_to_response(v) for v in views]

    @router.get(
        "/companies/{ticker}/filings",
        response_model=list[FilingResponse],
    )
    async def list_filings(
        ticker: str = Path(description="股票代码"),
        form_type: str | None = Query(default=None, description="报告类型过滤"),
        fiscal_year: int | None = Query(default=None, description="财年过滤"),
        fiscal_period: str | None = Query(default=None, description="财季过滤"),
        include_deleted: bool = Query(default=False, description="包含已删除"),
    ) -> list[FilingResponse]:
        """列出指定公司的 filings。"""

        views = service.list_filings(
            ticker,
            form_type=form_type,
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period,
            include_deleted=include_deleted,
        )
        return [_filing_to_response(v) for v in views]

    @router.get(
        "/companies/{ticker}/filings/{document_id}",
        response_model=FilingDetailResponse,
    )
    async def get_filing_detail(
        ticker: str = Path(description="股票代码"),
        document_id: str = Path(description="文档 ID"),
    ) -> FilingDetailResponse:
        """获取 filing 详情。"""

        try:
            view = service.get_filing_detail(ticker, document_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return FilingDetailResponse(
            filing=_filing_to_response(view.filing),
            files=[_file_to_response(f) for f in view.files],
            processed_summary=_processed_to_response(view.processed_summary) if view.processed_summary else None,
            section_count=view.section_count,
            table_count=view.table_count,
            has_financials=view.has_financials,
        )

    @router.get(
        "/companies/{ticker}/filings/{document_id}/processed",
        response_model=FilingProcessedResponse,
    )
    async def get_filing_processed(
        ticker: str = Path(description="股票代码"),
        document_id: str = Path(description="文档 ID"),
    ) -> FilingProcessedResponse:
        """获取 filing processed 详情。"""

        try:
            view = service.get_filing_processed(ticker, document_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return FilingProcessedResponse(
            artifact=_processed_to_response(view.artifact),
            sections=[_section_to_response(s) for s in view.sections],
            tables=[_table_to_response(t) for t in view.tables],
            xbrl_facts=[_xbrl_to_response(f) for f in view.xbrl_facts],
        )

    @router.get(
        "/companies/{ticker}/processed",
        response_model=list[ProcessedSummaryResponse],
    )
    async def list_processed_artifacts(
        ticker: str = Path(description="股票代码"),
        form_type: str | None = Query(default=None, description="报告类型过滤"),
        fiscal_year: int | None = Query(default=None, description="财年过滤"),
        fiscal_period: str | None = Query(default=None, description="财季过滤"),
        include_deleted: bool = Query(default=False, description="包含已删除"),
    ) -> list[ProcessedSummaryResponse]:
        """列出 processed 产物。"""

        views = service.list_processed_artifacts(
            ticker,
            form_type=form_type,
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period,
            include_deleted=include_deleted,
        )
        return [_processed_to_response(v) for v in views]

    @router.get(
        "/companies/{ticker}/health",
        response_model=PortfolioHealthResponse,
    )
    async def get_portfolio_health(
        ticker: str = Path(description="股票代码"),
    ) -> PortfolioHealthResponse:
        """获取健康度摘要。"""

        view = service.get_portfolio_health(ticker)
        return _health_to_response(view)

    @router.get(
        "/companies/{ticker}/filings/{document_id}/files/{filename}",
    )
    async def read_filing_file(
        ticker: str = Path(description="股票代码"),
        document_id: str = Path(description="文档 ID"),
        filename: str = Path(description="文件名"),
        preview: bool = Query(default=False, description="是否预览模式（inline）"),
    ) -> Response:
        """下载或预览 filing 文件。"""

        try:
            blob = service.read_filing_file(ticker, document_id, filename)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        # 预览模式：PDF/HTML/图片使用 inline，其他使用 attachment
        disposition = "attachment"
        if preview:
            content_type = blob.content_type or ""
            if content_type.startswith(("application/pdf", "text/html", "image/")):
                disposition = "inline"

        return Response(
            content=blob.content,
            media_type=blob.content_type,
            headers={"Content-Disposition": f"{disposition}; filename={blob.filename}"},
        )

    return router


__all__ = ["create_portfolio_router"]