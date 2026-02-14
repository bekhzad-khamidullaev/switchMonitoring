import os

_ENV = os.getenv('DJANGO_ENV', 'dev').strip().lower()

if _ENV in {'dev', 'development', 'local'}:
    from .dev import *
elif _ENV in {'prod', 'production'}:
    from .prod import *
else:
    raise RuntimeError(f"Unsupported DJANGO_ENV: {_ENV}")
