/* For your team: page behavior. Uses ../assets/kit.js (KIT). No network, nothing leaves the browser.
 * - Builds the 12-line context block from its form and puts it in front of Prompt 1 and the assistant bundles.
 * - Checks text for emails, phone numbers and card numbers before copying (a first pass only, not a guarantee).
 */
(function () {
  "use strict";

  /* ---------- pure helpers (also exposed as KIT.team for testing) ---------- */
  var CTX_LINES = [
    ["l1", "What we are"],
    ["l2", "Where we operate, and the nearest competitor or alternative"],
    ["l3", "Size (guests per trip or per day, rooms or seats, year-round and seasonal staff)"],
    ["l4", "Seasons we actually operate, and our real dates and hours"],
    ["l5", "Busiest month, slowest month, and how big the swing is"],
    ["l6", "Who our guests are"],
    ["l7", "How guests book us"],
    ["l8", "Who our staff are (in aggregate)"],
    ["l9", "Licenses, permits and certifications we hold or depend on (names only)"],
    ["l10", "What we are known for (the honest answer)"],
    ["l11", "What we never do (including safety lines)"],
    ["l12", "The thing that costs me the most time every single week"]
  ];

  function oneLine(s) { return String(s == null ? "" : s).replace(/\s+/g, " ").trim(); }

  function ctxFilled(v) {
    v = v || {};
    return CTX_LINES.some(function (l) { return oneLine(v[l[0]]) !== ""; });
  }

  function ctxText(v) {
    v = v || {};
    var out = [
      "My business context (tourism, 12 lines)",
      "Business name: " + (oneLine(v.name) || "[name]"),
      "Updated: " + (oneLine(v.updated) || "[date]"),
      ""
    ];
    CTX_LINES.forEach(function (l, i) {
      out.push((i + 1) + ". " + l[1] + ": " + (oneLine(v[l[0]]) || "Not supplied"));
    });
    return out.join("\n");
  }

  function luhn(digits) {
    var sum = 0, dbl = false;
    for (var i = digits.length - 1; i >= 0; i--) {
      var d = digits.charCodeAt(i) - 48;
      if (dbl) { d *= 2; if (d > 9) d -= 9; }
      sum += d; dbl = !dbl;
    }
    return sum % 10 === 0;
  }

  /* Returns a list of what looks like personal data. A first pass only. */
  function findPII(text) {
    text = String(text || "");
    var hits = [];
    if (/[A-Z0-9._%+-]+@[A-Z0-9-]+(\.[A-Z0-9-]+)*\.[A-Z]{2,}/i.test(text)) hits.push("an email address");
    if (/(^|[^\d])(\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)/.test(text)) hits.push("a phone number");
    var runs = text.match(/\d(?:[ -]?\d){12,18}/g) || [];
    if (runs.some(function (r) { var d = r.replace(/\D/g, ""); return d.length >= 13 && d.length <= 19 && luhn(d); })) hits.push("a card number");
    return hits;
  }

  function listWords(a) {
    if (a.length < 2) return a.join("");
    return a.slice(0, -1).join(", ") + " and " + a[a.length - 1];
  }

  var KIT = window.KIT = window.KIT || {};
  KIT.team = { ctxText: ctxText, ctxFilled: ctxFilled, findPII: findPII, luhn: luhn, CTX_LINES: CTX_LINES };

  if (typeof document === "undefined") return;

  /* ---------- page wiring ---------- */
  function $(id) { return document.getElementById(id); }
  var formCtx = $("form-ctx"), formP1 = $("form-p1"), formReply = $("form-reply");

  function values(form) { return form && KIT.formValues ? KIT.formValues(form) : {}; }
  function currentCtx() { return values(formCtx); }

  /* Warns, and keeps text that looks like personal data out of this browser's storage
     (kit.js saves form values on every change; this removes that copy again). */
  function warnPII(el, text, formKey) {
    var hits = findPII(text);
    if (hits.length && formKey && KIT.store) KIT.store.del("atiakit:team:" + formKey);
    if (!el) return;
    el.textContent = hits.length ? "This looks like it contains " + listWords(hits) + ". Remove guest and staff details before you copy. Until you do, this box is not saved in this browser." : "";
  }

  function renderCtx() {
    var v = currentCtx();
    var out = $("out-ctx");
    if (out) out.textContent = ctxText(v);
    warnPII($("pii-ctx"), Object.keys(v).map(function (k) { return v[k]; }).join("\n"), "ctx");
    renderP1();
    updateBundles();
  }

  function renderP1() {
    var pre = $("out-p1"), tpl = $("tpl-p1");
    if (!pre || !tpl || !formP1) return;
    var v = values(formP1);
    var notes = String(v.notes || "").trim();
    v.notesblock = notes ? "What I already know about it (rough notes):\n" + notes : "";
    var body = KIT.render(KIT.tplText("tpl-p1"), v).replace(/\n{3,}/g, "\n\n");
    var cv = currentCtx();
    var wantCtx = v.withctx === "yes";
    pre.textContent = (wantCtx && ctxFilled(cv)) ? ctxText(cv) + "\n\n---\n\n" + body : body;
    var note = $("p1-ctx-note");
    if (note) note.textContent = (wantCtx && !ctxFilled(cv)) ? "Your context block is still empty, so it is not included yet. Fill in section 1 first." : "";
    warnPII($("pii-p1"), (v.job || "") + "\n" + notes, "p1");
    var job = oneLine(v.job);
    document.querySelectorAll("button.job").forEach(function (b) {
      b.setAttribute("aria-pressed", String(job !== "" && b.getAttribute("data-job") === job));
    });
  }

  function renderReplyWarn() {
    var v = values(formReply);
    warnPII($("pii-reply"), [v.business, v.question, v.facts].join("\n"), "reply");
  }

  /* bundles: instructions + context block + starter */
  var BUNDLES = {
    coach: { instr: "coach-instr", select: "coach-starter", sum: "coach-sum" },
    camp: { instr: "camp-instr", select: "camp-starter", sum: "camp-sum" }
  };
  function bundleText(key) {
    var b = BUNDLES[key], sel = $(b.select);
    var instr = ($(b.instr) || {}).textContent || "";
    var starterEl = sel ? $(sel.value) : null;
    var parts = ["Follow these instructions for this whole conversation.\n\n" + instr.trim()];
    var cv = currentCtx();
    if (ctxFilled(cv)) parts.push("MY 12-LINE CONTEXT BLOCK\n" + ctxText(cv));
    parts.push(starterEl ? starterEl.textContent.trim() : "");
    return parts.join("\n\n---\n\n");
  }
  function updateBundles() {
    Object.keys(BUNDLES).forEach(function (key) {
      var sum = $(BUNDLES[key].sum);
      if (!sum) return;
      var withCtx = ctxFilled(currentCtx());
      sum.textContent = "Copies about " + bundleText(key).length.toLocaleString("en-US") + " characters: the instructions, " +
        (withCtx ? "your context block" : "no context block yet (fill in section 1)") + ", then the starter you picked.";
    });
  }

  /* <pre> text is read with textContent: innerText is empty inside a closed <details>. */
  function textFor(el) {
    if (!el) return "";
    return el.tagName === "PRE" ? el.textContent : KIT.textOf(el);
  }

  /* guarded copy: blocks text that looks like personal data until the user confirms.
     Each "copy anyway" button remembers its own source, and re-reads it when clicked,
     so it never copies another row's text or a stale version. */
  function overrideBtn(btn) { var row = btn.closest(".btns"); return row ? row.querySelector("button.override") : null; }
  function guardedCopy(getText, btn) {
    var text = getText(), hits = findPII(text), ob = overrideBtn(btn);
    if (hits.length) {
      if (ob) { ob._getText = getText; ob.hidden = false; }
      KIT.say(btn, "Not copied: this looks like it contains " + listWords(hits) + ". Remove it, or confirm it is fictional.");
      return;
    }
    if (ob) { ob.hidden = true; ob._getText = null; }
    KIT.copy(text, btn);
  }

  document.addEventListener("click", function (e) {
    var b = e.target.closest("button");
    if (!b) return;
    if (b.dataset.guardCopy) {
      e.preventDefault();
      var srcId = b.dataset.guardCopy;
      guardedCopy(function () { return textFor($(srcId)); }, b);
    } else if (b.dataset.bundleCopy) {
      e.preventDefault();
      var bkey = b.dataset.bundleCopy;
      guardedCopy(function () { return bundleText(bkey); }, b);
    } else if (b.classList.contains("override")) {
      e.preventDefault();
      b.hidden = true;
      if (b._getText) { KIT.copy(b._getText(), b); b._getText = null; }
    } else if (b.classList.contains("job")) {
      e.preventDefault();
      var input = $("f-job");
      if (!input) return;
      input.value = b.getAttribute("data-job");
      input.dispatchEvent(new Event("input", { bubbles: true }));
      var h = $("p1-h");
      if (h && h.scrollIntoView) h.scrollIntoView({ behavior: "smooth", block: "start" });
      input.focus({ preventScroll: true });
      KIT.say(input, "Job added to Prompt 1.");
    } else if (b.id === "forget") {
      e.preventDefault();
      ["ctx", "p1", "reply"].forEach(function (k) {
        KIT.store.del("atiakit:team:" + k);
        var bl = KIT.builders && KIT.builders[k];
        if (bl) { bl.form.reset(); bl.refresh(); KIT.store.del("atiakit:team:" + k); }
      });
      KIT.say(b, "Cleared. Nothing from this page is saved in this browser now.");
    }
  });

  if (formCtx) formCtx.addEventListener("kit:change", renderCtx);
  if (formP1) formP1.addEventListener("kit:change", renderP1);
  if (formReply) formReply.addEventListener("kit:change", renderReplyWarn);
  Object.keys(BUNDLES).forEach(function (key) {
    var sel = $(BUNDLES[key].select);
    if (sel) sel.addEventListener("change", updateBundles);
  });
  document.addEventListener("DOMContentLoaded", function () { renderCtx(); renderReplyWarn(); });
})();
