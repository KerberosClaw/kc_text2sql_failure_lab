/* Failure Lab gallery — vanilla JS, no build step, bilingual (EN / 繁中).
   Data comes from web/data/*.json produced by `failure_lab.runner --export-web`. */
(function () {
  "use strict";
  var app = document.getElementById("app");
  var CASES = null, REPORTS = [];
  var LANG = "en";
  try { LANG = localStorage.getItem("flab-lang") || "en"; } catch (e) {}

  var I18N = {
    en: {
      tagline: "Executable ≠ Correct — the SQL runs, the rows come back, the answer is still wrong.",
      nav_cases: "Cases", nav_score: "Scoreboard", toggle: "繁體中文",
      question: "Question (as given to the model)",
      clarification: "Binding clarification",
      trap: "The hidden trap",
      naive: "Naive SQL — plausible, executable, wrong",
      naive_result: "What the naive SQL returns",
      oracle_result: "What the answer should be",
      diff_hint: "Highlighted rows exist on one side only. Grading mode: ",
      oracle_sql: "Oracle SQL (one of many correct shapes — grading compares results, not strings)",
      scoreboard: "Model scoreboard",
      score_hint: "mock-naive and mock-oracle are the grader’s entrance exam: if they aren’t all-red and all-green, the grader itself is broken.",
      score: "score", back: "← all cases", pass: "✓ pass", fail: "✗ ",
      no_rows: "(no rows — silence that looks like an answer)",
      footer: "Every number on this page is produced live from demo.db by the runner — regenerate with make eval.",
      loading_fail: "Failed to load data. Serve over HTTP: "
    },
    zh: {
      tagline: "跑得動，不等於是對的 — SQL 執行了、資料回來了，答案還是錯的。",
      nav_cases: "案例", nav_score: "成績單", toggle: "English",
      question: "題目（原樣交給模型）",
      clarification: "具約束力的消歧說明",
      trap: "隱藏陷阱",
      naive: "天真 SQL — 看似合理、可執行、錯",
      naive_result: "天真 SQL 回傳的結果",
      oracle_result: "正確答案應該是",
      diff_hint: "高亮列僅存在於其中一側。判分模式：",
      oracle_sql: "Oracle SQL（眾多正確寫法之一 — 判分比結果、不比字串）",
      scoreboard: "模型成績單",
      score_hint: "mock-naive 與 mock-oracle 是判分器的入學考：如果不是一列全紅、一列全綠，壞掉的是判分器自己。",
      score: "得分", back: "← 全部案例", pass: "✓ 通過", fail: "✗ ",
      no_rows: "（無資料列 — 一種看起來像答案的沉默）",
      footer: "本頁每個數字都由 runner 從 demo.db 即時產生 — 用 make eval 重新生成。",
      loading_fail: "資料載入失敗。請以 HTTP 服務本目錄："
    }
  };

  function t(key) { return I18N[LANG][key]; }
  function cf(c, field) {
    if (LANG === "zh" && c.zh && c.zh[field]) return c.zh[field];
    return c[field];
  }

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function rowKey(r) { return JSON.stringify(r); }

  function resultTable(res, other) {
    var otherKeys = {};
    (other.rows || []).forEach(function (r) { otherKeys[rowKey(r)] = 1; });
    var html = "<table><thead><tr>";
    res.columns.forEach(function (c) { html += "<th>" + esc(c) + "</th>"; });
    html += "</tr></thead><tbody>";
    if (!res.rows.length) {
      html += '<tr class="diff"><td colspan="' + (res.columns.length || 1) +
              '"><em>' + esc(t("no_rows")) + "</em></td></tr>";
    }
    res.rows.forEach(function (r) {
      var cls = otherKeys[rowKey(r)] ? "" : ' class="diff"';
      html += "<tr" + cls + ">";
      r.forEach(function (v) { html += "<td>" + esc(v === null ? "NULL" : v) + "</td>"; });
      html += "</tr>";
    });
    return html + "</tbody></table>";
  }

  function viewGallery() {
    var html = '<div class="grid">';
    CASES.forEach(function (c) {
      var teaser = cf(c, "hidden_trap").split(LANG === "zh" ? "。" : ". ")[0];
      html += '<a class="card" href="#/case/' + esc(c.id) + '">' +
        '<span class="badge">' + esc(c.category) + "</span>" +
        "<h3>" + esc(cf(c, "title")) + "</h3>" +
        "<p>" + esc(teaser) + (LANG === "zh" ? "。" : ".") + "</p></a>";
    });
    html += "</div>";
    app.innerHTML = html;
  }

  function viewCase(id) {
    var c = CASES.find(function (x) { return x.id === id; });
    if (!c) { app.innerHTML = "<p>Unknown case.</p>"; return; }
    app.innerHTML =
      '<a class="back" href="#/">' + esc(t("back")) + "</a>" +
      '<div class="case"><span class="badge">' + esc(c.category) + "</span>" +
      "<h2>" + esc(cf(c, "title")) + "</h2>" +
      '<div class="panel"><h4>' + esc(t("question")) + "</h4><p>" + esc(cf(c, "question")) + "</p></div>" +
      '<div class="panel clar"><h4>' + esc(t("clarification")) + "</h4><p>" + esc(cf(c, "ambiguity_resolution")) + "</p></div>" +
      '<div class="panel trap"><h4>' + esc(t("trap")) + "</h4><p>" + esc(cf(c, "hidden_trap")) + "</p></div>" +
      '<div class="panel"><h4>' + esc(t("naive")) + "</h4><pre>" + esc(c.naive_sql) + "</pre></div>" +
      '<div class="results">' +
      '<div class="result naive"><h4>' + esc(t("naive_result")) + "</h4>" + resultTable(c.naive_result, c.oracle_result) + "</div>" +
      '<div class="result oracle"><h4>' + esc(t("oracle_result")) + "</h4>" + resultTable(c.oracle_result, c.naive_result) + "</div>" +
      "</div>" +
      '<p class="hint">' + esc(t("diff_hint")) + "<code>" + esc(c.grading) + "</code></p>" +
      '<div class="panel"><h4>' + esc(t("oracle_sql")) + "</h4><pre>" + esc(c.oracle_sql) + "</pre></div></div>";
  }

  function viewScoreboard() {
    var order = ["mock-naive", "gpt-5.4-nano", "gpt-5.5", "mock-oracle"];
    var reports = REPORTS.slice().sort(function (a, b) {
      var ia = order.indexOf(a.model), ib = order.indexOf(b.model);
      return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
    });
    var html = "<h2>" + esc(t("scoreboard")) + "</h2>" +
      '<p class="hint">' + esc(t("score_hint")) + "</p>" +
      '<table class="score"><thead><tr><th class="case-name">case</th>';
    reports.forEach(function (r) { html += "<th>" + esc(r.model) + "</th>"; });
    html += "</tr></thead><tbody>";
    CASES.forEach(function (c) {
      html += '<tr><td class="case-name"><a href="#/case/' + esc(c.id) + '">' + esc(c.id) + "</a></td>";
      reports.forEach(function (r) {
        var entry = r.cases.find(function (x) { return x.id === c.id; });
        var ok = entry && entry.status === "pass";
        html += '<td class="' + (ok ? "cell-pass" : "cell-fail") + '">' +
                (ok ? esc(t("pass")) : esc(t("fail")) + (entry ? entry.status : "n/a")) + "</td>";
      });
      html += "</tr>";
    });
    html += '</tbody><tfoot><tr><td class="case-name">' + esc(t("score")) + "</td>";
    reports.forEach(function (r) {
      html += "<td>" + r.summary.pass + "/" + r.summary.total + "</td>";
    });
    html += "</tr></tfoot></table>";
    app.innerHTML = html;
  }

  function applyChrome() {
    document.getElementById("tagline").textContent = t("tagline");
    document.querySelector('[data-nav="gallery"]').textContent = t("nav_cases");
    document.querySelector('[data-nav="scoreboard"]').textContent = t("nav_score");
    document.getElementById("lang-toggle").textContent = t("toggle");
    document.getElementById("footer-note").textContent = t("footer");
    document.documentElement.lang = LANG === "zh" ? "zh-Hant" : "en";
  }

  function route() {
    var h = location.hash || "#/";
    document.querySelectorAll("nav a[data-nav]").forEach(function (a) {
      a.classList.toggle("active",
        (a.dataset.nav === "scoreboard") === (h === "#/scoreboard"));
    });
    applyChrome();
    if (h === "#/scoreboard") viewScoreboard();
    else if (h.indexOf("#/case/") === 0) viewCase(h.slice(7));
    else viewGallery();
    window.scrollTo(0, 0);
  }

  document.getElementById("lang-toggle").addEventListener("click", function (e) {
    e.preventDefault();
    LANG = LANG === "en" ? "zh" : "en";
    try { localStorage.setItem("flab-lang", LANG); } catch (err) {}
    route();
  });

  fetch("data/cases.json").then(function (r) { return r.json(); })
    .then(function (cases) {
      CASES = cases;
      return fetch("data/reports_index.json").then(function (r) { return r.json(); });
    })
    .then(function (index) {
      return Promise.all(index.map(function (name) {
        return fetch("data/reports/" + name).then(function (r) { return r.json(); });
      }));
    })
    .then(function (reports) {
      REPORTS = reports;
      window.addEventListener("hashchange", route);
      route();
    })
    .catch(function (e) {
      app.innerHTML = '<p class="loading">' + esc(t("loading_fail")) +
        "<code>make gallery</code> (" + esc(e) + ")</p>";
    });
})();
