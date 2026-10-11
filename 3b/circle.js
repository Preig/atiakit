/* 3.b A partner circle with shared facts: page logic.
 * Everything runs in this browser. Nothing you type is sent anywhere, and nothing goes into a URL.
 * The pure functions (dates, fact-sheet checks and exports, CSV, the send-date rule, the draft check,
 * referral-code reconciliation) are exported for tests in Node:  node dev/circle.test.js
 * Teaching data is fictional: Bay Light Day Cruises, Seward, with Mile 12 Kennel and Harbor Kayak Co.
 */
(function (root) {
  "use strict";
  var C = {};

  C.STALE_DAYS = 60;          // a block checked more than 60 days ago is flagged
  C.LEAD_DAYS = 30;           // send_date = arrival minus 30 days
  C.LATE_DAYS = 3;            // Policy choice shown in the calculator: under 3 days, write personally
  C.DRAFT = "DRAFT - PENDING OWNER REVIEW";

  function str(v) { return v === undefined || v === null ? "" : String(v).trim(); }
  C.str = str;

  /* ---------- the shared fact sheet: one block per partner (Prompt Kit 3.b fields + owner + date) ---------- */
  C.FIELDS = [
    { key: "partner", label: "Partner", csv: "partner", kind: "text", req: true, hint: "business name as guests know it" },
    { key: "offer", label: "Offer and duration", csv: "offer_and_duration", kind: "area", req: true, hint: "what, how long" },
    { key: "departures", label: "Departures and season", csv: "departures_and_season", kind: "area", req: true, hint: "times, dates" },
    { key: "ages", label: "Minimum age and group limits", csv: "min_age_and_group_limits", kind: "area", req: true, hint: "ages, capacity" },
    { key: "weather", label: "Runs in rain / cancels when", csv: "runs_in_rain_cancels_when", kind: "area", req: true, hint: "in the words of the person who makes the call" },
    { key: "drive", label: "Meeting point and drive times", csv: "meeting_point_and_drive_times", kind: "area", req: true, hint: "where to meet; minutes from each partner's meeting point" },
    { key: "included", label: "What is included / not included", csv: "included_not_included", kind: "area", req: true, hint: "a short list" },
    { key: "cancel", label: "Cancellation terms", csv: "cancellation_terms", kind: "area", req: true, hint: "exact wording" },
    { key: "code", label: "Referral code", csv: "referral_code", kind: "text", req: true, hint: "exactly as guests will type it" },
    { key: "honored", label: "How the code is honored and counted", csv: "code_honored_and_counted", kind: "area", req: true, hint: "what the guest gets; how you count it" },
    { key: "owner", label: "Fact owner", csv: "fact_owner", kind: "text", req: true, hint: "a role or first name: who keeps this block true" },
    { key: "checked", label: "Last checked", csv: "last_checked", kind: "date", req: true, hint: "the day the fact owner last confirmed this block" },
    { key: "notSupplied", label: "Not supplied (ask the owner)", csv: "not_supplied", kind: "area", req: false, hint: "facts guests ask about that are not written yet" }
  ];
  C.CSV_COLS = C.FIELDS.map(function (f) { return f.csv; });
  C.blank = function () { var b = {}; C.FIELDS.forEach(function (f) { b[f.key] = ""; }); return b; };

  /* ---------- dates (all as YYYY-MM-DD strings, computed in UTC so daylight saving never shifts a day) ---------- */
  function pad(n) { return (n < 10 ? "0" : "") + n; }
  C.isoToday = function (d) { d = d || new Date(); return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()); };
  C.parseISO = function (s) {
    var m = /^\s*(\d{4})-(\d{1,2})-(\d{1,2})\s*$/.exec(String(s || ""));
    if (!m) return null;
    var y = +m[1], mo = +m[2], d = +m[3], t = Date.UTC(y, mo - 1, d), dt = new Date(t);
    if (dt.getUTCFullYear() !== y || dt.getUTCMonth() !== mo - 1 || dt.getUTCDate() !== d) return null;
    return t;
  };
  C.fmt = function (t) { var d = new Date(t); return d.getUTCFullYear() + "-" + pad(d.getUTCMonth() + 1) + "-" + pad(d.getUTCDate()); };
  C.addDays = function (iso, n) { var t = C.parseISO(iso); return t === null ? "" : C.fmt(t + n * 864e5); };
  C.daysBetween = function (a, b) { var x = C.parseISO(a), y = C.parseISO(b); return x === null || y === null ? null : Math.round((y - x) / 864e5); };
  /* accept what spreadsheets turn dates into: 7/22/2026, 2026/07/22, 2026-7-22 */
  C.normDate = function (s) {
    s = str(s);
    if (!s) return "";
    var m = /^(\d{4})[-\/.](\d{1,2})[-\/.](\d{1,2})$/.exec(s);
    if (m && C.parseISO(m[1] + "-" + m[2] + "-" + m[3]) !== null) return C.fmt(C.parseISO(m[1] + "-" + m[2] + "-" + m[3]));
    m = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(s);
    if (m && C.parseISO(m[3] + "-" + m[1] + "-" + m[2]) !== null) return C.fmt(C.parseISO(m[3] + "-" + m[1] + "-" + m[2]));
    return s;
  };

  /* ---------- referral codes ---------- */
  C.normCode = function (s) { return str(s).toUpperCase(); };
  C.looksLikeCode = function (s) { s = C.normCode(s); return /^[A-Z0-9][A-Z0-9_-]{1,39}$/.test(s) && /[A-Z]/.test(s); };
  C.sheetCodes = function (blocks) {
    var map = {};
    (blocks || []).forEach(function (b) { var c = C.normCode(b.code); if (C.looksLikeCode(c) && !map[c]) map[c] = str(b.partner); });
    return map;
  };
  C.levenshtein = function (a, b) {
    a = String(a); b = String(b);
    var prev = [], cur, i, j;
    for (j = 0; j <= b.length; j++) prev[j] = j;
    for (i = 1; i <= a.length; i++) {
      cur = [i];
      for (j = 1; j <= b.length; j++) cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
      prev = cur;
    }
    return prev[b.length];
  };
  C.closestCode = function (code, known) {
    var best = "", bd = 99;
    Object.keys(known || {}).forEach(function (k) { var d = C.levenshtein(code, k); if (d < bd) { bd = d; best = k; } });
    return bd <= Math.max(2, Math.floor(String(code).length / 3)) ? best : "";
  };

  /* ---------- checks on one block ---------- */
  C.blockFlags = function (b, today, all) {
    var f = { missing: [], age: null, stale: false, future: false, badDate: false, dupCode: false };
    C.FIELDS.forEach(function (fd) { if (fd.req && !str(b[fd.key])) f.missing.push(fd.label); });
    var ck = str(b.checked);
    if (ck) {
      var age = C.daysBetween(ck, today);
      if (age === null) f.badDate = true;
      else if (age < 0) f.future = true;
      else { f.age = age; f.stale = age > C.STALE_DAYS; }
    }
    var code = C.normCode(b.code);
    if (C.looksLikeCode(code) && all) f.dupCode = all.some(function (o) { return o !== b && C.normCode(o.code) === code; });
    f.ok = !f.missing.length && !f.stale && !f.future && !f.badDate && !f.dupCode;
    return f;
  };
  C.flagLines = function (f) {
    var out = [];
    if (f.missing.length) out.push({ level: "warn", text: "Empty: " + f.missing.join(", ") + ". The AI step will ask about these instead of guessing." });
    if (f.stale) out.push({ level: "bad", text: "Last checked " + f.age + " days ago (over " + C.STALE_DAYS + "). Ask the fact owner to re-check this block." });
    if (f.future) out.push({ level: "bad", text: "The last-checked date is in the future." });
    if (f.badDate) out.push({ level: "bad", text: "Last checked is not a date. Use YYYY-MM-DD." });
    if (f.dupCode) out.push({ level: "bad", text: "Another partner uses the same referral code. Each code needs to be unique, or the counts cannot be reconciled." });
    if (!out.length) out.push({ level: "ok", text: "Complete" + (f.age !== null ? ", checked " + (f.age === 0 ? "today" : f.age === 1 ? "yesterday" : f.age + " days ago") : "") + "." });
    return out;
  };
  C.sheetSummary = function (blocks, today) {
    var need = [];
    blocks.forEach(function (b) {
      var f = C.blockFlags(b, today, blocks), bits = [];
      if (f.missing.length) bits.push(f.missing.length + " empty field" + (f.missing.length > 1 ? "s" : ""));
      if (f.stale) bits.push("checked " + f.age + " days ago");
      if (f.future || f.badDate) bits.push("check the date");
      if (f.dupCode) bits.push("duplicate code");
      if (bits.length) need.push(C.shortName(b.partner || "Unnamed partner") + ": " + bits.join(", "));
    });
    var n = blocks.length;
    if (!n) return "No partner blocks yet. Add one, or load the fictional example.";
    return n + " partner block" + (n > 1 ? "s" : "") + ". " + (need.length ? "Needs attention: " + need.join("; ") + "." : "All complete and checked within " + C.STALE_DAYS + " days.");
  };
  C.shortName = function (s) { return str(s).replace(/\s*\((?:fictional|FICTIONAL)\)\s*/g, " ").replace(/,\s*Seward\b/, "").trim(); };
  C.isFictional = function (blocks) { return (blocks || []).some(function (b) { return /fictional/i.test((b.partner || "") + " " + (b.notSupplied || "")); }); };
  /* true when a block holds something the user typed (not the fictional example and not empty) */
  C.hasOwnData = function (blocks) {
    return (blocks || []).some(function (b) { return C.FIELDS.some(function (f) { return str(b[f.key]); }); }) && !C.isFictional(blocks);
  };

  /* ---------- exports ---------- */
  function oneLine(s) { return str(s).replace(/\s*\n\s*/g, " "); }
  C.sheetText = function (blocks, opts) {
    opts = opts || {};
    var out = ["SHARED FACT SHEET" + (opts.date ? " (exported " + opts.date + ")" : "")];
    if (C.isFictional(blocks)) out.push("FICTIONAL TEACHING DATA. Replace every block with approved facts from each partner.");
    blocks.forEach(function (b) {
      out.push("");
      C.FIELDS.forEach(function (fd) {
        var v = oneLine(b[fd.key]);
        if (!v) v = fd.req ? "[FILL: " + fd.label.toLowerCase() + "]" : "none listed";
        out.push((fd.key === "partner" ? "PARTNER" : fd.label) + ": " + v);
      });
    });
    return out.join("\n");
  };
  C.sheetMarkdown = function (blocks, opts) {
    opts = opts || {};
    var today = opts.today || C.isoToday(), out = [];
    out.push("# Shared fact sheet", "");
    out.push("Exported " + today + " from the ATIA AI Take-Home Kit, tool 3.b. " + blocks.length + " partner block" + (blocks.length === 1 ? "" : "s") + ".", "");
    if (C.isFictional(blocks)) out.push("> FICTIONAL TEACHING DATA. Bay Light Day Cruises, Mile 12 Kennel and Harbor Kayak Co. are invented. Replace every block with approved facts from each partner.", "");
    var need = [];
    blocks.forEach(function (b) {
      var f = C.blockFlags(b, today, blocks);
      if (!f.ok) C.flagLines(f).forEach(function (l) { need.push("- **" + C.shortName(b.partner || "Unnamed partner") + "**: " + l.text); });
    });
    out.push("## Needs attention", "");
    out.push(need.length ? need.join("\n") : "Nothing. Every block is complete and was checked within " + C.STALE_DAYS + " days.", "");
    blocks.forEach(function (b, i) {
      out.push("## " + (i + 1) + ". " + (str(b.partner) || "[FILL: partner]"), "");
      C.FIELDS.forEach(function (fd) {
        if (fd.key === "partner") return;
        var v = oneLine(b[fd.key]);
        out.push("- **" + fd.label + ":** " + (v || (fd.req ? "[FILL]" : "none listed")));
      });
      out.push("");
    });
    out.push("Each partner's fact owner keeps its block true. AI drafts kits from this sheet; a person approves every kit.");
    return out.join("\n") + "\n";
  };

  /* ---------- CSV ---------- */
  C.parseCSV = function (text) {
    var rows = [], row = [], cell = "", q = false, i, c;
    text = String(text || "").replace(/^\uFEFF/, "");
    for (i = 0; i < text.length; i++) {
      c = text[i];
      if (q) {
        if (c === '"') { if (text[i + 1] === '"') { cell += '"'; i++; } else q = false; }
        else cell += c;
      } else if (c === '"') q = true;
      else if (c === ",") { row.push(cell); cell = ""; }
      else if (c === "\n" || c === "\r") {
        if (c === "\r" && text[i + 1] === "\n") i++;
        row.push(cell); rows.push(row); row = []; cell = "";
      } else cell += c;
    }
    if (cell !== "" || row.length) { row.push(cell); rows.push(row); }
    return rows.filter(function (r) { return r.some(function (x) { return str(x) !== ""; }); });
  };
  /* quote cells that need it; neutralise spreadsheet formulas */
  C.csvCell = function (v) {
    var s = v === undefined || v === null ? "" : String(v);
    if (/^[=+\-@\t\r]/.test(s)) s = "'" + s;
    return /[",\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  };
  C.toCSV = function (header, rows) {
    return [header].concat(rows).map(function (r) { return r.map(C.csvCell).join(","); }).join("\r\n") + "\r\n";
  };
  C.sheetCSV = function (blocks) {
    return C.toCSV(C.CSV_COLS, blocks.map(function (b) { return C.FIELDS.map(function (f) { return str(b[f.key]); }); }));
  };

  function hkey(h) { return str(h).toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, ""); }
  var ALIAS = {};
  C.FIELDS.forEach(function (f) { ALIAS[f.csv] = f.key; ALIAS[hkey(f.label)] = f.key; ALIAS[f.key.toLowerCase()] = f.key; });
  // short forms and the 3.a partner-list columns
  var EXTRA = {
    name: "partner", partner_name: "partner", business: "partner",
    offer: "offer", departure_times: "departures", departures: "departures", times: "departures",
    min_age: "@minage", minimum_age: "@minage", weather_rule: "weather", weather: "weather",
    drive_minutes_from_meeting_point: "@drive", drive_minutes: "@drive", drive_time: "@drive",
    duration_minutes: "@duration", duration: "@duration",
    referral_code: "code", code: "code", fact_owner: "owner", owner: "owner",
    last_checked: "checked", checked: "checked", notes: "@notes", partner_confirmed: "@ignore", confirmed: "@ignore"
  };
  C.fromCSV = function (text) {
    var rows = C.parseCSV(text);
    if (!rows.length) return { blocks: [], error: "The file is empty." };
    var head = rows[0].map(function (h) { var k = hkey(h); return ALIAS[k] || EXTRA[k] || ""; });
    if (head.indexOf("partner") < 0) return { blocks: [], error: "No 'partner' column found. Start from shared-facts-template.csv on this page." };
    var ignored = rows[0].filter(function (h, i) { return !head[i]; }).map(str).filter(Boolean);
    var blocks = rows.slice(1).map(function (r) {
      var b = C.blank(), x = {};
      head.forEach(function (k, i) {
        var v = str(r[i]);
        if (!k || k === "@ignore") return;
        if (k.charAt(0) === "@") x[k] = v; else b[k] = v;
      });
      if (x["@duration"]) b.offer = b.offer ? b.offer.replace(/\.?$/, "") + ", " + x["@duration"] + (/^\d+$/.test(x["@duration"]) ? " minutes." : ".") : x["@duration"] + (/^\d+$/.test(x["@duration"]) ? " minutes" : "");
      if (x["@minage"] && !b.ages) b.ages = /^\d+$/.test(x["@minage"]) ? "Minimum age " + x["@minage"] + "." : x["@minage"];
      if (x["@drive"] && !b.drive) b.drive = /^\d+$/.test(x["@drive"]) ? x["@drive"] + " minutes by car from the host's meeting point." : x["@drive"];
      if (x["@notes"]) b.notSupplied = b.notSupplied ? b.notSupplied + " Notes: " + x["@notes"] : "Notes: " + x["@notes"];
      b.checked = C.normDate(b.checked);
      b.code = str(b.code);
      return b;
    }).filter(function (b) { return str(b.partner) !== ""; });
    var max = 12;
    return {
      blocks: blocks.slice(0, max),
      ignored: ignored,
      error: blocks.length > max ? "Only the first " + max + " partners were loaded." : (blocks.length ? "" : "No rows with a partner name.")
    };
  };

  /* ---------- the fictional example (dates relative to today so the flags always show) ---------- */
  C.demoBlocks = function (today) {
    today = today || C.isoToday();
    var b1 = C.blank(), b2 = C.blank(), b3 = C.blank();
    b1.partner = "Bay Light Day Cruises, Seward (FICTIONAL)";
    b1.offer = "4-hour wildlife and glacier cruise.";
    b1.departures = "Departs 9:00 and 14:00, May 15 to September 15.";
    b1.ages = "Minimum age 4. Capacity 40.";
    b1.weather = "Runs in rain. Cancels only for a marine warning, with a full refund.";
    b1.drive = "Small-boat harbor, a 12-minute walk from the cruise ship dock. Mile 12 Kennel is 15 minutes by car from the harbor.";
    b1.included = "Included: heated enclosed cabin, two restrooms, hot drinks. Not included: lunch.";
    b1.cancel = "Free cancellation until 48 hours before departure; inside 48 hours, no refund.";
    b1.code = "None (host business)";
    b1.honored = "Not applicable: Bay Light sends the kits.";
    b1.owner = "Owner, Bay Light (fictional)";
    b1.checked = C.addDays(today, -9);
    b1.notSupplied = "Group discounts, private charters, pet policy, accessibility of the vessel.";

    b2.partner = "Mile 12 Kennel (FICTIONAL)";
    b2.offer = "Summer sled-dog cart ride, 90 minutes.";
    b2.ages = "Ages 2 and up. Group limits not supplied.";
    b2.weather = "Runs in rain. Cancels when: not supplied.";
    b2.drive = "15 minutes by car from the Bay Light harbor.";
    b2.code = "BAYLIGHT-K";
    b2.owner = "Owner, Mile 12 Kennel (fictional)";
    b2.checked = C.addDays(today, -20);
    b2.notSupplied = "Departure times, group limits, what is included, cancellation terms, what a guest gets with the code.";

    b3.partner = "Harbor Kayak Co. (FICTIONAL)";
    b3.offer = "3-hour guided paddle.";
    b3.departures = "Departs 8:00 and 13:00. Season not supplied.";
    b3.ages = "Minimum age 12. Group limits not supplied.";
    b3.weather = "Cancels in wind over 15 knots.";
    b3.code = "BAYLIGHT-P";
    b3.owner = "Lead guide, Harbor Kayak Co. (fictional)";
    b3.checked = C.addDays(today, -80);
    b3.notSupplied = "Season dates, meeting point, drive time, what is included, cancellation terms, what a guest gets with the code.";
    return [b1, b2, b3];
  };
  C.DEMO_MONTHS = "July: 50 to 65 F, rain on about half of days, about 18 hours of daylight, afternoon wind common in the bay. (FICTIONAL NOTE)";

  /* ---------- the booking queue ---------- */
  C.QUEUE_COLS = ["booking_ref", "booked_on", "arrival", "departure", "send_date", "party", "ages", "product", "status", "drafted_on", "draft_link", "approved_by", "sent_date", "notes"];
  C.TEST_BOOKINGS = [
    { booking_ref: "TEST-001", booked_on: "2027-02-10", arrival: "2027-06-14", departure: "2027-06-16", party: "4", ages: "2 adults; children 6 and 9", product: "Wildlife and glacier cruise, 9:00 on 2027-06-15", status: "queued", notes: "FICTIONAL TEST. Children under 12 rule out the kayak. The 9:00 cruise ends at 13:00." },
    { booking_ref: "TEST-002", booked_on: "2027-03-02", arrival: "2027-06-14", departure: "2027-06-15", party: "2", ages: "2 adults", product: "Wildlife and glacier cruise, 14:00 on 2027-06-14", status: "queued", notes: "FICTIONAL TEST. Same send date as TEST-001: two kits on one run." },
    { booking_ref: "TEST-003", booked_on: "2027-04-18", arrival: "2027-07-08", departure: "2027-07-11", party: "3", ages: "2 adults; teen 13", product: "Wildlife and glacier cruise, 9:00 on 2027-07-09", status: "queued", notes: "FICTIONAL TEST. July: the month note exists." },
    { booking_ref: "TEST-004", booked_on: "2027-08-01", arrival: "2027-08-09", departure: "2027-08-11", party: "2", ages: "2 adults", product: "Wildlife and glacier cruise, 14:00 on 2027-08-10", status: "queued", notes: "FICTIONAL TEST. Booked 8 days out: send_date has already passed, so the next daily run picks it up." },
    { booking_ref: "TEST-005", booked_on: "2027-03-20", arrival: "2027-07-20", departure: "2027-07-22", party: "5", ages: "3 adults; children 4, 7 and 10", product: "Wildlife and glacier cruise, 9:00 on 2027-07-21", status: "canceled", notes: "FICTIONAL TEST. Canceled: the daily run skips it." }
  ];
  C.sendDate = function (arrival) { return C.addDays(arrival, -C.LEAD_DAYS); };
  /* first morning run that drafts the kit: send_date, or the morning after booking if that is later; never if canceled */
  C.firstRun = function (b) {
    if (/cancel/i.test(str(b.status))) return "";
    var s = C.sendDate(b.arrival);
    if (!s) return "";
    var next = b.booked_on ? C.addDays(b.booked_on, 1) : "";
    return next && next > s ? next : s;
  };
  /* the calculator's message for one booked-on / arrival pair */
  C.calcMessage = function (booked, arrival) {
    if (C.parseISO(arrival) === null) return "Enter an arrival date.";
    var bo = C.parseISO(booked) === null ? "" : str(booked);
    if (bo && C.daysBetween(bo, arrival) < 0) return "The arrival is before the booking date. Check both dates.";
    var s = C.sendDate(arrival), fr = C.firstRun({ booked_on: bo, arrival: arrival, status: "queued" }), lead = C.daysBetween(fr, arrival);
    var when = lead > 0 ? lead + " day" + (lead === 1 ? "" : "s") + " before arrival" : lead === 0 ? "on the arrival day" : (-lead) + " day" + (lead === -1 ? "" : "s") + " after arrival";
    var msg = "send_date = " + s + ". The first daily run that drafts it: " + fr + ", " + when + ".";
    if (lead < C.LATE_DAYS) msg += " That is under " + C.LATE_DAYS + " days. Policy choice in this kit: write to the guest yourself, delete the automated draft if one appears, and set the row to sent with a note.";
    return msg;
  };
  C.isDue = function (row, today) {
    return str(row.status).toLowerCase() === "queued" && !!str(row.send_date) && C.parseISO(row.send_date) !== null && row.send_date <= today;
  };
  C.queueCSV = function (rows) {
    return C.toCSV(C.QUEUE_COLS, rows.map(function (r) {
      return C.QUEUE_COLS.map(function (k) { return k === "send_date" ? (r.send_date || C.sendDate(r.arrival)) : str(r[k]); });
    }));
  };
  C.queueFromCSV = function (text) {
    var rows = C.parseCSV(text), head = rows.length ? rows[0].map(hkey) : [];
    return rows.slice(1).map(function (r) { var o = {}; head.forEach(function (k, i) { o[k] = str(r[i]); }); return o; });
  };

  /* ---------- the AI-step prompt ---------- */
  C.PLACEHOLDERS = ["shared_fact_sheet", "month_notes", "arrival", "departure", "party", "ages", "product"];
  C.promptFor = function (tpl, host, n) {
    host = str(host);
    var t = String(tpl);
    if (host && /\.$/.test(host)) t = t.split("[HOST BUSINESS].").join(host); // "Harbor Kayak Co." keeps one period
    // a circle needs at least two businesses; with fewer blocks the prompt keeps [N] for the owner to fill
    return t.split("[HOST BUSINESS]").join(host || "[HOST BUSINESS]").split("[N]").join(+n >= 2 ? String(n) : "[N]");
  };
  C.fill = function (tpl, values) {
    return String(tpl).replace(/\{\{\s*([a-z_]+)\s*\}\}/g, function (m, k) {
      var v = str(values[k]);
      return v || "[FILL: " + k.replace(/_/g, " ") + "]";
    });
  };
  C.monthName = function (iso) {
    var t = C.parseISO(iso);
    return t === null ? "" : ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"][new Date(t).getUTCMonth()];
  };

  /* ---------- privacy guard (guest details do not belong in any of these boxes) ---------- */
  function reEmail() { return /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi; }
  function rePhone() { return /(?:\+?1[\s.-]?)?(?:\(\d{3}\)\s?|\b\d{3}[\s.-]?)\d{3}[\s.-]?\d{4}\b/g; }
  function reCardish() { return /\b(?:\d[ -]?){13,19}\b/g; }
  C.luhn = function (d) {
    var sum = 0, alt = false, i, n;
    for (i = d.length - 1; i >= 0; i--) { n = +d[i]; if (alt) { n *= 2; if (n > 9) n -= 9; } sum += n; alt = !alt; }
    return sum % 10 === 0;
  };
  C.piiHits = function (text) {
    var s = String(text || ""), out = [];
    if (reEmail().test(s)) out.push("an email address");
    if ((s.match(reCardish()) || []).some(function (m) { var d = m.replace(/\D/g, ""); return d.length >= 13 && d.length <= 19 && C.luhn(d); })) out.push("a card number");
    if (rePhone().test(s.replace(/\b\d{4}-\d{2}-\d{2}\b/g, ""))) out.push("a phone number");
    return out;
  };

  /* ---------- check a pasted AI draft (a filter, not a verification) ---------- */
  C.childAges = function (ages) {
    var s = str(ages).replace(/\b\d+\s*adults?\b/gi, " ");
    return (s.match(/\b\d{1,2}\b/g) || []).map(Number);
  };
  C.minAge = function (s) {
    var m = /minimum age\s*(\d{1,2})|ages?\s*(\d{1,2})\s*(?:and up|\+)|(\d{1,2})\s*(?:and up|\+)/i.exec(str(s));
    return m ? +(m[1] || m[2] || m[3]) : null;
  };
  function numbersIn(s) {
    var set = {};
    (String(s || "").match(/\d+(?:[.,]\d+)?/g) || []).forEach(function (n) { set[n.replace(/^0+(?=\d)/, "")] = 1; });
    return set;
  }
  C.checkDraft = function (draft, ctx) {
    ctx = ctx || {};
    var d = String(draft || ""), out = [];
    function add(level, text) { out.push({ level: level, text: text }); }
    if (!str(d)) return [{ level: "info", text: "Paste a draft from your AI tool first." }];
    var blocks = ctx.blocks || [], b = ctx.booking || {};

    var pii = C.piiHits(d);
    if (pii.length) add("bad", "Contains " + pii.join(" and ") + ". Remove guest details. Business contact lines you add yourself are fine.");

    if (d.indexOf(C.DRAFT) >= 0) add("ok", "Marked " + C.DRAFT + ".");
    else add("bad", "The line " + C.DRAFT + " is missing. Treat it as unreviewed; regenerate or add it.");

    var words = (d.match(/\S+/g) || []).length;
    add(words > 400 ? "warn" : "ok", words + " words" + (words > 400 ? ". The prompt asks for under 400." : "."));

    var known = C.sheetCodes(blocks), found = {}, unknown = [];
    (d.match(/\b[A-Z0-9]{2,}(?:-[A-Z0-9]+)+\b/g) || []).forEach(function (c) {
      if (/^\d+(?:-\d+)+$/.test(c)) return; // a date or number range, not a code
      if (known[c]) found[c] = 1; else if (unknown.indexOf(c) < 0) unknown.push(c);
    });
    if (Object.keys(found).length) add("ok", "Referral codes from the sheet: " + Object.keys(found).join(", ") + ".");
    unknown.forEach(function (c) {
      var near = C.closestCode(c, known);
      add("warn", "Code not in the fact sheet: " + c + (near ? " (did it mean " + near + "?)" : "") + ". Fix it before sending.");
    });

    var src = [ctx.sheet || "", ctx.months || "", b.arrival, b.departure, b.party, b.ages, b.product].join("\n");
    var have = numbersIn(src), extra = [];
    var body = d.replace(/^\s*\d+[.)]\s/gm, " ").replace(/\bday\s+\d+\b/gi, " ").replace(/\b[A-Z0-9]{2,}(?:-[A-Z0-9]+)+\b/g, " ").replace(/\[FILL[^\]]*\]/gi, " ");
    Object.keys(numbersIn(body)).forEach(function (n) { if (!have[n] && extra.indexOf(n) < 0) extra.push(n); });
    if (extra.length) add("warn", "Numbers not in your fact sheet, month notes or booking: " + extra.slice(0, 12).join(", ") + (extra.length > 12 ? " and more" : "") + ". Check each one. A worked-out end time can be fine; a new price, distance or time is not.");
    else add("ok", "Every number appears in your facts or the booking.");

    var pr = d.match(/\b(guarantee[ds]?|promise[ds]?|definitely|certainly|you will see|you'll see|always|never cancels?|best)\b/gi);
    if (pr) add("warn", "Promise words: " + pr.filter(function (w, i, a) { return a.indexOf(w) === i; }).join(", ") + ". Do not promise weather, wildlife, availability or prices.");

    var kids = C.childAges(b.ages);
    if (kids.length) {
      blocks.forEach(function (p) {
        var min = C.minAge(p.ages), nm = C.shortName(p.partner);
        if (min === null || !nm) return;
        var young = kids.filter(function (a) { return a < min; });
        var key = nm.split(/\s+/).slice(0, 2).join(" ");
        if (young.length && key && d.toLowerCase().indexOf(key.toLowerCase()) >= 0)
          add("warn", "Mentions " + nm + " (minimum age " + min + ") but the party includes " + (young.length > 1 ? "ages " : "age ") + young.join(" and ") + ". Make sure it is not offered to this party.");
      });
    }

    var fills = (d.match(/\[FILL[^\]]*\]/gi) || []).length;
    if (fills) add("info", fills + " open [FILL] item" + (fills > 1 ? "s" : "") + ". Answer each one, or delete the line, before sending.");
    if (/QUESTIONS FOR THE OWNER/i.test(d)) add("info", "Has a QUESTIONS FOR THE OWNER list. Answer it, then delete it from the guest copy.");
    add("info", "This check is a filter, not a verification. One person still reads every line before sending.");
    return out;
  };

  /* ---------- referral-code reconciliation ---------- */
  C.parseCounts = function (text, known) {
    known = known || {};
    var counts = {}, order = [], bad = [], dup = [];
    String(text || "").split(/\r?\n/).forEach(function (line) {
      var raw = str(line);
      if (!raw) return;
      var toks = raw.split(/[\s,;:|\t=]+/).filter(Boolean);
      var code = "", n = null, i;
      // prefer a code from the fact sheet, then a mixed code such as AB-12, then any code-like word
      for (i = 0; i < toks.length && !code; i++) if (known[C.normCode(toks[i])]) code = C.normCode(toks[i]);
      for (i = 0; i < toks.length && !code; i++) if (C.looksLikeCode(toks[i]) && /[-_0-9]/.test(toks[i])) code = C.normCode(toks[i]);
      for (i = 0; i < toks.length && !code; i++) if (C.looksLikeCode(toks[i])) code = C.normCode(toks[i]);
      for (i = toks.length - 1; i >= 0; i--) if (/^\d+$/.test(toks[i])) { n = +toks[i]; break; }
      if (n === null && code && /^(CODE|REFERRAL|REFERRAL_CODE|COUNT)$/.test(code)) return; // a header line
      if (!code || n === null) { bad.push(raw); return; }
      if (counts[code] !== undefined) { counts[code] += n; if (dup.indexOf(code) < 0) dup.push(code); }
      else { counts[code] = n; order.push(code); }
    });
    return { counts: counts, order: order, bad: bad, dup: dup };
  };
  C.normName = function (s) { return C.shortName(s).toLowerCase().replace(/[^a-z0-9]+/g, " ").trim(); };
  C.sameBusiness = function (a, b) {
    a = C.normName(a); b = C.normName(b);
    if (!a || !b) return false;
    if (a === b || a.indexOf(b) === 0 || b.indexOf(a) === 0) return true;
    var wa = a.split(" ").slice(0, 2).join(" "), wb = b.split(" ").slice(0, 2).join(" ");
    return wa.length > 4 && wa === wb;
  };
  C.slug = function (s) { return C.normName(s).replace(/\s+/g, "_") || "list"; };
  C.reconcile = function (lists, blocks) {
    var known = C.sheetCodes(blocks), hasKnown = Object.keys(known).length > 0;
    var parsed = lists.map(function (l) { return C.parseCounts(l.text, known); });
    var codes = [];
    parsed.forEach(function (p) { p.order.forEach(function (c) { if (codes.indexOf(c) < 0) codes.push(c); }); });
    var rows = codes.map(function (code) {
      var counts = parsed.map(function (p) { return p.counts[code] === undefined ? null : p.counts[code]; });
      var rep = counts.filter(function (x) { return x !== null; });
      var honoredBy = known[code] || "";
      var r = { code: code, honoredBy: honoredBy, counts: counts, diff: "", status: "", agreed: "", note: "" };
      var hi = Math.max.apply(null, rep), lo = Math.min.apply(null, rep);
      if (hasKnown && !honoredBy) {
        var near = C.closestCode(code, known);
        r.status = "Unknown code";
        r.note = "Not in the shared fact sheet." + (near ? " Closest: " + near + ". Check for a typo." : "");
      } else if (rep.length < 2) {
        r.status = "One count only";
        var who = lists.filter(function (l, i) { return counts[i] === null; }).map(function (l) { return C.shortName(l.name) || "the other business"; });
        r.note = who.length ? "Ask " + who.join(" or ") + " for a count." : "Add a second count to compare.";
      } else if (hi === lo) {
        r.status = "Match"; r.agreed = lo; r.diff = 0;
      } else {
        r.status = "Mismatch"; r.diff = hi - lo;
        r.note = "Counts differ by " + (hi - lo) + ". Compare booking dates for this code, then agree a number.";
      }
      if (honoredBy && r.status !== "Unknown code" && !lists.some(function (l, i) { return counts[i] !== null && C.sameBusiness(l.name, honoredBy); }))
        r.note = (r.note ? r.note + " " : "") + "No count yet from " + C.shortName(honoredBy) + ", which honors this code.";
      return r;
    });
    var sum = { codes: rows.length, matched: 0, open: 0, agreedTotal: 0, unknown: 0 };
    rows.forEach(function (r) {
      if (r.status === "Match") { sum.matched++; sum.agreedTotal += r.agreed; } else sum.open++;
      if (r.status === "Unknown code") sum.unknown++;
    });
    var bad = [], dup = [];
    parsed.forEach(function (p, i) {
      p.bad.forEach(function (x) { bad.push((C.shortName(lists[i].name) || "Count " + (i + 1)) + ": " + x); });
      p.dup.forEach(function (x) { dup.push((C.shortName(lists[i].name) || "Count " + (i + 1)) + ": " + x); });
    });
    return { rows: rows, summary: sum, badLines: bad, dupLines: dup };
  };
  C.attachRate = function (agreed, kits) {
    kits = +kits;
    if (!(kits > 0)) return null;
    return Math.round((agreed / kits) * 1000) / 10;
  };
  C.reconCSV = function (res, lists, month) {
    var head = ["month", "code", "honored_by"].concat(lists.map(function (l, i) { return "count_" + (C.slug(l.name) === "list" ? "list_" + (i + 1) : C.slug(l.name)); }))
      .concat(["difference", "status", "agreed_count", "agreed_by", "notes"]);
    return C.toCSV(head, res.rows.map(function (r) {
      return [str(month), r.code, r.honoredBy].concat(r.counts.map(function (c) { return c === null ? "" : c; }))
        .concat([r.diff === "" ? "" : r.diff, r.status, r.agreed === "" ? "" : r.agreed, "", r.note]);
    }));
  };
  C.reconText = function (res, lists, month, kits) {
    var out = ["Referral code reconciliation" + (str(month) ? ", " + str(month) : "")];
    res.rows.forEach(function (r) {
      var bits = [];
      r.counts.forEach(function (c, i) { if (c !== null) bits.push((C.shortName(lists[i].name) || "Count " + (i + 1)) + " " + c); });
      out.push(r.code + (r.honoredBy ? " (" + C.shortName(r.honoredBy) + ")" : "") + ": " + bits.join(", ") + ". " + r.status + "." + (r.note ? " " + r.note : ""));
    });
    out.push("Agreed cross-referrals: " + res.summary.agreedTotal + ". Codes still to agree: " + res.summary.open + ".");
    var rate = C.attachRate(res.summary.agreedTotal, kits);
    if (rate !== null) out.push("Kits sent: " + kits + ". Attach rate from agreed codes: " + rate + " partner bookings per 100 kits.");
    return out.join("\n");
  };
  C.DEMO_RECON = {
    month: "2027-07", kits: "40",
    lists: [
      { name: "Bay Light Day Cruises (FICTIONAL)", text: "BAYLIGHT-K, 14\nBAYLIGHT-P, 6" },
      { name: "Mile 12 Kennel (FICTIONAL)", text: "BAYLIGHT-K, 12" },
      { name: "Harbor Kayak Co. (FICTIONAL)", text: "BAYLIGHT-P, 6\nBAYLITE-P, 1" }
    ]
  };

  if (typeof module !== "undefined" && module.exports) { module.exports = C; return; }
  root.CIRCLE = C;

  /* ======================================================================
   * Page wiring (browser only)
   * ==================================================================== */
  var KIT = root.KIT || {};
  var store = KIT.store || { get: function () { return null; }, set: function () { }, del: function () { } };
  var K = { blocks: "atiakit:3b:blocks", months: "atiakit:3b:months", host: "atiakit:3b:host", dry: "atiakit:3b:dry", recon: "atiakit:3b:recon" };
  var $ = function (id) { return document.getElementById(id); };
  var state = { blocks: [], months: "", host: "" };
  var TODAY = C.isoToday();

  function el(tag, attrs, text) {
    var e = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      if (k === "class") e.className = attrs[k]; else if (k in e && k !== "list") e[k] = attrs[k]; else e.setAttribute(k, attrs[k]);
    });
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function status(id, msg) {
    var box = $(id); if (!box) return;
    box.textContent = msg; clearTimeout(box._t); box._t = setTimeout(function () { box.textContent = ""; }, 7000);
  }
  function save() { store.set(K.blocks, state.blocks); store.set(K.months, state.months); store.set(K.host, state.host); }
  /* copy with a message that says where the text goes next (same fallbacks as kit.js) */
  function copyText(text, statusId, okMsg) {
    function done(ok) { status(statusId, ok ? okMsg : "Select the text and press Ctrl+C (Cmd+C on a Mac)."); }
    function fallback() {
      var a = document.createElement("textarea");
      a.value = text; a.setAttribute("readonly", ""); a.style.position = "fixed"; a.style.left = "-10000px";
      document.body.appendChild(a); a.select();
      var ok = false; try { ok = document.execCommand("copy"); } catch (e) { }
      a.remove(); done(ok);
    }
    if (navigator.clipboard && root.isSecureContext) navigator.clipboard.writeText(text).then(function () { done(true); }, fallback);
    else fallback();
  }
  var timer = null;
  function soon(fn) { clearTimeout(timer); timer = setTimeout(fn, 120); }
  /* short textareas grow to fit their text, so nothing is hidden on a phone */
  function grow(t) {
    if (!t || t.tagName !== "TEXTAREA" || !t.offsetParent) return;
    t.style.height = "auto"; t.style.height = (t.scrollHeight + 2) + "px";
  }
  function growAll(rootEl) { Array.prototype.forEach.call((rootEl || document).querySelectorAll("textarea.short"), grow); }

  /* ---------- fact-sheet builder ---------- */
  function pills(f) {
    var span = el("span", { class: "pills" });
    if (f.ok) span.appendChild(el("span", { class: "pill" }, "Complete"));
    if (f.missing.length) span.appendChild(el("span", { class: "pill amber" }, f.missing.length + " empty"));
    if (f.stale) span.appendChild(el("span", { class: "pill red" }, "Re-check: " + f.age + " days"));
    if (f.future || f.badDate) span.appendChild(el("span", { class: "pill red" }, "Check date"));
    if (f.dupCode) span.appendChild(el("span", { class: "pill red" }, "Duplicate code"));
    return span;
  }
  function blockHead(i) {
    var b = state.blocks[i], f = C.blockFlags(b, TODAY, state.blocks), s = $("pb" + i + "-sum");
    if (!s) return;
    s.textContent = "";
    s.appendChild(el("span", { class: "pname" }, (i + 1) + ". " + (C.shortName(b.partner) || "New partner")));
    s.appendChild(document.createTextNode(" "));
    s.appendChild(pills(f));
    C.FIELDS.forEach(function (fd) {
      var inp = $("pb" + i + "-" + fd.key);
      if (inp) inp.classList.toggle("empty", fd.req && !str(b[fd.key]));
    });
    var ul = $("pb" + i + "-flags");
    ul.textContent = "";
    C.flagLines(f).forEach(function (l) { var li = el("li", { class: l.level }); li.appendChild(el("span", { class: "tag" }, l.level === "ok" ? "OK" : l.level === "warn" ? "Fill" : "Fix")); li.appendChild(document.createTextNode(" " + l.text)); ul.appendChild(li); });
  }
  function renderBlocks(focusIdx) {
    var box = $("blocks");
    box.textContent = "";
    state.blocks.forEach(function (b, i) {
      var det = el("details", { class: "pblock", id: "pb" + i });
      det.open = true;
      det.appendChild(el("summary", { id: "pb" + i + "-sum" }));
      var body = el("div", { class: "pbody" }), grid = el("div", { class: "pfields" });
      C.FIELDS.forEach(function (fd) {
        var wrap = el("div", { class: "pf" + (fd.kind === "area" ? " wide" : "") });
        var id = "pb" + i + "-" + fd.key;
        var lab = el("label", { htmlFor: id }, fd.label + (fd.req ? "" : " "));
        lab.appendChild(el("small", null, " (" + fd.hint + (fd.req ? "" : "; optional") + ")"));
        wrap.appendChild(lab);
        var inp;
        if (fd.kind === "area") inp = el("textarea", { id: id, rows: 2, class: "short" });
        else inp = el("input", { id: id, type: fd.kind === "date" ? "date" : "text", autocomplete: "off" });
        inp.value = b[fd.key] || "";
        inp.setAttribute("data-i", i); inp.setAttribute("data-k", fd.key);
        if (fd.req) inp.setAttribute("aria-required", "true");
        wrap.appendChild(inp);
        grid.appendChild(wrap);
      });
      body.appendChild(grid);
      var ul = el("ul", { class: "chk", id: "pb" + i + "-flags", "aria-label": "Checks for this block" });
      body.appendChild(ul);
      var bt = el("div", { class: "btns tight" });
      bt.appendChild(el("button", { type: "button", class: "danger small", "data-remove": String(i) }, "Remove this partner"));
      body.appendChild(bt);
      det.appendChild(body);
      box.appendChild(det);
      blockHead(i);
    });
    growAll(box);
    if (focusIdx !== undefined && $("pb" + focusIdx + "-partner")) $("pb" + focusIdx + "-partner").focus();
    refreshSheet();
  }
  function refreshSheet() {
    var sum = C.sheetSummary(state.blocks, TODAY);
    if ($("sheet-summary").textContent !== sum) $("sheet-summary").textContent = sum;
    $("sheet-text").textContent = C.sheetText(state.blocks, { date: TODAY });
    refreshPrompt();
    refreshDry();
    if (recon.lists.length) refreshRecon(); // known codes and "honored by" come from the sheet
  }

  function onBlockInput(e) {
    var t = e.target, i = t.getAttribute("data-i"), k = t.getAttribute("data-k");
    if (i === null || !k || !state.blocks[+i]) return;
    state.blocks[+i][k] = t.value;
    save();
    soon(function () { state.blocks.forEach(function (b, j) { blockHead(j); }); refreshSheet(); });
  }

  /* ---------- prompt ---------- */
  function hostName() { return str(state.host) || (state.blocks[0] ? C.shortName(state.blocks[0].partner) : ""); }
  function promptTpl() { return KIT.tplText ? KIT.tplText("tpl-ai") : ($("tpl-ai") ? $("tpl-ai").innerHTML : ""); }
  function refreshPrompt() {
    $("prompt-ai").textContent = C.promptFor(promptTpl(), hostName(), state.blocks.length || "");
    if ($("host") && document.activeElement !== $("host") && !state.host) $("host").placeholder = hostName() || "Your business name";
  }

  /* ---------- dry run with a fictional booking ---------- */
  var DRY = ["arrival", "departure", "party", "ages", "product"];
  function dryValues() { var v = {}; DRY.forEach(function (k) { v[k] = $("dry-" + k).value; }); return v; }
  function refreshDry() {
    if (!$("dry-prompt")) return;
    var v = dryValues();
    v.shared_fact_sheet = C.sheetText(state.blocks, { date: TODAY });
    v.month_notes = state.months;
    $("dry-prompt").textContent = C.fill(C.promptFor(promptTpl(), hostName(), state.blocks.length || ""), v);
    var m = C.monthName(v.arrival), has = m && new RegExp("^\\s*" + m.slice(0, 3), "im").test(state.months || "");
    $("dry-month").textContent = m ? (has ? "The month notes have a line for " + m + "." : "No month note for " + m + ": the AI step will ask for one as [FILL].") : "";
    var pii = C.piiHits(DRY.map(function (k) { return v[k]; }).join("\n"));
    $("dry-pii").textContent = pii.length ? "This booking contains " + pii.join(" and ") + ". Remove guest details: the AI step gets dates, party and product only." : "";
    store.set(K.dry, { sel: $("dry-booking").value, v: dryValues() });
  }
  function setDry(b) { DRY.forEach(function (k) { $("dry-" + k).value = b[k] || ""; }); refreshDry(); }

  /* ---------- queue table and calculator ---------- */
  function renderQueue() {
    var tb = $("queue-rows"); if (!tb) return;
    tb.textContent = "";
    C.TEST_BOOKINGS.forEach(function (b) {
      var tr = el("tr"), fr = C.firstRun(b);
      [b.booking_ref, b.booked_on, b.arrival, C.sendDate(b.arrival), b.status].forEach(function (v) { tr.appendChild(el("td", null, v)); });
      var td = el("td");
      if (fr) { td.textContent = fr + (fr !== C.sendDate(b.arrival) ? " (late booking: next run after booking)" : ""); }
      else td.textContent = "Never (canceled)";
      tr.appendChild(td);
      tr.appendChild(el("td", null, b.notes.replace(/^FICTIONAL TEST\.\s*/, "")));
      tb.appendChild(tr);
    });
  }
  function refreshCalc() {
    $("calc-out").textContent = C.calcMessage($("calc-booked").value, $("calc-arrival").value);
  }

  /* ---------- draft check ---------- */
  function runCheck() {
    if (!str($("draft-in").value)) { $("draft-results").textContent = ""; status("st-check", "Paste a draft from your AI tool first."); $("draft-in").focus(); return; }
    var res = C.checkDraft($("draft-in").value, { blocks: state.blocks, months: state.months, sheet: C.sheetText(state.blocks), booking: dryValues() });
    var ul = $("draft-results"); ul.textContent = "";
    var bad = 0, warn = 0;
    res.forEach(function (r) {
      if (r.level === "bad") bad++; if (r.level === "warn") warn++;
      var li = el("li", { class: r.level });
      li.appendChild(el("span", { class: "tag" }, r.level === "ok" ? "OK" : r.level === "bad" ? "Fix" : r.level === "warn" ? "Check" : "Note"));
      li.appendChild(document.createTextNode(" " + r.text));
      ul.appendChild(li);
    });
    status("st-check", bad ? bad + " item" + (bad > 1 ? "s" : "") + " to fix, " + warn + " to check." : warn ? warn + " item" + (warn > 1 ? "s" : "") + " to check. Nothing blocking." : "No problems found by the filter. A person still reads every line.");
  }

  /* ---------- reconciliation ---------- */
  var recon = { lists: [], month: "", kits: "" };
  function defaultLists() {
    var names = state.blocks.map(function (b) { return str(b.partner); }).filter(Boolean);
    if (names.length < 2) names = ["", ""];
    return names.slice(0, 6).map(function (n) { return { name: n, text: "" }; });
  }
  function saveRecon() { store.set(K.recon, recon); }
  function renderLists() {
    var box = $("recon-lists"); box.textContent = "";
    recon.lists.forEach(function (l, i) {
      var fs = el("fieldset", { class: "rlist" });
      fs.appendChild(el("legend", null, "Count " + (i + 1)));
      fs.appendChild(el("label", { htmlFor: "rl" + i + "-name" }, "Counted by"));
      var nm = el("input", { type: "text", id: "rl" + i + "-name", autocomplete: "off" }); nm.value = l.name; nm.setAttribute("data-r", i); nm.setAttribute("data-f", "name");
      fs.appendChild(nm);
      var lab = el("label", { htmlFor: "rl" + i + "-text" }, "Codes and counts ");
      lab.appendChild(el("small", null, "(one per line, for example BAYLIGHT-K, 12)"));
      fs.appendChild(lab);
      var ta = el("textarea", { id: "rl" + i + "-text", rows: 3, class: "short mono" }); ta.value = l.text; ta.setAttribute("data-r", i); ta.setAttribute("data-f", "text");
      fs.appendChild(ta);
      var bt = el("div", { class: "btns tight" });
      if (recon.lists.length > 1) bt.appendChild(el("button", { type: "button", class: "ghost small", "data-rremove": String(i) }, "Remove this count"));
      fs.appendChild(bt);
      box.appendChild(fs);
    });
    growAll(box);
    refreshRecon();
  }
  function refreshRecon() {
    var res = C.reconcile(recon.lists, state.blocks), tb = $("recon-table");
    tb.textContent = "";
    var thead = el("thead"), hr = el("tr");
    ["Code", "Honored by"].concat(recon.lists.map(function (l, i) { return C.shortName(l.name) || "Count " + (i + 1); })).concat(["Difference", "Status", "Notes"]).forEach(function (h) { hr.appendChild(el("th", { scope: "col" }, h)); });
    thead.appendChild(hr); tb.appendChild(thead);
    var tbody = el("tbody");
    if (!res.rows.length) { var tr0 = el("tr"), td0 = el("td", { colSpan: 5 + recon.lists.length }, "No codes yet. Paste counts above, or load the fictional example."); tr0.appendChild(td0); tbody.appendChild(tr0); }
    res.rows.forEach(function (r) {
      var tr = el("tr");
      tr.appendChild(el("td", null, r.code));
      tr.appendChild(el("td", null, C.shortName(r.honoredBy) || "?"));
      r.counts.forEach(function (c) { tr.appendChild(el("td", { class: "num" }, c === null ? "" : String(c))); });
      tr.appendChild(el("td", { class: "num" }, r.diff === "" ? "" : String(r.diff)));
      var st = el("td"); st.appendChild(el("span", { class: "pill " + (r.status === "Match" ? "" : r.status === "Mismatch" || r.status === "Unknown code" ? "red" : "amber") }, r.status)); tr.appendChild(st);
      tr.appendChild(el("td", null, r.note));
      tbody.appendChild(tr);
    });
    tb.appendChild(tbody);
    var s = res.summary, rate = C.attachRate(s.agreedTotal, recon.kits), msg = [];
    if (res.rows.length) {
      msg.push(s.codes + " code" + (s.codes > 1 ? "s" : "") + ": " + s.matched + " match, " + s.open + " still to agree.");
      msg.push("Agreed cross-referrals: " + s.agreedTotal + ".");
      if (rate !== null) msg.push("Attach rate from agreed codes: " + rate + " partner bookings per 100 kits (" + s.agreedTotal + " of " + recon.kits + ").");
      else msg.push("Enter kits sent to see the attach rate.");
    }
    if (res.badLines.length) msg.push("Lines not read: " + res.badLines.join(" | ") + ".");
    if (res.dupLines.length) msg.push("Codes listed twice in one count were added together: " + res.dupLines.join(", ") + ".");
    $("recon-summary").textContent = msg.join(" ");
    var pii = C.piiHits(recon.lists.map(function (l) { return l.text; }).join("\n"));
    $("recon-pii").textContent = pii.length ? "These counts contain " + pii.join(" and ") + ". Paste codes and numbers only." : "";
    return res;
  }

  /* ---------- start ---------- */
  document.addEventListener("DOMContentLoaded", function () {
    if (!$("blocks")) return;
    var saved = store.get(K.blocks);
    state.blocks = Array.isArray(saved) ? saved.filter(function (b) { return b && typeof b === "object"; }).map(function (b) { var x = C.blank(); Object.keys(x).forEach(function (k) { x[k] = b[k] === undefined || b[k] === null ? "" : String(b[k]); }); return x; }) : C.demoBlocks(TODAY);
    if (!state.blocks.length) state.blocks = [C.blank()];
    var sm = store.get(K.months); state.months = typeof sm === "string" ? sm : C.DEMO_MONTHS;
    var sh = store.get(K.host); state.host = typeof sh === "string" ? sh : "";
    $("month-notes").value = state.months;
    $("host").value = state.host;

    $("blocks").addEventListener("input", onBlockInput);
    $("blocks").addEventListener("change", onBlockInput);
    $("blocks").addEventListener("click", function (e) {
      var b = e.target.closest("[data-remove]"); if (!b) return;
      var i = +b.getAttribute("data-remove"), nm = C.shortName(state.blocks[i].partner) || "this partner";
      if (!root.confirm("Remove " + nm + " from the shared fact sheet?")) return;
      state.blocks.splice(i, 1); save(); renderBlocks();
      status("st-sheet", "Removed " + nm + ".");
    });
    $("add-partner").addEventListener("click", function () {
      if (state.blocks.length >= 12) { status("st-sheet", "Twelve blocks is the limit here. A circle works best with three to five."); return; }
      state.blocks.push(C.blank()); save(); renderBlocks(state.blocks.length - 1);
      status("st-sheet", "Added a blank partner block. Fill it with that partner's approved facts.");
    });
    $("load-demo").addEventListener("click", function () {
      if (C.hasOwnData(state.blocks) && !root.confirm("Replace your blocks with the fictional example?")) return;
      state.blocks = C.demoBlocks(TODAY); state.months = C.DEMO_MONTHS; $("month-notes").value = state.months;
      save(); renderBlocks();
      status("st-sheet", "Fictional example loaded. Two partners have gaps and one is overdue for a re-check, on purpose.");
    });
    $("clear-all").addEventListener("click", function () {
      if (!root.confirm("Clear every partner block and the month notes in this browser?")) return;
      state.blocks = [C.blank()]; state.months = ""; $("month-notes").value = "";
      save(); renderBlocks(0); status("st-sheet", "Cleared. One blank block is ready.");
    });
    $("import-btn").addEventListener("click", function () { $("import-file").click(); });
    $("import-file").addEventListener("change", function () {
      var f = this.files && this.files[0]; if (!f) return;
      var rd = new FileReader();
      rd.onload = function () {
        var r = C.fromCSV(String(rd.result || ""));
        if (!r.blocks.length) { status("st-sheet", r.error || "Nothing to import."); return; }
        if (C.hasOwnData(state.blocks) && !root.confirm("Replace your " + state.blocks.length + " partner block" + (state.blocks.length > 1 ? "s" : "") + " with the " + r.blocks.length + " from " + f.name + "?")) { status("st-sheet", "Import canceled. Your blocks are unchanged."); return; }
        state.blocks = r.blocks; save(); renderBlocks();
        status("st-sheet", "Imported " + r.blocks.length + " partner block" + (r.blocks.length > 1 ? "s" : "") + " from " + f.name + "." + (r.error ? " " + r.error : "") + (r.ignored && r.ignored.length ? " Columns not used: " + r.ignored.join(", ") + "." : ""));
      };
      rd.onerror = function () { status("st-sheet", "Could not read that file."); };
      rd.readAsText(f);
      this.value = "";
    });
    $("save-csv").addEventListener("click", function () {
      KIT.download && KIT.download("shared-facts.csv", "\uFEFF" + C.sheetCSV(state.blocks), "text/csv");
      status("st-export", "Saved shared-facts.csv to your downloads. Open it in Excel or Google Sheets; import it here again after edits.");
    });
    $("save-md").addEventListener("click", function () {
      KIT.download && KIT.download("shared-facts.md", C.sheetMarkdown(state.blocks, { today: TODAY }), "text/markdown");
      status("st-export", "Saved shared-facts.md to your downloads. Paste it into a shared Google Doc, or print it for partners to sign off.");
    });
    $("month-notes").addEventListener("input", function () { state.months = this.value; save(); soon(refreshDry); });
    $("host").addEventListener("input", function () { state.host = this.value; save(); soon(function () { refreshPrompt(); refreshDry(); }); });

    /* dry run */
    var sel = $("dry-booking");
    C.TEST_BOOKINGS.forEach(function (b, i) { sel.appendChild(el("option", { value: String(i) }, b.booking_ref + ": " + b.ages + ", arriving " + b.arrival + (b.status === "canceled" ? " (canceled)" : ""))); });
    sel.appendChild(el("option", { value: "own" }, "My own fictional booking (type below)"));
    var sd = store.get(K.dry);
    if (sd && typeof sd === "object" && sd.v && typeof sd.v === "object") {
      sel.value = sd.sel && sel.querySelector('option[value="' + String(sd.sel).replace(/[^\w]/g, "") + '"]') ? String(sd.sel) : "own";
      setDry(sd.v);
    } else setDry(C.TEST_BOOKINGS[0]);
    sel.addEventListener("change", function () { if (this.value !== "own") setDry(C.TEST_BOOKINGS[+this.value]); });
    DRY.forEach(function (k) { $("dry-" + k).addEventListener("input", function () { sel.value = "own"; soon(refreshDry); }); });
    function copyDry() { KIT.copy($("dry-prompt").textContent, $("dry-copy")); $("dry-anyway").hidden = true; }
    $("dry-copy").addEventListener("click", function () {
      var v = dryValues(), hits = C.piiHits(DRY.map(function (k) { return v[k]; }).join("\n"));
      if (hits.length) { $("dry-anyway").hidden = false; status("st-dry", "Not copied: the booking contains " + hits.join(" and ") + ". Remove it, or confirm it is fictional."); return; }
      copyDry();
    });
    $("dry-anyway").addEventListener("click", copyDry);

    /* draft check */
    $("draft-check").addEventListener("click", runCheck);
    $("draft-clear").addEventListener("click", function () { $("draft-in").value = ""; $("draft-results").textContent = ""; status("st-check", "Cleared."); });

    /* queue + calculator */
    renderQueue();
    $("calc-booked").value = TODAY; $("calc-arrival").value = C.addDays(TODAY, 45);
    $("calc-booked").addEventListener("input", refreshCalc); $("calc-arrival").addEventListener("input", refreshCalc);
    $("calc-booked").addEventListener("change", refreshCalc); $("calc-arrival").addEventListener("change", refreshCalc);
    refreshCalc();

    /* reconciliation */
    var sr = store.get(K.recon);
    recon = sr && Array.isArray(sr.lists) && sr.lists.length ? sr : { lists: defaultLists(), month: "", kits: "" };
    $("recon-month").value = recon.month || ""; $("recon-kits").value = recon.kits || "";
    $("recon-lists").addEventListener("input", function (e) {
      var i = e.target.getAttribute("data-r"), f = e.target.getAttribute("data-f");
      if (i === null || !recon.lists[+i]) return;
      recon.lists[+i][f] = e.target.value; saveRecon(); soon(refreshRecon);
    });
    $("recon-lists").addEventListener("click", function (e) {
      var b = e.target.closest("[data-rremove]"); if (!b) return;
      recon.lists.splice(+b.getAttribute("data-rremove"), 1); saveRecon(); renderLists();
      status("st-recon", "Removed that count.");
    });
    $("recon-add").addEventListener("click", function () {
      if (recon.lists.length >= 8) { status("st-recon", "Eight counts is the limit here."); return; }
      recon.lists.push({ name: "", text: "" }); saveRecon(); renderLists();
      $("rl" + (recon.lists.length - 1) + "-name").focus();
    });
    $("recon-demo").addEventListener("click", function () {
      recon = JSON.parse(JSON.stringify(C.DEMO_RECON)); saveRecon();
      $("recon-month").value = recon.month; $("recon-kits").value = recon.kits; renderLists();
      status("st-recon", "Fictional July counts loaded. One code matches, one does not, and one has a typo.");
    });
    $("recon-clear").addEventListener("click", function () {
      recon = { lists: defaultLists(), month: "", kits: "" }; saveRecon();
      $("recon-month").value = ""; $("recon-kits").value = ""; renderLists(); status("st-recon", "Cleared.");
    });
    $("recon-month").addEventListener("input", function () { recon.month = this.value; saveRecon(); });
    $("recon-kits").addEventListener("input", function () { recon.kits = this.value; saveRecon(); soon(refreshRecon); });
    $("recon-save").addEventListener("click", function () {
      var res = C.reconcile(recon.lists, state.blocks);
      if (!res.rows.length) { status("st-recon", "Nothing to save yet."); return; }
      var name = "referral-reconciliation" + (str(recon.month) ? "-" + str(recon.month).replace(/[^0-9A-Za-z-]+/g, "") : "") + ".csv";
      KIT.download && KIT.download(name, "\uFEFF" + C.reconCSV(res, recon.lists, recon.month), "text/csv");
      status("st-recon", "Saved " + name + " to your downloads.");
    });
    $("recon-copy").addEventListener("click", function () {
      var res = C.reconcile(recon.lists, state.blocks);
      if (!res.rows.length) { status("st-recon", "Nothing to copy yet."); return; }
      copyText(C.reconText(res, recon.lists, recon.month, recon.kits), "st-recon", "Copied. Paste it into your monthly email to the partners.");
    });
    $("copy-sheet").addEventListener("click", function () {
      copyText($("sheet-text").textContent, "st-export", "Copied. Paste it into cell B2 of the facts tab, or into the dry run's AI tool.");
    });
    $("copy-prompt").addEventListener("click", function () {
      copyText($("prompt-ai").textContent, "st-prompt", "Copied. Paste it into the AI step in Zapier or Make, then map each {{placeholder}}.");
    });
    $("copy-approve").addEventListener("click", function () {
      copyText($("approve-list").textContent, "st-approve", "Copied. Keep it next to Gmail Drafts while you approve kits.");
    });

    /* forget everything */
    $("forget").addEventListener("click", function () {
      if (!root.confirm("Forget everything this page saved in this browser?")) return;
      Object.keys(K).forEach(function (k) { store.del(K[k]); });
      status("st-forget", "Done. Reload the page to start again from the fictional example.");
    });

    document.addEventListener("input", function (e) { if (e.target.matches && e.target.matches("textarea.short")) grow(e.target); });
    $("blocks").addEventListener("toggle", function (e) { growAll(e.target); }, true);
    var rt = null;
    root.addEventListener("resize", function () { clearTimeout(rt); rt = setTimeout(function () { growAll(); }, 200); });

    renderBlocks();
    renderLists();
    growAll();
  });
})(typeof window !== "undefined" ? window : this);
