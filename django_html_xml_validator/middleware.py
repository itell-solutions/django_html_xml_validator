import io
import re
from enum import Enum
from html import escape as html_escaped
from http import HTTPStatus
from typing import Callable, List, Union

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from lxml import etree
from lxml.etree import ParseError

_HTML5_BYTES_PATTERN = rb"^\s*<\s*!doctype\s+html>"
_HTML5_BYTES_REGEX = re.compile(_HTML5_BYTES_PATTERN, re.IGNORECASE)
_HTML5_REGEX = re.compile(_HTML5_BYTES_PATTERN.decode("ascii"), re.IGNORECASE)
_HTML5_INVALID_TAG_TO_IGNORE_REGEX = re.compile(r"^Tag (article|aside|footer|header|main|nav|section) invalid$")


class _ContentKind(Enum):
    HTML = "html"
    OTHER = "other"
    XHTML = "xhtml"
    XML = "xml"

    @staticmethod
    def from_response(response: HttpResponse) -> "_ContentKind":
        content_type = response["Content-Type"]
        plain_content_type = content_type.split(";")[0]
        return (
            _ContentKind.XHTML
            if plain_content_type == "application/xhtml+xml"
            else _ContentKind.HTML
            if plain_content_type == "text/html"
            else _ContentKind.XML
            if plain_content_type in ("application/xml", "text/xml") or plain_content_type.endswith("+xml")
            else _ContentKind.OTHER
        )


class HtmlXmlValidatorMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response: HttpResponse = self.get_response(request)
        if not response.streaming:
            is_debug = getattr(settings, "DEBUG", False)
            is_validate_html = getattr(settings, "VALIDATE_HTML", is_debug)
            is_validate_xml = getattr(settings, "VALIDATE_XML", is_debug)
            if is_validate_html or is_validate_xml:
                content_kind = _ContentKind.from_response(response)
                if response.status_code == HTTPStatus.OK and (
                    (is_validate_html and content_kind in [_ContentKind.HTML, _ContentKind.XHTML])
                    or (is_validate_xml and content_kind == _ContentKind.XML)
                ):
                    response = self._validated_response(response, content_kind)
        return response

    @staticmethod
    def _validated_response(response: HttpResponse, content_kind: _ContentKind) -> HttpResponse:
        is_validate_html_as_xml = getattr(settings, "VALIDATE_HTML_AS_XHTML", False)
        is_xml = content_kind != _ContentKind.HTML or is_validate_html_as_xml
        content = response.content
        if is_xml:
            parser = etree.XMLParser()
            content_text = None
            content_stream = io.BytesIO(content)
            is_html5 = _HTML5_BYTES_REGEX.match(content) is not None
        else:
            parser = etree.HTMLParser(recover=False)
            content_text = HtmlXmlValidatorMiddleware._content_text(response)
            content_stream = io.StringIO(content_text)
            is_html5 = _HTML5_REGEX.match(content_text) is not None
        try:
            etree.parse(content_stream, parser)
        except ParseError as error:
            assert len(parser.error_log) >= 1, f"error must have error_log: {error}"
        finally:
            content_stream.close()

        errors = HtmlXmlValidatorMiddleware._cleaned_errors(parser, is_html5)
        if len(errors) >= 1:
            markup_language = (("X" if is_xml else "") + "HTML5") if is_html5 else content_kind.name
            content_text = (
                content_text if content_text is not None else HtmlXmlValidatorMiddleware._content_text(response)
            )
            error_html = HtmlXmlValidatorMiddleware._errors_html(markup_language, content_text, errors)
            result = HttpResponse(error_html, status=HTTPStatus.INTERNAL_SERVER_ERROR)
        else:
            result = response
        return result

    @staticmethod
    def _content_text(response) -> str:
        return response.content.decode(response.charset)

    @staticmethod
    def _cleaned_errors(parser: Union[etree.HTMLParser, etree.XMLParser], is_html5: bool) -> List:
        # HACK: Filter spurious HTML5 errors for actually valid tags.
        return [
            error
            for error in parser.error_log.filter_from_warnings()
            if not is_html5 or _HTML5_INVALID_TAG_TO_IGNORE_REGEX.match(error.message) is None
        ]

    @staticmethod
    def _errors_html(markup_language: str, content_text: str, errors: List) -> str:
        content_lines = content_text.split("\n")
        error_log_html = "".join(error_line_html(error, content_lines) for error in errors)
        return "".join(
            (
                "<!DOCTYPE html>",
                "<html lang='en'>",
                f"<head><title>{markup_language} Validation Error</title></head>",
                "<body>",
                f"<h1>{markup_language} Validation Error</h1>",
                error_log_html,
                "</body>",
                "</html>",
            )
        )


def error_line_html(error, content_lines: List[str]) -> str:
    if error.line:
        content_line = content_lines[error.line - 1]
        content_line_without_leading_white_space = content_line.lstrip()
        indent = len(content_line) - len(content_line_without_leading_white_space)
        visual_error_column = error.column - indent
        result = f"<pre>" f"{html_escaped(content_line_without_leading_white_space.rstrip())}"
        if error.column:
            caret_indent = " " * (visual_error_column - 1)
            caret_line = caret_indent + "^"
            result += f"\n{caret_line}"
        result += f"</pre>" f"<p>Line {error.line}"
        if error.column:
            result += f", column {visual_error_column}"
        result += ": "
    else:
        result = "<p>"
    result += f"{html_escaped(error.message)}</p>"
    return result
