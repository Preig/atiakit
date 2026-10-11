/* Tool 1.b page behaviour. Needs ../assets/kit.js (KIT) and curated-core.js (CuratedCore).
 * State is kept in this browser only (localStorage, wrapped in try/catch by KIT.store).
 */
(function () {
  "use strict";
  var C = window.CuratedCore, K = window.KIT;
  if (!C || !K) return;
  var SKEY = "atiakit:1b:state:v1";
  var state, undoSnap = null, lastResult = null, lastBuild = null;

  function $(id) { return document.getElementById(id); }
  function el(tag, attrs, text) {
    var n = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      if (k === "class") n.className = attrs[k];
      else if (k in n && k !== "list" && k !== "form") n[k] = attrs[k];
      else n.setAttribute(k, attrs[k]);
    });
    if (text !== undefined) n.textContent = text;
    return n;
  }
  function debounce(fn, ms) {
    var t;
    return function () { var a = arguments; clearTimeout(t); t = setTimeout(function () { fn.apply(null, a); }, ms); };
  }

  /* ---------- state ---------- */
  function demoState() {
    return {
      items: C.clone(C.DEMO.items), types: C.clone(C.DEMO.types), questions: C.clone(C.DEMO.questions),
      platform: "claude", reply: C.demoReply(), settings: C.clone(C.DEMO.settings),
      approvals: {}, approvalsKey: "", fictional: true
    };
  }
  function loadState() {
    var d = demoState(), s = K.store.get(SKEY);
    if (!s || typeof s !== "object" || !Array.isArray(s.items)) return d;
    Object.keys(d).forEach(function (k) { if (s[k] === undefined || s[k] === null) s[k] = d[k]; });
    s.items = s.items.map(C.cleanItem);
    if (!Array.isArray(s.types)) s.types = d.types;
    ["who", "time", "matters"].forEach(function (k) { if (!Array.isArray(s.questions[k])) s.questions[k] = d.questions[k]; });
    s.settings = Object.assign({}, C.BLANK_SETTINGS, s.settings || {});
    if (!s.settings.links || typeof s.settings.links !== "object") s.settings.links = {};
    return s;
  }
  var paused = false;
  var saveSoon = debounce(function () { if (!paused) K.store.set(SKEY, state); }, 300);
  function save() { if (!paused) saveSoon(); }
  function snapshot() { undoSnap = C.clone(state); $("btn-undo").hidden = false; }

  /* ---------- copy with custom messages (mirrors KIT.copy) ---------- */
  function copyText(text, fromEl, okMsg) {
    function done(ok) { K.say(fromEl, ok ? okMsg : "Select the text and press Ctrl+C (Cmd+C on a Mac)."); }
    function fallback() {
      var a = document.createElement("textarea");
      a.value = text; a.setAttribute("readonly", ""); a.style.position = "fixed"; a.style.left = "-10000px";
      document.body.appendChild(a); a.select();
      var ok = false; try { ok = document.execCommand("copy"); } catch (e) { }
      a.remove(); done(ok);
    }
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(function () { done(true); }, fallback);
    else fallback();
  }

  /* ---------- step 1: inventory ---------- */
  var LAYOUT = { product_id: "", business: "", product: "w2", duration: "half", minimum_age: "half", season: "", departures: "", runs_in_rain: "w2", distance_from_meeting_point: "w2", notes: "w4" };
  var TEXTAREAS = { runs_in_rain: "short", distance_from_meeting_point: "short", notes: "" };
  function renderInventory() {
    var list = $("inv-list");
    list.textContent = "";
    state.items.forEach(function (it, i) {
      var fs = el("fieldset", { class: "inv-card" });
      var lg = el("legend");
      lg.appendChild(document.createTextNode("Trip " + (i + 1) + " "));
      lg.appendChild(el("code", { class: "inv-id" }, it.product_id || "no code yet"));
      fs.appendChild(lg);
      var grid = el("div", { class: "inv-grid" });
      C.COLUMNS.forEach(function (c) {
        var id = "inv-" + i + "-" + c.key, wrap = el("div", { class: LAYOUT[c.key] || "" });
        var lab = el("label", { for: id });
        lab.appendChild(document.createTextNode(c.label + " "));
        lab.appendChild(el("small", null, "(" + c.hint + ")"));
        var inp = c.key in TEXTAREAS ? el("textarea", { id: id, rows: 2, class: TEXTAREAS[c.key] }) : el("input", { id: id, type: "text" });
        inp.value = it[c.key] || "";
        inp.placeholder = "[FILL]";
        inp.dataset.i = i; inp.dataset.k = c.key;
        if (c.key === "product_id") { inp.setAttribute("autocapitalize", "characters"); inp.setAttribute("spellcheck", "false"); }
        wrap.appendChild(lab); wrap.appendChild(inp); grid.appendChild(wrap);
      });
      fs.appendChild(grid);
      var acts = el("div", { class: "row-actions" });
      if (i > 0) acts.appendChild(el("button", { type: "button", class: "ghost", "data-act": "up", "data-i": i, "aria-label": "Move trip " + (i + 1) + " up" }, "Move up"));
      acts.appendChild(el("button", { type: "button", class: "danger", "data-act": "remove", "data-i": i, "aria-label": "Remove trip " + (i + 1) }, "Remove this trip"));
      fs.appendChild(acts);
      list.appendChild(fs);
    });
    inventoryChanged(true);
  }
  function renderInvSummary() {
    var b = C.businesses(state.items), empty = C.emptyCount(state.items);
    $("inv-summary").textContent = state.items.length + " trip" + (state.items.length === 1 ? "" : "s") + " from " + b.length + " business" + (b.length === 1 ? "" : "es") +
      (b.length ? " (the first, " + b[0] + ", is treated as yours)" : "") + ". " +
      (empty ? empty + " empty box" + (empty === 1 ? "" : "es") + " will show as [FILL] in the prompt." : "No empty boxes.");
    var ul = $("inv-issues"); ul.textContent = "";
    C.checkInventory(state.items).forEach(function (is) { ul.appendChild(issueLi(is)); });
  }
  function renderInvTable() {
    var box = $("inv-table"); box.textContent = "";
    var t = el("table"), thead = el("thead"), tr = el("tr");
    C.COLUMNS.forEach(function (c) { tr.appendChild(el("th", { scope: "col" }, c.label)); });
    thead.appendChild(tr); t.appendChild(thead);
    var tb = el("tbody");
    state.items.forEach(function (it) {
      var r = el("tr");
      C.COLUMNS.forEach(function (c) { r.appendChild(el("td", null, it[c.key] || "[FILL]")); });
      tb.appendChild(r);
    });
    t.appendChild(tb); box.appendChild(t);
  }
  function inventoryChanged(structural) {
    renderInvSummary();
    renderInvTable();
    renderLinks();
    renderPrompts();
    if (structural) runValidation(false); else validateSoon();
    save();
  }
  function onInvInput(e) {
    var t = e.target;
    if (!t.dataset || t.dataset.k === undefined) return;
    var i = +t.dataset.i, k = t.dataset.k;
    if (!state.items[i]) return;
    state.items[i][k] = t.value;
    if (k === "product_id") {
      var code = t.closest("fieldset").querySelector(".inv-id");
      if (code) code.textContent = t.value || "no code yet";
    }
    inventoryChangedSoon();
  }
  var inventoryChangedSoon = debounce(function () { inventoryChanged(false); }, 250);
  function onInvClick(e) {
    var b = e.target.closest("button[data-act]");
    if (!b) return;
    var i = +b.dataset.i;
    if (b.dataset.act === "remove") {
      snapshot();
      var gone = state.items.splice(i, 1)[0];
      renderInventory();
      K.say($("inv-add"), "Removed " + (gone.product_id || "the trip") + ". Use Undo at the top to bring it back.");
      var next = $("inv-" + Math.min(i, state.items.length - 1) + "-product_id");
      (next || $("inv-add")).focus();
    } else if (b.dataset.act === "up" && i > 0) {
      var tmp = state.items[i - 1]; state.items[i - 1] = state.items[i]; state.items[i] = tmp;
      renderInventory();
      var card = $("inv-list").children[i - 1];
      var moved = card && (card.querySelector('button[data-act="up"]') || card.querySelector('button[data-act="remove"]'));
      if (moved) moved.focus();
      K.say($("inv-add"), "Moved up. The first business in the list is treated as yours.");
    }
  }
  function addTrip() {
    var it = C.blankItem(), n = state.items.length + 1, ids = state.items.map(function (x) { return x.product_id; });
    while (ids.indexOf("TRIP-" + n) >= 0) n++;
    it.product_id = "TRIP-" + n;
    state.items.push(it);
    renderInventory();
    var f = $("inv-" + (state.items.length - 1) + "-business");
    if (f) f.focus();
    K.say($("inv-add"), "Added " + it.product_id + ". Fill in what you know; leave the rest empty.");
  }
  function importText(text, fromEl, label) {
    var r = C.inventoryFromCSV(text);
    if (r.error) { K.say(fromEl, r.error); return; }
    snapshot();
    state.items = r.items.map(C.cleanItem);
    markOwn();
    renderInventory();
    K.say(fromEl, "Imported " + r.items.length + " trip" + (r.items.length === 1 ? "" : "s") + " from " + label + ". " + (r.notes || []).concat(["Undo is at the top if you need it."]).join(" "));
  }
  function exportCSV(fromEl) {
    K.download("inventory.csv", "\uFEFF" + C.inventoryToCSV(state.items), "text/csv");
    K.say(fromEl, "Saved inventory.csv to your downloads.");
  }

  /* ---------- step 2: traveler types ---------- */
  function renderQuestions() {
    ["who", "time", "matters"].forEach(function (k) { $("q-" + k).value = (state.questions[k] || []).join("\n"); });
  }
  function renderTypes() {
    var list = $("type-list"); list.textContent = "";
    state.types.forEach(function (t, i) {
      var fs = el("fieldset", { class: "type-card" });
      fs.appendChild(el("legend", null, "Traveler type " + (i + 1)));
      var nid = "ty-" + i + "-name";
      fs.appendChild(el("label", { for: nid }, "Name"));
      var name = el("input", { id: nid, type: "text" });
      name.value = t.name || ""; name.dataset.i = i; name.dataset.k = "name";
      fs.appendChild(name);
      var grid = el("div", { class: "type-grid" });
      ["who", "time", "matters"].forEach(function (k) {
        var sid = "ty-" + i + "-" + k, w = el("div");
        w.appendChild(el("label", { for: sid }, C.QUESTION_TEXT[k]));
        var sel = el("select", { id: sid });
        sel.dataset.i = i; sel.dataset.k = k;
        sel.appendChild(el("option", { value: "" }, "Any"));
        var opts = state.questions[k] || [], cur = t[k] || "";
        opts.forEach(function (o) { sel.appendChild(el("option", { value: o }, o)); });
        if (cur && opts.indexOf(cur) < 0) sel.appendChild(el("option", { value: cur }, cur + " (no longer a choice)"));
        sel.value = cur;
        w.appendChild(sel); grid.appendChild(w);
      });
      fs.appendChild(grid);
      var acts = el("div", { class: "row-actions" });
      acts.appendChild(el("button", { type: "button", class: "danger", "data-act": "remove-type", "data-i": i, "aria-label": "Remove traveler type " + (i + 1) }, "Remove this type"));
      fs.appendChild(acts);
      list.appendChild(fs);
    });
  }
  function typesChanged() {
    renderPrompts();
    validateSoon();
    save();
  }
  function onTypeInput(e) {
    var t = e.target;
    if (!t.dataset || t.dataset.k === undefined) return;
    var i = +t.dataset.i;
    if (!state.types[i]) return;
    state.types[i][t.dataset.k] = t.value;
    typesChanged();
  }
  function onTypeClick(e) {
    var b = e.target.closest("button[data-act=remove-type]");
    if (!b) return;
    snapshot();
    var i = +b.dataset.i, gone = state.types.splice(i, 1)[0];
    renderTypes(); typesChanged();
    K.say($("type-add"), "Removed \"" + (gone.name || "type") + "\". Use Undo at the top to bring it back.");
    var next = $("ty-" + Math.min(i, state.types.length - 1) + "-name");
    (next || $("type-add")).focus();
  }
  function onQuestionChange(e) {
    var k = e.target.dataset.q;
    if (!k) return;
    var opts = e.target.value.split(/\r?\n/).map(function (s) { return s.trim(); }).filter(Boolean);
    var seen = {}; opts = opts.filter(function (o) { if (seen[o]) return false; seen[o] = 1; return true; });
    state.questions[k] = opts;
    renderTypes(); typesChanged();
    K.say(e.target, "Answer choices updated.");
  }

  /* ---------- step 3: prompts ---------- */
  function renderPrompts() {
    if (pendingGuard) { pendingGuard.textContent = pendingGuard.dataset.label || pendingGuard.textContent; pendingGuard = null; }
    $("out-instructions").textContent = C.buildInstructions(state.items);
    $("out-run").textContent = C.buildRunPrompt(state.items, state.types);
  }
  function renderPlatform() {
    var p = state.platform || "claude";
    document.querySelectorAll('#platform input[name="platform"]').forEach(function (r) {
      r.checked = r.value === p;
      r.parentNode.classList.toggle("on", r.checked);
    });
    document.querySelectorAll(".platform-steps").forEach(function (d) { d.hidden = d.dataset.platform !== p; });
  }
  var pendingGuard = null;
  function guardedCopy(btn) {
    var text = K.textOf($(btn.dataset.guard));
    var hits = C.findPII(text);
    if (hits.length && pendingGuard !== btn) {
      pendingGuard = btn;
      btn.dataset.label = btn.dataset.label || btn.textContent;
      btn.textContent = "Copy anyway: it is fictional";
      K.say(btn, "Check first: the text contains what looks like " + hits.map(function (h) { return h.kind; }).join(", ") + ". Remove guest data in step 1 or 2, or press the button again if it is fictional.");
      return;
    }
    pendingGuard = null;
    if (btn.dataset.label) { btn.textContent = btn.dataset.label; }
    copyText(text, btn, "Copied. Paste it into Claude, ChatGPT or Gemini.");
  }

  /* ---------- step 4: validation ---------- */
  function issueLi(is) {
    var li = el("li");
    var pill = el("span", { class: "pill " + (is.level === "error" ? "red" : is.level === "warn" ? "amber" : "teal") }, is.level === "error" ? "Fix" : is.level === "warn" ? "Check" : "Note");
    li.appendChild(pill);
    li.appendChild(document.createTextNode(" "));
    li.appendChild(el("b", null, is.where + " "));
    li.appendChild(document.createTextNode(is.msg));
    return li;
  }
  function runValidation(announce) {
    var r = C.validatePicks(state.reply, state.items, state.types);
    lastResult = r;
    var sum = $("val-summary"), ul = $("val-issues"), tbl = $("val-table");
    ul.textContent = ""; tbl.textContent = "";
    sum.textContent = "";
    var badge = el("span", { class: "val-badge " + (r.ok ? (r.warnings.length ? "warn" : "ok") : "bad") });
    if (!state.reply.trim()) { badge.textContent = "Nothing to check yet."; badge.className = "val-badge"; }
    else if (r.ok) badge.textContent = (r.warnings.length ? "Passed, with " + r.warnings.length + " thing" + (r.warnings.length === 1 ? "" : "s") + " to check. " : "Passed. ") + r.lists.length + " traveler type" + (r.lists.length === 1 ? "" : "s") + ", " + r.pickCount + " pick" + (r.pickCount === 1 ? "" : "s") + ".";
    else badge.textContent = r.errors.length + " thing" + (r.errors.length === 1 ? "" : "s") + " to fix before the picker can be built." +
      (state.reply === C.demoReply() ? " This is the fictional example reply, so it only matches the fictional inventory. Paste your own AI's reply." : "");
    sum.appendChild(badge);
    if (state.reply.trim()) r.errors.concat(r.warnings, r.infos).forEach(function (is) { ul.appendChild(issueLi(is)); });
    if (r.lists.length) {
      var byId = {};
      state.items.forEach(function (it) { byId[it.product_id] = it; });
      var t = el("table"), h = el("tr");
      ["Traveler type", "Picks", "Note"].forEach(function (x) { h.appendChild(el("th", { scope: "col" }, x)); });
      var th = el("thead"); th.appendChild(h); t.appendChild(th);
      var tb = el("tbody");
      r.lists.forEach(function (l) {
        var tr = el("tr");
        tr.appendChild(el("td", { "data-label": "Traveler type" }, l.traveler_type));
        var td = el("td", { "data-label": "Picks" });
        if (!l.picks.length) td.textContent = "None";
        l.picks.forEach(function (p, i) {
          if (i) td.appendChild(el("br"));
          td.appendChild(document.createTextNode((i + 1) + ". " + ((byId[p.product_id] || {}).product || p.product_id) + " (" + p.business + ")"));
        });
        tr.appendChild(td);
        tr.appendChild(el("td", { "data-label": "Note" }, l.note_if_fewer_than_three || "Three picks."));
        tb.appendChild(tr);
      });
      t.appendChild(tb); tbl.appendChild(t);
    }
    if (announce) $("val-result").focus();
    renderApprovals();
    renderPicker();
  }
  var validateSoon = debounce(function () { runValidation(false); }, 450);

  /* ---------- step 5: picker ---------- */
  function renderSettings() {
    document.querySelectorAll("[data-set]").forEach(function (f) { f.value = state.settings[f.dataset.set] || ""; });
    $("pk-accent").value = C.safeColor(state.settings.accent);
  }
  function renderLinks() {
    var box = $("pk-links"); box.textContent = "";
    C.businesses(state.items).forEach(function (b, i) {
      var id = "pk-link-" + i, w = el("div");
      w.appendChild(el("label", { for: id }, b));
      var inp = el("input", { id: id, type: "url", placeholder: "https://", inputmode: "url" });
      inp.value = state.settings.links[b] || "";
      inp.dataset.biz = b;
      w.appendChild(inp); box.appendChild(w);
    });
  }
  /* Approvals cover what each business sees in the picker: the picks plus the duration and minimum age shown from its rows. */
  function approvalKey() {
    if (!lastResult || !lastResult.ok) return "";
    var byId = {};
    state.items.forEach(function (it) { byId[it.product_id] = it; });
    var shown = lastResult.lists.map(function (l) { return l.picks.map(function (p) { return C.pickMeta(byId[p.product_id] || {}); }); });
    return C.hash(JSON.stringify([lastResult.lists, shown]));
  }
  function pickBusinesses() {
    var seen = {}, out = [];
    (lastResult && lastResult.ok ? lastResult.lists : []).forEach(function (l) {
      l.picks.forEach(function (p) { if (!seen[p.business]) { seen[p.business] = 1; out.push(p.business); } });
    });
    var order = C.businesses(state.items);
    return out.sort(function (a, b) { return order.indexOf(a) - order.indexOf(b); });
  }
  function renderApprovals() {
    var key = approvalKey();
    if (key && key !== state.approvalsKey) { state.approvalsKey = key; state.approvals = {}; save(); }
    var box = $("pk-approve-boxes"); box.textContent = "";
    if (!key) { box.appendChild(el("p", { class: "hint" }, "Approvals appear here once the picks pass the check in step 4.")); return; }
    var bizs = pickBusinesses().map(function (b) { return { key: "biz:" + b, text: b + " has read and approved its own lines." }; });
    bizs.push({ key: "owner", text: "I read the whole picker on a phone and a computer, and it matches our approved facts." });
    bizs.forEach(function (a, i) {
      var id = "ap-" + i, lab = el("label", { for: id });
      var cb = el("input", { id: id, type: "checkbox" });
      cb.checked = !!state.approvals[a.key]; cb.dataset.ap = a.key;
      lab.appendChild(cb); lab.appendChild(document.createTextNode(a.text));
      box.appendChild(lab);
    });
  }
  function isApproved() {
    if (!lastResult || !lastResult.ok) return false;
    var need = pickBusinesses().map(function (b) { return "biz:" + b; }).concat(["owner"]);
    return need.every(function (k) { return state.approvals[k]; });
  }
  var renderPickerSoon = debounce(function () { renderPicker(); }, 300);
  function renderPicker() {
    var ok = !!(lastResult && lastResult.ok);
    document.querySelectorAll("[data-needs-valid]").forEach(function (b) { b.disabled = !ok; });
    var sum = $("pk-summary");
    if (!ok) {
      lastBuild = null;
      sum.textContent = String(state.reply || "").trim()
        ? "Fix the items marked Fix in step 4 to build the picker."
        : "Paste the AI's reply in step 4 and check it to build the picker.";
      $("pk-code").textContent = ""; $("pk-text").textContent = "";
      var fr0 = $("pv-frame");
      fr0.dataset.doc = ""; fr0.srcdoc = C.previewDoc('<p style="color:#555">The preview appears here once the picks pass the check in step 4.</p>');
      return;
    }
    var approved = isApproved();
    var opts = { lists: lastResult.lists, items: state.items, types: state.types, questions: state.questions, settings: state.settings, approved: approved };
    var snippet = C.buildPicker(opts), text = C.buildPlainText(opts);
    lastBuild = { snippet: snippet, text: text, approved: approved };
    $("pk-code").textContent = snippet;
    $("pk-text").textContent = text;
    var doc = C.previewDoc(snippet), fr = $("pv-frame");
    if (fr.dataset.doc !== C.hash(doc)) { fr.dataset.doc = C.hash(doc); fr.srcdoc = doc; }
    sum.textContent = approved
      ? "Approved version: no DRAFT banner. Test it on a hidden page before you publish."
      : "Draft version: the picker shows a DRAFT banner until every business and you have ticked the approvals above.";
  }
  function fullDoc(snippet) {
    return "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n<title>" + C.esc(state.settings.title || "Which trip fits you?") + "</title>\n" +
      "<style>body{margin:0;padding:16px;font:17px/1.5 Arial,Helvetica,sans-serif;color:#222;background:#fff}</style>\n</head>\n<body>\n" +
      "<!-- START OF PICKER: copy everything from here to END OF PICKER into a Squarespace Code block or a Wix Embed HTML element. -->\n" +
      snippet + "\n<!-- END OF PICKER -->\n</body>\n</html>\n";
  }

  /* ---------- whole-page actions ---------- */
  function markOwn() {
    if (state.fictional) { state.fictional = false; $("fictional-note").hidden = true; }
  }
  function renderAll() {
    $("fictional-note").hidden = !state.fictional;
    renderInventory();
    renderQuestions();
    renderTypes();
    renderPlatform();
    renderSettings();
    $("val-input").value = state.reply;
    renderPrompts();
    runValidation(false);
  }

  document.addEventListener("DOMContentLoaded", function () {
    state = loadState();
    renderAll();

    $("inv-list").addEventListener("input", onInvInput);
    $("inv-list").addEventListener("click", onInvClick);
    $("inv-add").addEventListener("click", addTrip);
    $("inv-export").addEventListener("click", function () { exportCSV(this); });
    $("inv-export-2").addEventListener("click", function () { exportCSV(this); });
    $("inv-file").addEventListener("change", function () {
      var f = this.files && this.files[0], inp = this;
      if (!f) return;
      if (f.size > 2000000) { K.say(inp, "That file is over 2 MB. An inventory is usually a few kilobytes; check you picked the right file."); inp.value = ""; return; }
      var rd = new FileReader();
      rd.onload = function () { importText(String(rd.result || ""), inp, f.name); inp.value = ""; };
      rd.onerror = function () { K.say(inp, "Could not read that file."); inp.value = ""; };
      rd.readAsText(f);
    });
    $("inv-paste-go").addEventListener("click", function () { importText($("inv-paste").value, this, "the pasted rows"); });

    $("type-list").addEventListener("input", onTypeInput);
    $("type-list").addEventListener("change", onTypeInput);
    $("type-list").addEventListener("click", onTypeClick);
    $("type-add").addEventListener("click", function () {
      state.types.push({ name: "", who: "", time: "", matters: "" });
      renderTypes(); typesChanged();
      $("ty-" + (state.types.length - 1) + "-name").focus();
      K.say(this, "Added a traveler type. Give it a name the AI and your visitors will understand.");
    });
    ["who", "time", "matters"].forEach(function (k) { $("q-" + k).addEventListener("change", onQuestionChange); });

    $("platform").addEventListener("change", function (e) {
      if (e.target.name !== "platform") return;
      state.platform = e.target.value; renderPlatform(); save();
    });
    document.querySelectorAll("button[data-guard]").forEach(function (b) {
      b.addEventListener("click", function () { guardedCopy(b); });
    });

    $("val-input").addEventListener("input", function () { state.reply = this.value; save(); validateSoon(); });
    $("val-run").addEventListener("click", function () {
      state.reply = $("val-input").value; save(); runValidation(true);
      K.say(this, lastResult.ok ? "Checked. See the results below." : "Checked. See what to fix below.");
    });
    $("val-demo").addEventListener("click", function () {
      var own = state.reply.trim() && state.reply !== C.demoReply();
      if (own) snapshot();
      state.reply = C.demoReply(); $("val-input").value = state.reply; save(); runValidation(false);
      K.say(this, "Fictional example reply loaded. It only matches the fictional inventory." + (own ? " Undo at the top brings back your reply." : ""));
    });
    $("val-clear").addEventListener("click", function () {
      state.reply = ""; $("val-input").value = ""; save(); runValidation(false);
      $("val-input").focus(); K.say(this, "Cleared.");
    });

    document.querySelectorAll("[data-set]").forEach(function (f) {
      f.addEventListener("input", function () { state.settings[f.dataset.set] = f.value; save(); renderPickerSoon(); });
    });
    $("pk-links").addEventListener("input", function (e) {
      var b = e.target.dataset.biz;
      if (!b) return;
      state.settings.links[b] = e.target.value.trim();
      e.target.setCustomValidity(e.target.value.trim() && !C.safeUrl(e.target.value) ? "Use a full address starting with https://" : "");
      save(); renderPickerSoon();
    });
    $("pk-approve-boxes").addEventListener("change", function (e) {
      var k = e.target.dataset.ap;
      if (!k) return;
      state.approvals[k] = e.target.checked; save(); renderPicker();
    });
    $("pv-phone").addEventListener("click", function () { $("pv-wrap").classList.add("phone"); this.setAttribute("aria-pressed", "true"); $("pv-full").setAttribute("aria-pressed", "false"); });
    $("pv-full").addEventListener("click", function () { $("pv-wrap").classList.remove("phone"); this.setAttribute("aria-pressed", "true"); $("pv-phone").setAttribute("aria-pressed", "false"); });
    window.addEventListener("message", function (e) {
      var f = $("pv-frame");
      if (!f || e.source !== f.contentWindow || !e.data || typeof e.data.tfpHeight !== "number") return;
      f.style.height = Math.max(240, Math.min(4000, Math.round(e.data.tfpHeight) + 6)) + "px";
    });
    $("pk-copy").addEventListener("click", function () {
      if (!lastBuild) return;
      copyText(lastBuild.snippet, this, lastBuild.approved ? "Copied. Paste it into a Squarespace Code block or a Wix Embed HTML element." : "Copied the DRAFT version. Get approvals before you publish it.");
    });
    $("pk-dl").addEventListener("click", function () {
      if (!lastBuild) return;
      K.download("which-trip-fits-you.html", fullDoc(lastBuild.snippet), "text/html");
      K.say(this, "Saved which-trip-fits-you.html. Open it in a browser to test; copy the part between the START and END comments into your site.");
    });
    $("pk-copy-txt").addEventListener("click", function () {
      if (!lastBuild) return;
      copyText(lastBuild.text, this, "Copied the plain-text version. Paste it into a normal text block.");
    });
    $("pk-dl-txt").addEventListener("click", function () {
      if (!lastBuild) return;
      K.download("which-trip-fits-you.txt", lastBuild.text, "text/plain");
      K.say(this, "Saved which-trip-fits-you.txt to your downloads.");
    });
    $("pk-dl-json").addEventListener("click", function () {
      if (!lastResult || !lastResult.ok) return;
      var out = lastResult.lists.map(function (l) {
        return { traveler_type: l.traveler_type, picks: l.picks.map(function (p) { return { product_id: p.product_id, business: p.business, reason: p.reason, cited_fact: p.cited_fact }; }), note_if_fewer_than_three: l.note_if_fewer_than_three };
      });
      K.download("picks.json", JSON.stringify(out, null, 2) + "\n", "application/json");
      K.say(this, "Saved picks.json to your downloads.");
    });

    $("btn-demo").addEventListener("click", function () {
      snapshot(); state = demoState(); renderAll(); save();
      K.say(this, "Fictional example loaded. Replace it with your own approved facts. Undo brings back what you had.");
    });
    $("btn-blank").addEventListener("click", function () {
      snapshot();
      var t = C.blankItem(); t.product_id = "TRIP-1";
      state = demoState();
      state.items = [t]; state.reply = ""; state.settings = C.clone(C.BLANK_SETTINGS); state.fictional = false;
      renderAll(); save();
      K.say(this, "Blank inventory ready. The four traveler types are kept; change them in step 2. Undo brings back what you had.");
    });
    /* after "Clear my saved data", nothing is stored again until the person changes something */
    ["input", "change"].forEach(function (t) { document.addEventListener(t, function () { paused = false; }, true); });
    document.addEventListener("click", function (e) { if (e.target.closest && e.target.closest("button") && !e.target.closest("#btn-forget")) paused = false; }, true);
    $("btn-forget").addEventListener("click", function () {
      paused = true;
      K.store.del(SKEY); undoSnap = null; $("btn-undo").hidden = true;
      state = demoState(); renderAll();
      K.say(this, "Your saved data is cleared from this browser. The fictional example is showing.");
    });
    $("btn-undo").addEventListener("click", function () {
      if (!undoSnap) return;
      var cur = C.clone(state);
      state = undoSnap; undoSnap = cur;
      renderAll(); save();
      K.say(this, "Undone. Press Undo again to redo.");
    });
  });
})();
