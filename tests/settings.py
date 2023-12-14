from typing import Any

SECRET_KEY = "NOT-A-SECRET"

ALLOWED_HOSTS: list[str] = []

DATABASES: dict[str, dict[str, Any]] = {}

INSTALLED_APPS = []

MIDDLEWARE: list[str] = []

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "OPTIONS": {"context_processors": []},
    }
]

TIME_ZONE = "UTC"
USE_TZ = True
