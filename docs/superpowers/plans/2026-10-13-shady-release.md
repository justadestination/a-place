# Shady release: road, zine, Serendipilyst and the Steward on the public site

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The public NightCal site runs the current `main`: the street-timeline road with the zine wall, the rebuilt zine, Serendipilyst, and the Steward's House door. The operator data the public box leaks today is closed first.

**Architecture:** One release branch is cut from `main`. The Steward core is vendored from its own repo at a pinned commit and wired into the NightCal server as a small `shadenet/house.py` module behind one public route. The release ships as a `git archive` tarball. Each release is unpacked into its own directory on the VPS and made live by switching a symlink, so rollback is the same switch. Nothing depends on pushing to GitHub.

**Tech Stack:** Python 3.11 stdlib (NightCal server, Steward House), vanilla ES modules (web, Steward PWA engine), Caddy, systemd or Docker Compose (Phase 0 finds out which), Playwright via `web/tools/browser.mjs` for smoke shots.

**Names used below.** These live only in an untracked `.env.deploy` (gitignored), never in the repo:

| Variable | Meaning |
| --- | --- |
| `SHADY_HOST` | the public hostname of the NightCal site |
| `SHADY_SSH` | the SSH alias for the public VPS (an `~/.ssh/config` Host entry) |
| `STEWARD_REPO` | path to the local Steward checkout (repo "Steward") |
| `SHADY_ROOT` | the app root on the VPS (today the web root is `$SHADY_ROOT/web`) |

---

## State of things (surveyed 2026-10-13)

- **Public site:** serves an old build. `/road/` is 404. `/api/operator/status` answers **200 to anyone**, with the moderation queue, key rotations, sync-mesh peers, scraper status, zine roster and vote tallies. Current code answers 401 there; only `/api/operator/door-verify` is public (`shadenet/ops/routes.py:22`).
- **The VPS is the host `jyesthra`.** It was last deployed on 2026-10-08 by an rsync of the whole working tree into `$SHADY_ROOT` (`/opt/shadenet`): `--exclude=.git --delete`, files owned by `www-data`. It runs under the systemd unit `shadenet.service` on `127.0.0.1:8765`, with Caddy on the same host at `/etc/caddy/Caddyfile`. That rsync also carried the local `shadenet/data/` over the live one; **never repeat it.** Releases here exclude data and state. `tools/deploy.py` is a stub that only writes `state/deploy_history.json`. `deploy/production/*.sh` and `docker-compose.yml` describe a container layout that the VPS does not use.
- **Local `main`:** 11 commits ahead of `origin/main`: the road (7), its design doc, the WorldSum docs and Lahti extract, and Serendipilyst (`7d9c19f`). The working tree also holds **uncommitted edits made by another session**: `README.md`, `shadenet/nightcal/surface.py`, `web/components/event-card/event-card.js` (vote direction on `nc:bodies`), `web/components/site-header/site-header.js`, `web/js/data/calendar.js` (`eventIsFree`), `web/js/pages/calendar.js`.
- **Push is blocked:** commit `86ace91` has two home-directory paths in `docs/superpowers/plans/2026-10-13-road-street-timeline.md` (lines 97 and 355), and the pre-push hook refuses it. This release does not need a push, but `main` should be cleaned before one.
- **Steward:** in `$STEWARD_REPO`, at commit `5eb063d`; 133 Python tests and the JS suite pass. Its README says "working core, not yet wired into an app". The House door `steward.door.operator_mail_event` → `operator_inbox` → `filed` was proven end to end on 2026-10-13.
- **Serendipilyst:** committed in `7d9c19f`. Routes `/api/flags*` are on the NightCal server. `obligation.py` release is refused by `may_release()` until a hand-over proof is designed. That is intended; ship it refused.
- **Zine:** `web/data/zine.json` is built by `web/tools/build_zine.py` from `shadenet/horizon/vault`. The road's zine wall reads that file.
- **Tests:** 299 Python tests are collected. Known failures before this work: `tests/test_ops.py::test_network_allowlist` and 7 in towncrier `test_nightcal.py`.

## Decisions only the owner can make (blockers)

- [ ] **D1. VPS access.** Add `Host jyesthra` (HostName, `User root`) to `~/.ssh/config` so `$SHADY_SSH=jyesthra` works, and allow the agent to SSH there (Claude Code blocks production SSH until a permission rule allows it). Phases 0, 1 and 4 cannot start without it.
- [ ] **D2. Uncommitted edits on `main`.** Either they ship (commit them as their own commit, Task 2.2), or they stay out (park them on a WIP branch, Task 2.2 alt). Default in this plan: **ship them**. They are small, and the road already runs on them on the test server.
- [ ] **D3. Steward activation.** The over-21 gate is not built (the blind-signature design awaits a go-ahead). This release ships the Steward **without activation**. The only public House surface is the operator door, which is the no-Steward web form, and `steward_id` is always null. Confirm that is acceptable.
- [ ] **D4. History cleanup before any push.** Allow the rewrite of `86ace91` (fixup + autosquash). It is not needed to deploy.

