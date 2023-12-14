from dataclasses import dataclass
from http import HTTPStatus

from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from django_html_xml_validator.decorators import add_no_html_xml_validation_header, no_html_xml_validation
from django_html_xml_validator.middleware import VALIDATION_HEADER, HtmlXmlValidatorMiddleware, error_line_html

_BROKEN_HTML = "<head></body>"


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

    @override_settings(VALIDATE_HTML=True)
    def test_can_accept_semantic_html(self):
        self.response = HttpResponse(
            "\n".join(
                [
                    "<!DOCTYPE html>",
                    '<html lang="en">',
                    "  <head><title>HTML5 example</title></head>",
                    "  <body>",
                    "    <header><nav>Some links here.</nav></header>",
                    "    <article>",
                    "      <section>First</section>",
                    "      <section>Second</section>",
                    "      <section>",
                    "        <figure>",
                    '          <img alt="example" src="example.png">',
                    "          <figcaption>Example</figcaption>",
                    "        </figure>",
                    "        <details>",
                    "          <summary>short</summary>",
                    "          <p>the long version with <mark>highlighted part</mark></p>",
                    "        </details>",
                    "        <time>10:00</time>",
                    "      </section>",
                    "    </article>",
                    "    <footer>Copyright etc</footer>",
                    "  </body>",
                    "</html>",
                ]
            )
        )
        response = self.middleware(self.request)
        assert response.status_code == HTTPStatus.OK

    @override_settings(VALIDATE_HTML=True)
    def test_can_accept_math_ml_html(self):
        self.response = HttpResponse(
            "\n".join(
                [
                    "<!DOCTYPE html>",
                    '<html lang="en">',
                    "  <head><title>HTML5 example</title></head>",
                    "  <body>",
                    "    <math>",
                    "       <msup><mi>a</mi><mn>2</mn></msup>",
                    "    </math>",
                    "  </body>",
                    "</html>",
                ]
            )
        )
        response = self.middleware(self.request)
        assert response.status_code == HTTPStatus.OK

    @override_settings(VALIDATE_HTML=True)
    def test_can_accept_svg_html(self):
        self.response = HttpResponse(
            "\n".join(
                [
                    "<!DOCTYPE html>",
                    '<html lang="en">',
                    "  <head><title>HTML5 example</title></head>",
                    "  <body>",
                    "    <svg height='100' width='100'>",
                    "      <circle cx='50' cy='50' r='40' />",
                    "    </svg>",
                    "  </body>",
                    "</html>",
                ]
            )
        )
        response = self.middleware(self.request)
        assert response.status_code == HTTPStatus.OK

    @override_settings(VALIDATE_HTML=True)
    def test_can_accept_upper_and_lower_case_tags(self):
        self.response = HttpResponse(
            "\n".join(
                [
                    "<!DOCTYPE html>",
                    '<html lang="en">',
                    "  <head><title>HTML5 example</title></head>",
                    "  <body>",
                    "    <sVg height='100' width='100'>",
                    "      <CiRcLe cx='50' cy='50' r='40' />",
                    "    </SvG>",
                    "  </body>",
                    "</html>",
                ]
            )
        )
        response = self.middleware(self.request)
        assert response.status_code == HTTPStatus.OK

    def test_can_accept_invalid_html_without_validation(self):
        self.response = _broken_html_response()
        response = self.middleware(self.request)
        assert response.status_code == HTTPStatus.OK

    @override_settings(VALIDATE_HTML=True)
    def test_can_accept_invalid_html_stream(self):
        self.response = StreamingHttpResponse(iter([b"<head></body>"]))
        response = self.middleware(self.request)
        assert response.status_code == HTTPStatus.OK

    @override_settings(VALIDATE_XML=True)
    def test_can_accept_invalid_html_with_no_validation_header(self):
        self.response = _broken_html_response()
        add_no_html_xml_validation_header(self.response)
        response = self.middleware(self.request)
        assert response.status_code == HTTPStatus.OK
        assert response.headers.get(VALIDATION_HEADER) == "0"

    @override_settings(VALIDATE_XML=True)
    def test_can_accept_invalid_html_with_no_validation_decorator(self):
        response = _broken_html_view(HttpRequest())
        assert response.status_code == HTTPStatus.OK
        assert response.headers.get(VALIDATION_HEADER) == "0"

    @override_settings(VALIDATE_HTML=True)
    def test_fails_on_invalid_html(self):
        self.response = _broken_html_response()
        response = self.middleware(self.request)
        assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
        assert "HTML Validation Error" in _html_from(response)

    @override_settings(DEBUG=True)
    def test_fails_on_invalid_html_on_debug(self):
        self.response = _broken_html_response()
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


def _broken_html_response():
    return HttpResponse(_BROKEN_HTML)


@no_html_xml_validation
def _broken_html_view(_request: HttpRequest) -> HttpResponse:
    return _broken_html_response()
