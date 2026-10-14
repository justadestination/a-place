# Shady deploy runbook

Names come from the untracked `.env.deploy` (template: `.env.deploy.example`).

## Layout (as of 2026-10-14)

- Host: `$SHADY_SSH`, systemd unit `shadenet.service` (User `www-data`, `127.0.0.1:8765`), Caddy on the same host at `/etc/caddy/Caddyfile`.
- `/opt/shadenet` is a symlink to the live release in `/opt/shadenet-releases/<sha>/`.
- Runtime state lives once in `/opt/shadenet-shared/` and is linked into every release:
  `shadenet/data`, `state`, `zine-automation/state`, `agent-scaffold/agent-scaffold/state`, `shadenet/steward/state`, `shadenet/.cache`.
- `/opt/shadenet-releases/previous` is the tree from before the first release (rsync era).
- Caddy imports `/etc/caddy/operator-guard.caddy` (copy of `deploy/caddy/operator-guard.caddy`) in each site block.

## Ship

```bash
set -a; . ./.env.deploy; set +a
art="$(tools/release.sh)"; sha="$(basename "$art" .tar.gz)"
scp "$art" "$SHADY_SSH":/tmp/
scp deploy/install_release.sh "$SHADY_SSH":/tmp/install_release.sh
ssh "$SHADY_SSH" "PUBLIC_DOMAIN=<domain> bash /tmp/install_release.sh $sha"
tools/smoke_public.sh
```

`install_release.sh` checks `/`, `/road/` and `/api/model` after the switch and puts the previous release back if any of them fail.

## Roll back by hand

```bash
ssh "$SHADY_SSH" 'ls -1t /opt/shadenet-releases'
ssh "$SHADY_SSH" 'ln -sfn /opt/shadenet-releases/<sha or previous> /opt/shadenet.next && mv -T /opt/shadenet.next /opt/shadenet && systemctl restart shadenet'
```

## Never

- Never rsync a working tree over `/opt/shadenet` (the 2026-10-08 method): it overwrites live data with the local copy.
