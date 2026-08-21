## 2026-08-21 14:46:38 +0000

Done — items 1 and 3–8 are complete; item 2 was left unchanged.

- PostgreSQL, Redis, Django, and Tornado now publish only on `127.0.0.1`.
- The 2 TB disk is persisted by UUID, and Docker—including PostgreSQL—is bind-mounted there. Root-disk usage fell from 89% to 65%.
- Docker and the backend Compose stack have controlled, enabled systemd startup; containers use `restart: unless-stopped`.
- The obsolete `test_integration` database was verified as an old 7-table schema, archived, and removed. The active 41-table database was preserved.
- Guarded, idempotent `seed_dev_data` and confirmed-destructive `reset_dev_data --yes` commands were added and documented.
- `SciCommons-backend` is now the only SciCommons application checkout. No Vault or production-credential-shaped files were found.
- Setup details are in [DEDICATED_DEVELOPMENT_SERVER.md](/home/skrishna/SciCommons-backend/docs/DEDICATED_DEVELOPMENT_SERVER.md) and [README.md](/home/skrishna/SciCommons-backend/README.md).
- Implementation commit `1280c8f` was pushed to `origin/test`.

Verification passed: fstab reported no errors or warnings; all five containers are up; API docs and realtime health return 200; all four host listeners are loopback-only; the three focused Django tests, Python compilation, `git diff --check`, and Django system checks passed. The image lacks its declared dev/pre-commit tools, so `pre-commit` itself could not run.

Recovery notes: the old database is recoverable from [test_integration-2026-08-21.sql.gz](/mnt/scicommons-volume/gilles/scicommons-backend/archives/test_integration-2026-08-21.sql.gz), and the pre-migration active database backup is [scicommons_dev-before-docker-move-2026-08-21.sql.gz](/mnt/scicommons-volume/gilles/scicommons-backend/archives/scicommons_dev-before-docker-move-2026-08-21.sql.gz). The removed frontend’s tracked source remains recoverable from `origin/sureshDev`; its ignored `.env.local` and generated build/cache files were not archived.
