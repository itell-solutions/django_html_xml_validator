from dataclasses import dataclass
from http import HTTPStatus

from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from django_html_xml_validator.middleware import HtmlXmlValidatorMiddleware, error_line_html


@dataclass
class _LxmlErrorMimic:
    message: str = "test error"
    line: int = 0
    column: int = 0


def test_can_render_error_html():
    assert error_line_html(_LxmlErrorMimic(), []) == "<p>test error</p>"
    assert error_line_html(_LxmlErrorMimic("<&>"), []) == "<p>&lt;&amp;&gt;</p>"
    assert error_line_html(_LxmlErrorMimic(line=1), ["<&>"]) == "<pre>&lt;&amp;&gt;</pre><p>Line 1: test error</p>"
    assert error_line_html(_LxmlErrorMimic(line=2, column=3), ["", "..."]) == (
        "<pre>...\n" "  ^</pre><p>Line 2, column 3: test error</p>"
    )


def test_can_render_error_html_with_indentation():
    assert error_line_html(_LxmlErrorMimic(line=2, column=5), ["", "  ..."]) == (
        "<pre>...\n" "  ^</pre><p>Line 2, column 3: test error</p>"
    )


class HtmlXmlValidatorMiddlewareTest(SimpleTestCase):
    request_factory = RequestFactory()

    def setUp(self):
        self.request = self.request_factory.get("/")
        self.response = HttpResponse(
            '<html lang="en"><head><title>Hello</title></head><body><p>Hello!</p></body></html>'
        )

        def get_response(_request: HttpRequest) -> HttpResponse:
            response = self.response
            if not getattr(response, "streaming", False):
                response["Content-Length"] = len(response.content)
            return response

        self.middleware = HtmlXmlValidatorMiddleware(get_response)

    @override_settings(VALIDATE_HTML=True)
    def test_can_accept_valid_html(self):
        response = self.middleware(self.request)
        assert response.status_code == HTTPStatus.OK

    @override_settings(VALIDATE_XML=True)
    def test_can_accept_valid_xml(self):
        self.response = HttpResponse('<?xml version="1.0"?><a/>', content_type="application/xml")
        response = self.middleware(self.request)
        assert response.status_code == HTTPStatus.OK

    def test_can_accept_invalid_html_without_validation(self):
        self.response = HttpResponse("<head></body>")
        response = self.middleware(self.request)
        assert response.status_code == HTTPStatus.OK

    @override_settings(VALIDATE_HTML=True)
    def test_can_accept_invalid_html_stream(self):
        self.response = StreamingHttpResponse(iter([b"<head></body>"]))
        response = self.middleware(self.request)
        assert response.status_code == HTTPStatus.OK

    @override_settings(VALIDATE_HTML=True)
    def test_fails_on_invalid_html(self):
        self.response = HttpResponse("<head></body>")
        response = self.middleware(self.request)
        assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
        assert "HTML Validation Error" in _html_from(response)

    @override_settings(DEBUG=True)
    def test_fails_on_invalid_html_on_debug(self):
        self.response = HttpResponse("<head></body>")
        response = self.middleware(self.request)
        assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
        assert "HTML Validation Error" in _html_from(response)

    @override_settings(VALIDATE_XML=True)
    def test_fails_on_invalid_xml(self):
        self.response = HttpResponse('<?xml version="1.0"?><a>', content_type="application/xml")
        response = self.middleware(self.request)
        assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
        assert "XML Validation Error" in _html_from(response)


def _html_from(response: HttpResponse) -> str:
    return response.content.decode(response.charset)
