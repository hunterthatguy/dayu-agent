"""PortfolioBrowsingService 单元测试。

测试只构造内存假仓储，验证服务把仓储数据正确聚合为 UI DTO，
不触碰真实文件系统也不复用 fins 集成测试基础设施。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from dayu.fins.domain.document_models import (
    BatchToken,
    CompanyMeta,
    CompanyMetaInventoryEntry,
    DocumentEntry,
    DocumentHandle,
    DocumentMeta,
    DocumentQuery,
    DocumentSummary,
    FileObjectMeta,
    ProcessedCreateRequest,
    ProcessedDeleteRequest,
    ProcessedHandle,
    ProcessedUpdateRequest,
    RejectedFilingArtifact,
    RejectedFilingArtifactUpsertRequest,
    SourceDocumentStateChangeRequest,
    SourceDocumentUpsertRequest,
    SourceHandle,
)
from dayu.fins.domain.enums import SourceKind
from dayu.engine.processors.source import Source
from dayu.fins.storage.repository_protocols import (
    BatchingRepositoryProtocol,
    CompanyMetaRepositoryProtocol,
    DocumentBlobRepositoryProtocol,
    FilingMaintenanceRepositoryProtocol,
    ProcessedDocumentRepositoryProtocol,
    SourceDocumentRepositoryProtocol,
)
from dayu.services.portfolio_browsing_service import PortfolioBrowsingService


@dataclass
class _FakeCompanyMetaRepository(CompanyMetaRepositoryProtocol):
    """内存公司元数据仓储。"""

    inventory: list[CompanyMetaInventoryEntry] = field(default_factory=list)
    metas: dict[str, CompanyMeta] = field(default_factory=dict)

    def scan_company_meta_inventory(self) -> list[CompanyMetaInventoryEntry]:
        return list(self.inventory)

    def get_company_meta(self, ticker: str) -> CompanyMeta:
        return self.metas[ticker]

    def upsert_company_meta(self, meta: CompanyMeta) -> None:
        self.metas[meta.ticker] = meta

    def resolve_existing_ticker(self, ticker_candidates: list[str]) -> str | None:
        for candidate in ticker_candidates:
            if candidate in self.metas:
                return candidate
        return None


@dataclass
class _FakeSourceDocumentRepository(SourceDocumentRepositoryProtocol):
    """内存源文档仓储。"""

    document_ids: dict[tuple[str, str], list[str]] = field(default_factory=dict)
    metas: dict[tuple[str, str, str], DocumentMeta] = field(default_factory=dict)

    def has_source_storage_root(self, ticker: str, source_kind: SourceKind) -> bool:
        return (ticker, source_kind.value) in self.document_ids

    def has_filing_xbrl_instance(self, ticker: str, document_id: str) -> bool:
        return False

    def create_source_document(
        self,
        req: SourceDocumentUpsertRequest,
        source_kind: SourceKind,
    ) -> DocumentHandle:
        raise NotImplementedError

    def update_source_document(
        self,
        req: SourceDocumentUpsertRequest,
        source_kind: SourceKind,
    ) -> DocumentHandle:
        raise NotImplementedError

    def delete_source_document(self, req: SourceDocumentStateChangeRequest) -> None:
        raise NotImplementedError

    def restore_source_document(self, req: SourceDocumentStateChangeRequest) -> DocumentHandle:
        raise NotImplementedError

    def get_source_meta(
        self,
        ticker: str,
        document_id: str,
        source_kind: SourceKind,
    ) -> DocumentMeta:
        return dict(self.metas[(ticker, document_id, source_kind.value)])

    def replace_source_meta(
        self,
        ticker: str,
        document_id: str,
        source_kind: SourceKind,
        meta: DocumentMeta,
    ) -> None:
        self.metas[(ticker, document_id, source_kind.value)] = dict(meta)

    def list_source_document_ids(self, ticker: str, source_kind: SourceKind) -> list[str]:
        return list(self.document_ids.get((ticker, source_kind.value), []))

    def get_source_handle(
        self,
        ticker: str,
        document_id: str,
        source_kind: SourceKind,
    ) -> SourceHandle:
        return SourceHandle(ticker=ticker, document_id=document_id, source_kind=source_kind.value)

    def get_primary_file(
        self,
        ticker: str,
        document_id: str,
        source_kind: SourceKind,
    ) -> FileObjectMeta:
        raise NotImplementedError

    def get_source(
        self,
        ticker: str,
        document_id: str,
        source_kind: SourceKind,
        filename: str,
    ) -> Source:
        raise NotImplementedError

    def get_primary_source(
        self,
        ticker: str,
        document_id: str,
        source_kind: SourceKind,
    ) -> Source:
        raise NotImplementedError


@dataclass
class _FakeProcessedDocumentRepository(ProcessedDocumentRepositoryProtocol):
    """内存 processed 文档仓储。"""

    summaries: dict[str, list[DocumentSummary]] = field(default_factory=dict)
    metas: dict[tuple[str, str], DocumentMeta] = field(default_factory=dict)

    def create_processed(self, req: ProcessedCreateRequest) -> DocumentHandle:
        raise NotImplementedError

    def update_processed(self, req: ProcessedUpdateRequest) -> DocumentHandle:
        raise NotImplementedError

    def delete_processed(self, req: ProcessedDeleteRequest) -> None:
        raise NotImplementedError

    def get_processed_handle(self, ticker: str, document_id: str) -> ProcessedHandle:
        return ProcessedHandle(ticker=ticker, document_id=document_id)

    def get_processed_meta(self, ticker: str, document_id: str) -> DocumentMeta:
        return dict(self.metas[(ticker, document_id)])

    def list_processed_documents(self, ticker: str, query: DocumentQuery) -> list[DocumentSummary]:
        result: list[DocumentSummary] = []
        for summary in self.summaries.get(ticker, []):
            if not query.include_deleted and summary.is_deleted:
                continue
            if query.source_kind and summary.source_kind != query.source_kind:
                continue
            if query.form_type and summary.form_type != query.form_type:
                continue
            if query.fiscal_years and summary.fiscal_year not in query.fiscal_years:
                continue
            if query.fiscal_periods and summary.fiscal_period not in query.fiscal_periods:
                continue
            result.append(summary)
        return result

    def clear_processed_documents(self, ticker: str) -> None:
        raise NotImplementedError

    def mark_processed_reprocess_required(
        self,
        ticker: str,
        document_id: str,
        required: bool,
    ) -> None:
        raise NotImplementedError


@dataclass
class _FakeDocumentBlobRepository(DocumentBlobRepositoryProtocol):
    """内存文件对象仓储。"""

    file_metas: dict[tuple[str, str], list[FileObjectMeta]] = field(default_factory=dict)
    file_bytes: dict[tuple[str, str, str], bytes] = field(default_factory=dict)

    def list_entries(self, handle: SourceHandle | ProcessedHandle) -> list[DocumentEntry]:
        return []

    def read_file_bytes(
        self,
        handle: SourceHandle | ProcessedHandle,
        name: str,
    ) -> bytes:
        ticker, document_id = handle.ticker, handle.document_id
        return self.file_bytes[(ticker, document_id, name)]

    def delete_entry(self, handle: SourceHandle | ProcessedHandle, name: str) -> None:
        raise NotImplementedError

    def store_file(
        self,
        handle: SourceHandle | ProcessedHandle,
        filename: str,
        data: Any,
        *,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> FileObjectMeta:
        raise NotImplementedError

    def list_files(self, handle: SourceHandle | ProcessedHandle) -> list[FileObjectMeta]:
        return list(self.file_metas.get((handle.ticker, handle.document_id), []))


@dataclass
class _FakeFilingMaintenanceRepository(FilingMaintenanceRepositoryProtocol):
    """内存 filing 维护治理仓储。"""

    rejected: dict[str, list[RejectedFilingArtifact]] = field(default_factory=dict)

    def clear_filing_documents(self, ticker: str) -> None:
        raise NotImplementedError

    def load_download_rejection_registry(self, ticker: str) -> dict[str, dict[str, str]]:
        return {}

    def save_download_rejection_registry(
        self,
        ticker: str,
        registry: dict[str, dict[str, str]],
    ) -> None:
        raise NotImplementedError

    def store_rejected_filing_file(
        self,
        ticker: str,
        document_id: str,
        filename: str,
        data: Any,
        *,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> FileObjectMeta:
        raise NotImplementedError

    def upsert_rejected_filing_artifact(
        self,
        req: RejectedFilingArtifactUpsertRequest,
    ) -> RejectedFilingArtifact:
        raise NotImplementedError

    def get_rejected_filing_artifact(
        self,
        ticker: str,
        document_id: str,
    ) -> RejectedFilingArtifact:
        for item in self.rejected.get(ticker, []):
            if item.document_id == document_id:
                return item
        raise KeyError(document_id)

    def list_rejected_filing_artifacts(self, ticker: str) -> list[RejectedFilingArtifact]:
        return list(self.rejected.get(ticker, []))

    def read_rejected_filing_file_bytes(
        self,
        ticker: str,
        document_id: str,
        filename: str,
    ) -> bytes:
        raise NotImplementedError

    def cleanup_stale_filing_documents(
        self,
        ticker: str,
        *,
        active_form_types: set[str],
        valid_document_ids: set[str],
    ) -> int:
        raise NotImplementedError


def _build_service(
    *,
    company_meta: _FakeCompanyMetaRepository,
    source_doc: _FakeSourceDocumentRepository,
    processed: _FakeProcessedDocumentRepository,
    blob: _FakeDocumentBlobRepository,
    maintenance: _FakeFilingMaintenanceRepository,
) -> PortfolioBrowsingService:
    """组装服务实例。"""

    return PortfolioBrowsingService(
        company_meta_repository=company_meta,
        source_document_repository=source_doc,
        processed_document_repository=processed,
        document_blob_repository=blob,
        filing_maintenance_repository=maintenance,
    )


def _make_filing_meta(
    *,
    form_type: str = "10-K",
    fiscal_year: int = 2023,
    fiscal_period: str = "FY",
    filing_date: str = "2023-11-03",
    is_deleted: bool = False,
    ingest_complete: bool = True,
    has_xbrl: bool = True,
) -> dict[str, Any]:
    """构造 filing meta dict。"""

    return {
        "form_type": form_type,
        "fiscal_year": fiscal_year,
        "fiscal_period": fiscal_period,
        "filing_date": filing_date,
        "report_date": "2023-09-30",
        "amended": False,
        "ingest_complete": ingest_complete,
        "is_deleted": is_deleted,
        "has_xbrl": has_xbrl,
        "primary_document": "aapl.htm",
    }


def _make_processed_summary(
    document_id: str,
    *,
    is_deleted: bool = False,
    section_count: int = 5,
    table_count: int = 2,
) -> DocumentSummary:
    """构造 processed 摘要。"""

    return DocumentSummary(
        document_id=document_id,
        internal_document_id=document_id.replace("fil_", ""),
        source_kind="filing",
        form_type="10-K",
        fiscal_year=2023,
        fiscal_period="FY",
        report_date="2023-09-30",
        filing_date="2023-11-03",
        amended=False,
        is_deleted=is_deleted,
        document_version="v1",
        quality="full",
        has_financials=True,
        section_count=section_count,
        table_count=table_count,
    )


def test_list_companies_aggregates_filing_and_processed_counts() -> None:
    """list_companies 应聚合 filing/processed 数量。"""

    company_meta = _FakeCompanyMetaRepository(
        inventory=[
            CompanyMetaInventoryEntry(
                directory_name="AAPL",
                status="available",
                company_meta=CompanyMeta(
                    company_id="320193",
                    company_name="Apple Inc.",
                    ticker="AAPL",
                    market="US",
                    resolver_version="v1",
                    updated_at="2026-04-18T04:07:22+00:00",
                    ticker_aliases=["AAPL"],
                ),
            ),
            CompanyMetaInventoryEntry(
                directory_name=".cache",
                status="hidden_directory",
                detail="hidden",
            ),
        ],
    )
    source_doc = _FakeSourceDocumentRepository(
        document_ids={
            ("AAPL", "filing"): ["fil_a", "fil_b"],
        },
        metas={
            ("AAPL", "fil_a", "filing"): _make_filing_meta(),
            ("AAPL", "fil_b", "filing"): _make_filing_meta(filing_date="2022-10-28", fiscal_year=2022),
        },
    )
    processed = _FakeProcessedDocumentRepository(
        summaries={
            "AAPL": [_make_processed_summary("fil_a")],
        },
    )
    blob = _FakeDocumentBlobRepository()
    maintenance = _FakeFilingMaintenanceRepository()
    service = _build_service(
        company_meta=company_meta,
        source_doc=source_doc,
        processed=processed,
        blob=blob,
        maintenance=maintenance,
    )

    companies = service.list_companies()

    assert [view.ticker or view.directory_name for view in companies] == [".cache", "AAPL"]
    apple = next(view for view in companies if view.ticker == "AAPL")
    assert apple.filing_count == 2
    assert apple.processed_count == 1
    assert apple.market == "US"
    hidden = next(view for view in companies if view.directory_name == ".cache")
    assert hidden.status == "hidden_directory"
    assert hidden.filing_count == 0


def test_list_filings_filters_and_sorts_by_date_desc() -> None:
    """list_filings 默认排除已删除并按 filing_date 倒序排序。"""

    source_doc = _FakeSourceDocumentRepository(
        document_ids={
            ("AAPL", "filing"): ["fil_old", "fil_new", "fil_deleted"],
        },
        metas={
            ("AAPL", "fil_old", "filing"): _make_filing_meta(filing_date="2021-10-29", fiscal_year=2021),
            ("AAPL", "fil_new", "filing"): _make_filing_meta(filing_date="2023-11-03"),
            ("AAPL", "fil_deleted", "filing"): _make_filing_meta(filing_date="2022-10-28", is_deleted=True),
        },
    )
    processed = _FakeProcessedDocumentRepository(
        summaries={"AAPL": [_make_processed_summary("fil_new")]},
    )
    service = _build_service(
        company_meta=_FakeCompanyMetaRepository(),
        source_doc=source_doc,
        processed=processed,
        blob=_FakeDocumentBlobRepository(),
        maintenance=_FakeFilingMaintenanceRepository(),
    )

    filings = service.list_filings("AAPL")

    assert [view.document_id for view in filings] == ["fil_new", "fil_old"]
    assert filings[0].has_processed is True
    assert filings[1].has_processed is False
    assert all(not view.is_deleted for view in filings)


def test_list_filings_supports_form_type_and_fiscal_year_filters() -> None:
    """list_filings 应能按 form_type 与 fiscal_year 过滤。"""

    source_doc = _FakeSourceDocumentRepository(
        document_ids={("AAPL", "filing"): ["fil_a", "fil_b", "fil_c"]},
        metas={
            ("AAPL", "fil_a", "filing"): _make_filing_meta(form_type="10-K", fiscal_year=2023),
            ("AAPL", "fil_b", "filing"): _make_filing_meta(form_type="10-Q", fiscal_year=2023),
            ("AAPL", "fil_c", "filing"): _make_filing_meta(form_type="10-K", fiscal_year=2022),
        },
    )
    service = _build_service(
        company_meta=_FakeCompanyMetaRepository(),
        source_doc=source_doc,
        processed=_FakeProcessedDocumentRepository(),
        blob=_FakeDocumentBlobRepository(),
        maintenance=_FakeFilingMaintenanceRepository(),
    )

    only_10k = service.list_filings("AAPL", form_type="10-K")
    only_2023 = service.list_filings("AAPL", fiscal_year=2023)

    assert {view.document_id for view in only_10k} == {"fil_a", "fil_c"}
    assert {view.document_id for view in only_2023} == {"fil_a", "fil_b"}


def test_get_filing_detail_attaches_files_and_processed_summary() -> None:
    """get_filing_detail 应同时返回文件清单与 processed 摘要。"""

    source_doc = _FakeSourceDocumentRepository(
        document_ids={("AAPL", "filing"): ["fil_a"]},
        metas={("AAPL", "fil_a", "filing"): _make_filing_meta()},
    )
    processed = _FakeProcessedDocumentRepository(
        summaries={"AAPL": [_make_processed_summary("fil_a")]},
    )
    blob = _FakeDocumentBlobRepository(
        file_metas={
            ("AAPL", "fil_a"): [
                FileObjectMeta(uri="local://AAPL/filings/fil_a/aapl.htm", size=100, content_type="text/html"),
                FileObjectMeta(uri="local://AAPL/filings/fil_a/aapl.xsd", size=200),
            ],
        },
    )
    service = _build_service(
        company_meta=_FakeCompanyMetaRepository(),
        source_doc=source_doc,
        processed=processed,
        blob=blob,
        maintenance=_FakeFilingMaintenanceRepository(),
    )

    detail = service.get_filing_detail("AAPL", "fil_a")

    assert detail.filing.document_id == "fil_a"
    assert {file_view.name for file_view in detail.files} == {"aapl.htm", "aapl.xsd"}
    assert detail.processed_summary is not None
    assert detail.section_count == 5
    assert detail.has_financials is True


def test_get_filing_processed_returns_sections_tables_and_xbrl() -> None:
    """get_filing_processed 应解析 sections / tables / xbrl_facts。"""

    source_doc = _FakeSourceDocumentRepository(
        document_ids={("AAPL", "filing"): ["fil_a"]},
        metas={("AAPL", "fil_a", "filing"): _make_filing_meta()},
    )
    processed = _FakeProcessedDocumentRepository(
        summaries={"AAPL": [_make_processed_summary("fil_a", section_count=2, table_count=1)]},
        metas={
            ("AAPL", "fil_a"): {
                "sections": [
                    {"section_id": "s1", "title": "Item 1", "depth": 1, "char_count": 100, "order": 0},
                    {"section_id": "s2", "title": "Item 2", "depth": 1, "char_count": 200, "order": 1},
                ],
                "tables": [
                    {"table_id": "t1", "caption": "Revenue", "section_id": "s1", "row_count": 5, "column_count": 3},
                ],
                "xbrl_facts": [
                    {
                        "concept": "us-gaap:Revenue",
                        "unit": "USD",
                        "value": "1000",
                        "period_end": "2023-09-30",
                        "decimals": "-3",
                    },
                ],
            }
        },
    )
    service = _build_service(
        company_meta=_FakeCompanyMetaRepository(),
        source_doc=source_doc,
        processed=processed,
        blob=_FakeDocumentBlobRepository(),
        maintenance=_FakeFilingMaintenanceRepository(),
    )

    view = service.get_filing_processed("AAPL", "fil_a")

    assert [section.section_id for section in view.sections] == ["s1", "s2"]
    assert view.tables[0].row_count == 5
    assert view.xbrl_facts[0].concept == "us-gaap:Revenue"
    assert view.xbrl_facts[0].unit == "USD"


def test_get_filing_processed_raises_when_summary_missing() -> None:
    """processed 不存在时应抛 FileNotFoundError。"""

    service = _build_service(
        company_meta=_FakeCompanyMetaRepository(),
        source_doc=_FakeSourceDocumentRepository(),
        processed=_FakeProcessedDocumentRepository(),
        blob=_FakeDocumentBlobRepository(),
        maintenance=_FakeFilingMaintenanceRepository(),
    )

    with pytest.raises(FileNotFoundError):
        service.get_filing_processed("AAPL", "fil_a")


def test_get_portfolio_health_summarizes_all_dimensions() -> None:
    """get_portfolio_health 应正确汇总各项指标。"""

    source_doc = _FakeSourceDocumentRepository(
        document_ids={("AAPL", "filing"): ["fil_a", "fil_b", "fil_c", "fil_d"]},
        metas={
            ("AAPL", "fil_a", "filing"): _make_filing_meta(),
            ("AAPL", "fil_b", "filing"): _make_filing_meta(ingest_complete=False),
            ("AAPL", "fil_c", "filing"): _make_filing_meta(is_deleted=True),
            ("AAPL", "fil_d", "filing"): _make_filing_meta(),
        },
    )
    processed = _FakeProcessedDocumentRepository(
        summaries={"AAPL": [_make_processed_summary("fil_a")]},
    )
    rejected_artifact = RejectedFilingArtifact(
        ticker="AAPL",
        document_id="fil_x",
        internal_document_id="0001",
        accession_number="0001",
        company_id="320193",
        form_type="6-K",
        filing_date="2024-01-02",
        report_date=None,
        primary_document="x.htm",
        selected_primary_document="x.htm",
        rejection_reason="not_primary",
        rejection_category="active_6k_secondary",
        classification_version="v1",
        source_fingerprint="abc",
        rejected_at="2026-04-18T05:00:00+00:00",
    )
    maintenance = _FakeFilingMaintenanceRepository(rejected={"AAPL": [rejected_artifact]})
    service = _build_service(
        company_meta=_FakeCompanyMetaRepository(),
        source_doc=source_doc,
        processed=processed,
        blob=_FakeDocumentBlobRepository(),
        maintenance=maintenance,
    )

    health = service.get_portfolio_health("AAPL")

    assert health.total_filings == 3
    assert health.deleted_filings == 1
    assert health.ingest_incomplete_filings == 1
    assert health.processed_filings == 1
    assert health.missing_processed_filings == 2
    assert health.rejected_filings == 1
    assert health.rejected_samples[0].document_id == "fil_x"


def test_read_filing_file_returns_blob_and_resolves_content_type() -> None:
    """read_filing_file 应返回字节内容并优先使用 meta 中的 content_type。"""

    source_doc = _FakeSourceDocumentRepository(
        document_ids={("AAPL", "filing"): ["fil_a"]},
        metas={("AAPL", "fil_a", "filing"): _make_filing_meta()},
    )
    blob = _FakeDocumentBlobRepository(
        file_metas={
            ("AAPL", "fil_a"): [
                FileObjectMeta(uri="local://AAPL/filings/fil_a/aapl.htm", size=10, content_type="text/html"),
            ]
        },
        file_bytes={("AAPL", "fil_a", "aapl.htm"): b"<html></html>"},
    )
    service = _build_service(
        company_meta=_FakeCompanyMetaRepository(),
        source_doc=source_doc,
        processed=_FakeProcessedDocumentRepository(),
        blob=blob,
        maintenance=_FakeFilingMaintenanceRepository(),
    )

    payload = service.read_filing_file("AAPL", "fil_a", "aapl.htm")

    assert payload.content == b"<html></html>"
    assert payload.content_type == "text/html"


def test_read_filing_file_raises_when_filename_missing() -> None:
    """目标文件不在 meta 中应抛 FileNotFoundError。"""

    source_doc = _FakeSourceDocumentRepository(
        document_ids={("AAPL", "filing"): ["fil_a"]},
        metas={("AAPL", "fil_a", "filing"): _make_filing_meta()},
    )
    service = _build_service(
        company_meta=_FakeCompanyMetaRepository(),
        source_doc=source_doc,
        processed=_FakeProcessedDocumentRepository(),
        blob=_FakeDocumentBlobRepository(file_metas={("AAPL", "fil_a"): []}),
        maintenance=_FakeFilingMaintenanceRepository(),
    )

    with pytest.raises(FileNotFoundError):
        service.read_filing_file("AAPL", "fil_a", "ghost.htm")
