/* Tool 3.c, ATIA AI Take-Home Kit: trip record checks for the browser.
 * The same three layers as validate_record.py (schema subset, personal-data scan, record rules), with the same messages.
 * No DOM, no network. Works in the page (window.TripRecord) and in node (module.exports) for tests.
 */
(function (root) {
  "use strict";

  var PATTERN_HINTS = {
    "^TR-[A-Z0-9]+(-[A-Z0-9]+)*$": "Use an opaque id like TR-DEMO-0714. Never a name, email or booking reference.",
    "^[A-Z0-9]+(-[A-Z0-9]+)*$": "Use capital letters, digits and hyphens, like BL-CRUISE-4H.",
    "^([01][0-9]|2[0-3]):[0-5][0-9]$": "Use 24-hour time, like 09:00.",
    "^Q[0-9]{1,3}$": "Use Q plus a number, like Q1.",
    "^[A-Za-z0-9][A-Za-z0-9_-]{2,63}$": "Use letters, digits, hyphens or underscores (3 to 64 characters)."
  };
  var FORMAT_HINTS = {
    "date": "Use a real date like 2027-07-15.",
    "date-time": "Use a real date and time with a time zone, like 2026-10-10T18:30:00Z."
  };
  var PERSONAL_DATA_REF = "#/$defs/looksLikePersonalData";
  var GENERIC_PERSONAL = "This text looks like personal data (an email, phone, card or ID number). Remove it.";

  function Issue(path, message, kind, level) { return { path: path, message: message, kind: kind, level: level || "error" }; }

  function Result() { this.errors = []; this.warnings = []; }
  Result.prototype.add = function (i) {
    var b = i.level === "error" ? this.errors : this.warnings;
    for (var k = 0; k < b.length; k++) if (b[k].path === i.path && b[k].message === i.message) return;
    b.push(i);
  };
  Object.defineProperty(Result.prototype, "ok", { get: function () { return this.errors.length === 0; } });
  Result.prototype.summary = function () {
    var e = this.errors.length, w = this.warnings.length;
    return (this.ok ? "VALID" : "NOT VALID") + " (" + e + " error" + (e !== 1 ? "s" : "") + ", " + w + " warning" + (w !== 1 ? "s" : "") + ")";
  };

  /* ------------------------------------------------------------ schema */
  function jsonType(v) {
    if (v === null) return "null";
    if (typeof v === "boolean") return "boolean";
    if (typeof v === "number") return Number.isInteger(v) ? "integer" : "number";
    if (typeof v === "string") return "string";
    if (Array.isArray(v)) return "array";
    if (typeof v === "object") return "object";
    return typeof v;
  }
  function isType(v, t) {
    var jt = jsonType(v);
    if (t === "number") return jt === "integer" || jt === "number";
    return jt === t;
  }
  function canon(v) {
    if (Array.isArray(v)) return "[" + v.map(canon).join(",") + "]";
    if (v && typeof v === "object") return "{" + Object.keys(v).sort().map(function (k) { return JSON.stringify(k) + ":" + canon(v[k]); }).join(",") + "}";
    return JSON.stringify(v);
  }
  function resolve(ref, rootSchema) {
    if (ref.indexOf("#/") !== 0) throw new Error("Only local $ref values are supported, not " + ref);
    var node = rootSchema;
    ref.slice(2).split("/").forEach(function (p) { node = node[p.replace(/~1/g, "/").replace(/~0/g, "~")]; });
    return node;
  }
  function validDate(s) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
    if (!m) return false;
    var y = +m[1], mo = +m[2], d = +m[3], dt = new Date(Date.UTC(y, mo - 1, d));
    return dt.getUTCFullYear() === y && dt.getUTCMonth() === mo - 1 && dt.getUTCDate() === d;
  }
  function validDateTime(s) {
    var m = /^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?(Z|[+-](\d{2}):(\d{2}))$/.exec(s);
    if (!m || !validDate(m[1])) return false;
    if (+m[2] > 23 || +m[3] > 59 || (m[4] !== undefined && +m[4] > 59)) return false;
    if (m[6] !== undefined && (+m[6] > 23 || +m[7] > 59)) return false;
    return true;
  }
  function validFormat(v, f) { return f === "date" ? validDate(v) : f === "date-time" ? validDateTime(v) : true; }
  function ptr(path, key) { return path + "/" + String(key).replace(/~/g, "~0").replace(/\//g, "~1"); }
  function plural(n) { return n !== 1 ? "s" : ""; }

  function check(inst, sch, path, rootSchema, out) {
    if (sch === true) return;
    if (sch === false) { out.push(Issue(path, "No value is allowed here.", "schema")); return; }
    if (sch.$ref) check(inst, resolve(sch.$ref, rootSchema), path, rootSchema, out);

    if (sch.type !== undefined) {
      var types = Array.isArray(sch.type) ? sch.type : [sch.type];
      if (!types.some(function (t) { return isType(inst, t); })) {
        out.push(Issue(path, "Expected " + types.join(" or ") + ", found " + jsonType(inst) + ".", "schema"));
        return;
      }
    }
    if ("const" in sch && canon(inst) !== canon(sch["const"])) {
      out.push(Issue(path, /\/agent_may_confirm$/.test(path) ? "Use false. In this design an agent may hold and ask; a person at the business confirms." : "Use " + JSON.stringify(sch["const"]) + ".", "schema"));
    }
    if (sch["enum"] && !sch["enum"].some(function (e) { return canon(inst) === canon(e); })) {
      out.push(Issue(path, "Use one of: " + sch["enum"].map(function (e) { return JSON.stringify(e); }).join(", ") + ".", "schema"));
    }
    if (typeof inst === "string") {
      var n = Array.from(inst).length;
      if (sch.minLength !== undefined && n < sch.minLength) out.push(Issue(path, "Too short (at least " + sch.minLength + " characters).", "schema"));
      if (sch.maxLength !== undefined && n > sch.maxLength) out.push(Issue(path, "Too long (" + n + " characters; the limit is " + sch.maxLength + ").", "schema"));
      var fmtBad = sch.format && !validFormat(inst, sch.format);
      if (sch.pattern && !new RegExp(sch.pattern).test(inst)) {
        out.push(Issue(path, FORMAT_HINTS[sch.format || ""] || PATTERN_HINTS[sch.pattern] || "The format is not allowed here.", "schema"));
      } else if (fmtBad) {
        out.push(Issue(path, FORMAT_HINTS[sch.format] || "Wrong format.", "schema"));
      }
    }
    if (typeof inst === "number") {
      if (sch.minimum !== undefined && inst < sch.minimum) out.push(Issue(path, "Too small (the minimum is " + sch.minimum + ").", "schema"));
      if (sch.maximum !== undefined && inst > sch.maximum) out.push(Issue(path, "Too large (the maximum is " + sch.maximum + ").", "schema"));
    }
    if (Array.isArray(inst)) {
      if (sch.minItems !== undefined && inst.length < sch.minItems) out.push(Issue(path, "Needs at least " + sch.minItems + " item" + plural(sch.minItems) + ".", "schema"));
      if (sch.maxItems !== undefined && inst.length > sch.maxItems) out.push(Issue(path, "Too many items (" + inst.length + "; the limit is " + sch.maxItems + ").", "schema"));
      if (sch.uniqueItems) {
        var seen = {}, dup = false;
        inst.forEach(function (x) { var c = canon(x); if (seen[c]) dup = true; seen[c] = 1; });
        if (dup) out.push(Issue(path, "An item is repeated.", "schema"));
      }
      if (sch.items !== undefined) inst.forEach(function (it, i) { check(it, sch.items, ptr(path, i), rootSchema, out); });
    }
    if (jsonType(inst) === "object") {
      (sch.required || []).forEach(function (k) { if (!Object.prototype.hasOwnProperty.call(inst, k)) out.push(Issue(path, "Missing required field \"" + k + "\".", "schema")); });
      var props = sch.properties || {};
      Object.keys(inst).forEach(function (k) {
        if (Object.prototype.hasOwnProperty.call(props, k)) check(inst[k], props[k], ptr(path, k), rootSchema, out);
        else if ("additionalProperties" in sch) {
          if (sch.additionalProperties === false) {
            if (!personalKey(k)) out.push(Issue(ptr(path, k), "Field \"" + k + "\" is not part of the trip record. Remove it or rename it to a schema field.", "schema"));
          } else check(inst[k], sch.additionalProperties, ptr(path, k), rootSchema, out);
        }
      });
    }
    if (sch.allOf) sch.allOf.forEach(function (s) { check(inst, s, path, rootSchema, out); });
    if (sch.anyOf) {
      var allFail = sch.anyOf.every(function (s) { var t = []; check(inst, s, path, rootSchema, t); return t.length > 0; });
      if (allFail) out.push(Issue(path, "Does not match any allowed form.", "schema"));
    }
    if (sch.not) {
      var t = [];
      check(inst, sch.not, path, rootSchema, t);
      if (!t.length) {
        if (sch.not.$ref === PERSONAL_DATA_REF && Object.keys(sch.not).length === 1) out.push(Issue(path, GENERIC_PERSONAL, "personal-data"));
        else out.push(Issue(path, "This value is not allowed here.", "schema"));
      }
    }
  }

  /* ------------------------------------------------------------ personal data */
  var PERSONAL_KEYS_EXACT = ["name", "firstname", "lastname", "fullname", "surname", "givenname", "familyname", "guestname",
    "travelername", "leadname", "contactname", "passengername", "contact", "address", "street",
    "streetaddress", "homeaddress", "zip", "zipcode", "postcode", "postalcode", "dob", "birthday",
    "gender", "nationality", "ip", "ipaddress", "deviceid", "medical", "health",
    "allergies", "allergy", "diet", "dietary", "disability", "medication", "medications"];
  var PERSONAL_KEY_TOKENS = ["email", "phone", "mobile", "telephone", "cell", "sms", "whatsapp", "card", "cvv", "cvc",
    "iban", "routing", "account", "payment", "billing", "passport", "license", "licence", "ssn",
    "socialsecurity", "birth", "loyalty", "membership", "password", "token"];
  function personalKey(key) {
    var k = String(key).toLowerCase().replace(/[\s_\-]/g, "");
    return PERSONAL_KEYS_EXACT.indexOf(k) >= 0 || PERSONAL_KEY_TOKENS.some(function (t) { return k.indexOf(t) >= 0; });
  }

  var RE_EMAIL = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/;
  var RE_PHONE = /(?:^|[^0-9A-Za-z])((?:\+?1[ .-]?)?\(?[2-9][0-9]{2}\)?[ .-]?[0-9]{3}[ .-]?[0-9]{4})(?![0-9A-Za-z])/;
  var RE_LONGNUM = /(?:^|[^0-9])((?:[0-9][ -]?){12,18}[0-9])(?![0-9])/g;
  var RE_SSN = /(?:^|[^0-9])([0-9]{3}-[0-9]{2}-[0-9]{4})(?![0-9])/;
  var RE_STREET = /\b[0-9]{1,6}\s+(?:[A-Z][a-z]+\s){1,3}(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Way|Ct|Court|Hwy|Highway|Pl|Place|Loop|Cir|Circle)\b/;
  var RE_LABEL = /\b(name|first name|last name|full name|guest|e-?mail|phone|cell|mobile|tel|card|cvv|cvc|passport|driver'?s license|license no|date of birth|dob|ssn|address|account)\s*(?:#|:|=)/i;
  var RE_TITLE_NAME = /\b(?:Mr|Mrs|Ms|Mx|Miss)\.?\s+[A-Z][a-z]+/;
  var RE_FAMILY_NAME = /\b[Tt]he\s+([A-Z][a-z]+)\s+(?:family|party|group)\b/;
  var RE_HEALTH = /\b(allerg\w*|anaphyla\w*|diabet\w*|epi-?pen|insulin|medication\w*|medicine|pregnan\w*|seizure\w*|epilep\w*|asthma\w*|wheelchair|disabilit\w*|disabled|diagnos\w*|heart condition|surgery|medical)\b/i;

  function luhnOk(digits) {
    var total = 0, alt = false;
    for (var i = digits.length - 1; i >= 0; i--) {
      var d = +digits.charAt(i);
      if (alt) { d *= 2; if (d > 9) d -= 9; }
      total += d; alt = !alt;
    }
    return total % 10 === 0;
  }

  function scanText(text, path, res) {
    if (RE_EMAIL.test(text)) res.add(Issue(path, "Looks like an email address. Remove it: the record never holds contact details.", "personal-data"));
    if (RE_SSN.test(text)) res.add(Issue(path, "Looks like a Social Security number. Remove it.", "personal-data"));
    else if (RE_PHONE.test(text)) res.add(Issue(path, "Looks like a phone number. Remove it: the record never holds contact details.", "personal-data"));
    RE_LONGNUM.lastIndex = 0;
    var m;
    while ((m = RE_LONGNUM.exec(text))) {
      var digits = m[1].replace(/[^0-9]/g, "");
      if (digits.length >= 13 && digits.length <= 19) {
        var what = luhnOk(digits) ? "a payment card number" : "a card, account or ID number";
        res.add(Issue(path, "Looks like " + what + " (" + digits.length + " digits). Remove it: the record never holds payment data.", "personal-data"));
        break;
      }
    }
    if (RE_STREET.test(text)) res.add(Issue(path, "Looks like a street address. Remove it.", "personal-data"));
    var lm = RE_LABEL.exec(text);
    if (lm) res.add(Issue(path, "Looks like a label for personal data (\"" + lm[0].trim() + "\"). Remove the label and the value.", "personal-data"));
    if (RE_TITLE_NAME.test(text)) res.add(Issue(path, "Looks like a person's name (a title such as Mr or Ms followed by a name). Remove it.", "personal-data"));
    var fm = RE_FAMILY_NAME.exec(text);
    if (fm && ["Bay", "Harbor", "Mile"].indexOf(fm[1]) < 0) res.add(Issue(path, "\"" + fm[0] + "\" may be a family name. Describe the party by counts and age bands instead.", "personal-data", "warning"));
    var hm = RE_HEALTH.exec(text);
    if (hm) res.add(Issue(path, "\"" + hm[0] + "\" may be health information about a person. Record a question about the business instead (for example: Is the vessel step-free?), never a person's condition.", "personal-data", "warning"));
  }

  function scanPersonalData(rec, res, path) {
    res = res || new Result(); path = path || "";
    if (Array.isArray(rec)) rec.forEach(function (v, i) { scanPersonalData(v, res, ptr(path, i)); });
    else if (rec && typeof rec === "object") {
      Object.keys(rec).forEach(function (k) {
        var p = ptr(path, k);
        if (personalKey(k)) res.add(Issue(p, "Field \"" + k + "\" looks like personal data. The trip record never holds names, contact details, payment data, IDs or health details.", "personal-data"));
        scanPersonalData(rec[k], res, p);
      });
    } else if (typeof rec === "string") scanText(rec, path, res);
    return res;
  }

  /* ------------------------------------------------------------ record rules */
  function parseDT(v) {
    if (typeof v !== "string" || !validDateTime(v)) return null;
    var t = Date.parse(v);
    return isNaN(t) ? null : t;
  }
  function parseD(v) { return typeof v === "string" && validDate(v) ? Date.parse(v + "T00:00:00Z") : null; }
  function obj(v) { return v && typeof v === "object" && !Array.isArray(v) ? v : {}; }
  function arr(v) { return Array.isArray(v) ? v : []; }
  function isInt(v) { return typeof v === "number" && Number.isInteger(v); }

  function rules(rec, res, now) {
    var party = obj(rec.party), bands = arr(party.age_bands);
    if (isInt(party.count) && bands.length && bands.every(function (b) { return b && isInt(b.count); })) {
      var total = bands.reduce(function (s, b) { return s + b.count; }, 0);
      if (total !== party.count) res.add(Issue("/party", "The age-band counts add up to " + total + ", but party.count is " + party.count + ".", "rule"));
      var names = bands.map(function (b) { return b.band; });
      if (names.some(function (n, i) { return names.indexOf(n) !== i; })) res.add(Issue("/party/age_bands", "An age band is listed twice. Combine the counts.", "rule"));
    }
    var dates = obj(rec.dates), arrive = parseD(dates.arrive), depart = parseD(dates.depart);
    if (arrive !== null && depart !== null) {
      if (depart < arrive) res.add(Issue("/dates", "depart is before arrive.", "rule"));
      else if ((depart - arrive) / 86400000 > 60) res.add(Issue("/dates", "The trip is longer than 60 days. Check the dates.", "rule", "warning"));
    }
    function outside(d) { return d !== null && arrive !== null && depart !== null && (d < arrive || d > depart); }
    ["shortlisted", "rejected", "holds"].forEach(function (ln) {
      arr(rec[ln]).forEach(function (it, i) { if (it && typeof it === "object" && outside(parseD(it.date))) res.add(Issue("/" + ln + "/" + i + "/date", "This date is outside the trip dates.", "rule", "warning")); });
    });
    function key(it) { return JSON.stringify([it.product_id === undefined ? null : it.product_id, it.date === undefined ? null : it.date, it.departure === undefined ? null : it.departure]); }
    var rejKeys = arr(rec.rejected).filter(function (r) { return r && typeof r === "object"; }).map(key);
    arr(rec.shortlisted).forEach(function (s, i) {
      if (s && typeof s === "object" && rejKeys.indexOf(key(s)) >= 0) res.add(Issue("/shortlisted/" + i, "The same option is both short-listed and rejected. Keep it in one list.", "rule", "warning"));
    });
    var holds = arr(rec.holds), seen = {};
    holds.forEach(function (h, i) {
      if (!h || typeof h !== "object") return;
      var hid = h.hold_id;
      if (typeof hid === "string") { if (seen[hid]) res.add(Issue("/holds/" + i + "/hold_id", "Hold " + hid + " is listed twice.", "rule")); seen[hid] = 1; }
      var placed = parseDT(h.placed_at), expires = parseDT(h.expires_at);
      if (placed !== null && expires !== null && expires <= placed) res.add(Issue("/holds/" + i + "/expires_at", "The hold expires before it was placed.", "rule"));
      if ((h.status === "active" || h.status === "pending_staff_confirmation") && expires !== null && expires <= now) {
        res.add(Issue("/holds/" + i + "/expires_at", "Hold " + hid + " was set to expire at " + h.expires_at + ", which has passed. A live server reports it as expired and the seats go back on sale. That is how a reversible hold works.", "rule", "warning"));
      }
      if (h.status === "pending_staff_confirmation" && !h.confirmation_id) res.add(Issue("/holds/" + i, "A hold waiting for staff has no confirmation_id.", "rule", "warning"));
      if (isInt(h.seats) && isInt(party.count) && h.seats > party.count) res.add(Issue("/holds/" + i + "/seats", "The hold has more seats than the party has people.", "rule", "warning"));
    });
    var consent = obj(rec.consent);
    var live = holds.filter(function (h) { return h && typeof h === "object" && ["active", "pending_staff_confirmation", "confirmed"].indexOf(h.status) >= 0; });
    if (live.length && consent.agent_may_place_holds === false) res.add(Issue("/consent/agent_may_place_holds", "The record has holds, but consent says the agent may not place holds.", "rule"));
    if (consent.traveler_reviewed === false && live.length) res.add(Issue("/consent/traveler_reviewed", "There are holds the traveler has not reviewed yet. Review comes before confirmation.", "rule", "warning"));
    var qids = {};
    arr(rec.open_questions).forEach(function (q, i) {
      if (!q || typeof q !== "object") return;
      if (q.status === "answered" && !q.answer) res.add(Issue("/open_questions/" + i, "Marked answered, but there is no answer.", "rule", "warning"));
      if (typeof q.id === "string") { if (qids[q.id]) res.add(Issue("/open_questions/" + i + "/id", "Question id " + q.id + " is used twice.", "rule")); qids[q.id] = 1; }
    });
  }

  /* ------------------------------------------------------------ entry point */
  function validate(record, schema, now) {
    var res = new Result(), found = [];
    now = now === undefined ? Date.now() : (now instanceof Date ? now.getTime() : now);
    check(record, schema, "", schema, found);
    found.forEach(function (i) { res.add(i); });
    scanPersonalData(record, res, "");
    var specific = {};
    res.errors.forEach(function (i) { if (i.kind === "personal-data" && i.message !== GENERIC_PERSONAL) specific[i.path] = 1; });
    res.errors = res.errors.filter(function (i) { return !(i.message === GENERIC_PERSONAL && specific[i.path]); });
    if (jsonType(record) === "object") rules(record, res, now);
    return res;
  }

  var API = { validate: validate, scanPersonalData: scanPersonalData, personalKey: personalKey, luhnOk: luhnOk, Result: Result };
  if (typeof module === "object" && module.exports) module.exports = API;
  else root.TripRecord = API;
})(typeof window !== "undefined" ? window : this);
