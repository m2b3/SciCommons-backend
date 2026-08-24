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

## 2026-08-21 15:16:28 +0000

Yes—but the application is **already behind SSH** in practice.

I verified:

- Django `8000`, Tornado `8888`, PostgreSQL `5432`, and Redis `6379` listen only on `127.0.0.1`.
- SSH listens publicly on port `22`.
- SSH key authentication is enabled and password authentication is disabled.
- SSH TCP forwarding is enabled, while `GatewayPorts` is disabled.

From your workstation, connect to this server's public IP:

```bash
ssh -N -o ExitOnForwardFailure=yes \
  -L 8000:127.0.0.1:8000 \
  -L 8888:127.0.0.1:8888 \
  skrishna@SERVER_PUBLIC_IP
```

Then use `http://127.0.0.1:8000/api/docs/` and `http://127.0.0.1:8888/health` on your workstation. Add `-L 5432:127.0.0.1:5432` only when you need a local database client. Your workstation itself does not need a public IP; it only needs outbound SSH access to this server.

The remaining optional hardening is the host firewall: UFW is currently inactive. The current application ports are still non-public because of their loopback bindings, but enabling a firewall that permits SSH and denies other inbound traffic would protect against a future service accidentally binding to `0.0.0.0`. Disabling SSH root login entirely would also be sensible. I have not made either change because firewall/SSH changes can lock you out and item 2 was excluded.

## 2026-08-21 17:03:33 +0000

Completed. Backend `test` now contains PRs #165–#168 and is available to pull from another development machine.

- Feature-integration commit: `af039994346dbe4dc950a5b75820f178cc61a595`
- Local `test` was first fast-forwarded to the prior remote head `98e405a`.
- #165, #166, #167, and #168 were merged in order as separate merge commits.
- Because #168 is stacked on #167, merging #167 first caused #168 to apply only its later delta; no #167 code was duplicated.
- All 85 PR-specific tests passed together.
- Docker build/start, Django system checks, migration consistency, migration plan, `git diff --check`, and Tornado health passed.
- The full suite ran 218 tests and reproduced exactly the current base branch's 15 failures and 4 errors. The integration introduced no additional failures, but the branch is still not green and should not be promoted for deployment yet.
- The disposable validation containers and PostgreSQL volume were removed.

The direct push succeeded but GitHub reported that it bypassed the branch rule requiring changes through pull requests. Direct backend pushes trigger dynamic CodeQL analysis, not the pull-request-only Django CI workflow. No infrastructure pin was changed, so this push did not trigger backend deployment.

## 2026-08-24 00:38:55 +0000

Recovery complete. The corrected work is now on local `test`, with no `sureshBack` history included.

- Started cleanly from `test`/`origin/test` at `9867080`.
- Applied PR #169 as its direct child commit `a8e9b48`.
- Applied only the intended identity repair (`e53e012`), repaired tests (`5d8f9e4`), and extension documentation (`a07b530`).
- Renumbered the identity migration to `0038` after PR #169's `0037` in `7473c13`.
- Confirmed that `origin/sureshBack` is not an ancestor of the corrected `test` branch. Its nine old deltas and ancient merge history are absent.
- Preserved the mistaken local `sureshBack` branch at `171f0ea` as a safety copy; it was not merged or pushed.

Validation passed: Docker Compose configuration, Django system checks, migration drift checks, the applied `0037 → 0038` chain, `git diff --check`, and all 224 backend tests (`OK`, 52.603s). The documented pre-commit command could not run because the existing web image does not contain the `pre-commit` executable.

Local `test` contains five scoped functional/documentation commits plus a separate required `codexOutput.md` operation-log commit. `origin/test` remains unchanged at `9867080`; nothing was pushed or deployed. The working tree is clean.
