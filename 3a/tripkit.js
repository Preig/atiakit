/* 3.a The AI trip kit: page behaviour.
 * Needs ../assets/kit.js (window.KIT) and tripkit-core.js (window.TripKit), both loaded with defer before this file.
 * Nothing leaves the browser. Values are kept in this browser's storage only, and "Clear everything" removes them.
 */
(function () {
  "use strict";
  var T = window.TripKit, K = window.KIT;
  if (!T || !K) return;

  var PKEY = "atiakit:3a:partners", CPKEY = "atiakit:3a:calpartner", MKEY = "atiakit:3a:measure", HKEY = "atiakit:3a:handoff";

  /* fictional teaching partners: same facts as KIT.demo.partners and partners.csv */
  var DEMO_PARTNERS = [
    { partner: "Mile 12 Kennel", offer: "Summer sled-dog cart ride", duration_minutes: "90", drive_minutes_from_meeting_point: "15", min_age: "2", departure_times: "", weather_rule: "Runs in rain", referral_code: "BAYLIGHT-K", partner_confirmed: "yes", fact_owner: "", last_checked: "", notes: "FICTIONAL TEACHING PARTNER. Departure times not supplied: ask the partner." },
    { partner: "Harbor Kayak Co.", offer: "3-hour guided paddle", duration_minutes: "180", drive_minutes_from_meeting_point: "", min_age: "12", departure_times: "8:00; 13:00", weather_rule: "Cancels in wind over 15 knots", referral_code: "BAYLIGHT-P", partner_confirmed: "yes", fact_owner: "", last_checked: "", notes: "FICTIONAL TEACHING PARTNER. Drive time from our meeting point not supplied: ask the partner." }
  ];
  var PF = [
    ["partner", "Partner name", "text"],
    ["offer", "What they offer", "text"],
    ["duration_minutes", "Duration (minutes)", "number"],
    ["drive_minutes_from_meeting_point", "Drive time (minutes)", "number", "from your meeting point"],
    ["min_age", "Minimum age", "number"],
    ["departure_times", "Departure times", "text", "for example 8:00; 13:00"],
    ["weather_rule", "Weather rule", "text", "runs in rain, or cancels when"],
    ["referral_code", "Referral code", "text"]
  ];
  var PF2 = [
    ["fact_owner", "Who confirms these facts", "text", "a role, not a guest"],
    ["last_checked", "Last checked", "date"],
    ["notes", "Notes", "text"]
  ];

  var STANCES = {
    match: "Found a lower price for the same trip? Tell us before [FILL: free-cancellation cutoff] and we will match it by [FILL: how, for example refunding the difference].",
    credit: "Found a lower price for the same trip? Keep your booking and we will give you the difference as a credit toward [FILL: what the credit can be used for, and when it expires].",
    addon: "Found a lower price for the same trip? Keep your booking and we will add [FILL: approved add-on] at no charge.",
    explain: "Our price includes [FILL: what is included, from your fact sheet]. If your plans change, cancellation is free until [FILL: cutoff].",
    custom: "",
    undecided: ""
  };

  /* sample drafts with planted mistakes, for teaching the checker (fictional) */
  var SAMPLE_KIT = [
    "Your Seward trip kit: July 14 to 16",
    "",
    "Day 1, Wed July 14: arrival day",
    "Settle in after you arrive. Mile 12 Kennel runs a 90-minute sled-dog cart ride, 15 minutes by car from our harbor. Ages 2 and up, and it runs in rain. Code BAYLIGHT-K. Departure times: [FILL: departure times].",
    "",
    "Day 2, Thu July 15: your Bay Light cruise",
    "Meet at the small-boat harbor at 8:30 for the 9:00 departure. The cruise runs 9:00 to 13:00. Hot drinks are included; lunch is not, so pack food for the kids.",
    "Afternoon: Harbor Kayak Co. has a 3-hour guided paddle at 1:00 pm, $89 per person. Code BAYLIGHT-P.",
    "",
    "Day 3, Fri July 16: departure day",
    "A slow morning in town, or the kennel ride if you missed it.",
    "",
    "What to wear in July",
    "Layers for 50 to 65 F and a real rain jacket. You will definitely see whales from the heated cabin.",
    "",
    "Weather plan B (operator confirms on the day)",
    "The cruise runs in rain. If wind cancels the kayak, try the kennel.",
    "",
    "Things first-time visitors get wrong",
    "About 18 hours of daylight in July, and sunset comes around 11:30 pm. Afternoon wind is common in the bay.",
    "",
    "Questions for the owner",
    "1. Mile 12 Kennel departure times?",
    "2. What time does the party arrive and leave?"
  ].join("\n");
  var SAMPLE_CAL = [
    "DRAFT - PENDING OWNER REVIEW",
    "1. Confirmation",
    "Subject: Your cruise is booked",
    "Hi [GUEST FIRST NAME], you are booked for [TRIP DATE] at [START TIME]. Meet at the small-boat harbor, a 12-minute walk from the cruise ship dock. Dress in layers and bring a real rain jacket; the cabin is heated. We run in rain and cancel only for a marine warning, with a full refund. Your one-page trip kit is attached.",
    "",
    "DRAFT - PENDING OWNER REVIEW",
    "2. T-30",
    "Subject: An idea for an open afternoon",
    "Hi Sarah, Mile 12 Kennel runs a 90-minute sled-dog cart ride, 15 minutes by car from our harbor, ages 2 and up. Mention code BAYLIGHT-K and save $15.",
    "[FILL: business postal address]. Reply STOP OFFERS to opt out of offers.",
    "",
    "DRAFT - PENDING OWNER REVIEW",
    "3. T-7",
    "Subject: One week to go",
    "We run in rain. If a marine warning cancels the trip, you get a full refund. Our price includes a heated enclosed cabin and hot drinks. If your plans change, cancellation is free until 48 hours before departure.",
    "",
    "4. T-1",
    "Subject: See you tomorrow",
    "Meet at the small-boat harbor at [START TIME]. [FILL ON THE DAY: conditions from the captain]. Questions: [FILL: staff first name and business phone].",
    "",
    "DRAFT - PENDING OWNER REVIEW",
    "5. After",
    "Subject: How was your day on the bay?",
    "Thank you for coming out with us. Would you leave an honest review? It helps the next traveler plan."
  ].join("\n");

  var partners = [], last = { pre: null, kit: "", cal: "", sched: null }, piiHits = { kit: [], cal: [] };

  function $(id) { return document.getElementById(id); }
  function clone(x) { return JSON.parse(JSON.stringify(x)); }
  function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
  function sayTo(id, msg) {
    var box = $(id); if (!box) return;
    box.textContent = msg; clearTimeout(box._t); box._t = setTimeout(function () { box.textContent = ""; }, 8000);
  }
  function normPartner(p) { var o = T.blankPartner(); T.PARTNER_COLS.forEach(function (k) { if (p && p[k] !== undefined && p[k] !== null) o[k] = String(p[k]); }); return o; }
  function savePartners() { K.store.set(PKEY, partners); }

  /* ---------- partner editor ---------- */
  function fieldHTML(i, f, p) {
    var id = "p" + i + "-" + f[0], type = f[2];
    return '<div><label for="' + id + '">' + esc(f[1]) + (f[3] ? " <small>(" + esc(f[3]) + ")</small>" : "") + '</label><input type="' + type + '" id="' + id + '" data-k="' + f[0] + '" value="' + esc(p[f[0]] || "") + '"' +
      (type === "number" ? ' min="0" max="9999" inputmode="numeric"' : type === "text" ? ' autocomplete="off"' : "") + "></div>";
  }
  function renderPartners() {
    var box = $("partners"), html = "";
    partners.forEach(function (p, i) {
      html += '<div class="partner" data-i="' + i + '"><div class="ph"><h4>Partner ' + (i + 1) + (p.partner ? ": " + esc(p.partner) : "") + '</h4>' +
        '<button type="button" class="ghost small" data-remove="' + i + '" aria-label="Remove partner ' + (i + 1) + '">Remove</button></div><div class="fgrid">';
      PF.forEach(function (f) { html += fieldHTML(i, f, p); });
      html += '</div><label class="chk" for="p' + i + '-ok"><input type="checkbox" id="p' + i + '-ok" data-k="partner_confirmed"' + (T.isConfirmed(p) ? " checked" : "") +
        "> This partner confirmed these facts and agreed to be listed.</label>" +
        '<details><summary>Record keeping (not sent to the AI)</summary><div class="fgrid">';
      PF2.forEach(function (f) { html += fieldHTML(i, f, p); });
      html += "</div></details></div>";
    });
    box.innerHTML = html || '<p class="hint">No partners yet. Add one, or import a partners CSV.</p>';
    $("add-partner").disabled = partners.length >= 8;
  }
  function onPartnerEdit(e) {
    var el = e.target, k = el.dataset && el.dataset.k, wrap = el.closest && el.closest(".partner");
    if (!k || !wrap) return;
    var i = +wrap.dataset.i;
    if (!partners[i]) return;
    partners[i][k] = el.type === "checkbox" ? (el.checked ? "yes" : "no") : el.value;
    if (k === "partner") { var h = wrap.querySelector("h4"); if (h) h.textContent = "Partner " + (i + 1) + (el.value ? ": " + el.value : ""); }
    savePartners();
  }

  /* ---------- pre-check list ---------- */
  var ORDER = { bad: 0, warn: 1, fill: 2, ok: 3, info: 4 };
  function pillFor(c) {
    if (/^Excluded:/.test(c.text)) return ["pill red", "Excluded"];
    if (/^Clash/.test(c.text)) return ["pill amber", "Clash"];
    return { bad: ["pill red", "Fix"], warn: ["pill amber", "Check"], fill: ["pill grey", "[FILL]"], ok: ["pill", "OK"], info: ["pill teal", "Note"] }[c.level] || ["pill", "Note"];
  }
  function renderList(ul, list) {
    ul.textContent = "";
    list.slice().sort(function (a, b) { return ORDER[a.level] - ORDER[b.level]; }).forEach(function (c) {
      var li = document.createElement("li"), pill = document.createElement("span"), body = document.createElement("span"), pf = pillFor(c);
      pill.className = pf[0]; pill.textContent = pf[1];
      body.textContent = c.text || c.title || "";
      if (c.detail) { var d = document.createElement("span"); d.className = "d"; d.textContent = c.detail; body.appendChild(d); }
      li.appendChild(pill); li.appendChild(body); ul.appendChild(li);
    });
  }

  /* ---------- privacy gate on copy ---------- */
  function piiGate(which, text) {
    var hits = T.piiScan(text), p = $("pii-" + which), wrap = $("piiok-" + which + "-wrap");
    piiHits[which] = hits;
    if (hits.length) {
      p.textContent = "Possible personal data in your boxes: " + hits.slice(0, 5).map(function (h) { return h.kind + " (" + h.text + ")"; }).join("; ") +
        ". Remove guest details before you copy.";
      wrap.hidden = false;
    } else { p.textContent = ""; wrap.hidden = true; $("piiok-" + which).checked = false; }
  }
  function copyGuarded(which, btn) {
    if (piiHits[which].length && !$("piiok-" + which).checked) {
      sayTo("st-copy-" + which, "Not copied. Remove the personal data flagged above, or tick the box if it is fictional or your own business contact.");
      return;
    }
    K.copy(last[which], btn);
  }
  /* "Save as .txt" goes through the same privacy gate as Copy */
  function saveGuarded(which) {
    if (piiHits[which].length && !$("piiok-" + which).checked) {
      sayTo("st-copy-" + which, "Not saved. Remove the personal data flagged above, or tick the box if it is fictional or your own business contact.");
      return;
    }
    var name = which === "cal" ? "3a-post-booking-prompt.txt" : "3a-trip-kit-prompt.txt";
    K.download(name, last[which], "text/plain");
    sayTo("st-copy-" + which, "Saved " + name + " to your downloads.");
  }

  /* ---------- the trip-kit prompt ---------- */
  function kitValues() { var v = K.builders.kit ? K.builders.kit.values() : {}; v.partners = partners; return v; }
  function recompute() {
    var v = kitValues(), pre = T.precheck(v);
    last.pre = pre;
    renderList($("pre"), pre.checks);
    last.kit = K.render(K.tplText("tpl-kit"), {
      business: v.business, facts: v.facts, partners: pre.partnerBlock, months: pre.monthBlock,
      booking: pre.bookingBlock, dayframe: pre.dayBlock, rules: pre.rulesBlock
    });
    $("out-kit").textContent = last.kit;
    piiGate("kit", [v.business, v.facts, v.months, v.child_ages, v.product, v.other_plans].concat(partners.map(function (p) {
      return T.PARTNER_COLS.map(function (k) { return p[k]; }).join(" | ");
    })).join("\n"));
    fillPartnerSelect();
    recomputeCal();
    if ($("draft").value.trim()) runCheck(true);
  }

  /* ---------- post-booking calendar ---------- */
  function calValues() { return K.builders.cal ? K.builders.cal.values() : {}; }
  function fillPartnerSelect() {
    var sel = $("c-partner"), stored = K.store.get(CPKEY), names = partners.map(function (p) { return p.partner; }).filter(Boolean);
    var cur = stored === null ? (names[0] || "") : stored;
    if (names.indexOf(cur) < 0) cur = "";
    sel.textContent = "";
    var none = document.createElement("option"); none.value = ""; none.textContent = "No partner offer this season"; sel.appendChild(none);
    names.forEach(function (n) { var o = document.createElement("option"); o.value = n; o.textContent = n; sel.appendChild(o); });
    sel.value = cur;
  }
  function selectedPartner() {
    var name = $("c-partner").value;
    for (var i = 0; i < partners.length; i++) if (partners[i].partner === name && name) return partners[i];
    return null;
  }
  function renderSchedule(sch) {
    var box = $("sched-out");
    box.textContent = "";
    if (sch.error) { var e = document.createElement("p"); e.className = "pii"; e.textContent = sch.error; box.appendChild(e); return; }
    var p = document.createElement("p");
    p.innerHTML = "<b>" + (sch.lead === 0 ? "Booked on the trip date." : "Booked " + sch.lead + (sch.lead === 1 ? " day" : " days") + " before the trip.") + "</b> " + esc(sch.rule);
    box.appendChild(p);
    var wrap = document.createElement("div"); wrap.className = "tablewrap";
    var html = '<table class="sched"><caption class="visually-hidden">Send dates for this booking</caption><thead><tr><th scope="col">Message</th><th scope="col">Send on</th><th scope="col" class="num">Days from trip</th><th scope="col">Its one job</th></tr></thead><tbody>';
    sch.rows.forEach(function (r) {
      html += "<tr><td><b>" + esc(r.message) + "</b></td><td data-label=\"Send on\">" + esc(T.longDate(r.date)) + "</td><td class=\"num\" data-label=\"Days from trip\">" + (r.offset > 0 ? "+" : "") + r.offset +
        "</td><td data-label=\"Its one job\">" + esc(r.job) + (r.sameDay ? ' <span class="pill amber">Same day as the confirmation: merge or skip</span>' : "") + "</td></tr>";
    });
    html += "</tbody></table>";
    wrap.innerHTML = html; box.appendChild(wrap);
    if (sch.skipped.length) {
      var s = document.createElement("p"); s.className = "hint";
      s.textContent = "Not sent for this booking: " + sch.skipped.map(function (x) { return x.message + " (" + x.reason.replace(/\.$/, "") + ")"; }).join("; ") + ".";
      box.appendChild(s);
    }
  }
  function recomputeCal() {
    if (!K.builders.cal || !K.builders.kit) return;
    var c = calValues(), v = K.builders.kit.values();
    var sch = T.schedule({ booking: c.booking_date, trip: c.trip_date, tripEnd: c.trip_end, rate: c.rate, afterDays: c.after_days });
    /* announce the outcome once when it changes, not the whole table on every keystroke */
    var summary = sch.error || (sch.rows.length + " messages for this booking. " + sch.rule);
    if (last.sched && summary !== last.schedSummary) sayTo("st-sched", summary);
    last.sched = sch; last.schedSummary = summary;
    renderSchedule(sch);
    var after = T.intOrNull(c.after_days); if (after === null || after > 60) after = 1;
    var p = selectedPartner(), pLine = p ? T.partnerSentence(p) : "";
    last.cal = K.render(K.tplText("tpl-cal"), {
      business: v.business, facts: v.facts, partner: pLine,
      stance: c.stance === "undecided" ? "" : c.stance_text,
      after_label: after + (after === 1 ? " day" : " days") + " after the trip"
    });
    $("out-cal").textContent = last.cal;
    $("cal-csv").textContent = sch.error ? "Fix the dates above to see the CSV." : T.scheduleCSV(sch);
    piiGate("cal", [v.business, v.facts, c.stance_text, pLine].join("\n"));
  }

  /* ---------- check the draft ---------- */
  function runCheck(silent) {
    var kind = $("draft-kind").value, draft = $("draft").value, pre = last.pre || T.precheck(kitValues());
    var ctx = kind === "cal"
      ? { prompt: last.cal, extra: [], excluded: {}, partners: pre.partners.map(function (p) { return { name: p.name, code: p.code }; }), kind: "cal" }
      : { prompt: last.kit, extra: pre.knownExtra, excluded: pre.excluded, partners: pre.partners.map(function (p) { return { name: p.name, code: p.code }; }), kind: "kit" };
    var res = T.checkDraft(draft, ctx);
    renderList($("check-list"), res.items);
    var box = $("draft-hl"); box.textContent = "";
    if (draft.trim()) {
      var pos = 0;
      res.marks.forEach(function (m) {
        if (m.start > pos) box.appendChild(document.createTextNode(draft.slice(pos, m.start)));
        var mk = document.createElement("mark"); mk.className = "m-" + m.kind; mk.textContent = draft.slice(m.start, m.end); box.appendChild(mk);
        pos = m.end;
      });
      box.appendChild(document.createTextNode(draft.slice(pos)));
    }
    $("hl-legend").hidden = !draft.trim();
    if (!silent) {
      var nBad = res.items.filter(function (x) { return x.level === "bad"; }).length, nWarn = res.items.filter(function (x) { return x.level === "warn"; }).length;
      sayTo("st-check", draft.trim() ? "Checked: " + nBad + " to fix, " + nWarn + " to look at. " + res.words + " words." : "Paste a draft first.");
    }
  }

  /* ---------- measure ---------- */
  var MF = ["m-bk", "m-ref", "m-add", "m-q", "m-flex", "m-win"];
  function measure() {
    var v = {}; MF.forEach(function (id) { v[id] = $(id).value; });
    K.store.set(MKEY, v);
    function n(id) { var x = parseFloat(v[id]); return isNaN(x) || x < 0 ? null : x; }
    function r2(x) { return Math.round(x * 100) / 100; }
    var b = n("m-bk"), out = [];
    if (b) {
      if (n("m-ref") !== null) out.push("Partner referrals per booking: " + r2(n("m-ref") / b) + " (" + n("m-ref") + " referrals, " + b + " bookings)");
      if (n("m-add") !== null) out.push("Add-ons per booking: " + r2(n("m-add") / b) + " (" + n("m-add") + " add-ons)");
      if (n("m-q") !== null) out.push("Repeat questions per booking (Number 3): " + r2(n("m-q") / b) + " (" + n("m-q") + " questions)");
    } else out.push("Enter this month's bookings to see the per-booking rates.");
    var f = n("m-flex"), w = n("m-win");
    if (f && w !== null) out.push("In-window changes and cancellations, flexible bookings (Number 4): " + w + " of " + f + " = " + r2(100 * w / f) + "%");
    else out.push("Number 4: enter flexible bookings and how many changed or canceled inside the window.");
    out.push("Compare with your baseline month. Count non-refundable bookings separately.");
    $("m-out").textContent = out.join("\n");
  }

  /* ---------- wiring ---------- */
  document.addEventListener("DOMContentLoaded", function () {
    var stored = K.store.get(PKEY);
    partners = Array.isArray(stored) ? stored.slice(0, 8).map(normPartner) : clone(DEMO_PARTNERS).map(normPartner);
    renderPartners();

    var pbox = $("partners");
    pbox.addEventListener("input", onPartnerEdit);
    pbox.addEventListener("change", onPartnerEdit);
    pbox.addEventListener("click", function (e) {
      var b = e.target.closest("[data-remove]"); if (!b) return;
      partners.splice(+b.dataset.remove, 1); savePartners(); renderPartners(); recompute();
      sayTo("st-partners", "Partner removed.");
      var first = $("add-partner"); if (first) first.focus();
    });
    $("add-partner").addEventListener("click", function () {
      if (partners.length >= 8) return;
      partners.push(T.blankPartner()); savePartners(); renderPartners(); recompute();
      var el = $("p" + (partners.length - 1) + "-partner"); if (el) el.focus();
    });
    $("import-partners").addEventListener("change", function () {
      var f = this.files && this.files[0], input = this; if (!f) return;
      var rd = new FileReader();
      rd.onload = function () {
        var res = T.partnersFromCSV(String(rd.result || ""));
        if (!res.partners.length) { sayTo("st-partners", "Nothing loaded. " + (res.error || "No partner rows found.")); }
        else {
          partners = res.partners.map(normPartner); savePartners(); renderPartners(); recompute();
          sayTo("st-partners", "Loaded " + partners.length + " partner" + (partners.length === 1 ? "" : "s") + " from " + f.name + ". Check each one. " + (res.error || ""));
        }
        input.value = "";
      };
      rd.onerror = function () { sayTo("st-partners", "Could not read that file."); input.value = ""; };
      rd.readAsText(f);
    });
    $("export-partners").addEventListener("click", function () {
      K.download("partners.csv", T.partnersToCSV(partners), "text/csv");
      sayTo("st-partners", "Saved partners.csv to your downloads.");
    });

    $("kit-form").addEventListener("kit:change", recompute);
    $("load-demo").addEventListener("click", function () {
      partners = clone(DEMO_PARTNERS).map(normPartner); savePartners(); renderPartners();
      K.builders.kit.form.reset(); K.builders.kit.refresh();
      sayTo("st-kit", "Fictional example loaded. Replace it with your own approved facts.");
    });
    $("clear-kit").addEventListener("click", function () {
      partners = [T.blankPartner()]; savePartners(); renderPartners();
      var empty = {}; Array.prototype.forEach.call(K.builders.kit.form.elements, function (el) { if (el.name) empty[el.name] = ""; });
      empty.buffer = "30"; /* the default gap (Policy choice) stays visible, since the prompt uses it anyway */
      K.builders.kit.set(empty);
      sayTo("st-kit", "Cleared. The prompt now shows [FILL] wherever a fact is missing. The gap between activities is back to 30 minutes; change it if your policy differs.");
    });
    $("copy-kit").addEventListener("click", function () { copyGuarded("kit", this); });
    $("copy-cal").addEventListener("click", function () { copyGuarded("cal", this); });
    $("save-kit").addEventListener("click", function () { saveGuarded("kit"); });
    $("save-cal").addEventListener("click", function () { saveGuarded("cal"); });
    $("piiok-kit").addEventListener("change", function () { if (this.checked) sayTo("st-copy-kit", "Noted. Copy is allowed for this text."); });
    $("piiok-cal").addEventListener("change", function () { if (this.checked) sayTo("st-copy-cal", "Noted. Copy is allowed for this text."); });

    /* check the draft */
    var tmr = null;
    $("draft").addEventListener("input", function () { clearTimeout(tmr); tmr = setTimeout(function () { runCheck(true); }, 250); });
    $("draft-kind").addEventListener("change", function () { runCheck(true); });
    $("check-btn").addEventListener("click", function () { runCheck(false); });
    $("sample-draft").addEventListener("click", function () {
      var kind = $("draft-kind").value;
      $("draft").value = kind === "cal" ? SAMPLE_CAL : SAMPLE_KIT;
      runCheck(true);
      sayTo("st-check", "Sample loaded (fictional, with planted mistakes). Read the flags below, then compare them with the highlighted draft.");
    });
    $("clear-draft").addEventListener("click", function () { $("draft").value = ""; runCheck(true); sayTo("st-check", "Cleared."); $("draft").focus(); });

    /* hand the draft to the kit template through this browser's storage (never the address bar) */
    $("to-template").addEventListener("click", function () {
      var text = $("draft").value.trim();
      if (!text) { sayTo("st-template", "Paste the AI draft into Check the draft first."); return; }
      if ($("draft-kind").value === "cal") { sayTo("st-template", "The template is for the trip kit. Set \"Which prompt was it?\" to the trip kit."); return; }
      var v = K.builders.kit.values(), pre = last.pre || T.precheck(kitValues());
      var data = { text: text, business: v.business || "", trip: (pre.tripLabel ? pre.tripLabel : "") + (pre.partySize ? " · party of " + pre.partySize : ""), at: new Date().toISOString() };
      try { window.localStorage.setItem(HKEY, JSON.stringify(data)); }
      catch (e) { sayTo("st-template", "This browser blocked storage. Open the template and paste the draft there."); return; }
      window.location.href = "kit-template.html";
    });

    /* calendar */
    var cform = $("cal-form");
    cform.addEventListener("kit:change", recomputeCal);
    cform.addEventListener("change", function (e) {
      if (e.target.name === "stance") {
        var key = e.target.value;
        $("c-stance").value = STANCES[key] || "";
        K.builders.cal.refresh();
        if (key === "custom") { $("c-stance").placeholder = "Write your stance in one or two sentences."; $("c-stance").focus(); }
      }
    });
    /* typing a stance while "Not decided yet" is picked: switch to "Write my own" so the text reaches the prompt */
    $("c-stance").addEventListener("input", function () {
      var und = cform.querySelector('input[name="stance"][value="undecided"]');
      if (und && und.checked && this.value.trim()) {
        cform.querySelector('input[name="stance"][value="custom"]').checked = true;
        K.builders.cal.refresh();
        sayTo("st-cal", "Stance set to \"Write my own\".");
      }
    });
    $("cal-clear").addEventListener("click", function () {
      K.builders.cal.set({ booking_date: "", trip_date: "", trip_end: "", after_days: "1", rate: "flexible", stance: "undecided", stance_text: "" });
      K.store.set(CPKEY, ""); fillPartnerSelect(); recomputeCal();
      sayTo("st-cal", "Cleared. Enter your dates, pick a stance and a partner. The prompt shows [FILL] until you do.");
    });
    $("c-partner").addEventListener("change", function () { K.store.set(CPKEY, this.value); recomputeCal(); });
    $("use-kit-date").addEventListener("click", function () {
      var d = K.builders.kit.values().product_date;
      if (!T.parseISO(d)) { sayTo("st-sched", "The trip kit has no trip date yet."); return; }
      $("c-trip").value = d; K.builders.cal.refresh();
      sayTo("st-sched", "Trip date set to " + T.longDate(d) + ".");
    });
    $("cal-demo").addEventListener("click", function () {
      K.builders.cal.form.reset();
      K.store.set(CPKEY, partners.some(function (p) { return p.partner === "Mile 12 Kennel"; }) ? "Mile 12 Kennel" : null);
      fillPartnerSelect(); K.builders.cal.refresh();
      sayTo("st-cal", "Fictional example loaded for the calendar.");
    });
    $("save-cal-csv").addEventListener("click", function () {
      var sch = last.sched;
      if (!sch || sch.error) { sayTo("st-csv", "Fix the dates first: " + (sch ? sch.error : "")); return; }
      K.download("3a-post-booking-calendar.csv", T.scheduleCSV(sch), "text/csv");
      sayTo("st-csv", "Saved 3a-post-booking-calendar.csv to your downloads.");
    });

    /* measure */
    var mv = K.store.get(MKEY) || {};
    MF.forEach(function (id) { if (mv[id] !== undefined) $(id).value = mv[id]; $(id).addEventListener("input", measure); });
    measure();

    $("forget").addEventListener("click", function () {
      try {
        var ks = [];
        for (var i = 0; i < window.localStorage.length; i++) { var k = window.localStorage.key(i); if (k && k.indexOf("atiakit:3a") === 0) ks.push(k); }
        ks.forEach(function (k) { window.localStorage.removeItem(k); });
      } catch (e) { }
      MF.forEach(function (id) { $(id).value = ""; });
      $("draft").value = "";
      partners = clone(DEMO_PARTNERS).map(normPartner); renderPartners();
      K.builders.kit.form.reset(); K.builders.cal.form.reset();
      K.builders.kit.refresh(); K.builders.cal.refresh(); measure();
      try { ["atiakit:3a:kit", "atiakit:3a:cal", MKEY].forEach(function (k) { window.localStorage.removeItem(k); }); } catch (e) { }
      runCheck(true); /* empties the old check results and highlights */
      sayTo("st-forget", "Cleared what this page saved in this browser, including the kit template. The fictional example is showing again.");
    });

    recompute();
  });
})();