---

## File map

| File | Role |
| --- | --- |
| `.gitignore` | add `.env.deploy`, `releases/` |
| `.env.deploy.example` | tracked template with the four names, no values |
| `tools/vendor_steward.py` | copy the Steward core from `$STEWARD_REPO` at a pinned commit into `vendor/steward/` |
| `vendor/steward/` | vendored `steward/` package, `policy/`, `pwa/*.js`, `VENDORED_FROM` |
| `shadenet/house.py` | the House as the NightCal server sees it: one `House` object, `operator_mail()` |
| `shadenet/nightcal/server.py` | route `POST /api/house/operator-mail` → `House.operator_mail` |
| `tests/test_house.py` | door filing, refusals, replay, transport-owned `steward_id` |
| `tools/release.sh` | build `releases/<sha>.tar.gz` from a commit with `git archive` |
| `tools/smoke_public.sh` | curl smoke checks against `https://$SHADY_HOST` |
| `deploy/caddy/operator-guard.caddy` | Caddy snippet that 404s private operator paths |
| `docs/operations/shady-deploy.md` | the runbook this plan produces (layout, ship, rollback) |

---

## Phase 0 — Recon on the VPS (read-only)

### Task 0.1: Map what the VPS runs

**Files:** Create: `docs/operations/shady-deploy.md`

- [ ] **Step 1: Load the names**

```bash
cd shadenet-a            # the repo root
set -a; . ./.env.deploy; set +a
ssh -o BatchMode=yes "$SHADY_SSH" 'hostname; uptime'
```
Expected: the VPS hostname and uptime. If it asks for a password or is refused, stop: D1 is not done.

- [ ] **Step 2: Find the web root, the app process and Caddy**

```bash
ssh "$SHADY_SSH" 'ls -la "'"$SHADY_ROOT"'" | head -30;
  systemctl list-units --type=service --no-pager | grep -iE "caddy|nightcal|shadenet";
  docker ps --format "{{.Names}} {{.Image}} {{.Status}}" 2>/dev/null;
  ss -ltnp | grep -E ":(80|443|8765) ";
  ls /etc/caddy 2>/dev/null; caddy version 2>/dev/null'
```
Expected (as of 2026-10-08): shape **(a) systemd**: `caddy.service`, plus `shadenet.service` running Python on `127.0.0.1:8765` as `www-data`. If you see containers instead, the box has changed since then; write down what you find and use the compose notes in Phase 4.

- [ ] **Step 3: Record the running version**

```bash
ssh "$SHADY_SSH" 'cd "'"$SHADY_ROOT"'" && (git log -1 --format="%h %s" 2>/dev/null || ls -la --time-style=+%F web | head -5);
  grep -n "bust =" web/road/index.html 2>/dev/null; ls web/road 2>/dev/null | head'
```
Expected: no `web/road` (it is 404 today). If `$SHADY_ROOT` is a git checkout, note its commit.

- [ ] **Step 4: Find the database and state**

```bash
ssh "$SHADY_SSH" 'cd "'"$SHADY_ROOT"'" && ls -la shadenet/data state 2>/dev/null; du -sh shadenet/data state 2>/dev/null'
```
Expected: `shadenet/data/shadenet.db` (live data) and `state/` (secrets, operator tokens). **Neither is ever overwritten by a release.**

- [ ] **Step 5: Write the runbook skeleton**

Create `docs/operations/shady-deploy.md` with the findings, using the variable names (no hostnames, IPs or user names):

```markdown
# Shady deploy runbook

## Layout (found 2026-10-13)
- Process model: <systemd | compose>, service names: <...>
- App root: $SHADY_ROOT; web root: $SHADY_ROOT/web
- Data that releases never touch: $SHADY_ROOT/shadenet/data/, $SHADY_ROOT/state/
- Caddy config: <path>; reload with: <command>
- Running version before this release: <commit or date>

## Ship
(filled in by Task 4.x)

## Roll back
(filled in by Task 4.x)
```

- [ ] **Step 6: Commit**

```bash
git add docs/operations/shady-deploy.md
git commit -m "docs(ops): shady deploy runbook, recon"
```

### Task 0.2: Back up the VPS before touching it

- [ ] **Step 1: Snapshot app, data and Caddy config to this machine**

