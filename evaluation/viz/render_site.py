#!/usr/bin/env python3
"""Render docs/tasks/<task>.html from the per-task JSON + (optional) analysis JSON.

Usage:
  python3 evaluation/viz/render_site.py            # render all tasks that have data
  python3 evaluation/viz/render_site.py <task>...  # render specific tasks
The page is a thin shell; site.js + the task JSON do the actual rendering in-browser.
Analysis prose (if docs/data/analysis/<task>.json exists) is inlined.
"""
import os, sys, json, html

DOCS = "/home/shenhaiyang/Source/EvoCodeBench/docs"
DATA = DOCS + "/data"
TASKS_JSON = DATA + "/tasks"
ANALYSIS = DATA + "/analysis"
OUT = DOCS + "/tasks"

PAGE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>%%TITLE%% — EvoCode-Bench</title>
<link rel="stylesheet" href="../assets/site.css">
</head><body>
<div class="wrap">
  <header class="top">
    <h1>%%NAME%%</h1>
    <span class="crumb"><a href="../index.html">← all tasks</a></span>
  </header>
  <p class="sub">
    <span class="pill %%DIFF%%">%%DIFF%%</span>
    <span class="pill">%%CATEGORY%%</span>
    <span class="pill">%%N%% rounds</span>
    <span class="pill">%%TASKID%%</span><br>
    %%INTENT%%
  </p>

  %%HEADLINE%%

  <h2>What the agent is asked, round by round</h2>
  <p class="sub" style="margin-top:0">Each round adds new requirements to the same workspace. Click a round to read the exact task the agent was given.</p>
  <div id="rounds"></div>

  <h2>Per-round test-case results</h2>
  <div class="keybox">
    <b>How to read the grid.</b> Every round ships an executable test suite. A cell like <b>43</b>/45&nbsp;<span class="xf">2✗</span>
    means the model passed <b>43 of the round's 45 test cases</b> and <b>2 failed</b>. The round earns a reward of
    <b>1 only if every case passes</b> — so a model can pass 43/45 and still score 0 for that round. The case counts
    show the partial progress the 0/1 round score hides. Cell <b>color = how many cases failed</b> (green = 0).
    A <b>build&nbsp;✗</b> cell means the model's code did not compile, so the tests could not run (a real 0 — the
    reference solution builds fine). <b>n/a</b> means that run never reached this round. <b>Click any cell</b> for details below.
  </div>
  <div id="heatmap"></div>
  <div class="legend">cases failed in the cell:
    <i style="background:#2fae5f"></i>0<i style="background:#8ec74e"></i>1-2<i style="background:#d6c34a"></i>3-5
    <i style="background:#e89a3c"></i>6-10<i style="background:#e3692f"></i>11-20<i style="background:#d23b34"></i>20+
    <i style="background:#3a2730"></i>code didn't build<i style="background:#22272f"></i>round not run (n/a)</div>
  <div id="detail"><span class="ph">Click a cell above to see the round's task and that model's failed requirements.</span></div>

  %%DIFFICULTY%%

  <h2>Per-model failures (whole task)</h2>
  <p class="sub" style="margin-top:0">Click a model to expand every requirement it failed across all rounds, with a representative reason from the verifier.</p>
  <div id="breakdown"></div>

  %%GAP%%

  <p class="foot">Test-case data extracted from the verifier <code>CASE_RESULT</code> logs of each model's run.
    Reasons are the verifier's own <code>failure_reason</code> (back-filled from expected/actual when terse).</p>
</div>

<script src="../assets/site.js"></script>
<script>
fetch("../data/tasks/%%TASKID%%.json").then(function(r){return r.json();}).then(function(T){
  window.__MODELS__ = Object.keys(T.models);
  var detail = document.getElementById("detail");
  EvoViz.renderRounds(document.getElementById("rounds"), T);
  EvoViz.renderHeatmap(document.getElementById("heatmap"), T, function(model, round){
    EvoViz.renderDetail(detail, T, model, round);
    detail.scrollIntoView({behavior:"smooth", block:"nearest"});
  });
  EvoViz.renderBreakdown(document.getElementById("breakdown"), T);
});
</script>
</body></html>
"""


def block(kind, title, htmltext):
    if not htmltext:
        return ""
    return f"<h2>{title}</h2>\n  <div class='analysis'>{htmltext}</div>"


def render(task):
    tj = os.path.join(TASKS_JSON, task + ".json")
    if not os.path.exists(tj):
        print("  skip (no data):", task); return False
    T = json.load(open(tj))
    md = T["meta"]
    A = {}
    aj = os.path.join(ANALYSIS, task + ".json")
    if os.path.exists(aj):
        A = json.load(open(aj))
    headline = ""
    if A.get("headline"):
        headline = f"<div class='analysis'><p style='margin:0'><strong>{html.escape(A['headline'])}</strong></p></div>"
    repl = {
        "%%TITLE%%": html.escape(md.get("name", task)),
        "%%NAME%%": html.escape(md.get("name", task)),
        "%%DIFF%%": html.escape(md.get("difficulty", "") or "?"),
        "%%CATEGORY%%": html.escape((md.get("category", "") or "").replace("-", " ")),
        "%%N%%": str(T["n_rounds"]),
        "%%TASKID%%": html.escape(task),
        "%%INTENT%%": html.escape(T.get("intent1", "")),
        "%%HEADLINE%%": headline,
        "%%DIFFICULTY%%": block("difficulty", "Difficulty analysis", A.get("difficulty", "")),
        "%%GAP%%": block("gap", "Performance gap", A.get("gap", "")),
    }
    page = PAGE
    for k, v in repl.items():
        page = page.replace(k, v)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, task + ".html"), "w") as f:
        f.write(page)
    print("  rendered:", task, "(analysis:", "yes" if A else "no", ")")
    return True


if __name__ == "__main__":
    targets = sys.argv[1:]
    if not targets:
        targets = [f[:-5] for f in sorted(os.listdir(TASKS_JSON)) if f.endswith(".json")]
    n = sum(render(t) for t in targets)
    print(f"rendered {n} pages -> {OUT}/")
