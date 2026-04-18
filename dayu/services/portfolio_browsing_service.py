"""portfolio 只读浏览服务。

该服务把财报仓储原始数据聚合为 UI 友好的稳定 DTO，本身不写入任何文件。
所有数据访问严格通过 ``dayu.fins.storage`` 仓储协议完成，避免直接访问
工作区目录或 manifest 文件。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from dayu.fins.domain.document_models import (
    CompanyMeta,
    CompanyMetaInventoryEntry,
    DocumentMeta,
    DocumentQuery,
    DocumentSummary,
    FileObjectMeta,
)
from dayu.fins.domain.enums import SourceKind
from dayu.fins.storage.repository_protocols import (
    CompanyMetaRepositoryProtocol,
    DocumentBlobRepositoryProtocol,
    FilingMaintenanceRepositoryProtocol,
    ProcessedDocumentRepositoryProtocol,
    SourceDocumentRepositoryProtocol,
)
from dayu.services.contracts import (
    CompanyView,
    FilingDetailView,
    FilingFileBlob,
    FilingFileView,
    FilingProcessedView,
    FilingSectionView,
    FilingTableView,
    FilingView,
    PortfolioHealthView,
    ProcessedArtifactView,
    RejectedFilingView,
    XbrlFactView,
)


_AVAILABLE_STATUS = "available"
_DEFAULT_BLOB_CONTENT_TYPE = "application/octet-stream"
_INVENTORY_AVAILABLE_DETAIL = ""
_REJECTED_SAMPLE_LIMIT = 10


@dataclass(frozen=True)
class PortfolioBrowsingService:
    """portfolio 浏览服务。

    依赖窄仓储协议，聚合公司/filing/processed 信息为 UI 视图。

    Attributes:
        company_meta_repository: 公司元数据仓储。
        source_document_repository: 源文档仓储。
        processed_document_repository: processed 产物仓储。
        document_blob_repository: 文件对象仓储。
        filing_maintenance_repository: filing 维护治理仓储。
    """

    company_meta_repository: CompanyMetaRepositoryProtocol
    source_document_repository: SourceDocumentRepositoryProtocol
    processed_document_repository: ProcessedDocumentRepositoryProtocol
    document_blob_repository: DocumentBlobRepositoryProtocol
    filing_maintenance_repository: FilingMaintenanceRepositoryProtocol

    def list_companies(self) -> list[CompanyView]:
        """列出 workspace 中所有公司及其汇总状态。

        Returns:
            公司视图列表，按 ticker 升序排序。

        Raises:
            OSError: 仓储扫描失败时抛出。
        """

        inventory = self.company_meta_repository.scan_company_meta_inventory()
        result: list[CompanyView] = []
        for entry in inventory:
            result.append(self._build_company_view(entry))
        result.sort(key=lambda view: view.ticker or view.directory_name)
        return result

    def list_filings(
        self,
        ticker: str,
        *,
        form_type: str | None = None,
        fiscal_year: int | None = None,
        fiscal_period: str | None = None,
        include_deleted: bool = False,
    ) -> list[FilingView]:
        """列出指定公司的 filings。

        Args:
            ticker: 股票代码。
            form_type: 报告类型过滤；``None`` 不过滤。
            fiscal_year: 财年过滤；``None`` 不过滤。
            fiscal_period: 财季过滤；``None`` 不过滤。
            include_deleted: 是否包含已逻辑删除的 filings。

        Returns:
            filing 视图列表，按 filing_date 倒序、document_id 升序排序。

        Raises:
            OSError: 仓储读取失败时抛出。
        """

        normalized_ticker = ticker.strip()
        processed_ids = self._collect_processed_filing_ids(normalized_ticker)
        document_ids = self.source_document_repository.list_source_document_ids(
            normalized_ticker,
            SourceKind.FILING,
        )
        result: list[FilingView] = []
        for document_id in document_ids:
            meta = self.source_document_repository.get_source_meta(
                normalized_ticker,
                document_id,
                SourceKind.FILING,
            )
            view = _build_filing_view(
                ticker=normalized_ticker,
                document_id=document_id,
                meta=meta,
                has_processed=document_id in processed_ids,
            )
            if not include_deleted and view.is_deleted:
                continue
            if form_type and view.form_type != form_type:
                continue
            if fiscal_year is not None and view.fiscal_year != fiscal_year:
                continue
            if fiscal_period and view.fiscal_period != fiscal_period:
                continue
            result.append(view)
        result.sort(key=_filing_sort_key, reverse=True)
        return result

    def get_filing_detail(self, ticker: str, document_id: str) -> FilingDetailView:
        """读取单份 filing 的详情。"""

        normalized_ticker = ticker.strip()
        normalized_document_id = document_id.strip()
        meta = self.source_document_repository.get_source_meta(
            normalized_ticker,
            normalized_document_id,
            SourceKind.FILING,
        )
        processed_ids = self._collect_processed_filing_ids(normalized_ticker)
        filing_view = _build_filing_view(
            ticker=normalized_ticker,
            document_id=normalized_document_id,
            meta=meta,
            has_processed=normalized_document_id in processed_ids,
        )
        handle = self.source_document_repository.get_source_handle(
            normalized_ticker,
            normalized_document_id,
            SourceKind.FILING,
        )
        file_metas = self.document_blob_repository.list_files(handle)
        files = tuple(_build_filing_file_view(item) for item in file_metas)
        processed_summary: ProcessedArtifactView | None = None
        section_count = 0
        table_count = 0
        has_financials = False
        if filing_view.has_processed:
            summary = self._find_processed_summary(normalized_ticker, normalized_document_id)
            if summary is not None:
                processed_summary = _build_processed_view(normalized_ticker, summary)
                section_count = summary.section_count
                table_count = summary.table_count
                has_financials = summary.has_financials
        return FilingDetailView(
            filing=filing_view,
            files=files,
            processed_summary=processed_summary,
            section_count=section_count,
            table_count=table_count,
            has_financials=has_financials,
        )

    def get_filing_processed(self, ticker: str, document_id: str) -> FilingProcessedView:
        """读取单份 filing 的 processed 详情。"""

        normalized_ticker = ticker.strip()
        normalized_document_id = document_id.strip()
        summary = self._find_processed_summary(normalized_ticker, normalized_document_id)
        if summary is None:
            raise FileNotFoundError(
                f"未找到 processed 产物: ticker={normalized_ticker} document_id={normalized_document_id}"
            )
        artifact_view = _build_processed_view(normalized_ticker, summary)
        meta = self.processed_document_repository.get_processed_meta(
            normalized_ticker,
            normalized_document_id,
        )
        sections = tuple(_build_section_view(item, index) for index, item in enumerate(_iter_meta_items(meta, "sections")))
        tables = tuple(_build_table_view(item) for item in _iter_meta_items(meta, "tables"))
        xbrl_facts = tuple(_build_xbrl_fact_view(item) for item in _iter_xbrl_facts(meta))
        return FilingProcessedView(
            artifact=artifact_view,
            sections=sections,
            tables=tables,
            xbrl_facts=xbrl_facts,
        )

    def list_processed_artifacts(
        self,
        ticker: str,
        *,
        form_type: str | None = None,
        fiscal_year: int | None = None,
        fiscal_period: str | None = None,
        include_deleted: bool = False,
    ) -> list[ProcessedArtifactView]:
        """列出指定公司的 processed 产物。"""

        normalized_ticker = ticker.strip()
        query = DocumentQuery(
            form_type=form_type,
            fiscal_years=[fiscal_year] if fiscal_year is not None else None,
            fiscal_periods=[fiscal_period] if fiscal_period else None,
            source_kind=None,
            include_deleted=include_deleted,
        )
        summaries = self.processed_document_repository.list_processed_documents(normalized_ticker, query)
        result = [_build_processed_view(normalized_ticker, item) for item in summaries]
        result.sort(key=_processed_sort_key, reverse=True)
        return result

    def get_portfolio_health(self, ticker: str) -> PortfolioHealthView:
        """计算单家公司的健康度。"""

        normalized_ticker = ticker.strip()
        all_filings = self.list_filings(normalized_ticker, include_deleted=True)
        active_filings = [item for item in all_filings if not item.is_deleted]
        ingest_incomplete = sum(1 for item in active_filings if not item.ingest_complete)
        deleted = sum(1 for item in all_filings if item.is_deleted)
        processed_filings = sum(1 for item in active_filings if item.has_processed)
        missing_processed = sum(1 for item in active_filings if not item.has_processed)
        rejected = self.filing_maintenance_repository.list_rejected_filing_artifacts(normalized_ticker)
        rejected_views = tuple(_build_rejected_view(item) for item in rejected)
        rejected_views = tuple(sorted(rejected_views, key=lambda view: view.rejected_at, reverse=True))
        rejected_samples = rejected_views[:_REJECTED_SAMPLE_LIMIT]
        return PortfolioHealthView(
            ticker=normalized_ticker,
            total_filings=len(active_filings),
            ingest_incomplete_filings=ingest_incomplete,
            deleted_filings=deleted,
            processed_filings=processed_filings,
            missing_processed_filings=missing_processed,
            rejected_filings=len(rejected_views),
            rejected_samples=rejected_samples,
        )

    def read_filing_file(self, ticker: str, document_id: str, filename: str) -> FilingFileBlob:
        """读取 filing 目录下指定文件。"""

        normalized_ticker = ticker.strip()
        normalized_document_id = document_id.strip()
        normalized_filename = filename.strip()
        if not normalized_filename:
            raise FileNotFoundError("filename 不能为空")
        handle = self.source_document_repository.get_source_handle(
            normalized_ticker,
            normalized_document_id,
            SourceKind.FILING,
        )
        file_metas = self.document_blob_repository.list_files(handle)
        target_meta = _find_file_meta_by_name(file_metas, normalized_filename)
        content = self.document_blob_repository.read_file_bytes(handle, normalized_filename)
        content_type = target_meta.content_type or _DEFAULT_BLOB_CONTENT_TYPE
        return FilingFileBlob(
            filename=normalized_filename,
            content=content,
            content_type=content_type,
        )

    def _build_company_view(self, entry: CompanyMetaInventoryEntry) -> CompanyView:
        """把扫描条目转换为公司视图。"""

        if entry.status != _AVAILABLE_STATUS or entry.company_meta is None:
            return CompanyView(
                ticker="",
                company_name="",
                market="",
                company_id="",
                updated_at="",
                ticker_aliases=(),
                directory_name=entry.directory_name,
                status=entry.status,
                detail=entry.detail,
                filing_count=0,
                processed_count=0,
            )
        company_meta = entry.company_meta
        filings = self.list_filings(company_meta.ticker)
        processed_count = sum(1 for filing in filings if filing.has_processed)
        return _build_company_view_from_meta(
            entry=entry,
            company_meta=company_meta,
            filing_count=len(filings),
            processed_count=processed_count,
        )

    def _collect_processed_filing_ids(self, ticker: str) -> set[str]:
        """收集已存在 processed 产物的 filing document_id 集合。"""

        query = DocumentQuery(source_kind=SourceKind.FILING.value, include_deleted=False)
        summaries = self.processed_document_repository.list_processed_documents(ticker, query)
        return {summary.document_id for summary in summaries}

    def _find_processed_summary(self, ticker: str, document_id: str) -> DocumentSummary | None:
        """在 processed manifest 中按 document_id 定位摘要。"""

        query = DocumentQuery(include_deleted=True)
        summaries = self.processed_document_repository.list_processed_documents(ticker, query)
        for summary in summaries:
            if summary.document_id == document_id:
                return summary
        return None


def _build_company_view_from_meta(
    *,
    entry: CompanyMetaInventoryEntry,
    company_meta: CompanyMeta,
    filing_count: int,
    processed_count: int,
) -> CompanyView:
    """根据公司元数据构造公司视图。"""

    return CompanyView(
        ticker=company_meta.ticker,
        company_name=company_meta.company_name,
        market=company_meta.market,
        company_id=company_meta.company_id,
        updated_at=company_meta.updated_at,
        ticker_aliases=tuple(company_meta.ticker_aliases),
        directory_name=entry.directory_name,
        status=entry.status,
        detail=_INVENTORY_AVAILABLE_DETAIL,
        filing_count=filing_count,
        processed_count=processed_count,
    )


def _build_filing_view(
    *,
    ticker: str,
    document_id: str,
    meta: DocumentMeta,
    has_processed: bool,
) -> FilingView:
    """从 source meta 构造 filing 视图。"""

    return FilingView(
        ticker=ticker,
        document_id=document_id,
        form_type=_optional_str(meta.get("form_type")),
        fiscal_year=_optional_int(meta.get("fiscal_year")),
        fiscal_period=_optional_str(meta.get("fiscal_period")),
        report_date=_optional_str(meta.get("report_date")),
        filing_date=_optional_str(meta.get("filing_date")),
        amended=bool(meta.get("amended", False)),
        ingest_complete=bool(meta.get("ingest_complete", True)),
        is_deleted=bool(meta.get("is_deleted", False)),
        has_xbrl=_optional_bool(meta.get("has_xbrl")),
        has_processed=has_processed,
        primary_document=_str_or_empty(meta.get("primary_document")),
    )


def _build_filing_file_view(file_meta: FileObjectMeta) -> FilingFileView:
    """从 FileObjectMeta 构造文件视图。"""

    return FilingFileView(
        name=_filename_from_uri(file_meta.uri),
        size=file_meta.size,
        content_type=file_meta.content_type,
        sha256=file_meta.sha256,
    )


def _build_processed_view(ticker: str, summary: DocumentSummary) -> ProcessedArtifactView:
    """从 DocumentSummary 构造 processed 视图。"""

    return ProcessedArtifactView(
        ticker=ticker,
        document_id=summary.document_id,
        source_kind=summary.source_kind,
        form_type=summary.form_type,
        fiscal_year=summary.fiscal_year,
        fiscal_period=summary.fiscal_period,
        report_date=summary.report_date,
        filing_date=summary.filing_date,
        amended=summary.amended,
        is_deleted=summary.is_deleted,
        document_version=summary.document_version,
        quality=summary.quality,
        has_financials=summary.has_financials,
        section_count=summary.section_count,
        table_count=summary.table_count,
    )


def _build_section_view(item: Mapping[str, Any], fallback_order: int) -> FilingSectionView:
    """从 processed meta 中的 sections 条目构造 section 视图。"""

    return FilingSectionView(
        section_id=_str_or_empty(item.get("section_id") or item.get("id")),
        title=_str_or_empty(item.get("title")),
        depth=_optional_int(item.get("depth")) or 0,
        order=_optional_int(item.get("order")) or fallback_order,
        char_count=_optional_int(item.get("char_count")) or 0,
    )


def _build_table_view(item: Mapping[str, Any]) -> FilingTableView:
    """从 processed meta 中的 tables 条目构造 table 视图。"""

    return FilingTableView(
        table_id=_str_or_empty(item.get("table_id") or item.get("id")),
        caption=_str_or_empty(item.get("caption") or item.get("title")),
        section_id=_str_or_empty(item.get("section_id")),
        row_count=_optional_int(item.get("row_count")) or 0,
        column_count=_optional_int(item.get("column_count")) or 0,
    )


def _build_xbrl_fact_view(item: Mapping[str, Any]) -> XbrlFactView:
    """从 processed meta 中的 xbrl facts 条目构造视图。"""

    return XbrlFactView(
        concept=_str_or_empty(item.get("concept") or item.get("name")),
        unit=_str_or_empty(item.get("unit")),
        value=_str_or_empty(item.get("value")),
        period_start=_str_or_empty(item.get("period_start")),
        period_end=_str_or_empty(item.get("period_end")),
        decimals=_str_or_empty(item.get("decimals")),
        context_id=_str_or_empty(item.get("context_id")),
    )


def _build_rejected_view(artifact: Any) -> RejectedFilingView:
    """从 RejectedFilingArtifact 构造视图。"""

    return RejectedFilingView(
        ticker=_str_or_empty(getattr(artifact, "ticker", "")),
        document_id=_str_or_empty(getattr(artifact, "document_id", "")),
        accession_number=_str_or_empty(getattr(artifact, "accession_number", "")),
        form_type=_str_or_empty(getattr(artifact, "form_type", "")),
        filing_date=_str_or_empty(getattr(artifact, "filing_date", "")),
        rejection_reason=_str_or_empty(getattr(artifact, "rejection_reason", "")),
        rejection_category=_str_or_empty(getattr(artifact, "rejection_category", "")),
        rejected_at=_str_or_empty(getattr(artifact, "rejected_at", "")),
    )


def _iter_meta_items(meta: DocumentMeta, key: str) -> Iterable[Mapping[str, Any]]:
    """遍历 processed meta 内某个数组字段。"""

    raw = meta.get(key)
    if not isinstance(raw, list):
        return ()
    items: list[Mapping[str, Any]] = []
    for item in raw:
        if isinstance(item, Mapping):
            items.append(item)
    return items


def _iter_xbrl_facts(meta: DocumentMeta) -> Iterable[Mapping[str, Any]]:
    """遍历 processed meta 内的 XBRL facts。"""

    candidate_keys = ("xbrl_facts", "xbrl", "financials_xbrl_facts")
    for key in candidate_keys:
        raw = meta.get(key)
        if isinstance(raw, list):
            return [item for item in raw if isinstance(item, Mapping)]
        if isinstance(raw, Mapping):
            facts = raw.get("facts")
            if isinstance(facts, list):
                return [item for item in facts if isinstance(item, Mapping)]
    return ()


def _filing_sort_key(view: FilingView) -> tuple[str, str]:
    """filing 视图排序键：先按 filing_date 倒序，再按 document_id 字典序。"""

    return (view.filing_date or "", view.document_id)


def _processed_sort_key(view: ProcessedArtifactView) -> tuple[str, str]:
    """processed 视图排序键。"""

    return (view.filing_date or view.report_date or "", view.document_id)


def _filename_from_uri(uri: str) -> str:
    """从文件 URI 中提取文件名。"""

    raw = uri.strip()
    if not raw:
        return ""
    if "://" in raw:
        raw = raw.split("://", 1)[1]
    raw = raw.rstrip("/")
    if not raw:
        return ""
    return raw.split("/")[-1]


def _find_file_meta_by_name(file_metas: list[FileObjectMeta], filename: str) -> FileObjectMeta:
    """按文件名查找 FileObjectMeta。"""

    for item in file_metas:
        if _filename_from_uri(item.uri) == filename:
            return item
    raise FileNotFoundError(f"未找到文件: {filename}")


def _optional_str(value: Any) -> str | None:
    """规范化字符串可选值。"""

    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _str_or_empty(value: Any) -> str:
    """规范化字符串，空值返回空串。"""

    if value is None:
        return ""
    return str(value).strip()


def _optional_int(value: Any) -> int | None:
    """规范化整数可选值。"""

    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return int(text)
        except ValueError:
            return None
    return None


def _optional_bool(value: Any) -> bool | None:
    """规范化布尔可选值。"""

    if isinstance(value, bool):
        return value
    return None


__all__ = ["PortfolioBrowsingService"]
