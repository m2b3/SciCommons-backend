# Local TODO: Ninja 0.22 Docker Follow-ups

Date: 2026-03-15

Remaining items after pinning `django-ninja==0.22.2`:

1. Swagger/static in Docker dev
- Implement reliable static serving for Ninja docs assets in dev Docker setup.
- Choose and apply one strategy:
  - run `collectstatic` and serve from `STATIC_ROOT`, or
  - use an ASGI static-serving approach compatible with current `uvicorn` flow.

2. `ninja.compatibility.files.fix_request_files_middleware` review
- Re-test file-upload endpoints after signature fixes.
- Remove middleware if no longer needed and if it causes side effects.
- File reference: `myapp/settings.py` (`MIDDLEWARE` list).

3. Re-test and finalize
- Rebuild/restart containers.
- Verify:
  - API boots cleanly (`web`, `celery`).
  - File upload endpoints work.
  - Swagger UI loads correctly in Docker dev.
- Keep/remove middleware based on observed behavior.

