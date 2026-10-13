"""Operator Steward: a deterministic command console, no model inference.

Commands are parsed with a fixed grammar and call the same functions as the
HTTP API, under the same rules (dangerous changes need TOTP step-up). Anything
it doesn't recognise gets "unknown command" + help, never a guess.
"""

from __future__ import annotations

import shlex
from typing import Any, Callable

from shadenet.flags import FeatureFlagManager
from shadenet.health import check_subsystems
from shadenet.ops import agegate, audit, auth, logs, metrics, recovery, settings

HELP = [
    ("help", "this list"),
    ("status", "subsystem health + traffic summary"),
    ("errors [n]", "most recent error groups"),
    ("logs [level] [text...]", "recent log lines, e.g. logs warning scraper"),
    ("metrics", "request counts and latency"),
    ("get <key>", "read a setting, e.g. get chat.enabled"),
    ("set <key> <value>", "change a setting (dangerous ones need step-up)"),
    ("settings <tab>", "list settings on a tab, e.g. settings nightcal"),
    ("flags", "feature flags"),
    ("flag <name> on|off", "toggle a feature flag"),
    ("recoveries [status]", "account recovery requests"),
    ("overrides", "active 21+ overrides"),
    ("sessions", "signed-in operators"),
    ("venues-pending", "business nodes naming a venue nobody has verified"),
    ("venue-verify <node_id> [off]", "confirm a node really is its venue (needs step-up)"),
    ("audit [n]", "recent operator actions"),
]


class StepUpRequired(Exception):
    pass


def _fmt_help() -> str:
    width = max(len(c) for c, _ in HELP)
    return "\n".join(f"{c.ljust(width)}  {d}" for c, d in HELP)


def run(command: str, *, actor: str, stepped_up: bool) -> dict[str, Any]:
    try:
        parts = shlex.split(command.strip())
    except ValueError as exc:
        return {"ok": False, "text": f"couldn't parse that: {exc}"}
    if not parts:
        return {"ok": False, "text": _fmt_help()}
    cmd, args = parts[0].lower().lstrip("!/"), parts[1:]
    handler = COMMANDS.get(cmd)
    if not handler:
        return {"ok": False, "text": f"unknown command {cmd!r}\n\n{_fmt_help()}"}
    try:
        text, data = handler(args, actor, stepped_up)
    except StepUpRequired as exc:
        return {"ok": False, "step_up_required": True, "text": str(exc)}
    except (KeyError, ValueError, IndexError) as exc:
        return {"ok": False, "text": f"error: {exc}"}
    return {"ok": True, "text": text, "data": data}


def _status(args, actor, su):
    h = check_subsystems()
    m = metrics.snapshot()
    lines = [f"overall: {h.get('status', '?')}"]
    for name, sub in (h.get("subsystems") or h.get("components") or {}).items():
        state = sub.get("status", sub) if isinstance(sub, dict) else sub
        lines.append(f"  {name}: {state}")
    lines.append(f"requests since start: {sum(r['count'] for r in m['routes'])}, "
                 f"5xx: {m['status'].get('5xx', 0)}, p95 {m['latency_ms']['p95']} ms")
    return "\n".join(lines), {"health": h, "metrics": m}


def _errors(args, actor, su):
    n = int(args[0]) if args else 10
    groups = logs.error_groups()[:n]
    if not groups:
        return "no recent errors", groups
    return "\n".join(f"{g['count']:>4}x  {g['key']}  (last {g['last'].get('timestamp', '?')})" for g in groups), groups


def _logs(args, actor, su):
    level = args[0].upper() if args and args[0].upper() in logs.LEVELS else ""
    text = " ".join(args[1:] if level else args)
    res = logs.query(level=level, q=text, limit=20)
    lines = [f"{r.get('timestamp', '')[:19]} {r.get('level', ''):<7} {r.get('event', '')} {r.get('message', '')}".rstrip()
             for r in res["records"]]
    return "\n".join(lines) or f"no matching lines (source: {res['source']['kind']})", res


def _metrics(args, actor, su):
    m = metrics.snapshot()
    top = "\n".join(f"  {r['count']:>6}  {r['route']}  avg {r['avg_ms']} ms" for r in m["routes"][:8])
    return f"uptime {m['uptime_seconds']}s  status {m['status']}  latency {m['latency_ms']}\n{top}", m


