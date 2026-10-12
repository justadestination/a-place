#!/usr/bin/env python3
"""State helpers for the zine automation system. Stdlib only.

Usage:
  state.py gate --chance 40
  state.py pick
  state.py topic <slug>
  state.py stance --persona ID --subject S --stance S --draft F
  state.py predict --persona ID --claim C --check-date YYYY-MM-DD --draft F
  state.py log --persona ID --prompt TYPE --draft F [--notes N]
"""
import argparse, json, os, random, sys
from datetime import date

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(BASE, 'state', 'state.json')
LOG = os.path.join(BASE, 'state', 'run-log.md')

PERSONAS = ["mags-pilecki", "juno-voss", "mara-okwonko", "dev-malik",
            "nico-varela", "priya-raman", "silas-brandt", "bea-luna",
            "dante-morales", "esme-navarro", "felix-brauer",
            "julian-croft", "camilla-thorne"]
# Relative selection weights: standard writers post frequently (weight 10),
# while quiet/occasional writers post far less frequently (weight 2).
PERSONA_WEIGHTS = {
    "julian-croft": 2,      # Contrarian cultural critique — quiet, occasional
    "camilla-thorne": 2,    # Etiquette, protocol & hierarchy — quiet, occasional
}
# (prompt file, weight) — editors-letter is never auto-picked
PROMPTS = [("hot-take", 35), ("dossier", 20), ("prediction", 20),
           ("cartoon-brief", 15), ("topic-overview", 10)]
# cartoon-brief only valid for nico-varela
PROMPT_PERSONA = {"cartoon-brief": ["nico-varela"]}

def load():
    with open(STATE) as f:
        return json.load(f)

def save(s):
    with open(STATE, 'w') as f:
        json.dump(s, f, indent=2)

def log_line(text):
    with open(LOG, 'a') as f:
        f.write(text.rstrip() + '\n')

def cmd_gate(a):
    roll = random.randint(1, 100)
    ok = roll <= a.chance
    print(f"roll={roll} chance={a.chance} -> {'PROCEED' if ok else 'SKIP'}")
    if not ok:
        log_line(f"{date.today()} — skipped (gate roll {roll}/{a.chance})")
    sys.exit(0 if ok else 3)

def cmd_pick(a):
    s = load()
    avail_p = [p for p in PERSONAS if p not in s['recent_personas']]
    p_weights = [PERSONA_WEIGHTS.get(p, 10) for p in avail_p]
    persona = random.choices(avail_p, weights=p_weights)[0]
    names = [n for n, _ in PROMPTS]
    weights = [w for _, w in PROMPTS]
    prompt = random.choices(names, weights=weights)[0]
    if prompt in PROMPT_PERSONA and persona not in PROMPT_PERSONA[prompt]:
        persona = random.choice(PROMPT_PERSONA[prompt])
    if persona == "nico-varela" and prompt != "cartoon-brief":
        prompt = "cartoon-brief"
    print(f"persona={persona} prompt={prompt}")

def cmd_topic(a):
    s = load()
    s['topics'][a.slug] = {"created": str(date.today()), "overview": True, "report": True}
    save(s)
    log_line(f"{date.today()} — topic created: {a.slug}")
    print(f"recorded topic {a.slug}")

def cmd_stance(a):
    s = load()
    s['stances'].insert(0, {"date": str(date.today()), "persona": a.persona,
                            "subject": a.subject, "stance": a.stance, "draft": a.draft})
    save(s)
    print(f"recorded stance for {a.persona}")

def cmd_predict(a):
    s = load()
    s['predictions'].insert(0, {"date": str(date.today()), "persona": a.persona,
                                "claim": a.claim, "check_date": a.check_date,
                                "draft": a.draft, "result": None})
    save(s)
    print(f"recorded prediction for {a.persona}, check {a.check_date}")

def cmd_log(a):
    s = load()
    s['recent_personas'] = ([a.persona] + s['recent_personas'])[:5]
    s['recent_prompts'] = ([a.prompt] + s['recent_prompts'])[:5]
    s['runs'] += 1
    if a.draft:
        s['pieces'] += 1
    save(s)
    log_line(f"{date.today()} — {a.persona} / {a.prompt} → {a.draft or 'no piece'}"
             + (f" — {a.notes}" if a.notes else ""))
    print("logged")

def _flip_status(path):
    with open(path) as f:
        text = f.read()
    text = text.replace('status: draft', 'status: published', 1)
    with open(path, 'w') as f:
        f.write(text)

def cmd_publish(a):
    import shutil
    s = load()
    src = os.path.join(BASE, 'drafts', a.draft)
    dst = os.path.join(BASE, 'published', a.draft)
    if not os.path.exists(src):
        print(f"ERROR: {src} not found"); sys.exit(1)
    _flip_status(src)
    shutil.move(src, dst)
    if a.topic:
        tdir = os.path.join(BASE, 'topics', a.topic)
        for fn in ('overview.md', 'full-report.md'):
            p = os.path.join(tdir, fn)
            if os.path.exists(p):
                _flip_status(p)
    s['published'] = s.get('published', 0) + 1
    save(s)
    log_line(f"{date.today()} — PUBLISHED {a.draft}" + (f" (+topic {a.topic})" if a.topic else ""))
    print(f"published {a.draft}")

def cmd_escalate(a):
    import shutil
    src = os.path.join(BASE, 'drafts', a.draft)
    dst = os.path.join(BASE, 'needs-operator', a.draft)
    if not os.path.exists(src):
        print(f"ERROR: {src} not found"); sys.exit(1)
    shutil.move(src, dst)
    log_line(f"{date.today()} — ESCALATED {a.draft}: {a.reason}")
    print(f"escalated {a.draft}: {a.reason}")

p = argparse.ArgumentParser()
sub = p.add_subparsers(dest='cmd', required=True)

g = sub.add_parser('gate'); g.add_argument('--chance', type=int, default=40)
sub.add_parser('pick')
t = sub.add_parser('topic'); t.add_argument('slug')
st = sub.add_parser('stance')
st.add_argument('--persona', required=True); st.add_argument('--subject', required=True)
st.add_argument('--stance', required=True); st.add_argument('--draft', required=True)
pr = sub.add_parser('predict')
pr.add_argument('--persona', required=True); pr.add_argument('--claim', required=True)
pr.add_argument('--check-date', required=True); pr.add_argument('--draft', required=True)
lg = sub.add_parser('log')
lg.add_argument('--persona', required=True); lg.add_argument('--prompt', required=True)
lg.add_argument('--draft', default=''); lg.add_argument('--notes', default='')
pb = sub.add_parser('publish')
pb.add_argument('--draft', required=True); pb.add_argument('--topic', default='')
es = sub.add_parser('escalate')
es.add_argument('--draft', required=True); es.add_argument('--reason', required=True)

args = p.parse_args()
{'gate': cmd_gate, 'pick': cmd_pick, 'topic': cmd_topic,
 'stance': cmd_stance, 'predict': cmd_predict, 'log': cmd_log,
 'publish': cmd_publish, 'escalate': cmd_escalate}[args.cmd](args)
