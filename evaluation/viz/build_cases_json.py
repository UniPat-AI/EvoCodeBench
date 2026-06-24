#!/usr/bin/env python3
"""Build docs/data/cases.json for the EvoCode-Bench results site.

For every (task, round, model) it records:
  - pass/total test cases, fail count, round reward
  - the failing cases: requirement_ref, case_type, a cleaned failure reason
And per task it aggregates cross-model "common failure" requirements.

Source: <TASKS_DIR>/<task>/harbor_jobs/<model-short>/<latest 2026-*>/**/steps/round-N/verifier/test-stdout.txt
"""
import os, glob, re, json, html
from collections import defaultdict, Counter

TASKS_DIR = os.environ.get(
    "EVOCODEBENCH_TASKS_DIR",
    "/nvme1/shenhaiyang/Source/swebenchpp/data/multiturn/archives/harbor_official_multistep_converted/evocodebench_wotraj",
)
OUT_DIR = os.environ.get("EVOCODEBENCH_DOCS_DATA", "/nvme1/shenhaiyang/Source/EvoCodeBench/docs/data")
OUT_INDEX = OUT_DIR + "/index.json"
OUT_TASKS = OUT_DIR + "/tasks"

# display name -> harbor_jobs subdir
MODELS = [
    ("Opus-4.8-xhigh", "claude-opus-4-8"), ("GPT-5.5", "gpt-5.5"), ("Kimi-K2.6", "kimi-k2.6"),
    ("Kimi-K2.7-Code", "kimi-k2.7-code"),
    ("MiniMax-M3", "minimax-m3"), ("DeepSeek-V4-Pro", "deepseek-v4-pro"), ("Qwen3.6-Plus", "qwen3.6-plus"),
    ("Doubao-Seed-2.1-Pro", "doubao-seed-2-1-pro"),
    ("GLM-5.1", "glm-5.1"), ("GLM-5.2", "glm-5.2"), ("Qwen3.7-Max", "qwen3.7-max"),
    ("DeepSeek-V4-Flash", "deepseek-v4-flash"), ("MiniMax-M2.7", "minimax-m2.7"),
]

# (display, task) cells that are BLANK (excluded, NOT scored 0). None currently.
BLANK_CELLS = set()

CASE_RE = re.compile(
    r'CASE_RESULT\s+case_id=(?P<cid>\S+)\s+origin_step=(?P<orig>\S+)\s+'
    r'requirement_ref=(?P<req>\S+)\s+case_type=(?P<ct>\S+)\s+status=(?P<st>\S+)\s+'
    r'intent="(?P<intent>[^"]*)"\s+scenario="(?P<scn>[^"]*)"\s+'
    r'input="(?P<inp>[^"]*)"\s+expected="(?P<exp>[^"]*)"\s+'
    r'actual="(?P<act>[^"]*)"\s+failure_reason="(?P<fr>[^"]*)"')
SUMMARY_RE = re.compile(r'^CASE_SUMMARY total_cases=(\d+) success_count=(\d+) fail_count=(\d+)', re.M)


def metadata(task):
    p = os.path.join(TASKS_DIR, task, "task.toml")
    md = {"name": task, "difficulty": "", "category": ""}
    try:
        txt = open(p).read()
        for k in ("name", "difficulty", "category"):
            m = re.search(rf'^{k}\s*=\s*"([^"]*)"', txt, re.M)
            if m:
                md[k] = m.group(1)
    except Exception:
        pass
    return md


def round_intent(task, rnd):
    p = os.path.join(TASKS_DIR, task, "steps", f"round-{rnd}", "instruction.md")
    try:
        for line in open(p):
            s = line.strip()
            if s and not s.startswith("#"):
                return s[:200]
    except Exception:
        pass
    return ""


def round_doc(task, rnd):
    """Full instruction for a round: (title, markdown body)."""
    p = os.path.join(TASKS_DIR, task, "steps", f"round-{rnd}", "instruction.md")
    try:
        md = open(p, errors="ignore").read()
    except Exception:
        return ("", "")
    title = ""
    for line in md.splitlines():
        s = line.strip()
        if s.startswith("#"):
            title = s.lstrip("# ").strip(); break
        if s:
            title = s[:90]; break
    return (title, md)


def clean_reason(c):
    """Human-meaningful reason; back-fill terse failure_reason from expected/actual/intent."""
    fr = (c.get("fr") or "").strip()
    exp, act = (c.get("exp") or "").strip(), (c.get("act") or "").strip()
    if fr and fr.rstrip(":").strip() and len(fr.rstrip(": ")) > 3:
        return fr
    if exp or act:
        return f"expected {exp or '?'}, got {act or '(empty)'}"
    return c.get("intent", "") or "(no reason)"


def latest_run(task, ms):
    r = sorted(glob.glob(os.path.join(TASKS_DIR, task, "harbor_jobs", ms, "2026-*")))
    return r[-1] if r else None


