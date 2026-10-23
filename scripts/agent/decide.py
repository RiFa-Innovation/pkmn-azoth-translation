"""Pick an option: Jev (TypeSafe's decision model) with a confidence gate, falling back to the heuristic.

Jev: POST https://api.typesafe.ai/v1/systemone {model, state, questions}; a `choice` question takes `criteria` = {key: description}
and answers {choice, probabilities, confidence}. The key comes from TYPESAFE_API_KEY; without it every decision is the heuristic
and the request that would have been sent is still logged.
"""
import json
import os
import time
import urllib.error
import urllib.request

import options as op

URL = "https://api.typesafe.ai/v1/systemone"
MODEL = os.environ.get("JEV_MODEL", "jev-latest")
INSTRUCTIONS = {
    "win": "You are playing a Pokemon battle turn. Pick the action most likely to win the battle without losing team members: "
           "prefer moves that knock the foe out first, avoid ineffective moves, switch only to escape a likely knockout.",
    "flee": "You are exploring and want to avoid this wild battle. Pick the action that ends it safely, usually running away.",
}


def request_body(state, opts, goal):
    return {"model": MODEL, "state": op.context(state),
            "questions": {"action": {"type": "choice", "instructions": INSTRUCTIONS[goal],
                                     "criteria": {o["key"]: o["desc"] for o in opts}}}}


def ask_jev(body, key, timeout=10):
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    t = time.monotonic()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        resp = json.load(r)
    return resp, round(1000 * (time.monotonic() - t))


def decide(state, opts, goal="win", min_conf=0.5):
    """Returns a log record; record["action"] is the option key to play."""
    rec = {"t": time.time(), "goal": goal, "state": op.context(state), "options": {o["key"]: o["desc"] for o in opts}}
    rec["heuristic"] = op.heuristic(state, opts, goal)
    key = os.environ.get("TYPESAFE_API_KEY")
    if not key:
        rec.update(source="heuristic", why="no TYPESAFE_API_KEY", action=rec["heuristic"])
        return rec
    body = request_body(state, opts, goal)
    try:
        resp, ms = ask_jev(body, key)
    except (urllib.error.URLError, TimeoutError, OSError) as ex:
        detail = ex.read().decode(errors="replace")[:300] if isinstance(ex, urllib.error.HTTPError) else ""
        rec.update(source="heuristic", why=f"jev error: {ex} {detail}".strip(), action=rec["heuristic"])
        return rec
    ans = resp.get("answers", {}).get("action", {})
    rec["jev"] = {"choice": ans.get("choice"), "confidence": ans.get("confidence"), "probabilities": ans.get("probabilities"),
                  "model": resp.get("model"), "usage": resp.get("usage"), "ms": ms}
    valid = {o["key"] for o in opts}
    if ans.get("choice") in valid and (ans.get("confidence") or 0) >= min_conf:
        rec.update(source="jev", action=ans["choice"])
    else:
        rec.update(source="heuristic", why=f"jev confidence {ans.get('confidence')} < {min_conf} or invalid choice",
                   action=rec["heuristic"])
    rec["agree"] = rec["jev"]["choice"] == rec["heuristic"]
    return rec
