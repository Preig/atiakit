/* ATIA AI Take-Home Kit - shared behaviour. No dependencies, works offline, nothing leaves the browser.
 *
 * Conventions every tool page can use:
 *   <button data-copy="ID" [data-copy-msg="..."] [data-status="ID"]>  copy the text of #ID; optional custom message and status target
 *   <form data-builder="KEY"> + inputs   live prompt builder; inputs need name="field"
 *   <template id="T"> ... {{field|[FALLBACK]}} ... </template>
 *   <pre data-render="T" data-builder-src="KEY"></pre>   rendered from template T with the form's values
 *   <button data-fill="KEY" data-example="NAME">         fill form KEY from KIT.examples[NAME] (or <script type="application/json" id="NAME">)
 *   <button data-reset="KEY">            clear the form (and its saved values)
 *   <button data-download="file.ext" data-from="ID" [data-mime="text/csv"]>  save the text of #ID as a file
 *   <nav class="tool-nav" data-toolnav="1a"></nav>       standard links across the kit
 * Form values are remembered in this browser only (localStorage), so a page can be closed and reopened.
 */
(function () {
  "use strict";
  var KIT = window.KIT = window.KIT || {};

  KIT.tools = [
    ["1a", "Rewrite for the short list", 1, 1], ["1b", "Your own curated ten", 1, 2], ["1c", "AI answer monitoring", 1, 3],
    ["2a", "The honest picture", 2, 1], ["2b", "Grounded answer assistant", 2, 2], ["2c", "Post-booking retention engine", 2, 3],
    ["3a", "The AI trip kit", 3, 1], ["3b", "Partner circle", 3, 2], ["3c", "Agent-ready trip record", 3, 3]
  ];

  /* ---------- fictional teaching data (same business as Prompt-Kit-3x3.html) ---------- */
  KIT.demo = {
    business: "Bay Light Day Cruises, Seward (FICTIONAL TEACHING BUSINESS)",
    facts: [
      "FICTIONAL TEACHING BUSINESS: Bay Light Day Cruises, Seward",
      "Offer: 4-hour wildlife and glacier cruise. Departs 9:00 and 14:00, May 15 to September 15. Capacity 40. Minimum age 4. Heated enclosed cabin, two restrooms, hot drinks included, lunch not included. Meeting point: small-boat harbor, a 12-minute walk from the cruise ship dock. Runs in rain. Cancels only for a marine warning, with a full refund. Free cancellation until 48 hours before departure; inside 48 hours, no refund.",
      "Channels: own website, Viator, Google Business Profile, two hotel desks.",
      "Not supplied (ask the owner): group discounts, private charters, pet policy, accessibility of the vessel."
    ].join("\n"),
    partners: [
      "Partner A: Mile 12 Kennel. Summer sled-dog cart ride, 90 minutes, 15 minutes by car from the harbor, ages 2 and up, runs in rain. Referral code BAYLIGHT-K.",
      "Partner B: Harbor Kayak Co. 3-hour guided paddle, departs 8:00 and 13:00, minimum age 12, cancels in wind over 15 knots. Referral code BAYLIGHT-P."
    ].join("\n"),
    reviews: [
      "1. (5 stars) Saw humpbacks and the glacier calving. Cabin was warm.",
      "2. (4 stars) Wonderful crew. Wish we had known lunch was not included; the kids were hungry by noon.",
      "3. (3 stars) Rough water on the way back and two in our group were seasick. Crew handled it well.",
      "4. (4 stars) The walk from the cruise ship was longer than we expected with a stroller.",
      "5. (5 stars) Rained the whole time and we still saw otters and puffins. Bring a real rain jacket.",
      "6. (2 stars) Booked through a third party and the pickup instructions conflicted with the email from the company."
    ].join("\n"),
    month: "July: 50 to 65 F, rain on about half of days, about 18 hours of daylight, afternoon wind common in the bay.",
    listing: "Unforgettable scenery, friendly crew, perfect for families. Alaska's best half-day cruise!"
  };
  KIT.examples = KIT.examples || {};

  /* ---------- storage (never required; private windows may block it) ---------- */
  var store = {
    get: function (k) { try { return JSON.parse(window.localStorage.getItem(k) || "null"); } catch (e) { return null; } },
    set: function (k, v) { try { window.localStorage.setItem(k, JSON.stringify(v)); } catch (e) { } },
    del: function (k) { try { window.localStorage.removeItem(k); } catch (e) { } }
  };
  KIT.store = store;
  var pageKey = "atiakit:" + (document.body && document.body.dataset.page || location.pathname);

  /* ---------- status line ---------- */
  function say(fromEl, msg) {
    var box = null, n = fromEl;
    if (fromEl && fromEl.dataset && fromEl.dataset.status) box = document.getElementById(fromEl.dataset.status);
    while (n && !box) { box = n.querySelector && n.querySelector(".status"); n = n.parentElement; }
    box = box || document.getElementById("copy-status");
    if (box) { box.textContent = msg; clearTimeout(box._t); box._t = setTimeout(function () { box.textContent = ""; }, 6000); }
  }
  KIT.say = say;

  function textOf(el) {
    if (!el) return "";
    if ("value" in el && (el.tagName === "TEXTAREA" || el.tagName === "INPUT" || el.tagName === "SELECT")) return el.value;
    return el.innerText !== undefined ? el.innerText : el.textContent;
  }
  KIT.textOf = textOf;

  /* ---------- copy ---------- */
  KIT.copy = function (text, fromEl, okMsg) {
    var msgOk = okMsg || (fromEl && fromEl.dataset && fromEl.dataset.copyMsg) || "Copied. Paste it into Claude, ChatGPT or Gemini.";
    function fallback() {
      var area = document.createElement("textarea");
      area.value = text; area.setAttribute("readonly", ""); area.style.position = "fixed"; area.style.left = "-10000px";
      document.body.appendChild(area); area.select();
      var ok = false; try { ok = document.execCommand("copy"); } catch (e) { }
      area.remove();
      say(fromEl, ok ? msgOk : "Select the text and press Ctrl+C (Cmd+C on a Mac).");
    }
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(function () { say(fromEl, msgOk); }, fallback);
    } else fallback();
  };

  /* ---------- download ---------- */
  KIT.download = function (name, text, mime) {
    var blob = new Blob([text], { type: (mime || "text/plain") + ";charset=utf-8" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = name;
    document.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 500);
  };

  /* ---------- template rendering: {{field}} or {{field|[FALLBACK]}} ---------- */
  KIT.render = function (tpl, values) {
    return tpl.replace(/\{\{\s*([\w.-]+)\s*(?:\|([^}]*))?\}\}/g, function (_, k, fb) {
      var v = values[k];
      if (v === undefined || v === null || String(v).trim() === "") return fb !== undefined ? fb : "[" + k.toUpperCase().replace(/[_-]/g, " ") + "]";
      return String(v).trim();
    });
  };
  function tplText(id) {
    var t = document.getElementById(id);
    if (!t) return "";
    var raw = t.tagName === "TEMPLATE" ? t.innerHTML : t.textContent;
    // decode entities written in the template (&amp; &lt; &gt; &quot;)
    var d = document.createElement("textarea"); d.innerHTML = raw; return d.value.replace(/^\n/, "");
  }
  KIT.tplText = tplText;

  function formValues(form) {
    var v = {};
    Array.prototype.forEach.call(form.elements, function (el) {
      if (!el.name) return;
      if (el.type === "checkbox") { if (el.checked) v[el.name] = v[el.name] ? v[el.name] + "\n" + el.value : el.value; else if (!(el.name in v)) v[el.name] = ""; }
      else if (el.type === "radio") { if (el.checked) v[el.name] = el.value; else if (!(el.name in v)) v[el.name] = ""; }
      else v[el.name] = el.value;
    });
    return v;
  }
  KIT.formValues = formValues;
  function setValues(form, vals) {
    Array.prototype.forEach.call(form.elements, function (el) {
      if (!el.name || !(el.name in vals)) return;
      if (el.type === "checkbox") el.checked = String(vals[el.name]).split("\n").indexOf(el.value) >= 0;
      else if (el.type === "radio") el.checked = vals[el.name] === el.value;
      else el.value = vals[el.name];
    });
  }

  KIT.builders = {};
  function wireBuilder(form) {
    var key = form.dataset.builder, sk = pageKey + ":" + key;
    var saved = store.get(sk); if (saved) setValues(form, saved);
    function refresh() {
      var vals = formValues(form);
      store.set(sk, vals);
      document.querySelectorAll('[data-builder-src="' + key + '"]').forEach(function (out) {
        if (out.dataset.render) out.textContent = KIT.render(tplText(out.dataset.render), vals);
      });
      form.dispatchEvent(new CustomEvent("kit:change", { detail: vals }));
    }
    form.addEventListener("input", refresh);
    form.addEventListener("change", refresh);
    form.addEventListener("submit", function (e) { e.preventDefault(); refresh(); });
    KIT.builders[key] = { form: form, refresh: refresh, values: function () { return formValues(form); }, set: function (v) { setValues(form, v); refresh(); } };
    refresh();
  }

  function exampleData(name) {
    var s = document.getElementById(name);
    if (s && s.type === "application/json") { try { return JSON.parse(s.textContent); } catch (e) { } }
    var ex = KIT.examples[name];
    return typeof ex === "function" ? ex() : ex;
  }

  function wireToolNav(nav) {
    var cur = nav.dataset.toolnav, root = nav.dataset.root || "../";
    var html = '<a href="' + root + '"' + (cur === "hub" ? ' aria-current="page"' : "") + '>All tools</a>';
    html += '<a href="' + root + 'audit/"' + (cur === "audit" ? ' aria-current="page"' : "") + '>AI visibility audit</a>';
    KIT.tools.forEach(function (t) {
      html += '<a href="' + root + t[0] + '/"' + (cur === t[0] ? ' aria-current="page"' : "") + ' title="' + t[1] + '">' + t[0].charAt(0) + "." + t[0].charAt(1) + " " + t[1] + "</a>";
    });
    html += '<a href="' + root + 'team/"' + (cur === "team" ? ' aria-current="page"' : "") + '>For your team</a>';
    nav.innerHTML = html;
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("form[data-builder]").forEach(wireBuilder);
    document.querySelectorAll("nav[data-toolnav]").forEach(wireToolNav);
    document.addEventListener("click", function (e) {
      var b = e.target.closest("button, a.button");
      if (!b) return;
      if (b.dataset.copy) { e.preventDefault(); KIT.copy(textOf(document.getElementById(b.dataset.copy)), b); }
      else if (b.dataset.download) {
        e.preventDefault();
        var src = b.dataset.from ? textOf(document.getElementById(b.dataset.from)) : (b.dataset.text || "");
        KIT.download(b.dataset.download, src, b.dataset.mime);
        say(b, "Saved " + b.dataset.download + " to your downloads.");
      }
      else if (b.dataset.fill) {
        e.preventDefault();
        var bl = KIT.builders[b.dataset.fill], data = exampleData(b.dataset.example);
        if (bl && data) { bl.set(data); say(b, "Fictional example loaded. Replace it with your own approved facts."); }
      }
      else if (b.dataset.reset) {
        e.preventDefault();
        var bb = KIT.builders[b.dataset.reset];
        if (bb) { bb.form.reset(); store.del(pageKey + ":" + b.dataset.reset); bb.refresh(); say(b, "Cleared."); }
      }
    });
  });
})();
