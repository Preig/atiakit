/* 3.a The AI trip kit: pure logic, no page access, no network.
 * Used by index.html (as window.TripKit) and by the Node tests in dev/ (require).
 * Everything here is deterministic: the same inputs always give the same checks.
 */
(function (root) {
  "use strict";
  var T = {};

  var MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  var DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  var DAY_MS = 86400000;
  T.MONTHS = MONTHS;

  function pad(n) { return (n < 10 ? "0" : "") + n; }
  function str(v) { return v === undefined || v === null ? "" : String(v).trim(); }
  function intOrNull(v) {
    var s = str(v);
    if (!/^\d{1,4}$/.test(s)) return null;
    return parseInt(s, 10);
  }
  T.intOrNull = intOrNull;
  function joinAnd(list) {
    if (list.length <= 1) return list.join("");
    if (list.length === 2) return list[0] + " and " + list[1];
    return list.slice(0, -1).join(", ") + " and " + list[list.length - 1];
  }
  T.joinAnd = joinAnd;

  /* ---------- dates (UTC, so daylight saving never shifts a day) ---------- */
  T.parseISO = function (s) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(str(s));
    if (!m) return null;
    var y = +m[1], mo = +m[2], d = +m[3];
    var t = Date.UTC(y, mo - 1, d), dt = new Date(t);
    if (dt.getUTCFullYear() !== y || dt.getUTCMonth() !== mo - 1 || dt.getUTCDate() !== d) return null;
    return t;
  };
  T.iso = function (t) { var d = new Date(t); return d.getUTCFullYear() + "-" + pad(d.getUTCMonth() + 1) + "-" + pad(d.getUTCDate()); };
  T.addDays = function (iso, n) { var t = T.parseISO(iso); return t === null ? null : T.iso(t + n * DAY_MS); };
  /* b minus a, in whole days */
  T.diffDays = function (a, b) {
    var ta = T.parseISO(a), tb = T.parseISO(b);
    if (ta === null || tb === null) return null;
    return Math.round((tb - ta) / DAY_MS);
  };
  T.longDate = function (iso) {
    var t = T.parseISO(iso); if (t === null) return "";
    var d = new Date(t);
    return DAYS[d.getUTCDay()] + ", " + MONTHS[d.getUTCMonth()] + " " + d.getUTCDate() + ", " + d.getUTCFullYear();
  };
  T.shortDate = function (iso) {
    var t = T.parseISO(iso); if (t === null) return "";
    var d = new Date(t);
    return DAYS[d.getUTCDay()].slice(0, 3) + " " + MONTHS[d.getUTCMonth()] + " " + d.getUTCDate();
  };
  T.monthDay = function (iso) {
    var t = T.parseISO(iso); if (t === null) return "";
    var d = new Date(t);
    return MONTHS[d.getUTCMonth()] + " " + d.getUTCDate();
  };
  T.monthIndex = function (iso) { var t = T.parseISO(iso); return t === null ? -1 : new Date(t).getUTCMonth(); };
  /* "July 14 to 16, 2027", "July 30 to August 2, 2027", "December 30, 2027 to January 2, 2028" */
  T.rangeLabel = function (a, b) {
    var ta = T.parseISO(a), tb = T.parseISO(b);
    if (ta === null) return "";
    var da = new Date(ta);
    if (tb === null || tb === ta) return MONTHS[da.getUTCMonth()] + " " + da.getUTCDate() + ", " + da.getUTCFullYear();
    var db = new Date(tb);
    if (da.getUTCFullYear() !== db.getUTCFullYear())
      return MONTHS[da.getUTCMonth()] + " " + da.getUTCDate() + ", " + da.getUTCFullYear() + " to " + MONTHS[db.getUTCMonth()] + " " + db.getUTCDate() + ", " + db.getUTCFullYear();
    if (da.getUTCMonth() !== db.getUTCMonth())
      return MONTHS[da.getUTCMonth()] + " " + da.getUTCDate() + " to " + MONTHS[db.getUTCMonth()] + " " + db.getUTCDate() + ", " + db.getUTCFullYear();
    return MONTHS[da.getUTCMonth()] + " " + da.getUTCDate() + " to " + db.getUTCDate() + ", " + db.getUTCFullYear();
  };

  /* ---------- times (minutes after midnight) ---------- */
  function hm(h, m, ap) {
    h = +h; m = +(m || 0);
    if (m > 59) return null;
    if (ap) {
      if (h < 1 || h > 12) return null;
      h = h % 12 + (ap.toLowerCase() === "p" ? 12 : 0);
    } else if (h > 23) return null;
    return h * 60 + m;
  }
  T.parseTime = function (s) {
    var m = /^\s*(\d{1,2})(?::(\d{2}))?\s*(?:([ap])\.?\s?m\.?)?\s*$/i.exec(str(s));
    if (!m || (!m[2] && !m[3])) return null;
    return hm(m[1], m[2], m[3]);
  };
  T.fmtTime = function (min) {
    if (min === null || min === undefined || isNaN(min)) return "";
    min = ((min % 1440) + 1440) % 1440;
    return Math.floor(min / 60) + ":" + pad(min % 60);
  };
  /* every time in a free-text field: "8:00; 13:00", "8am and 1 pm", "08:00,13:00" */
  T.parseTimes = function (s) {
    var out = [], re = /(\d{1,2}):(\d{2})(?:\s*([ap])\.?\s?m\.?(?![a-z]))?|(\d{1,2})\s*([ap])\.?\s?m\.?(?![a-z])/gi, m;
    s = str(s);
    while ((m = re.exec(s))) {
      var v = m[1] !== undefined ? hm(m[1], m[2], m[3]) : hm(m[4], 0, m[5]);
      if (v !== null && out.indexOf(v) < 0) out.push(v);
    }
    return out.sort(function (a, b) { return a - b; });
  };

  /* ---------- party ---------- */
  T.parseAges = function (s) {
    var ages = [], bad = [];
    str(s).split(/\s*(?:,|;|\band\b|\s)\s*/i).forEach(function (p) {
      if (!p) return;
      if (/^\d{1,2}$/.test(p)) ages.push(parseInt(p, 10)); else bad.push(p);
    });
    return { ages: ages, bad: bad };
  };

  /* ---------- CSV ---------- */
  T.parseCSV = function (text) {
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
  /* quote every cell that needs it; neutralise spreadsheet formulas */
  T.csvCell = function (v) {
    if (typeof v === "number") return String(v);
    var s = v === undefined || v === null ? "" : String(v);
    if (/^[=+\-@\t\r]/.test(s) && !/^-?\d+(?:\.\d+)?$/.test(s)) s = "'" + s;
    return /[",\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  };
  T.toCSV = function (header, rows) {
    return [header].concat(rows).map(function (r) { return r.map(T.csvCell).join(","); }).join("\r\n") + "\r\n";
  };

  /* ---------- partners ---------- */
  T.PARTNER_COLS = ["partner", "offer", "duration_minutes", "drive_minutes_from_meeting_point", "min_age", "departure_times", "weather_rule", "referral_code", "partner_confirmed", "fact_owner", "last_checked", "notes"];
  var ALIASES = {
    name: "partner", partner_name: "partner", business: "partner",
    duration: "duration_minutes", duration_min: "duration_minutes", minutes: "duration_minutes",
    drive: "drive_minutes_from_meeting_point", drive_minutes: "drive_minutes_from_meeting_point", drive_time: "drive_minutes_from_meeting_point",
    minimum_age: "min_age", age_minimum: "min_age",
    departures: "departure_times", times: "departure_times",
    weather: "weather_rule", code: "referral_code", confirmed: "partner_confirmed"
  };
  T.blankPartner = function () { var p = {}; T.PARTNER_COLS.forEach(function (k) { p[k] = ""; }); return p; };
  T.partnersFromCSV = function (text) {
    var rows = T.parseCSV(text);
    if (!rows.length) return { partners: [], error: "The file is empty." };
    var head = rows[0].map(function (h) {
      var k = str(h).toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
      return ALIASES[k] || k;
    });
    if (head.indexOf("partner") < 0) return { partners: [], error: "No 'partner' column found. Start from partners.csv on this page." };
    var list = rows.slice(1).map(function (r) {
      var p = T.blankPartner();
      head.forEach(function (k, i) { if (T.PARTNER_COLS.indexOf(k) >= 0) p[k] = str(r[i]); });
      return p;
    }).filter(function (p) { return p.partner !== ""; });
    return { partners: list.slice(0, 8), error: list.length > 8 ? "Only the first 8 partners were loaded." : "" };
  };
  T.partnersToCSV = function (list) {
    return T.toCSV(T.PARTNER_COLS, (list || []).map(function (p) { return T.PARTNER_COLS.map(function (k) { return p[k] || ""; }); }));
  };
  T.isConfirmed = function (p) { return /^(y|yes|true|1|x)$/i.test(str(p.partner_confirmed)); };

  /* ---------- month notes: one line per month, starting with the month name ---------- */
  T.parseMonthNotes = function (text) {
    var notes = {};
    str(text).split(/\r?\n/).forEach(function (line) {
      var m = /^\s*(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b\s*[:.]?\s*(.*)$/i.exec(line);
      if (!m || !str(m[2])) return;
      var key = m[1].slice(0, 3).toLowerCase();
      var idx = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"].indexOf(key);
      if (idx >= 0 && !notes[idx]) notes[idx] = str(line);
    });
    return notes;
  };

  function fill(what) { return "[FILL: " + what + "]"; }

  /* ---------- the deterministic pre-checks ----------
   * s: form values (business, facts, months, buffer, arrival, departure, adults, child_ages, product,
   *    product_date, start, duration, product_min_age, arrive_time, leave_time, other_plans) + s.partners[]
   * returns blocks for the prompt and a list of checks for the page.
   */
  T.precheck = function (s) {
    var r = { checks: [], rules: [], excluded: {}, clashes: {}, ownerQs: [], partners: [], fills: 0, errors: 0 };
    function check(level, text) { r.checks.push({ level: level, text: text }); if (level === "bad") r.errors++; if (level === "fill") r.fills++; }

    /* party */
    var adults = intOrNull(s.adults), kidsP = T.parseAges(s.child_ages), kids = kidsP.ages;
    if (kidsP.bad.length) check("bad", "Could not read the children's ages (" + kidsP.bad.join(", ") + "). Use numbers separated by commas, for example 6, 9.");
    var size = (adults || 0) + kids.length, party;
    if (!size) { party = fill("party size and ages"); check("fill", "Party size and ages are missing."); }
    else {
      var bits = [];
      if (adults) bits.push(adults + (adults === 1 ? " adult" : " adults"));
      if (kids.length) bits.push(kids.length === 1 ? "1 child aged " + kids[0] : kids.length + " children aged " + joinAnd(kids.map(String)));
      party = size + (size === 1 ? " person: " : " people: ") + (bits.join(" and ") || "0 adults");
    }
    r.partySize = size; r.kids = kids; r.party = party;

    /* stay */
    var arr = str(s.arrival), dep = str(s.departure), arrT = T.parseISO(arr), depT = T.parseISO(dep), days = null;
    if (arrT === null) check("fill", "Arrival date is missing.");
    if (depT === null) check("fill", "Departure date is missing.");
    if (arrT !== null && depT !== null) {
      days = T.diffDays(arr, dep) + 1;
      if (days < 1) { check("bad", "The departure date is before the arrival date."); days = null; }
      else if (days > 21) { check("bad", "Stays over 21 days are not framed day by day. Check the dates."); days = null; }
      else if (days > 7) check("warn", "Long stay (" + days + " days). A one-page kit works best for the days around your booking.");
    }
    r.days = days;

    /* the booking with us */
    var pDate = str(s.product_date), pT = T.parseISO(pDate);
    var start = T.parseTime(s.start), dur = intOrNull(s.duration), end = start !== null && dur !== null ? start + dur : null;
    var product = str(s.product) || fill("what was booked");
    if (!str(s.product)) check("fill", "What was booked is missing.");
    if (pT === null) check("fill", "The date of the booked trip is missing.");
    if (start === null) check("fill", "The start time of the booked trip is missing.");
    if (dur === null) check("fill", "The length of the booked trip (minutes) is missing.");
    if (end !== null && end > 1440) check("warn", "The booked trip runs past midnight. Check the start time and length.");
    if (pT !== null && arrT !== null && depT !== null && (pT < arrT || pT > depT)) check("bad", "The booked trip date is outside the stay. Fix the dates.");
    r.slot = { date: pDate, start: start, end: end };
    var pMin = intOrNull(s.product_min_age);
    if (pMin !== null && kids.length) {
      var under = kids.filter(function (a) { return a < pMin; });
      if (under.length) {
        check("bad", "Your own trip has a minimum age of " + pMin + ", and the party includes a child aged " + joinAnd(under.map(String)) + ". Check this booking with the owner before you send anything.");
        r.ownerQs.push("The party includes a child aged " + joinAnd(under.map(String)) + "; our minimum age is " + pMin + ". How do we handle this booking?");
      }
    }

    /* buffer between activities (Policy choice) */
    var buf = intOrNull(s.buffer); if (buf === null) buf = 30;
    r.buffer = buf;
    r.rules.push("Leave at least " + buf + " minutes plus the drive time between activities.");

    /* partners */
    var dateLbl = pT !== null ? T.monthDay(pDate) : "the booked day";
    (s.partners || []).forEach(function (p) {
      var name = str(p.partner);
      if (!name) return;
      var offer = str(p.offer), pd = intOrNull(p.duration_minutes), drive = intOrNull(p.drive_minutes_from_meeting_point),
        minAge = intOrNull(p.min_age), rawTimes = str(p.departure_times), times = T.parseTimes(rawTimes),
        weather = str(p.weather_rule), code = str(p.referral_code), missing = [];
      if (!offer) missing.push("offer");
      if (pd === null) missing.push("duration");
      if (drive === null) missing.push("drive time");
      if (minAge === null) missing.push("minimum age");
      if (!rawTimes) missing.push("departure times");
      if (!weather) missing.push("weather rule");
      if (!code) missing.push("referral code");
      var line = "- " + name + ": " + (offer || fill("offer")) + ". Duration: " + (pd !== null ? pd + " minutes" : fill("duration")) +
        ". Drive from our meeting point: " + (drive !== null ? drive + " minutes" : fill("drive time")) +
        ". Minimum age: " + (minAge !== null ? minAge : fill("minimum age")) +
        ". Departure times: " + (times.length ? joinAnd(times.map(T.fmtTime)) : rawTimes ? rawTimes : fill("departure times")) +
        ". Weather: " + (weather || fill("weather rule")) +
        ". Referral code: " + (code || fill("referral code")) + ".";
      if (!T.isConfirmed(p)) {
        line += " (Not yet confirmed by the partner: present every detail as 'to confirm'.)";
        check("warn", name + " has not confirmed these facts. Ask them before the kit goes out.");
      }
      r.partners.push({ name: name, code: code, line: line });
      if (missing.length) check("fill", name + ": " + joinAnd(missing) + " not supplied. The prompt says [FILL] there, so the AI does not guess.");
      var tooYoung = minAge !== null && kids.some(function (a) { return a < minAge; });
      /* an age-excluded partner stays out of the kit, so its gaps are not owner questions for this booking */
      if (missing.length && !tooYoung)
        r.rules.push("Where the partner list says [FILL] for " + name + " (" + joinAnd(missing) + "), write [FILL] in the kit and add it to the owner questions. Do not guess.");
      if (rawTimes && !times.length) check("warn", name + ": could not read the departure times (" + rawTimes + "). Use times like 8:00; 13:00. Clashes were not checked.");

      /* minimum age against the party */
      if (kids.length) {
        if (minAge === null) {
          r.rules.push("Do not suggest " + name + " for the children until the owner confirms its minimum age.");
        } else {
          var young = kids.filter(function (a) { return a < minAge; });
          if (young.length) {
            var why = "minimum age is " + minAge + " and the party includes " + (young.length === 1 ? "a child aged " : "children aged ") + joinAnd(young.map(String));
            r.excluded[name] = why;
            check("bad", "Excluded: " + name + " (minimum age " + minAge + "; " + (young.length === 1 ? "a child aged " : "children aged ") + joinAnd(young.map(String)) + " in the party).");
            r.rules.push("Do not suggest " + name + " for this party, not even for part of the group: its " + why + ".");
          } else check("ok", name + ": every child meets its minimum age of " + minAge + ".");
        }
      } else if (minAge !== null) check("ok", name + ": minimum age " + minAge + ", no children in the party.");

      /* time clashes with our booked trip */
      if (start !== null && end !== null) {
        var gap = buf + (drive || 0), gapTxt = drive !== null ? drive + " minutes drive and " + buf + " minutes buffer" : buf + " minutes buffer; drive time not supplied";
        if (times.length) {
          var bad = [], good = [];
          times.forEach(function (t) {
            var tEnd = t + (pd !== null ? pd : 0);
            if (t < end + gap && tEnd + gap > start) bad.push(t); else good.push(t);
          });
          if (bad.length) {
            r.clashes[name] = bad.map(T.fmtTime);
            var all = !good.length;
            check("warn", "Clash on " + dateLbl + ": " + name + " at " + joinAnd(bad.map(T.fmtTime)) + " overlaps your trip (" + T.fmtTime(start) + " to " + T.fmtTime(end) + ", plus " + gapTxt + ")." + (pd === null ? " Its duration is missing, so this check is partial." : ""));
            r.rules.push("On " + dateLbl + ", " + name + " at " + joinAnd(bad.map(T.fmtTime)) + " clashes with our trip (" + T.fmtTime(start) + " to " + T.fmtTime(end) + ", plus " + gapTxt + "). " +
              (r.excluded[name] ? "It is already excluded for this party by minimum age, so do not offer it at any time." :
                all ? "Do not place " + name + " on " + dateLbl + "." : "On " + dateLbl + " offer only " + joinAnd(good.map(T.fmtTime)) + "."));
          } else check("ok", name + ": no clash with your trip on " + dateLbl + ".");
        } else if (pd !== null) {
          var earliest = end + gap;
          r.rules.push("If you place " + name + " on " + dateLbl + ", it starts no earlier than " + T.fmtTime(earliest) + " (our trip ends " + T.fmtTime(end) + ", plus " + gapTxt + "). Its departure times are not supplied: write [FILL: departure times].");
          check("fill", name + " has no departure times, so the page cannot check clashes. Earliest start after your trip on " + dateLbl + ": " + T.fmtTime(earliest) + ".");
        }
      }
    });
    if (!r.partners.length) check("warn", "No partners listed. The kit will have no partner options for open half-days.");

    /* month notes: only what you supplied; no invented weather */
    var notes = T.parseMonthNotes(s.months), months = [];
    if (arrT !== null && days) { for (var i = 0; i < days; i++) { var mi = T.monthIndex(T.addDays(arr, i)); if (months.indexOf(mi) < 0) months.push(mi); } }
    else if (pT !== null) months.push(T.monthIndex(pDate));
    r.monthLines = [];
    if (!months.length) { r.monthLines.push(fill("month and typical conditions")); }
    months.forEach(function (mi) {
      var mn = MONTHS[mi];
      if (notes[mi]) { r.monthLines.push(notes[mi]); check("ok", "Month note found for " + mn + "."); }
      else {
        r.monthLines.push(mn + ": " + fill("typical conditions for " + mn + ", from a trusted source, approved by the owner"));
        r.rules.push("There is no month note for " + mn + ". Do not describe weather, temperatures or daylight for " + mn + ". Write [FILL: what to wear in " + mn + "] and add it to the owner questions.");
        check("fill", "No month note for " + mn + ". The prompt says [FILL]; the AI is told not to invent weather.");
      }
    });

    /* day frame */
    r.dayLines = [];
    var arrive = T.parseTime(s.arrive_time), leave = T.parseTime(s.leave_time);
    if (days) {
      for (var d = 0; d < days; d++) {
        var iso = T.addDays(arr, d), parts = [];
        if (d === 0) parts.push("arrival day, " + (arrive !== null ? "arriving about " + T.fmtTime(arrive) : "arrival time [FILL]"));
        if (d === days - 1) parts.push("departure day, " + (leave !== null ? "leaving about " + T.fmtTime(leave) : "departure time [FILL]"));
        if (iso === pDate) {
          parts.push("booked with us: " + product + (start !== null ? ", " + T.fmtTime(start) + (end !== null ? " to " + T.fmtTime(end) : "") : ""));
          if (start !== null && end !== null) parts.push("open before " + T.fmtTime(start) + " and after " + T.fmtTime(end));
        } else parts.push(d === 0 || d === days - 1 ? "open" : "open all day");
        r.dayLines.push("Day " + (d + 1) + ", " + T.shortDate(iso) + ": " + parts.join("; ") + ".");
      }
      if (arrive === null) r.ownerQs.push("What time does the party arrive?");
      if (leave === null) r.ownerQs.push("What time does the party leave?");
    } else r.dayLines.push(fill("stay dates"));

    /* booking block */
    var b = [];
    b.push("Stay: " + (arrT !== null ? T.longDate(arr) : fill("arrival date")) + " to " + (depT !== null ? T.longDate(dep) : fill("departure date")) + (days ? " (" + days + (days === 1 ? " day)." : " days).") : "."));
    b.push("Party: " + party + ".");
    b.push("Booked with us: " + product + ", " + (pT !== null ? T.longDate(pDate) : fill("date")) + ", " +
      (start !== null ? T.fmtTime(start) : fill("start time")) + " to " + (end !== null ? T.fmtTime(end) : fill("end time")) +
      (pMin !== null ? ". Minimum age: " + pMin + "." : "."));
    if (str(s.other_plans)) b.push("Other fixed plans the guest mentioned: " + str(s.other_plans).replace(/\s*\n\s*/g, "; "));
    r.bookingBlock = b.join("\n");
    r.partnerBlock = r.partners.map(function (p) { return p.line; }).join("\n");
    r.monthBlock = r.monthLines.join("\n");
    r.dayBlock = r.dayLines.join("\n");
    var qs = r.ownerQs.length ? "\n- Add these to the owner questions: " + r.ownerQs.join(" ") : "";
    r.rulesBlock = r.rules.map(function (x) { return "- " + x; }).join("\n") + qs;
    r.tripLabel = arrT !== null ? T.rangeLabel(arr, depT !== null ? dep : arr) : "";
    /* extra numbers the AI may legitimately write: month and day numbers of the stay */
    r.knownExtra = [];
    if (days) for (var k = 0; k < days; k++) { var x = T.addDays(arr, k).split("-"); r.knownExtra.push(+x[0], +x[1], +x[2]); }
    return r;
  };

  /* partner line for the post-booking calendar */
  T.partnerSentence = function (p) {
    if (!p || !str(p.partner)) return "";
    var pd = intOrNull(p.duration_minutes), drive = intOrNull(p.drive_minutes_from_meeting_point), minAge = intOrNull(p.min_age), times = T.parseTimes(p.departure_times);
    return str(p.partner) + ": " + (str(p.offer) || fill("offer")) + ", " + (pd !== null ? pd + " minutes" : fill("duration")) + ", " +
      (drive !== null ? drive + " minutes by car from our meeting point" : fill("drive time from our meeting point")) + ", minimum age " +
      (minAge !== null ? minAge : fill("minimum age")) + ", departures " + (times.length ? joinAnd(times.map(T.fmtTime)) : str(p.departure_times) || fill("departure times")) +
      ", " + (str(p.weather_rule) || fill("weather rule")) + ". Referral code " + (str(p.referral_code) || fill("referral code")) + ".";
  };

  /* ---------- the post-booking calendar: deterministic send dates ---------- */
  T.MESSAGES = [
    { id: "Confirmation", job: "The fact sheet: what to wear, where to meet, weather terms. Attach the trip kit." },
    { id: "T-30", job: "Fill the gaps: your add-on or a partner's offer." },
    { id: "T-7", job: "Weather plan B; for flexible bookings, your price-drop stance." },
    { id: "T-1", job: "Meeting point, live conditions, a named person and phone." },
    { id: "After", job: "Ask for the dated review that becomes next season's proof." }
  ];
  T.schedule = function (o) {
    var r = { error: "", rows: [], skipped: [], lead: null, rule: "" };
    var booking = str(o.booking), trip = str(o.trip), tripEnd = str(o.tripEnd);
    if (T.parseISO(booking) === null) { r.error = "Enter the booking date."; return r; }
    if (T.parseISO(trip) === null) { r.error = "Enter the trip date."; return r; }
    var end = T.parseISO(tripEnd) !== null ? tripEnd : trip;
    if (T.diffDays(trip, end) < 0) { r.error = "The last day of the trip is before the trip date."; return r; }
    var lead = T.diffDays(booking, trip);
    if (lead < 0) { r.error = "The trip date is before the booking date."; return r; }
    var after = intOrNull(o.afterDays); if (after === null || after > 60) after = 1;
    var flexible = o.rate !== "nonref", set;
    if (!flexible) { set = ["Confirmation", "T-1", "After"]; r.rule = "Non-refundable: Confirmation, T-1 and After only."; }
    else if (lead < 7) { set = ["Confirmation", "T-1", "After"]; r.rule = "Flexible but booked under 7 days out: Confirmation, T-1 and After only."; }
    else if (lead < 30) { set = ["Confirmation", "T-7", "T-1", "After"]; r.rule = "Flexible, booked 7 to 29 days out: no T-30, because its date comes before the booking."; }
    else { set = ["Confirmation", "T-30", "T-7", "T-1", "After"]; r.rule = "Flexible, booked 30 or more days out: all five messages."; }
    r.lead = lead; r.flexible = flexible; r.after = after;
    var perRule = {
      "Confirmation": "Every booking, at booking",
      "T-30": "Flexible bookings made 30 or more days out",
      "T-7": "Flexible bookings made 7 or more days out",
      "T-1": "Every booking, the day before",
      "After": "Every booking, " + after + (after === 1 ? " day" : " days") + " after the trip"
    };
    T.MESSAGES.forEach(function (m) {
      var date = m.id === "Confirmation" ? booking : m.id === "T-30" ? T.addDays(trip, -30) : m.id === "T-7" ? T.addDays(trip, -7) : m.id === "T-1" ? T.addDays(trip, -1) : T.addDays(end, after);
      if (set.indexOf(m.id) < 0) {
        r.skipped.push({ message: m.id, reason: !flexible ? "Non-refundable booking." : lead < 7 ? "Booked under 7 days out." : "Its date (" + date + ") comes before the booking." });
        return;
      }
      if (T.diffDays(booking, date) < 0) { r.skipped.push({ message: m.id, reason: "Its date (" + date + ") comes before the booking. Put its content in the confirmation." }); return; }
      r.rows.push({
        message: m.id, date: date, offset: T.diffDays(trip, date), rule: perRule[m.id], job: m.job,
        sameDay: m.id !== "Confirmation" && date === booking
      });
    });
    return r;
  };
  T.CAL_COLS = ["message", "send_date", "offset_days", "rule", "subject", "body", "approved_by"];
  T.scheduleCSV = function (sch) {
    return T.toCSV(T.CAL_COLS, (sch.rows || []).map(function (x) {
      return [x.message, x.date, x.offset, x.rule + (x.sameDay ? " (same day as the confirmation: merge or skip)" : ""),
        "[PASTE APPROVED " + x.message.toUpperCase() + " SUBJECT]", "[PASTE APPROVED " + x.message.toUpperCase() + " BODY]", ""];
    }));
  };

  /* ---------- privacy guard (first pass only) ---------- */
  T.luhn = function (digits) {
    var sum = 0, alt = false;
    for (var i = digits.length - 1; i >= 0; i--) {
      var n = +digits[i];
      if (alt) { n *= 2; if (n > 9) n -= 9; }
      sum += n; alt = !alt;
    }
    return sum % 10 === 0;
  };
  T.piiScan = function (text) {
    var hits = [], s = String(text || ""), m;
    function add(kind, m0, idx) { hits.push({ kind: kind, text: m0, start: idx, end: idx + m0.length }); }
    var res = [
      ["email address", /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi],
      ["phone number", /(?:\+?1[\s.-]?)?(?:\(\d{3}\)|\b\d{3})[\s.-]?\d{3}[\s.-]?\d{4}\b/g],
      ["street address", /\b\d{1,6}\s+(?:[A-Z][a-z]+\s){1,3}(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Way|Ct|Court|Hwy|Highway|Pl|Place)\b\.?/g],
      ["name", /\b(?:Mr|Mrs|Ms|Miss|Dr)\.?\s+[A-Z][a-z]+/g],
      ["name", /\b(?:[Gg]uest|[Nn]ame|[Bb]ooked by|[Ll]ead traveler)\s*:\s*[A-Z][a-z]+/g]
    ];
    res.forEach(function (p) { p[1].lastIndex = 0; while ((m = p[1].exec(s))) add(p[0], m[0], m.index); });
    var card = /\b(?:\d[ -]?){12,18}\d\b/g;
    while ((m = card.exec(s))) {
      var dg = m[0].replace(/\D/g, "");
      if (dg.length >= 13 && dg.length <= 19 && T.luhn(dg)) add("card number", m[0], m.index);
    }
    return hits;
  };

  /* ---------- number guard: what the draft says that the inputs do not ---------- */
  var PRICE_RE = /(?:\$|\bUSD\s?)\s?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?/gi;
  var TIME_RE = /\b(\d{1,2}):([0-5]\d)(?:\s*([ap])\.?\s?m\.?(?![a-z]))?|\b(\d{1,2})\s*([ap])\.?\s?m\.?(?![a-z])/gi;
  var NUM_RE = /\d+(?:,\d{3})*(?:\.\d+)?/g;
  function normNum(s) { var n = parseFloat(String(s).replace(/,/g, "")); return isNaN(n) ? String(s) : String(n); }
  function priceVal(m) { return normNum(m[1] + (m[2] ? "." + m[2] : "")); }
  T.known = function (text, extra) {
    var k = { nums: {}, times: {}, prices: {} }, s = String(text || ""), m;
    PRICE_RE.lastIndex = 0; while ((m = PRICE_RE.exec(s))) k.prices[priceVal(m)] = 1;
    var dollars = /(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:dollars|USD)\b/gi; while ((m = dollars.exec(s))) k.prices[normNum(m[1])] = 1;
    TIME_RE.lastIndex = 0;
    while ((m = TIME_RE.exec(s))) { var v = m[1] !== undefined ? hm(m[1], m[2], m[3]) : hm(m[4], 0, m[5]); if (v !== null) k.times[v] = 1; }
    NUM_RE.lastIndex = 0; while ((m = NUM_RE.exec(s))) k.nums[normNum(m[0])] = 1;
    (extra || []).forEach(function (n) { k.nums[normNum(n)] = 1; });
    return k;
  };
  function timeKnown(k, m) {
    if (m[1] !== undefined) {
      var v = hm(m[1], m[2], m[3]); if (v === null) return true;
      if (k.times[v]) return true;
      /* "1:00" with no am/pm may mean 13:00 */
      if (!m[3] && +m[1] >= 1 && +m[1] <= 11 && k.times[v + 720]) return true;
      return false;
    }
    var w = hm(m[4], 0, m[5]); return w === null || !!k.times[w];
  }

  /* ctx: { prompt, extra:[numbers], excluded:{name:why}, partners:[{name, code}], kind:"kit"|"cal" } */
  T.checkDraft = function (draft, ctx) {
    var s = String(draft || ""), items = [], marks = [], m;
    ctx = ctx || {};
    function item(level, title, detail) { items.push({ level: level, title: title, detail: detail || "" }); }
    if (!s.trim()) return { items: [{ level: "info", title: "Paste a draft to check it.", detail: "" }], marks: [], words: 0 };
    var k = T.known(ctx.prompt, ctx.extra), masked = s.split("");
    function mask(a, b) { for (var i = a; i < b; i++) masked[i] = " "; }
    function overlaps(a, b) { return marks.some(function (x) { return a < x.end && b > x.start; }); }

    /* DRAFT marker */
    var markerRe = /DRAFT\s*[-:\u2013\u2014]?\s*PENDING\s+(?:OWNER|STAFF)\s+REVIEW/gi, nMarkers = (s.match(markerRe) || []).length;
    if (!nMarkers) item("bad", "No DRAFT - PENDING OWNER REVIEW marker.", "Keep the marker on every draft until a person has approved it.");
    else if (ctx.kind === "cal" && nMarkers < 5) item("warn", "Found " + nMarkers + " DRAFT marker" + (nMarkers === 1 ? "" : "s") + ".", "Expect one on each of the five messages.");
    else item("ok", "DRAFT marker present.", "");

    /* [FILL] items: mask so their digits are not flagged */
    var fills = [], fre = /\[FILL[^\]]*\]/gi;
    while ((m = fre.exec(s))) { fills.push(m[0]); marks.push({ start: m.index, end: m.index + m[0].length, kind: "fill" }); mask(m.index, m.index + m[0].length); }

    /* privacy */
    var pii = T.piiScan(s);
    pii.forEach(function (h) { if (!overlaps(h.start, h.end)) marks.push({ start: h.start, end: h.end, kind: "pii" }); mask(h.start, h.end); });
    if (pii.length) item("bad", "Possible personal data: " + pii.map(function (h) { return h.kind; }).filter(function (x, i, a) { return a.indexOf(x) === i; }).join(", ") + ".", "Remove it here and in your AI chat. Guest names and contact details stay out of AI tools.");

    var mtext = masked.join("");
    /* prices */
    var badPrices = [];
    PRICE_RE.lastIndex = 0;
    while ((m = PRICE_RE.exec(mtext))) {
      if (!k.prices[priceVal(m)]) { badPrices.push(m[0].trim()); marks.push({ start: m.index, end: m.index + m[0].length, kind: "price" }); }
      mask(m.index, m.index + m[0].length);
    }
    mtext = masked.join("");
    /* times */
    var badTimes = [];
    TIME_RE.lastIndex = 0;
    while ((m = TIME_RE.exec(mtext))) {
      /* "11:30 pm." at the end of a sentence: leave the full stop out of the flag */
      var tok = m[0].replace(/\s+$/, ""); if (/\.$/.test(tok) && tok.indexOf(".") === tok.length - 1) tok = tok.slice(0, -1);
      if (!timeKnown(k, m)) { badTimes.push(tok); marks.push({ start: m.index, end: m.index + tok.length, kind: "time" }); }
      mask(m.index, m.index + m[0].length);
    }
    mtext = masked.join("");
    /* other numbers (list markers at line start are skipped) */
    var badNums = [];
    NUM_RE.lastIndex = 0;
    while ((m = NUM_RE.exec(mtext))) {
      var lineStart = mtext.lastIndexOf("\n", m.index - 1) + 1, before = mtext.slice(lineStart, m.index), afterCh = mtext.charAt(m.index + m[0].length);
      if (/^\s*$/.test(before) && /[.)]/.test(afterCh) && m[0].length <= 2) continue;
      if (/[A-Za-z]$/.test(before)) {
        /* part of a code like BAYLIGHT2: known if the whole word is in the prompt */
        var w0 = before.match(/[A-Za-z0-9-]+$/)[0] + m[0];
        if (String(ctx.prompt || "").indexOf(w0) >= 0) continue;
      }
      if (!k.nums[normNum(m[0])]) { badNums.push(m[0]); marks.push({ start: m.index, end: m.index + m[0].length, kind: "num" }); }
    }
    function uniq(a) { return a.filter(function (x, i) { return a.indexOf(x) === i; }); }
    if (badPrices.length) item("bad", "Price not in your inputs: " + uniq(badPrices).join(", ") + ".", "The AI is told not to state prices. Delete it or replace it with your approved price.");
    if (badTimes.length) item("bad", "Time not in your inputs: " + uniq(badTimes).join(", ") + ".", "Check it against your facts and the partner list. Invented times are the usual mistake.");
    if (badNums.length) item("warn", "Number not in your inputs: " + uniq(badNums).join(", ") + ".", "Each one is either a fact you forgot to give the AI, or a guess. Check it.");
    if (!badPrices.length && !badTimes.length && !badNums.length) item("ok", "Every number, time and price also appears in your inputs.", "That does not prove each one is used correctly. Read them.");

    /* excluded partners and referral codes */
    var low = s.toLowerCase();
    Object.keys(ctx.excluded || {}).forEach(function (name) {
      var i = low.indexOf(name.toLowerCase());
      if (i >= 0) {
        item("bad", "Mentions " + name + ", which the pre-checks excluded for this party.", "Its " + ctx.excluded[name] + ". Remove it, unless the line only says why it is not offered.");
        var j = i; while (j >= 0) { marks.push({ start: j, end: j + name.length, kind: "excl" }); j = low.indexOf(name.toLowerCase(), j + 1); }
      }
    });
    (ctx.partners || []).forEach(function (p) {
      if (!p.name || (ctx.excluded || {})[p.name]) return;
      if (low.indexOf(p.name.toLowerCase()) >= 0 && p.code && s.indexOf(p.code) < 0) item("warn", "Mentions " + p.name + " without its referral code " + p.code + ".", "The code is how you count referrals.");
    });

    /* promise and money words */
    var promise = /\b(guarantee[sd]?|promise[sd]?|definitely|certainly|for sure|you(?:'ll| will) see|always|never)\b/gi, pw = [];
    while ((m = promise.exec(s))) { pw.push(m[0]); if (!overlaps(m.index, m.index + m[0].length)) marks.push({ start: m.index, end: m.index + m[0].length, kind: "word" }); }
    if (pw.length) item("warn", "Promise words: " + uniq(pw.map(function (x) { return x.toLowerCase(); })).join(", ") + ".", "Weather, wildlife and partner availability cannot be promised. Read each line.");
    var money = /\b(refunds?|refunded|credits?|discounts?|free|price match(?:ing)?|cheaper)\b/gi, mw = [];
    while ((m = money.exec(s))) { mw.push(m[0]); if (!overlaps(m.index, m.index + m[0].length)) marks.push({ start: m.index, end: m.index + m[0].length, kind: "word" }); }
    if (mw.length) item("warn", "Money terms: " + uniq(mw.map(function (x) { return x.toLowerCase(); })).join(", ") + ".", "Each one should match your written terms word for word.");

    if (fills.length) item("warn", fills.length + " open [FILL] item" + (fills.length === 1 ? "" : "s") + ".", "Answer each one before anything goes to a guest.");

    var words = (s.match(/\S+/g) || []).length;
    if (ctx.kind !== "cal") {
      if (words > 400) item("warn", words + " words. The kit should be under 400 to fit one page.", "");
      if (!/plan\s*b/i.test(s)) item("warn", "No weather plan B found.", "Every outdoor item needs one. Your captain or another qualified person owns it.");
      if (fills.length && !/questions?\s+(?:for|to)\s+(?:the\s+)?owner|owner\s+questions/i.test(s)) item("warn", "No \"Questions for the owner\" section.", "The prompt asks for one so missing facts are easy to find.");
    }
    var greet = /\b(?:Dear|Hi|Hello|Hey)\s+([A-Z][a-z]+)\b/g, names = [];
    while ((m = greet.exec(s))) {
      if (/^(?:There|All|Everyone|Friends|Folks|Team|Again)$/.test(m[1])) continue;
      names.push(m[1]);
      var st = m.index + m[0].length - m[1].length;
      if (!overlaps(st, st + m[1].length)) marks.push({ start: st, end: st + m[1].length, kind: "pii" });
    }
    if (names.length) item("bad", "Greeting with a name: " + uniq(names).join(", ") + ".", "Use the [GUEST FIRST NAME] placeholder. Names are merged in your booking platform, not in an AI chat.");
    marks.sort(function (a, b) { return a.start - b.start || b.end - a.end; });
    var clean = [], last = -1;
    marks.forEach(function (x) { if (x.start >= last) { clean.push(x); last = x.end; } });
    return { items: items, marks: clean, words: words, fills: fills.length };
  };

  if (typeof module !== "undefined" && module.exports) module.exports = T;
  else root.TripKit = T;
})(this);
