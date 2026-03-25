from __future__ import annotations

from dataclasses import dataclass

from apps.content_service.schemas.source import (
    FieldSelectorDTO,
    HTMLSourceValidationRequest,
    RSSSourceValidationRequest,
    SourceValidationResultDTO,
)
from scout_pipeline.config import FieldSelector, HTMLSource, RSSSource


@dataclass(frozen=True)
class ValidationContext:
    name: str
    source_type: str


def validate_source_payload(
    request: RSSSourceValidationRequest | HTMLSourceValidationRequest,
) -> SourceValidationResultDTO:
    if isinstance(request, RSSSourceValidationRequest):
        return _validate_rss_request(request)
    return _validate_html_request(request)


def _validate_rss_request(request: RSSSourceValidationRequest) -> SourceValidationResultDTO:
    source = RSSSource(type="rss", name=request.name, url=request.url)
    context = ValidationContext(name=request.name, source_type="rss")
    try:
        items = _collect_rss_items(source)
        return _success_result(context, items, status_code=200)
    except Exception as exc:
        return _error_result(context, exc, status_code=_extract_status_code(exc))


def _validate_html_request(request: HTMLSourceValidationRequest) -> SourceValidationResultDTO:
    source = HTMLSource(
        type="html",
        name=request.name,
        url=request.url,
        list_selector=request.list_selector,
        fields={key: _to_field_selector(value) for key, value in request.fields.items()},
    )
    context = ValidationContext(name=request.name, source_type="html")
    try:
        items = _collect_html_items(source)
        return _success_result(context, items, status_code=200)
    except Exception as exc:
        return _error_result(context, exc, status_code=_extract_status_code(exc))


def _to_field_selector(value: FieldSelectorDTO) -> FieldSelector:
    return FieldSelector(selector=value.selector, attr=value.attr, multiple=value.multiple)


def _collect_rss_items(source: RSSSource):
    from scout_pipeline.collector import collect_rss

    return collect_rss(source)


def _collect_html_items(source: HTMLSource):
    from scout_pipeline.collector import collect_html

    return collect_html(source)


def _extract_status_code(exc: Exception) -> int | None:
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    return int(status_code) if status_code is not None else None


def _success_result(context: ValidationContext, items: list[object], *, status_code: int) -> SourceValidationResultDTO:
    sample_titles: list[str] = []
    for item in items[:3]:
        title = str(getattr(item, "title", "") or "").strip()
        url = str(getattr(item, "url", "") or "").strip()
        if title:
            sample_titles.append(title)
        elif url:
            sample_titles.append(url)
    return SourceValidationResultDTO(
        ok=bool(items),
        name=context.name,
        type=context.source_type,
        status_code=status_code,
        item_count=len(items),
        sample_titles=sample_titles,
        message=None if items else "No items found from source",
    )


def _error_result(
    context: ValidationContext,
    exc: Exception,
    *,
    status_code: int | None,
) -> SourceValidationResultDTO:
    return SourceValidationResultDTO(
        ok=False,
        name=context.name,
        type=context.source_type,
        status_code=status_code,
        item_count=0,
        sample_titles=[],
        message=str(exc),
    )
