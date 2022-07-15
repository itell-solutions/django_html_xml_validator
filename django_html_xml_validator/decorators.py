from functools import wraps

from django.http import HttpResponse

from django_html_xml_validator.middleware import VALIDATION_HEADER


def no_html_xml_validation(view_func):
    """
    Decorator that prevents a view from being validated.
    """

    @wraps(view_func)
    def _wrapped_view_func(request, *args, **kwargs):
        # Ensure argument looks like a request.
        if not hasattr(request, "META"):
            raise TypeError(
                "skip_html_xml_validation didn't receive an HttpRequest. If you are "
                "decorating a classmethod, be sure to use @method_decorator."
            )
        response = view_func(request, *args, **kwargs)
        add_no_html_xml_validation_header(response)
        return response

    return _wrapped_view_func


def add_no_html_xml_validation_header(response: HttpResponse):
    """
    Mark `response` to not be validated.
    """
    response.headers[VALIDATION_HEADER] = 0
