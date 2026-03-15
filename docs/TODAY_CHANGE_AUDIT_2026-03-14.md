# Change Audit (Today)

Date captured: 2026-03-14 (America/Toronto)

## Changes applied in this session

### 1) `myapp/settings.py`
- Added conditional import guard for Ninja compatibility middleware:
  - `from importlib.util import find_spec`
- Removed hardcoded middleware entry:
  - `"ninja.compatibility.files.fix_request_files_middleware"`
- Appends that middleware only when available:
  - `if find_spec("ninja.compatibility.files") is not None: ...`

Reason: fixed startup crash after pinning `django-ninja==0.22.2` where that module path may not exist.

### 2) `myapp/urls.py`
- In debug mode, changed static serving to finder-based staticfiles serving:
  - `urlpatterns += staticfiles_urlpatterns()`

Reason: fixed blank Swagger UI in Docker dev when `STATIC_ROOT` did not contain collected assets.

### 3) `myapp/realtime.py`
- Added transport helper:
  - `send_event_to_tornado(event: Dict) -> int`
- Updated event publisher to use this helper.

Reason: explicit reusable transport function for Django -> Tornado event publish flow.

### 4) `tornado_server.py`
- Added optional strict recipient filtering via `subscriber_ids` when present in payload.
- Added catch-up detection helper:
  - `is_catchup_required(queue_id, last_event_id)`
- Updated `/realtime/poll` behavior:
  - validates integer `last_event_id`
  - returns `{ "catchup_required": true, "last_event_id": ... }` when client falls behind queue buffer
- Replaced deprecated `datetime.utcnow()` usage with timezone-aware UTC:
  - `datetime.now(UTC)`

Reason: correctness for targeted event delivery, documented catch-up semantics, and cleaner logs.

## Runtime/system actions (non-file)
- No migrations created.
- No dependency versions changed during this session.
- No environment variables changed by agent.
- No destructive git/docker operations run by agent.
- Local syntax checks run with `python -m py_compile` on edited files.
## Verification pass: all repo changes for today

Scan basis:
- Local timezone: America/Toronto
- Today window used: `2026-03-14 00:00:00 -04:00` to `2026-03-14 23:59:59 -04:00`

### A) Uncommitted working tree (tracked + untracked)
From `git status --short --untracked-files=all`:
- `M myapp/realtime.py`
- `M myapp/settings.py`
- `M myapp/urls.py`
- `M tornado_server.py`
- `?? docs/TODAY_CHANGE_AUDIT_2026-03-14.md`

### B) Commits today on current branch (`sureshBack`)
- `b82bf60 | 2026-03-14 20:44:44 -0400 | bsureshkrishna | making changes to issues form ayu`
  - `articles/api.py`
  - `communities/api.py`
  - `docker-compose.dev.yml`
  - `docs/LOCAL_TODO_DOCKER_NINJA.md`
  - `pyproject.toml`
  - `users/api.py`

### C) Commits in all refs during today window (includes non-current branches/remotes)
- `b82bf60 | 2026-03-14 20:44:44 -0400 | (HEAD -> sureshBack) | bsureshkrishna`
  - same files as section B
- `912ad23 | 2026-03-15 03:10:55 +0530 | (origin/test) | Armaan Alam`
  - `users/api.py`
  - `users/schemas.py`
- `a50d5c6 | 2026-03-15 03:07:22 +0530 | Armaan Alam`
  - `users/api.py`
  - `users/schemas.py`
- `1b8113f | 2026-03-15 02:20:02 +0530 | Armaan Alam`
  - `articles/api.py`
  - `articles/discussion_api.py`
  - `articles/review_api.py`
  - `communities/api_invitation.py`
  - `communities/api_join.py`
  - `communities/articles_api.py`
  - `myapp/flags_api.py`
  - `myapp/services/__init__.py`
  - `myapp/services/notifications.py`
  - `myapp/services/send_emails.py`
  - `templates/join_request_approved.html`
  - `tornado_server.py`
  - `users/api.py`
  - `users/models.py`
  - `users/schemas.py`
  - `users/tests/test_users_models.py`
- `7770603 | 2026-03-15 02:18:02 +0530 | Armaan Alam`
  - `articles/api.py`
  - `articles/discussion_api.py`
  - `articles/review_api.py`
  - `communities/api_invitation.py`
  - `communities/api_join.py`
  - `communities/articles_api.py`
  - `myapp/flags_api.py`
  - `myapp/services/__init__.py`
  - `myapp/services/notifications.py`
  - `tornado_server.py`
  - `users/api.py`
  - `users/models.py`
  - `users/schemas.py`
  - `users/tests/test_users_models.py`
- `45c64b8 | 2026-03-14 21:47:06 +0530 | Armaan Alam`
  - `communities/api_join.py`
  - `myapp/services/send_emails.py`
  - `templates/join_request_approved.html`

## Conclusion
The changes made in this session are present as uncommitted modifications in 4 tracked files plus 1 new untracked markdown file.
In addition, there are other commits dated within the same local-day window (some from non-current refs/timezones), so "all changes made today" is broader than only this session's edits.
