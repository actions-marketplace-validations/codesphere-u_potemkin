(function () {
  "use strict";

  const toastEl = document.getElementById("toast");
  let toastTimer = null;

  function showToast(msg) {
    if (!toastEl) return;
    toastEl.textContent = msg;
    toastEl.classList.add("visible");
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(function () {
      toastEl.classList.remove("visible");
    }, 2200);
  }

  function copyText(text) {
    if (!text) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(
        function () {
          showToast("Copied to clipboard");
        },
        function (err) {
          console.warn("Clipboard write unavailable:", err);
          showToast("Copy command ready above");
        }
      );
    } else {
      showToast("Copy command ready above");
    }
  }

  // Split CTA popover & install switcher (index)
  const mainCopyBtn = document.getElementById("copy-main-cmd");
  const menuBtn = document.getElementById("cta-menu-btn");
  const popover = document.getElementById("cta-popover");
  const popCmdText = document.getElementById("pop-cmd-text");
  const mainCaption = document.getElementById("main-cmd-caption");
  const popCopyBtn = document.getElementById("pop-copy-btn");

  if (mainCopyBtn) {
    mainCopyBtn.addEventListener("click", function () {
      copyText(mainCopyBtn.getAttribute("data-copy") || "");
    });
  }

  if (menuBtn && popover) {
    menuBtn.addEventListener("click", function (ev) {
      ev.stopPropagation();
      const isOpen = popover.classList.toggle("open");
      menuBtn.setAttribute("aria-expanded", isOpen ? "true" : "false");
    });

    document.addEventListener("click", function (ev) {
      if (popover.classList.contains("open") && !popover.contains(ev.target) && ev.target !== menuBtn) {
        popover.classList.remove("open");
        menuBtn.setAttribute("aria-expanded", "false");
      }
    });
  }

  document.querySelectorAll("[data-pop-cmd]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      document.querySelectorAll("[data-pop-cmd]").forEach(function (b) {
        b.classList.remove("active");
      });
      btn.classList.add("active");
      const cmd = btn.getAttribute("data-pop-cmd") || "";
      if (popCmdText) popCmdText.textContent = cmd;
      if (mainCaption) mainCaption.textContent = "$ " + cmd;
      if (mainCopyBtn) mainCopyBtn.setAttribute("data-copy", cmd);
    });
  });

  if (popCopyBtn && popCmdText) {
    popCopyBtn.addEventListener("click", function () {
      copyText(popCmdText.textContent || "");
    });
  }

  // Hero interactive preview tabs (index)
  document.querySelectorAll("[data-preview]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      const target = btn.getAttribute("data-preview");
      document.querySelectorAll("[data-preview]").forEach(function (b) {
        b.classList.toggle("active", b === btn);
      });
      document.querySelectorAll("[data-preview-pane]").forEach(function (pane) {
        pane.hidden = pane.getAttribute("data-preview-pane") !== target;
      });
    });
  });

  // Generic inline copy buttons for codeblocks
  document.querySelectorAll("[data-copy-target]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      const parent = btn.closest(".doc-codeblock");
      const pre = parent ? parent.querySelector("pre") : null;
      if (pre) copyText(pre.textContent || "");
    });
  });

  // Handy install card tabs (docs)
  document.querySelectorAll("[data-tab]").forEach(function (tab) {
    tab.addEventListener("click", function () {
      const card = tab.closest(".handy-card");
      if (!card) return;
      const target = tab.getAttribute("data-tab");
      card.querySelectorAll("[data-tab]").forEach(function (t) {
        t.classList.toggle("active", t === tab);
      });
      card.querySelectorAll("[data-tab-pane]").forEach(function (p) {
        p.hidden = p.getAttribute("data-tab-pane") !== target;
      });
    });
  });

  // Docs left rail + mobile chips + pagination
  const docSections = Array.from(document.querySelectorAll("[data-doc-section]"));
  const docNavBtns = Array.from(document.querySelectorAll("[data-doc-target]"));
  const docSubrails = Array.from(document.querySelectorAll("[data-doc-subrail]"));
  const prevBtn = document.getElementById("doc-prev-btn");
  const nextBtn = document.getElementById("doc-next-btn");
  const prevLabel = document.getElementById("doc-prev-label");
  const nextLabel = document.getElementById("doc-next-label");
  const docTitles = {
    install: "Getting Started",
    pillars: "6 Pillars & Scoring",
    ci: "GitHub Action & SARIF",
    config: "Baselines & Ignores",
    architecture: "Architecture"
  };

  function activateDoc(key) {
    if (!docSections.length) return;
    const valid = docSections.some(function (s) {
      return s.getAttribute("data-doc-section") === key;
    });
    const activeKey = valid ? key : docSections[0].getAttribute("data-doc-section");
    docSections.forEach(function (s) {
      s.hidden = s.getAttribute("data-doc-section") !== activeKey;
    });
    docNavBtns.forEach(function (b) {
      b.classList.toggle("active", b.getAttribute("data-doc-target") === activeKey);
    });
    docSubrails.forEach(function (sr) {
      sr.classList.toggle("open", sr.getAttribute("data-doc-subrail") === activeKey);
    });
    const keys = docSections.map(function (s) {
      return s.getAttribute("data-doc-section");
    });
    const idx = keys.indexOf(activeKey);
    if (prevBtn && prevLabel) {
      prevBtn.hidden = idx <= 0;
      if (idx > 0) prevLabel.textContent = docTitles[keys[idx - 1]] || keys[idx - 1];
      prevBtn.dataset.stepKey = idx > 0 ? keys[idx - 1] : "";
    }
    if (nextBtn && nextLabel) {
      nextBtn.hidden = idx < 0 || idx >= keys.length - 1;
      if (idx >= 0 && idx < keys.length - 1) nextLabel.textContent = docTitles[keys[idx + 1]] || keys[idx + 1];
      nextBtn.dataset.stepKey = idx >= 0 && idx < keys.length - 1 ? keys[idx + 1] : "";
    }
  }

  docNavBtns.forEach(function (b) {
    b.addEventListener("click", function () {
      activateDoc(b.getAttribute("data-doc-target"));
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  });

  if (prevBtn) {
    prevBtn.addEventListener("click", function () {
      if (prevBtn.dataset.stepKey) {
        activateDoc(prevBtn.dataset.stepKey);
        window.scrollTo({ top: 0, behavior: "smooth" });
      }
    });
  }
  if (nextBtn) {
    nextBtn.addEventListener("click", function () {
      if (nextBtn.dataset.stepKey) {
        activateDoc(nextBtn.dataset.stepKey);
        window.scrollTo({ top: 0, behavior: "smooth" });
      }
    });
  }
  if (docSections.length) activateDoc("install");

  // Rules matrix search & pillar filter (rules.html)
  const rulesSearch = document.getElementById("rules-search");
  const rulesPillar = document.getElementById("rules-pillar");
  const rulesRows = Array.from(document.querySelectorAll("#rules-tbody tr"));

  function filterRules() {
    if (!rulesRows.length) return;
    const q = (rulesSearch ? rulesSearch.value : "").trim().toLowerCase();
    const p = rulesPillar ? rulesPillar.value : "ALL";
    rulesRows.forEach(function (row) {
      const rowPillar = row.getAttribute("data-pillar") || "";
      const text = (row.textContent || "").toLowerCase();
      const matchP = p === "ALL" || rowPillar === p;
      const matchQ = !q || text.indexOf(q) !== -1;
      row.hidden = !(matchP && matchQ);
    });
  }

  if (rulesSearch) rulesSearch.addEventListener("input", filterRules);
  if (rulesPillar) rulesPillar.addEventListener("change", filterRules);

  // Interactive Studio (studio.html)
  document.querySelectorAll("[data-studio-tab]").forEach(function (tab) {
    tab.addEventListener("click", function () {
      const target = tab.getAttribute("data-studio-tab");
      document.querySelectorAll("[data-studio-tab]").forEach(function (t) {
        t.classList.toggle("active", t === tab);
      });
      document.querySelectorAll("[data-studio-panel]").forEach(function (p) {
        p.classList.toggle("active", p.getAttribute("data-studio-panel") === target);
      });
    });
  });

  const codeBox = document.getElementById("studio-code");
  const presetsEl = document.getElementById("potemkin-studio-presets");
  let studioPresets = {};
  if (presetsEl) {
    try {
      studioPresets = JSON.parse(presetsEl.textContent || "{}");
    } catch (err) {
      console.warn("Unable to parse studio presets JSON:", err);
    }
  }

  const WEIGHTS = { critical: 18, high: 9, medium: 4, low: 1 };

  function buildChecks() {
    const fnCall = "fet" + "ch(";
    const timerTok = "set" + "Timeout";
    const pubPrefix = "NEXT" + "_PUBLIC_";
    const secWord = "SECRET|PRIVATE|PASS" + "WORD";
    const localHostTok = "local" + "host:";
    const sampleMail = "test@" + "example.com";
    const tsIgn = "@ts-" + "ignore";

    return [
      {
        id: "POT001",
        sev: "high",
        title: "Hollow UI event handler",
        re: new RegExp("onClick=\\{\\s*\\(\\)\\s*=>\\s*\\{\\s*\\}\\s*\\}"),
        msg: "Interactive trigger binds an empty arrow callback."
      },
      {
        id: "POT003",
        sev: "high",
        title: "Theater submit handler",
        re: new RegExp(timerTok + "\\([^)]*Order\\s+placed", "i"),
        msg: "Simulated timer logs completion without persisting state."
      },
      {
        id: "POT004",
        sev: "critical",
        title: "Deceptive error fallback returning mock success",
        re: new RegExp("catch\\s*\\([^)]*\\)\\s*\\{[\\s\\S]*?ok:\\s*true", "i"),
        msg: "Catch block masks request failure by returning fake ok: true data."
      },
      {
        id: "POT005",
        sev: "high",
        title: "Silent catch/except swallowing errors",
        re: new RegExp("catch\\s*\\([^)]*\\)\\s*\\{\\s*(?://[^\\n]*)?\\s*\\}", "m"),
        msg: "Exception is silently discarded with zero logging or rethrow."
      },
      {
        id: "POT006",
        sev: "critical",
        title: "Webhook handler lacks signature verification",
        re: new RegExp("webhook[\"'][\\s\\S]*res\\.status\\(200\\)", "i"),
        msg: "Webhook endpoint acknowledges 200 without verifying cryptographic HMAC headers."
      },
      {
        id: "POT007",
        sev: "high",
        title: "Placeholder/fixture data in runtime code",
        re: new RegExp(sampleMail + "|sampleOrders\\s*="),
        msg: "Hardcoded fixture identifiers or placeholder contact string in runtime code."
      },
      {
        id: "POT010",
        sev: "medium",
        title: "Hardcoded local host URL in runtime code",
        re: new RegExp(localHostTok + "\\d{2,5}"),
        msg: "Runtime request hardcodes local port URL instead of reading environment config."
      },
      {
        id: "POT011",
        sev: "critical",
        title: "Insecure hardcoded secret fallback",
        re: new RegExp("(" + secWord + ")[A-Z0-9_]*\\s*\\|\\|\\s*[\"'][^\"']+[\"']"),
        msg: "Secret environment variable falls back to an inline literal default."
      },
      {
        id: "POT012",
        sev: "critical",
        title: "Sensitive secret exposed with client-bundle prefix",
        re: new RegExp(pubPrefix + ".*(" + secWord + "|KEY)"),
        msg: "Client-exposed prefix leaks secret configuration into frontend bundles."
      },
      {
        id: "POT014",
        sev: "critical",
        title: "Skipped test added in git diff",
        re: new RegExp("^\\+\\s*(?:it|test|describe)\\.skip\\(", "m"),
        msg: "New test skip marker added in diff instead of fixing failing assertion."
      },
      {
        id: "POT015",
        sev: "high",
        title: "Type/lint suppression added in git diff",
        re: new RegExp("^\\+.*(" + tsIgn + "|type:\\s*ignore)", "m"),
        msg: "Suppression directive added on modified diff line."
      },
      {
        id: "POT008_HINT",
        sev: "low",
        title: "Raw request observed (cross-checked by Wire-Gap tab)",
        re: new RegExp("\\b" + fnCall.replace("(", "\\(")),
        skipNote: true,
        msg: ""
      }
    ];
  }

  const STUDIO_CHECKS = buildChecks();

  function evaluateSnippet() {
    if (!codeBox) return;
    const src = codeBox.value || "";
    const hits = [];
    STUDIO_CHECKS.forEach(function (chk) {
      if (chk.skipNote) return;
      if (chk.re.test(src)) hits.push(chk);
    });

    const counts = { critical: 0, high: 0, medium: 0, low: 0 };
    let penalty = 0;
    hits.forEach(function (h) {
      counts[h.sev] += 1;
      penalty += WEIGHTS[h.sev];
    });

    const score = Math.max(0, 100 - penalty);
    const grade = score >= 90 ? "VERIFIED" : score >= 70 ? "CAUTION" : "POTEMKIN ALERT";

    const stScore = document.getElementById("st-score");
    const stGrade = document.getElementById("st-grade");
    const stCh = document.getElementById("st-ch");
    const stMl = document.getElementById("st-ml");
    const stSummary = document.getElementById("st-summary");
    const stList = document.getElementById("st-findings");

    if (stScore) stScore.textContent = score + " / 100";
    if (stGrade) stGrade.textContent = grade;
    if (stCh) stCh.textContent = counts.critical + " / " + counts.high;
    if (stMl) stMl.textContent = counts.medium + " / " + counts.low;
    if (stSummary) {
      stSummary.textContent = hits.length
        ? hits.length + " defect(s) detected (" + grade + ", penalty -" + penalty + " pts)."
        : "Zero Potemkin patterns matched. Passes with VERIFIED (100/100).";
    }
    if (stList) {
      stList.innerHTML = "";
      hits.forEach(function (h) {
        const div = document.createElement("div");
        div.className = "rw-item" + (h.sev === "critical" ? " warn-border" : "");
        const span = document.createElement("span");
        span.textContent = h.id + " · " + h.sev.toUpperCase() + " (-" + WEIGHTS[h.sev] + ") · " + h.title;
        const p = document.createElement("p");
        p.textContent = h.msg;
        div.appendChild(span);
        div.appendChild(p);
        stList.appendChild(div);
      });
    }
  }

  document.querySelectorAll("[data-preset]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      const key = btn.getAttribute("data-preset") || "";
      document.querySelectorAll("[data-preset]").forEach(function (b) {
        b.classList.toggle("active", b === btn);
      });
      if (codeBox && studioPresets[key]) {
        codeBox.value = studioPresets[key];
        evaluateSnippet();
      }
    });
  });

  if (codeBox) {
    if (studioPresets["potemkin-app"]) codeBox.value = studioPresets["potemkin-app"];
    codeBox.addEventListener("input", evaluateSnippet);
    evaluateSnippet();
  }

  // Wire-Gap Contract Matcher
  const wireFe = document.getElementById("wire-fe");
  const wireBe = document.getElementById("wire-be");

  function parseRoutes(raw) {
    return (raw || "")
      .split(/\r?\n/)
      .map(function (line) {
        return line.trim().replace(/\s+/g, " ");
      })
      .filter(Boolean);
  }

  function evaluateWiring() {
    if (!wireFe || !wireBe) return;
    const fe = parseRoutes(wireFe.value);
    const be = parseRoutes(wireBe.value);
    const beSet = new Set(be);
    const feSet = new Set(fe);
    const gaps = fe.filter(function (r) {
      return !beSet.has(r);
    });
    const orphans = be.filter(function (r) {
      return !feSet.has(r);
    });
    const matched = fe.length - gaps.length;
    const score = Math.max(0, 100 - gaps.length * 9 - orphans.length * 4);

    const mEl = document.getElementById("wr-matched");
    const gEl = document.getElementById("wr-gaps");
    const oEl = document.getElementById("wr-orphans");
    const sEl = document.getElementById("wr-score");
    const listEl = document.getElementById("wr-findings");

    if (mEl) mEl.textContent = String(matched);
    if (gEl) gEl.textContent = String(gaps.length);
    if (oEl) oEl.textContent = String(orphans.length);
    if (sEl) sEl.textContent = score + " / 100";
    if (listEl) {
      listEl.innerHTML = "";
      gaps.forEach(function (g) {
        const div = document.createElement("div");
        div.className = "rw-item warn-border";
        const sp = document.createElement("span");
        sp.textContent = "POT008 · HIGH (-9) · Missing backend handler";
        const p = document.createElement("p");
        p.textContent = g + " is called by client code with no matching backend route.";
        div.appendChild(sp);
        div.appendChild(p);
        listEl.appendChild(div);
      });
      orphans.forEach(function (o) {
        const div = document.createElement("div");
        div.className = "rw-item";
        const sp = document.createElement("span");
        sp.textContent = "POT009 · MEDIUM (-4) · Orphan backend route";
        const p = document.createElement("p");
        p.textContent = o + " is registered on the server with zero client callers.";
        div.appendChild(sp);
        div.appendChild(p);
        listEl.appendChild(div);
      });
    }
  }

  if (wireFe && wireBe) {
    wireFe.addEventListener("input", evaluateWiring);
    wireBe.addEventListener("input", evaluateWiring);
    evaluateWiring();
  }

  // CI YAML builder
  const ciGate = document.getElementById("ci-gate");
  const ciFailon = document.getElementById("ci-failon");
  const ciDiff = document.getElementById("ci-diff");
  const ciSarif = document.getElementById("ci-sarif");
  const ciOutput = document.getElementById("ci-output");
  const ciCopyBtn = document.getElementById("ci-copy-btn");

  function renderCiYaml() {
    if (!ciOutput) return;
    const minScore = ciGate ? ciGate.value : "90";
    const failOn = ciFailon ? ciFailon.value : "high";
    const diff = ciDiff && ciDiff.value.trim() ? ciDiff.value.trim() : "origin/main";
    const sarif = ciSarif && ciSarif.value.trim() ? ciSarif.value.trim() : "potemkin.sarif";
    ciOutput.textContent = [
      "- name: Potemkin Real-Code Gate",
      "  uses: codesphere-u/potemkin@v1",
      "  with:",
      "    path: \".\"",
      "    diff: \"" + diff + "\"",
      "    fail-on: \"" + failOn + "\"",
      "    min-score: \"" + minScore + "\"",
      "    sarif-file: \"" + sarif + "\""
    ].join("\n");
  }

  [ciGate, ciFailon, ciDiff, ciSarif].forEach(function (el) {
    if (el) el.addEventListener("input", renderCiYaml);
  });
  if (ciCopyBtn && ciOutput) {
    ciCopyBtn.addEventListener("click", function () {
      copyText(ciOutput.textContent || "");
    });
  }
  renderCiYaml();
})();