```bash
stamp=$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "backups/shady-$stamp"
ssh "$SHADY_SSH" 'sudo tar -C / -czf - "'"${SHADY_ROOT#/}"'" etc/caddy 2>/dev/null' > "backups/shady-$stamp/root.tar.gz"
ssh "$SHADY_SSH" 'sqlite3 "'"$SHADY_ROOT"'/shadenet/data/shadenet.db" ".backup /tmp/shadenet-backup.db" && cat /tmp/shadenet-backup.db && rm /tmp/shadenet-backup.db' > "backups/shady-$stamp/shadenet.db"
ls -la "backups/shady-$stamp"
```
Expected: two non-empty files. `backups/` is outside git (add it to `.gitignore` in Task 2.1).

- [ ] **Step 2: Verify the database copy is whole**

```bash
sqlite3 "backups/shady-$stamp/shadenet.db" "PRAGMA integrity_check;"
```
Expected: `ok`

---

## Phase 1 — Close the operator leak now (before the release)

### Task 1.1: Guard private operator paths at Caddy

**Files:** Create: `deploy/caddy/operator-guard.caddy`

- [ ] **Step 1: Confirm the leak (the failing check)**

```bash
curl -s -o /dev/null -w '%{http_code}\n' "https://$SHADY_HOST/api/operator/status"
```
Expected today: `200` (the leak).

- [ ] **Step 2: Write the snippet**

```caddy
# Private operator and ops APIs never answer the public internet.
# /api/operator/door-verify stays public (shadenet/ops/routes.py PUBLIC_OPERATOR_PATHS).
@operator_private {
	path /api/operator/* /api/ops/*
	not path /api/operator/door-verify
}
respond @operator_private 404
```

- [ ] **Step 3: Install it inside the site block, above the `/api/*` reverse proxy, and reload**

For **systemd** (shape a):
```bash
scp deploy/caddy/operator-guard.caddy "$SHADY_SSH":/tmp/operator-guard.caddy
ssh "$SHADY_SSH" 'sudo install -m 0644 /tmp/operator-guard.caddy /etc/caddy/operator-guard.caddy'
# Add one line, `import /etc/caddy/operator-guard.caddy`, as the first line inside the site block of /etc/caddy/Caddyfile (edit by hand: sudoedit /etc/caddy/Caddyfile)
ssh "$SHADY_SSH" 'sudo caddy validate --config /etc/caddy/Caddyfile && sudo systemctl reload caddy'
```
For **compose** (shape b): put the file in the mounted `config/caddy/` directory, add the same `import` line inside the site block, then `docker compose exec caddy caddy validate --config /etc/caddy/Caddyfile && docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile`.

Expected: `Valid configuration`, then a clean reload.

- [ ] **Step 4: Verify closed, and the public paths still open**

```bash
for p in /api/operator/status /api/ops/login /api/operator/door-verify /api/model /; do
  printf '%s %s\n' "$p" "$(curl -s -o /dev/null -w '%{http_code}' "https://$SHADY_HOST$p")"; done
```
Expected: `/api/operator/status 404`, `/api/ops/login 404`, `/api/operator/door-verify` anything **but** 404 (405 or 400 are fine for a GET), `/api/model 200`, `/ 200`.

- [ ] **Step 5: Commit the snippet and note it in the runbook**

```bash
git add deploy/caddy/operator-guard.caddy docs/operations/shady-deploy.md
git commit -m "ops: guard private operator paths at Caddy"
```

> The guard stays after the release as a second line of defence; the server's own 401 is the first.

---

## Phase 2 — Cut the release branch

### Task 2.1: Release worktree and deploy hygiene

**Files:** Modify: `.gitignore`; Create: `.env.deploy.example`

- [ ] **Step 1: Worktree from `main`**

```bash
git worktree add ../shadenet-a-release -b release/2026-10 main
cd ../shadenet-a-release
```

- [ ] **Step 2: Ignore deploy-local files**

Append to `.gitignore`:
```gitignore
# Deploy: names and build output that never belong in the repo
.env.deploy
releases/
backups/
vendor/steward/**/__pycache__/
```

- [ ] **Step 3: Tracked template**

Create `.env.deploy.example`:
```bash
# Copy to .env.deploy (untracked) and fill in. Never commit the filled copy.
SHADY_HOST=
SHADY_SSH=
STEWARD_REPO=
SHADY_ROOT=
```

- [ ] **Step 4: Commit**

```bash
git add .gitignore .env.deploy.example
git commit -m "chore(deploy): ignore local deploy names and build output"
```

### Task 2.2: Bring in the uncommitted edits from `main` (D2 = ship)

- [ ] **Step 1: Review them in the main checkout**

```bash
git -C ../shadenet-a diff --stat
git -C ../shadenet-a diff -- web/components/event-card/event-card.js web/js/data/calendar.js
```
Expected: the six files listed in "State of things". The event-card change adds a `direction` to the `nc:bodies` detail; calendar adds `eventIsFree` and `categories`/`price`/`free` on events.

