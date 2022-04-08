from typing import Any, Dict, List

SECRET_KEY = "NOT-A-SECRET"

ALLOWED_HOSTS: List[str] = []

DATABASES: Dict[str, Dict[str, Any]] = {}

INSTALLED_APPS = []

MIDDLEWARE: List[str] = []

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "OPTIONS": {"context_processors": []},
    }
]

TIME_ZONE = "UTC"
USE_TZ = True
