/* EvoCode-Bench results site — shared rendering. Pages load their own data JSON. */
(function (G) {
  "use strict";

  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
    return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]; }); }

  // ---- tiny markdown -> HTML (headings, bold, inline code, fenced code, lists, paragraphs) ----
  function md2html(md) {
    var lines = String(md || "").replace(/\r/g, "").split("\n");
    var out = [], i = 0, inCode = false, code = [], inList = false;
    function inline(t) {
      return esc(t)
        .replace(/`([^`]+)`/g, "<code>$1</code>")
        .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    }
    function closeList() { if (inList) { out.push("</ul>"); inList = false; } }
    for (; i < lines.length; i++) {
      var ln = lines[i];
      if (/^```/.test(ln)) {
        if (inCode) { out.push("<pre><code>" + esc(code.join("\n")) + "</code></pre>"); code = []; inCode = false; }
        else { closeList(); inCode = true; }
        continue;
      }
      if (inCode) { code.push(ln); continue; }
      var h = ln.match(/^(#{1,6})\s+(.*)$/);
      if (h) { closeList(); out.push("<h" + (h[1].length + 2) + ">" + inline(h[2]) + "</h" + (h[1].length + 2) + ">"); continue; }
      if (/^\s*[-*]\s+/.test(ln)) { if (!inList) { out.push("<ul>"); inList = true; } out.push("<li>" + inline(ln.replace(/^\s*[-*]\s+/, "")) + "</li>"); continue; }
      if (/^\s*$/.test(ln)) { closeList(); continue; }
      closeList(); out.push("<p>" + inline(ln) + "</p>");
    }
    if (inCode) out.push("<pre><code>" + esc(code.join("\n")) + "</code></pre>");
    closeList();
    return out.join("\n");
  }

  // ---- color by FAILED-case count (bucketed). null=n/a grey, early-exit=dark slate ----
  function failColor(cell) {
    if (!cell) return ["#22272f", "#7d8694"];               // truly absent (sandbox never ran)
    if (cell.early) return ["#3a2730", "#e7a6a0"];          // build/setup early-exit (real 0, no cases)
    var f = cell.fail, bg, fg = "#0c0e12";
    if (f === 0) bg = "#2fae5f";
    else if (f <= 2) bg = "#8ec74e";
    else if (f <= 5) bg = "#d6c34a";
    else if (f <= 10) bg = "#e89a3c";
    else if (f <= 20) bg = "#e3692f";
    else { bg = "#d23b34"; fg = "#fff"; }
    return [bg, fg];
  }

  function orderedModels(T) {
    return window.__MODELS__.slice().sort(function (a, b) { return (T.score[b] || 0) - (T.score[a] || 0); });
  }

  // ---- heatmap: rows = rounds, cols = models. Cell = passed/total, color = fails. Click pins detail. ----
  function renderHeatmap(host, T, onPick) {
    var models = orderedModels(T), n = T.n_rounds;
    var h = "<table class='hm-t'><thead><tr><th class='rh'>round</th>";
    models.forEach(function (m) { h += "<th>" + esc(m) + "</th>"; });
    h += "</tr></thead><tbody>";
    for (var r = 1; r <= n; r++) {
      h += "<tr><td class='rh' title='click a cell to see details'>round " + r + "</td>";
      models.forEach(function (m) {
        var c = T.models[m][r], col = failColor(c);
        if (!c) { h += "<td class='cell nodata' style='background:" + col[0] + ";color:" + col[1] + "'>n/a</td>"; return; }
        if (c.early) {
          h += "<td class='cell earlyx' style='background:" + col[0] + ";color:" + col[1] + "' data-m='" + esc(m) + "' data-r='" + r + "'>build&nbsp;✗</td>";
          return;
        }
        var mark = c.reward === 1 ? " <span class='okmark'>✓</span>" : (c.fail ? " <span class='xf'>" + c.fail + "✗</span>" : "");
        h += "<td class='cell' style='background:" + col[0] + ";color:" + col[1] + "' data-m='" + esc(m) + "' data-r='" + r + "'>"
          + "<b>" + c.pass + "</b>/" + c.total + mark + "</td>";
      });
      h += "</tr>";
    }
    h += "<tr class='summ'><td class='rh'>rounds fully passed</td>";
    models.forEach(function (m) {
      var builds = 0, absent = 0;
      for (var r = 1; r <= n; r++) { var c = T.models[m][r]; if (!c) absent++; else if (c.early) builds++; }
      var note = "";
      if (builds) note += "<span class='s2'>" + builds + " build✗</span>";
      if (absent) note += "<span class='s2'>" + absent + " n/a</span>";
      h += "<td>" + (T.score[m] || 0) + " / " + n + note + "</td>";
    });
    h += "</tr></tbody></table>";
    host.innerHTML = "<div class='hm'>" + h + "</div>";
    // interactions
    host.querySelectorAll("td.cell[data-m]").forEach(function (td) {
      td.addEventListener("click", function () {
        host.querySelectorAll("td.cell.sel").forEach(function (e) { e.classList.remove("sel"); });
        td.classList.add("sel");
        onPick(td.dataset.m, +td.dataset.r);
      });
    });
  }

  // a failing-requirement row that expands to the individual cases (intent/scenario/expected/actual)
  function reqBlock(f) {
    var head = "<summary><span class='reqname'>" + esc(f.req) + "</span> <span class='reqcnt'>"
      + f.n + " case" + (f.n > 1 ? "s" : "") + " · " + esc(f.type) + " · " + esc(f.reason) + "</span></summary>";
    var cs = (f.cases || []).map(function (c) {
      var rows = "";
      if (c.intent) rows += "<div class='cf'><span>intent</span>" + esc(c.intent) + "</div>";
      if (c.scenario) rows += "<div class='cf'><span>scenario</span>" + esc(c.scenario) + "</div>";
      if (c.expected) rows += "<div class='cf'><span>expected</span>" + esc(c.expected) + "</div>";
      if (c.actual) rows += "<div class='cf'><span>actual</span><span class='bad'>" + esc(c.actual || "(empty)") + "</span></div>";
      if (c.reason && c.reason !== c.actual) rows += "<div class='cf'><span>reason</span>" + esc(c.reason) + "</div>";
      return "<div class='case'><div class='cid'>" + esc(c.id) + "</div>" + rows + "</div>";
    }).join("");
    var more = f.n > (f.cases || []).length ? "<div class='rs morec'>+ " + (f.n - f.cases.length) + " more failing case(s) of this requirement</div>" : "";
    return "<details class='req'>" + head + "<div class='cases'>" + cs + more + "</div></details>";
  }
  function renderDetail(host, T, model, round) {
    var c = T.models[model][round];
    var rd = (T.rounds || []).find(function (x) { return x.n === round; }) || {};
    var h = "<div class='dt-head'><span class='dt-r'>Round " + round + "</span> · <b>" + esc(model) + "</b></div>";
    if (!c) {
      h += "<p class='rs'>This model's run never reached round " + round + " — no result was recorded (the sandbox/chain did not run this round).</p>";
    } else if (c.early) {
      h += "<p class='dt-score'><b>Round reward 0 — the model's code did not build.</b> "
        + "The test script exited before any test case could run, because the project failed to compile/start.</p>"
        + "<div class='dt-fails'><div class='dt-lbl'>Verifier output:</div>"
        + "<div class='reqrow'><div class='reason'>" + esc(c.early) + "</div>"
        + "<div class='rs' style='margin-top:4px;font-size:11px'>(The reference oracle solution builds and passes this round, so this is the model's code, not a task defect.)</div></div></div>";
    } else {
      var pct = Math.round(c.pass / c.total * 100);
      h += "<p class='dt-score'><b>" + c.pass + " of " + c.total + "</b> test cases passed (" + pct + "%) · "
        + (c.fail ? "<span class='xf'>" + c.fail + " failed</span>" : "all passed")
        + " · round reward <b>" + (c.reward === 1 ? "1 (all requirements met)" : "0 (some cases failed)") + "</b></p>";
      if (c.fails && c.fails.length) {
        h += "<div class='dt-fails'><div class='dt-lbl'>Failed requirements this round (click to expand the cases):</div>";
        c.fails.forEach(function (f) { h += reqBlock(f); });
        h += "</div>";
      }
    }
    h += "<details class='roundtask'><summary>What round " + round + " asked the agent to do"
      + (rd.title ? " — " + esc(rd.title) : "") + "</summary><div class='md'>" + md2html(rd.md) + "</div></details>";
    host.innerHTML = h;
  }

  // ---- per-model breakdown (collapsible), plain-language lead ----
  function renderBreakdown(host, T) {
    var models = orderedModels(T), n = T.n_rounds, out = "";
    models.forEach(function (m) {
      var agg = {}, totPass = 0, totCase = 0, seen = 0, builds = 0, absent = 0;
      for (var r = 1; r <= n; r++) {
        var c = T.models[m][r];
        if (!c) { absent++; continue; }
        if (c.early) { builds++; continue; }
        seen++; totPass += c.pass; totCase += c.total;
        (c.fails || []).forEach(function (f) {
          if (!agg[f.req]) agg[f.req] = { req: f.req, n: 0, reason: f.reason, type: f.type, cases: [] };
          agg[f.req].n += f.n;
          (f.cases || []).forEach(function (cc) { if (agg[f.req].cases.length < 8) agg[f.req].cases.push(cc); });
        });
      }
      var reqs = Object.values(agg).sort(function (a, b) { return b.n - a.n; });
      var pct = totCase ? Math.round(totPass / totCase * 100) : 0;
      var notes = [];
      if (builds) notes.push("<span class='xf'>" + builds + " round" + (builds > 1 ? "s" : "") + " failed to build</span>");
      if (absent) notes.push("<span class='rs'>" + absent + " round" + (absent > 1 ? "s" : "") + " not run</span>");
      var lead = "passed <b>" + (T.score[m] || 0) + "/" + n + "</b> rounds fully"
        + (totCase ? " · <b>" + totPass + "/" + totCase + "</b> cases (" + pct + "%) on rounds that built" : "")
        + (notes.length ? " · " + notes.join(" · ") : "");
      var body = reqs.length
        ? reqs.map(reqBlock).join("")
        : "<div class='reqrow rs'>" + (builds ? "Code did not build on the rounds it reached." : "No failing cases — passed every test it reached.") + "</div>";
      out += "<details class='mdl'><summary><span>" + esc(m) + "</span><span class='scorebadge'>" + lead + "</span></summary><div>" + body + "</div></details>";
    });
    host.innerHTML = out;
  }

  // ---- rounds section: each round's task instruction, collapsible ----
  function renderRounds(host, T) {
    var out = "";
    (T.rounds || []).forEach(function (rd) {
      out += "<details class='roundtask'><summary><span class='rnum'>Round " + rd.n + "</span> "
        + esc(rd.title || "") + "</summary><div class='md'>" + md2html(rd.md) + "</div></details>";
    });
    host.innerHTML = out;
  }

  G.EvoViz = { renderHeatmap: renderHeatmap, renderDetail: renderDetail, renderBreakdown: renderBreakdown,
    renderRounds: renderRounds, md2html: md2html, esc: esc };
})(window);