def parse_round(run, rnd):
    so = glob.glob(os.path.join(run, f"**/steps/round-{rnd}/verifier/test-stdout.txt"), recursive=True)
    rt = glob.glob(os.path.join(run, f"**/steps/round-{rnd}/verifier/reward.txt"), recursive=True)
    reward = None
    if rt:
        try:
            reward = float(open(rt[0]).read().strip())
        except Exception:
            pass
    if not so:
        # no verifier stdout at all: the run never reached this round (sandbox/chain truly absent)
        if reward is None:
            return None
        # reward exists but no stdout: count as a real scored round with no case detail
        return {"pass": 0, "total": 0, "fail": 0, "reward": int(reward) if reward in (0.0, 1.0) else round(reward, 3),
                "fails": [], "note": "no test output captured"}
    txt = open(so[0], errors="ignore").read()
    cases = [m.groupdict() for m in CASE_RE.finditer(txt)]
    m = SUMMARY_RE.search(txt)
    if m:
        total, succ, fail = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        succ = sum(1 for c in cases if c["st"] == "success")
        fail = sum(1 for c in cases if c["st"] == "fail")
        total = succ + fail
    if total == 0:
        # test.sh exited before any CASE_RESULT — almost always a build/setup early-exit.
        # This is a REAL scored round (reward present), not missing data. Surface the reason.
        early = ""
        for line in txt.splitlines():
            s = line.strip()
            if s.startswith("FAIL:") or "Build failed" in s or "not found" in s.lower() or "error:" in s.lower():
                early = s[:160]
                if s.startswith("FAIL:"):
                    break
        return {"pass": 0, "total": 0, "fail": 0,
                "reward": None if reward is None else (int(reward) if reward in (0.0, 1.0) else round(reward, 3)),
                "fails": [], "early": early or "test exited before any case ran (likely build/setup failure)"}
    # aggregate failing cases by requirement_ref; keep up to CASE_CAP representative
    # cases per requirement for drill-down (rest summarized by count).
    CASE_CAP = 5
    byreq = {}
    for c in cases:
        if c["st"] == "fail":
            req = c["req"]
            if req not in byreq:
                byreq[req] = {"req": req, "type": c["ct"], "n": 0, "reason": clean_reason(c)[:140], "cases": []}
            byreq[req]["n"] += 1
            if len(byreq[req]["cases"]) < CASE_CAP:
                byreq[req]["cases"].append({
                    "id": c["cid"],
                    "intent": c.get("intent", "")[:170],
                    "scenario": c.get("scn", "")[:170],
                    "expected": c.get("exp", "")[:170],
                    "actual": c.get("act", "")[:170],
                    "reason": (c.get("fr", "") or "")[:170],
                })
    fails = sorted(byreq.values(), key=lambda x: -x["n"])
    return {"pass": succ, "total": total, "fail": fail,
            "reward": None if reward is None else (int(reward) if reward in (0.0, 1.0) else round(reward, 3)),
            "fails": fails}


tasks = sorted(d for d in os.listdir(TASKS_DIR)
               if d.startswith("theme_") and os.path.isdir(os.path.join(TASKS_DIR, d, "steps")))

out = {"models": [d for d, _ in MODELS], "tasks": {}}
index = {"models": [d for d, _ in MODELS], "tasks": []}
os.makedirs(OUT_TASKS, exist_ok=True)
for t in tasks:
    nrounds = len(glob.glob(os.path.join(TASKS_DIR, t, "steps", "round-*")))
    md = metadata(t)
    rec = {"task": t, "meta": md, "n_rounds": nrounds, "intent1": round_intent(t, 1),
           "rounds": [], "models": {}, "score": {}}
    for rnd in range(1, nrounds + 1):
        title, body = round_doc(t, rnd)
        rec["rounds"].append({"n": rnd, "title": title, "md": body})
    req_fail_models = defaultdict(set)   # requirement -> models that ever fail it
    req_reason_ex = {}                    # requirement -> a sample reason
    for disp, ms in MODELS:
        run = latest_run(t, ms)
        rounds = {}
        passed_rounds = 0
        blank = (disp, t) in BLANK_CELLS
        for rnd in range(1, nrounds + 1):
            pr = None if blank else (parse_round(run, rnd) if run else None)
            rounds[rnd] = pr
            if pr and pr["reward"] == 1:
                passed_rounds += 1
            if pr:
                for f in pr["fails"]:
                    req_fail_models[f["req"]].add(disp)
                    req_reason_ex.setdefault(f["req"], f["reason"])
        rec["models"][disp] = rounds
        rec["score"][disp] = None if blank else passed_rounds  # passed rounds out of nrounds; None = provider-outage blank
    # cross-model common-pain requirements (failed by >= half the models that ran)
    nmodels = len(MODELS)
    common = sorted(
        ([req, sorted(ms), req_reason_ex.get(req, "")] for req, ms in req_fail_models.items() if len(ms) >= nmodels // 2),
        key=lambda x: -len(x[1]))
    rec["common_fail"] = common[:12]
    # per-task file
    with open(os.path.join(OUT_TASKS, t + ".json"), "w") as f:
        json.dump(rec, f, separators=(",", ":"))
    # index entry (lightweight: scores + meta)
    index["tasks"].append({
        "task": t, "name": md["name"], "difficulty": md["difficulty"],
        "category": md["category"], "n_rounds": nrounds,
        "score": {d: (None if rec["score"][d] is None else (round(rec["score"][d] / nrounds, 3) if nrounds else 0)) for d in rec["score"]},
    })

with open(OUT_INDEX, "w") as f:
    json.dump(index, f, separators=(",", ":"))
# stats
cells = sum(nrounds for t in index["tasks"] for nrounds in [t["n_rounds"]]) * len(MODELS)
print(f"tasks={len(index['tasks'])} models={len(MODELS)}")
print(f"wrote {OUT_INDEX} + {len(index['tasks'])} per-task files under {OUT_TASKS}/")
import subprocess
print("per-task json sizes:", subprocess.getoutput(f"du -sh {OUT_TASKS} | cut -f1"))