def _get(args, actor, su):
    s = settings.lookup(args[0])
    return f"{s.key} = {settings.get(s.key)!r}" + ("" if s.wired else "  (stored only, not read by the app yet)"), None


def _set(args, actor, su):
    s = settings.lookup(args[0])
    if s.dangerous and not su:
        raise StepUpRequired(f"{s.key} needs step-up: enter a fresh authenticator code and resend")
    res = settings.set_value(s.key, " ".join(args[1:]), actor)
    audit.record(actor, "settings.set", target=s.key, via="steward", old=res["old"], new=res["value"])
    return f"{s.key}: {res['old']!r} -> {res['value']!r}", res


def _settings(args, actor, su):
    rows = settings.listing(args[0] if args else "")["settings"]
    return "\n".join(f"{r['key']} = {r['value']!r}" for r in rows) or "no settings on that tab", rows


def _flags(args, actor, su):
    flags = FeatureFlagManager().get_all_flags()
    return "\n".join(f"{k}: {'on' if v.get('enabled') else 'off'} ({v.get('rollout_percentage', 100)}%)" for k, v in flags.items()), flags


def _flag(args, actor, su):
    name, state = args[0], args[1].lower()
    if state not in ("on", "off"):
        raise ValueError("use on or off")
    toggle_flag(name, state == "on")
    audit.record(actor, "flags.set", target=name, via="steward", enabled=state == "on")
    return f"{name} -> {state}", None


def toggle_flag(name: str, enabled: bool) -> dict:
    """Flip a flag without disturbing its rollout percentage (set_flag resets it to 100 otherwise)."""
    mgr = FeatureFlagManager()
    current = mgr.get_all_flags()
    if name not in current:
        raise KeyError(f"unknown flag {name!r}")
    return mgr.set_flag(name, enabled=enabled, rollout_percentage=current[name].get("rollout_percentage", 100))


def _recoveries(args, actor, su):
    reqs = recovery.listing(args[0] if args else "")
    return "\n".join(f"{r['id']}  {r['status']:<9} {r['account']}" for r in reqs) or "none", reqs


def _overrides(args, actor, su):
    rows = [o for o in agegate.listing() if o["active"]]
    return "\n".join(f"{o['id']}  {o['kind']:<5} {o['subject']}  until {o['expires_at'][:10]}  ({o['reason']})" for o in rows) or "none active", rows


def _sessions(args, actor, su):
    rows = auth.active_sessions()
    return "\n".join(f"{s['username']}  from {s['ip']}" for s in rows) or "none", rows


def _audit(args, actor, su):
    rows = audit.tail(int(args[0]) if args else 15)
    return "\n".join(f"{e['ts'][:19]}  {e['actor']:<10} {e['action']}  {e['target']}" for e in rows) or "empty", rows


def _venues_pending(args, actor, su):
    from shadenet.serendipilyst import get_store, pending_venues

    rows = [{k: v for k, v in node.items() if k != "controller"} for node in pending_venues(get_store())]
    return "\n".join(f"{r['id']}  {r['venue_id']:<20} {r['name']}" for r in rows) or "none waiting", rows


def _venue_verify(args, actor, su):
    from shadenet.serendipilyst import FlagError, get_store, verify_venue

    if not su:
        raise StepUpRequired("venue-verify needs step-up: enter a fresh authenticator code and resend")
    on = not (len(args) > 1 and args[1].lower() == "off")
    try:
        node = verify_venue(get_store(), node_id=args[0], verified=on)
    except FlagError as exc:
        raise ValueError(str(exc)) from None
    audit.record(actor, "venue.verify", target=args[0], via="steward", venue_id=node["venue_id"], verified=on)
    return f"{node['name']} {'is' if on else 'is no longer'} {node['venue_id']}", None


COMMANDS: dict[str, Callable] = {
    "help": lambda a, u, s: (_fmt_help(), None),
    "status": _status, "health": _status,
    "errors": _errors, "logs": _logs, "metrics": _metrics,
    "get": _get, "set": _set, "settings": _settings,
    "flags": _flags, "flag": _flag,
    "recoveries": _recoveries, "overrides": _overrides,
    "sessions": _sessions, "audit": _audit,
    "venues-pending": _venues_pending, "venue-verify": _venue_verify,
}