- [ ] **Step 2: Carry them over as one commit**

```bash
git -C ../shadenet-a diff > /tmp/main-wip.patch
git apply /tmp/main-wip.patch
git add -A README.md shadenet/nightcal/surface.py web/components/event-card/event-card.js \
  web/components/site-header/site-header.js web/js/data/calendar.js web/js/pages/calendar.js
git commit -m "feat(calendar): free detection from source fields; vote direction on nc:bodies"
```

**D2 = keep out (alt):** skip this task; the main checkout keeps its edits untouched, and the release ships without them.

### Task 2.3: Baseline tests

- [ ] **Step 1: Python suite**

```bash
python3 -m pytest -q 2>&1 | tail -5
```
Expected: everything passes except the known failures (`tests/test_ops.py::test_network_allowlist`, 7 in towncrier `test_nightcal.py`). Any new failure blocks the release.

- [ ] **Step 2: Web tests**

```bash
node web/tests/test_road_layout.mjs
```
Expected: `road layout checks passed`

---

## Phase 3 — Bring the parts together

### Task 3.1: Rebuild the zine

**Files:** Modify: `web/data/zine.json`

- [ ] **Step 1: Rebuild from the vault**

```bash
python3 web/tools/build_zine.py
git diff --stat web/data/zine.json
```
Expected: `zine.json` changes only if the vault changed since the last build. If it is unchanged, skip to Step 3.

- [ ] **Step 2: Check the road's wall still finds pieces**

```bash
python3 -I -c "
import json; d=json.load(open('web/data/zine.json'))
w={'article','review','letter','editorial','stance','dossier','dossier-piece','prediction','cartoon-brief','topic-overview','topic-report'}
print(sum(1 for n in d['nodes'] if n.get('type') in w and (n.get('status') or 'published')=='published'))"
```
Expected: a number ≥ 1 (13 on 2026-10-13).

- [ ] **Step 3: Commit (if changed)**

```bash
git add web/data/zine.json
git commit -m "zine: rebuild for release"
```

### Task 3.2: Vendor the Steward core at a pinned commit

**Files:** Create: `tools/vendor_steward.py`, `vendor/steward/` (generated)

- [ ] **Step 1: Write the vendoring tool**

