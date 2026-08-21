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

## 2026-08-21 14:58:32 +0000

Yes. This machine is ready for backend development.

Your normal workflow is:

```bash
cd /home/skrishna/SciCommons-backend
git switch test
git pull --ff-only origin test
git switch -c your-feature-branch
```

The backend stack is already running and starts automatically after reboot. Check it with:

```bash
sudo docker compose -f docker-compose.dev.yml --env-file .env.local ps
```

Develop against the local `scicommons_dev` database, run tests in the `web` container, then commit, push your feature branch, and open a pull request. Production credentials and the real production database are intentionally unavailable here.

One important limitation: this is now a backend-only development server. The frontend checkout was deliberately removed under item 8. Use a frontend running on your workstation, or re-clone it later if you decide this should be a combined full-stack server. Since the service ports bind to `127.0.0.1`, browser access from your workstation still requires the SSH port forwarding discussed earlier.

## 2026-08-21 15:02:28 +0000

Yes—I inspected the new backend-infrastructure commit [`7c5b04e`](https://github.com/m2b3/scicommons-backendinfra/commit/7c5b04eef71af13716d7e6c758154a8b9af0d54a). It adds a guarded [`tools/promote_backend.sh`](https://github.com/m2b3/scicommons-backendinfra/blob/main/tools/promote_backend.sh) deployment-promotion helper and documents it in [`docs/newdeveloper.md`](https://github.com/m2b3/scicommons-backendinfra/blob/main/docs/newdeveloper.md).

The intended flow is now:

1. Develop here, push a backend feature branch, and open/test the pull request.
2. On a separate deployment-admin/controller checkout, run `tools/promote_backend.sh test [BACKEND_REF]` or `prod [BACKEND_REF]`.
3. The helper resolves an immutable 40-character backend SHA, verifies `pyproject.toml` and `poetry.lock`, updates only the selected environment pin and lockfile, and creates a local infrastructure commit.
4. Review that commit. The helper deliberately does **not** push or deploy.
5. Pushing the reviewed infrastructure commit to `main` triggers the [`Deploy SciCommons backend`](https://github.com/m2b3/scicommons-backendinfra/blob/main/.github/workflows/deploy-backend.yml) workflow, which runs Ansible and deploys the pinned production and test revisions.

So you do **not** merge code manually on the actual application server. Also, pushing `SciCommons-backend/test` alone does not deploy it. Infrastructure currently pins test to `4f82ff69…`, while `origin/test` contains newer commits, including implementation commit `1280c8f`.

My recommendation is to leave this machine unchanged as the isolated development server. Keep the infrastructure checkout and Vault/deployment authority on the admin/controller side. When you want the current backend deployed to test, an administrator should run the new helper there, review its generated commit, and explicitly push infrastructure `main`. I have not triggered that deployment.

## 2026-08-21 15:04:29 +0000

Yes, technically you can keep a separate `scicommons-backendinfra` checkout on this machine. It could run `tools/promote_backend.sh`, review the generated commit, and push infrastructure `main`.

But a different folder is organization, not security isolation. That would reverse item 8 and give this public development machine deployment-trigger authority through its GitHub credentials. A compromise of the machine could potentially be turned into a deployment.

The roles are distinct:

- `/home/skrishna/SciCommons-backend`: application development.
- An infrastructure checkout: prepares and pushes promotion commits; it does not need the decrypted Vault password.
- The existing GitHub self-hosted controller: receives the workflow job and uses the protected Vault secret to run Ansible.

My preference is to keep the infrastructure checkout on a private administrator workstation. If you intentionally want it here, use a separate Unix account and protected home directory—not merely another folder—and keep all Vault passwords, production `.env` files, SSH deployment keys, and cloud credentials off this machine. Do not register this host as the self-hosted deployment controller.

So: **possible, yes; equivalent security separation, no.** I have not created the checkout. If you choose this arrangement, I can set it up as a promotion-only admin checkout with no Vault or production credentials.