```python
#!/usr/bin/env python3
"""Copy the Steward core into vendor/steward/ from a pinned commit.

Usage: STEWARD_REPO=<path> python3 tools/vendor_steward.py <commit>

Copies the `steward/` package, `policy/` and `pwa/*.js` exactly as they are
at <commit> (via `git archive`, so uncommitted work in the Steward checkout
never leaks in), and records the commit in vendor/steward/VENDORED_FROM.
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "vendor" / "steward"
KEEP = ("steward/", "policy/", "pwa/")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    commit = sys.argv[1]
    repo = os.environ.get("STEWARD_REPO")
    if not repo:
        print("STEWARD_REPO is not set", file=sys.stderr)
        return 2
    full = subprocess.run(["git", "-C", repo, "rev-parse", commit], check=True, capture_output=True, text=True).stdout.strip()
    blob = subprocess.run(["git", "-C", repo, "archive", "--format=tar", full], check=True, capture_output=True).stdout
    if DEST.exists():
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(blob)) as tar:
        for member in tar.getmembers():
            name = member.name
            if not name.startswith(KEEP) or "/test" in name or "__pycache__" in name:
                continue
            if name.startswith("pwa/") and member.isfile() and not name.endswith(".js"):
                continue
            tar.extract(member, DEST, filter="data")
    (DEST / "VENDORED_FROM").write_text(f"{full}\n", encoding="utf-8")
    print(f"vendored steward {full[:7]} into {DEST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run it at the tested commit**

```bash
set -a; . ./.env.deploy; set +a
python3 tools/vendor_steward.py 5eb063d
ls vendor/steward; cat vendor/steward/VENDORED_FROM
```
Expected: `policy  pwa  steward  VENDORED_FROM`, and the full hash of `5eb063d…`.

- [ ] **Step 3: The vendored copy validates on its own**

```bash
PYTHONPATH=vendor/steward python3 -m steward check
```
Expected: every graph and the posted rules check out (same output as in `$STEWARD_REPO`).

- [ ] **Step 4: Commit**

```bash
git add tools/vendor_steward.py vendor/steward
git commit -m "vendor: Steward core at 5eb063d"
```

### Task 3.3: The House door in the NightCal server (TDD)

**Files:** Create: `shadenet/house.py`, `tests/test_house.py`; Modify: `shadenet/nightcal/server.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_house.py`:
```python
"""The House door as the NightCal server serves it (operator mail, R8)."""

from __future__ import annotations

import json
from pathlib import Path

from shadenet.house import House, RULES_PATH

from steward.stamp import mint  # importable once shadenet.house has put vendor/ on the path

AT = "2026-10-13T20:00:00Z"


def stamped(text: str, mail_id: str = "m-1", at: str = AT) -> dict:
    rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    mail = {"mail_id": mail_id, "case_id": None, "text": text}
    return {"mail": mail, "stamp": mint(mail, at, rules["parameters"]["operator_stamp_bits"])}


def test_stamped_mail_is_filed(tmp_path: Path) -> None:
    house = House(ledger=tmp_path / "inbox.jsonl")
    code, body = house.operator_mail(stamped("the door works"), arrived_at=AT)
    assert code == 202 and body == {"filed": "m-1"}
    records = [json.loads(line) for line in (tmp_path / "inbox.jsonl").read_text().splitlines()]
    assert records[-1]["to"] == "filed"


def test_unstamped_mail_is_refused_and_not_filed(tmp_path: Path) -> None:
    house = House(ledger=tmp_path / "inbox.jsonl")
    request = stamped("no work done")
    request["stamp"]["nonce"] = "0"
    code, body = house.operator_mail(request, arrived_at=AT)
    assert code == 400 and "refused" in body
    assert not (tmp_path / "inbox.jsonl").exists()


def test_replayed_mail_is_refused(tmp_path: Path) -> None:
    house = House(ledger=tmp_path / "inbox.jsonl")
    request = stamped("once only")
    assert house.operator_mail(request, arrived_at=AT)[0] == 202
    assert house.operator_mail(request, arrived_at="2026-10-13T20:01:00Z")[0] == 400


def test_sender_cannot_claim_a_steward(tmp_path: Path) -> None:
    house = House(ledger=tmp_path / "inbox.jsonl")
    request = stamped("pretending", mail_id="m-2")
    request["steward_id"] = "stw-somebody-else"
    code, _ = house.operator_mail(request, arrived_at=AT)
    assert code == 202
    filed = [json.loads(line) for line in (tmp_path / "inbox.jsonl").read_text().splitlines()][-1]
    assert filed["event"]["payload"]["steward_id"] is None
```

- [ ] **Step 2: Run them to see them fail**

Run: `python3 -m pytest tests/test_house.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'shadenet.house'`

- [ ] **Step 3: Write `shadenet/house.py`**

```python
"""The House, as the NightCal server serves it.

One public door for now: operator mail to @dontwastemytime (posted rule R8).
The Steward core is vendored in vendor/steward at a pinned commit
(tools/vendor_steward.py). Everything that can refuse happens in
steward.door before an event exists; a request that passes is filed by the
operator_inbox graph and written to the ledger. Nothing else files mail.

steward_id belongs to the transport. Until Steward signatures are verified
here, every request is the no-Steward web form and steward_id is null,
whatever the sender put in the body.
"""

from __future__ import annotations

import json
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "vendor" / "steward"
if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))

from steward import graph as graphs  # noqa: E402
from steward.catalog import load_catalog  # noqa: E402
from steward.door import operator_mail_event  # noqa: E402
from steward.engine import start, step  # noqa: E402
from steward.ledger import append  # noqa: E402
from steward.policy import load_policy  # noqa: E402
from steward.stamp import SeenMail, StampError  # noqa: E402

RULES_PATH = VENDOR / "policy" / "house_rules.json"
LEDGER_PATH = ROOT / "state" / "house" / "operator_inbox.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class House:
    def __init__(self, ledger: Path = LEDGER_PATH, rules_path: Path = RULES_PATH) -> None:
        self.rules = json.loads(rules_path.read_text(encoding="utf-8"))
        self.catalog = load_catalog(rules_path)
        self.policy = load_policy(rules_path, self.catalog)
        self.inbox = graphs.load("operator_inbox", self.catalog)
        self.seen = SeenMail(self.rules)  # in memory: a restart forgets mail_ids older than the stamp window anyway
        self.ledger = ledger
        self._lock = threading.Lock()

    def operator_mail(self, body: Any, arrived_at: str | None = None) -> tuple[int, dict[str, Any]]:
        """202 {"filed": mail_id}, or 400 {"refused": reason}."""
        if not isinstance(body, dict):
            return 400, {"refused": "request must be a JSON object"}
        request = {"mail": body.get("mail"), "stamp": body.get("stamp"), "steward_id": None}
        at = arrived_at or _now()
        with self._lock:
            try:
                event = operator_mail_event(request, at, self.rules, self.seen)
            except StampError as exc:
                return 400, {"refused": str(exc)}
            opened = start(self.inbox, f"inbox-{event.payload['mail_id']}", {})
            filed = step(self.inbox, opened.instance, event, self.policy, self.catalog.signals)
            self.ledger.parent.mkdir(parents=True, exist_ok=True)
            append(self.ledger, opened.record)
            append(self.ledger, filed.record)
        return 202, {"filed": event.payload["mail_id"]}
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `python3 -m pytest tests/test_house.py -q`
Expected: `4 passed`. (A step record carries `event.payload` and `to`; checked against the engine on 2026-10-13.)

- [ ] **Step 5: Wire the route into the server**

In `shadenet/nightcal/server.py`, add the import next to the other `shadenet` imports:
```python
from shadenet.house import House
```
Below the module-level server state (near `_ops_ctx`), add:
```python
_house: House | None = None


def _the_house() -> House:
    global _house
    if _house is None:
        _house = House()
    return _house
```
In `do_POST`, directly after `if self._flags("POST", path, body): return`, add:
```python
        if path == "/api/house/operator-mail":
            code, payload = _the_house().operator_mail(body)
            self._json(code, payload)
            return
```
This path is not under `/api/operator/`, so `require_operator` does not apply. It is public by design (R8: the door always delivers, from anyone). It falls under the `submissions` rate-limit bucket already applied to `/api/*` at the top of `do_POST`.

- [ ] **Step 6: Exercise the route on a local server**

```bash
NIGHTCAL_PORT=8097 NIGHTCAL_HOST=127.0.0.1 python3 -m shadenet.nightcal.server & srv=$!
sleep 2
python3 - <<'EOF'
import json, sys, urllib.request
sys.path.insert(0, "vendor/steward")
from datetime import datetime, timezone
from steward.stamp import mint
at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
mail = {"mail_id": "smoke-1", "case_id": None, "text": "door smoke test"}
rules = json.load(open("vendor/steward/policy/house_rules.json"))
body = json.dumps({"mail": mail, "stamp": mint(mail, at, rules["parameters"]["operator_stamp_bits"])}).encode()
req = urllib.request.Request("http://127.0.0.1:8097/api/house/operator-mail", body, {"Content-Type": "application/json"})
print(urllib.request.urlopen(req).status)
EOF
kill $srv
tail -1 state/house/operator_inbox.jsonl
```
Expected: `202`, and the last ledger line shows `"to":"filed"`. Then delete the smoke line: `rm state/house/operator_inbox.jsonl` (state/ is untracked).

- [ ] **Step 7: Full suite, then commit**

```bash
python3 -m pytest -q 2>&1 | tail -3
git add shadenet/house.py tests/test_house.py shadenet/nightcal/server.py
git commit -m "feat(house): operator mail door served by NightCal (R8)"
```
Expected: no new failures beyond the known ones.

### Task 3.4: Serve the Steward PWA engine with the site

**Files:** Create: `web/steward/house/engine.js`, `web/steward/house/registry.js`, `web/steward/house/stamp.js`, `web/steward/house/VENDORED_FROM` (copies of the vendored PWA modules)

- [ ] **Step 1: Copy the vendored PWA modules under the web root**

```bash
mkdir -p web/steward/house
cp vendor/steward/pwa/engine.js vendor/steward/pwa/registry.js vendor/steward/pwa/stamp.js web/steward/house/
cp vendor/steward/VENDORED_FROM web/steward/house/VENDORED_FROM
```

- [ ] **Step 2: Check they load as modules in a browser and mint a stamp**

```bash
python3 web/tools/serve.py --port 8098 & srv=$!; sleep 1
node --input-type=module -e '
import { launch } from "./web/tools/browser.mjs";
const b = await launch(); const p = await (await b.newContext()).newPage();
await p.goto("http://127.0.0.1:8098/steward/");
const ok = await p.evaluate(async () => {
  const s = await import("/steward/house/stamp.js");
  const mail = { mail_id: "x", case_id: null, text: "hi" };
  const st = s.mint(mail, new Date().toISOString().replace(/\.\d+Z$/, "Z"), 8);
  return typeof st.nonce === "string";
});
console.log(ok ? "pwa stamp ok" : "pwa stamp FAILED"); await b.close();'
kill $srv
```
Expected: `pwa stamp ok`. (Check `web/tools/serve.py --help` for the port flag if it differs.)

- [ ] **Step 3: Commit**

```bash
git add web/steward/house
git commit -m "steward: serve the House PWA engine (engine, registry, stamp)"
```

> Wiring the Steward drawer UI to mint and send operator mail is follow-on work once D3 is settled; this release ships the door and the engine, not activation.

### Task 3.5: Serendipilyst ships with release refused

- [ ] **Step 1: Prove release is still refused**

```bash
python3 -m pytest -q -k "obligation or serendip or flags" 2>&1 | tail -3
grep -n "def may_release" -A 8 shadenet/serendipilyst/obligation.py
```
Expected: the tests pass, and `may_release` returns the refusal. If the file lives elsewhere, `grep -rn "def may_release" shadenet` finds it.

- [ ] **Step 2: Smoke the routes on the local server**

```bash
NIGHTCAL_PORT=8097 NIGHTCAL_HOST=127.0.0.1 python3 -m shadenet.nightcal.server & srv=$!; sleep 2
curl -s -o /dev/null -w 'flags %{http_code}\n' http://127.0.0.1:8097/api/flags
kill $srv
```
Expected: `flags 200` (or the code the route returns for an anonymous GET; anything but 5xx).

---

## Phase 4 — Ship

### Task 4.1: Build the release artifact

**Files:** Create: `tools/release.sh`

- [ ] **Step 1: Write the build script**

```bash
#!/usr/bin/env bash
# Build releases/<sha>.tar.gz from a commit. Only tracked files ship; local
# data, state and secrets never do.
set -euo pipefail
commit="${1:-HEAD}"
sha="$(git rev-parse --short=12 "$commit")"
mkdir -p releases
git archive --format=tar.gz --prefix="$sha/" -o "releases/$sha.tar.gz" "$commit" \
  -- . ':!shadenet/data' ':!state' ':!backups' ':!docs/audit/report.json'
echo "releases/$sha.tar.gz"
```

- [ ] **Step 2: Build and inspect**

```bash
chmod +x tools/release.sh
git add tools/release.sh && git commit -m "tools: release artifact via git archive"
art="$(tools/release.sh)"; echo "$art"
tar -tzf "$art" | grep -cE '^[0-9a-f]+/(shadenet/data|state)/' || true
tar -tzf "$art" | grep -E '/web/road/zine-wall.js$|/shadenet/house.py$|/vendor/steward/VENDORED_FROM$'
```
Expected: `0` data or state entries, and all three files listed.

### Task 4.2: Install side by side, switch, verify, keep the old one

These steps assume shape (a), systemd. For shape (b), compose, swap "restart the service" for `docker compose up -d --build shadenet` in `$SHADY_ROOT`, and record that in the runbook.

- [ ] **Step 1: Upload and unpack next to the live app**

```bash
sha="$(basename "$art" .tar.gz)"
scp "$art" "$SHADY_SSH":/tmp/
ssh "$SHADY_SSH" 'set -e; R="'"$SHADY_ROOT"'"; mkdir -p "$R-releases";
  tar -C "$R-releases" -xzf /tmp/'"$sha"'.tar.gz; rm /tmp/'"$sha"'.tar.gz; ls "$R-releases"'
```
Expected: the new `<sha>` directory beside any earlier ones.

- [ ] **Step 2: Carry over live data and state (by link, never copy back)**

```bash
ssh "$SHADY_SSH" 'set -e; R="'"$SHADY_ROOT"'"; N="$R-releases/'"$sha"'";
  ln -sfn "$R/shadenet/data" "$N/shadenet/data"; ln -sfn "$R/state" "$N/state"; ls -la "$N/shadenet/data" "$N/state" | head'
```
Expected: both resolve to the live directories.

> First release only: `$SHADY_ROOT` is a plain directory, not a symlink. Move it once to `$SHADY_ROOT-releases/previous` and put the data and state links back from there. Record the exact commands in the runbook, and do it inside the maintenance window in Step 3.

- [ ] **Step 3: Switch and restart**

```bash
ssh "$SHADY_SSH" 'set -e; R="'"$SHADY_ROOT"'";
  ln -sfn "$R-releases/'"$sha"'" "$R.next" && mv -T "$R.next" "$R";
  chown -h www-data:www-data "$R"; systemctl restart shadenet; sleep 2;
  systemctl is-active shadenet'
```
Expected: `active`.

- [ ] **Step 4: Smoke the public site**

Create `tools/smoke_public.sh`:
```bash
#!/usr/bin/env bash
# Public smoke checks. Exit 1 on the first wrong status.
set -euo pipefail
base="https://${SHADY_HOST:?set SHADY_HOST}"
check() { got="$(curl -s -o /dev/null -w '%{http_code}' "$base$1")"; [[ "$got" == "$2" ]] || { echo "FAIL $1 $got (want $2)"; exit 1; }; echo "ok   $1 $got"; }
check /                         200
check /road/                    200
check /road/zine-wall.js        200
check /zine/                    200
check /data/zine.json           200
check /api/model                200
check /api/operator/status      404
check /api/ops/login            404
curl -s "$base/road/" | grep -q 'bust = "timeline' && echo "ok   road cache token present"
```
Run:
```bash
chmod +x tools/smoke_public.sh && tools/smoke_public.sh
```
Expected: every line `ok`.

- [ ] **Step 5: Browser check on the public road**

```bash
node --input-type=module -e '
import { launch } from "./web/tools/browser.mjs";
const b = await launch(); const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: "dark", serviceWorkers: "block" });
const p = await ctx.newPage(); const errs = []; p.on("pageerror", e => errs.push(String(e)));
await p.goto(`https://${process.env.SHADY_HOST}/road/?scope=all`, { waitUntil: "networkidle" });
await p.waitForTimeout(1500);
const n = await p.evaluate(() => ({ signs: document.querySelectorAll(".road-sign").length, posters: document.querySelectorAll(".zine-poster").length }));
await p.screenshot({ path: "/tmp/shady-road.png" }); console.log(JSON.stringify(n), errs); await b.close();'
```
Expected: `signs` > 0, `posters` > 0, no errors. Look at `/tmp/shady-road.png`.

- [ ] **Step 6: House door, live**

Run the Task 3.3 Step 6 Python snippet with the URL changed to `https://$SHADY_HOST/api/house/operator-mail`.
Expected: `202`, and on the VPS the last line of `$SHADY_ROOT/state/house/operator_inbox.jsonl` shows `"to":"filed"`.

- [ ] **Step 7: Write ship and rollback into the runbook; commit**

Rollback is the same switch, pointed back:
```bash
ssh "$SHADY_SSH" 'R="'"$SHADY_ROOT"'"; P="$(ls -1t "$R-releases" | sed -n 2p)"; ln -sfn "$R-releases/$P" "$R.next" && mv -T "$R.next" "$R" && systemctl restart shadenet && systemctl is-active shadenet'
```
```bash
git add tools/smoke_public.sh docs/operations/shady-deploy.md
git commit -m "ops: public smoke checks; ship and rollback runbook"
```

### Task 4.3: Land the release on `main`

- [ ] **Step 1: Fast-forward `main` to the release**

```bash
git -C ../shadenet-a merge --ff-only release/2026-10
```
Expected: fast-forward. If Task 2.2 carried the uncommitted edits, `git -C ../shadenet-a status` will show them as already committed; check with `git -C ../shadenet-a diff --stat` that nothing is left over.

- [ ] **Step 2: Test server follows**

```bash
curl -s -o /dev/null -w 'test server road %{http_code}\n' http://127.0.0.1:8765/road/
sudo systemctl restart nightcal   # the server now imports shadenet.house
curl -s -o /dev/null -w 'house %{http_code}\n' -X POST -H 'Content-Type: application/json' -d '{}' http://127.0.0.1:8765/api/house/operator-mail
```
Expected: `road 200`, `house 400` (an empty body is refused, which proves the route is live).

---

## Phase 5 — Before any push (D4)

### Task 5.1: Clean `86ace91`, then push

- [ ] **Step 1: Neutralise the two paths**

```bash
sed -i 's#^cd /home/[^ ]*/Downloads/shadenet-a   \# or this worktree root$#cd shadenet-a   \# the repo root, or this worktree#; s#^If `/home/[^`]*/hermes-completions.log` is writable#If the shared `hermes-completions.log` (outside the repo) is writable#' docs/superpowers/plans/2026-10-13-road-street-timeline.md
git add docs/superpowers/plans/2026-10-13-road-street-timeline.md
git commit --fixup=86ace91
GIT_SEQUENCE_EDITOR=: git rebase -i --autosquash origin/main
```
Expected: a clean rebase. The hook's own scan is the check:

- [ ] **Step 2: Push the release branch**

```bash
git push -u origin release/2026-10
```
Expected: the pre-push hook passes. If it refuses, fix what it names. Never `--no-verify` without the owner's say-so.

---

## Spec coverage

| Asked for | Where |
| --- | --- |
| Road (street timeline, cards, clock, key, zine wall) | already on `main`; ships in 4.1–4.2, checked in 4.2 Step 5 |
| Zine | 3.1 rebuild, smoke in 4.2 Step 4 |
| Serendipilyst | 3.5 (release refused by design), ships with `main` |
| Steward | 3.2 vendor, 3.3 House door, 3.4 PWA engine; activation held by D3 |
| Public site at the real host | Phase 0 recon, Phase 4 ship, rollback in 4.2 Step 7 |
| Close today's leak | Phase 1, before anything else |
| Nothing personal in the repo | names only in `.env.deploy`; Phase 5 for the old commit |

## Risks

- **Process model unknown until Task 0.1.** Phase 4 is written for systemd, with compose noted. The runbook records which one applies, so the next release is mechanical.
- **First switch to a symlinked root** is the only step with downtime (a service restart). Do it at a quiet hour and keep `previous` until the smoke checks pass.
- **The in-memory replay guard** (`SeenMail`) resets on restart. A replay inside the 10-minute stamp window after a restart would be filed twice; the operator sees both in the ledger. Acceptable for now; persist it if it ever matters.
- **Steward drawer** (`web/steward/`) is the older port and still fails open client-side on the age gate. Nothing in this release makes it stricter or looser. D3 decides that next.
