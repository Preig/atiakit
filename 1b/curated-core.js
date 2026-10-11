/* Tool 1.b "Your own curated ten": core logic with no page code in it.
 * Used by index.html in the browser and by the tests in dev/ under Node.
 * Nothing here sends data anywhere. All checks are plain text matching.
 */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.CuratedCore = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /* ---------- inventory columns ---------- */
  var COLUMNS = [
    { key: "product_id", label: "Product ID", hint: "short code", aliases: ["product id", "id", "product code", "code", "sku", "trip id"] },
    { key: "business", label: "Business", hint: "who runs it", aliases: ["operator", "company", "partner", "business name", "provider"] },
    { key: "product", label: "Product", hint: "the trip, in plain words", aliases: ["trip", "tour", "activity", "product name", "name", "trip name"] },
    { key: "duration", label: "Duration", hint: "like 4 hours", aliases: ["length", "time", "how long"] },
    { key: "minimum_age", label: "Minimum age", hint: "years", aliases: ["min age", "age minimum", "ages", "age", "minimum age years"] },
    { key: "season", label: "Season", hint: "dates it runs", aliases: ["dates", "operating season", "season dates", "operating dates"] },
    { key: "departures", label: "Departures", hint: "start times", aliases: ["departure times", "times", "schedule", "start times", "departure"] },
    { key: "runs_in_rain", label: "Runs in rain", hint: "and when it cancels", aliases: ["rain", "rain policy", "weather", "weather policy", "in rain"] },
    { key: "distance_from_meeting_point", label: "Distance from meeting point", hint: "walk or drive time", aliases: ["distance", "meeting point", "travel time", "drive time", "distance from dock", "location"] },
    { key: "notes", label: "Notes", hint: "other checkable facts", aliases: ["note", "other", "details", "other facts", "facts"] }
  ];
  var KEYS = COLUMNS.map(function (c) { return c.key; });
  var QKEYS = ["who", "time", "matters"];
  var QUESTION_TEXT = { who: "Who is traveling?", time: "How much time do you have?", matters: "What matters most?" };
  var DRAFT = "DRAFT - PENDING OWNER REVIEW";

  /* ---------- fictional teaching data (Bay Light Day Cruises, Seward; same facts as KIT.demo) ---------- */
  var DEMO = {
    items: [
      {
        product_id: "BL-CRUISE-4H", business: "Bay Light Day Cruises", product: "Wildlife and glacier cruise",
        duration: "4 hours", minimum_age: "4", season: "May 15 to September 15", departures: "9:00 and 14:00",
        runs_in_rain: "Yes. Cancels only for a marine warning, with a full refund.",
        distance_from_meeting_point: "Small-boat harbor, a 12-minute walk from the cruise ship dock",
        notes: "FICTIONAL EXAMPLE. Capacity 40. Heated enclosed cabin, two restrooms, hot drinks included, lunch not included."
      },
      {
        product_id: "MK-CART-90", business: "Mile 12 Kennel", product: "Summer sled-dog cart ride",
        duration: "90 minutes", minimum_age: "2", season: "Summer", departures: "",
        runs_in_rain: "Yes", distance_from_meeting_point: "15 minutes by car from the harbor",
        notes: "FICTIONAL EXAMPLE. How guests without a car get there: not supplied."
      },
      {
        product_id: "HK-PADDLE-3H", business: "Harbor Kayak Co.", product: "Guided paddle",
        duration: "3 hours", minimum_age: "12", season: "", departures: "8:00 and 13:00",
        runs_in_rain: "Not supplied. Cancels in wind over 15 knots.", distance_from_meeting_point: "",
        notes: "FICTIONAL EXAMPLE. Meeting point not supplied."
      }
    ],
    questions: {
      who: ["Family with children under 10", "A couple", "Adults, solo or in a group"],
      time: ["A few hours (cruise ship stop)", "A full day", "Several days or more"],
      matters: ["Wildlife and photos", "Easy with young kids", "Fitting the most into a short stop", "Being outdoors and active"]
    },
    types: [
      { name: "Family with children under 10", who: "Family with children under 10", time: "", matters: "Easy with young kids" },
      { name: "Serious photographer", who: "", time: "", matters: "Wildlife and photos" },
      { name: "Cruise ship day visitor with 5 hours ashore", who: "", time: "A few hours (cruise ship stop)", matters: "Fitting the most into a short stop" },
      { name: "Couple on a 10-day road trip", who: "A couple", time: "Several days or more", matters: "Being outdoors and active" }
    ],
    picks: [
      {
        traveler_type: "Family with children under 10",
        picks: [
          { product_id: "MK-CART-90", business: "Mile 12 Kennel", reason: "Children aged 2 and up can ride, and the ride takes 90 minutes. It runs in rain, so bring rain gear for everyone.", cited_fact: "Minimum age 2" },
          { product_id: "BL-CRUISE-4H", business: "Bay Light Day Cruises", reason: "Children aged 4 and up can come, and the heated enclosed cabin has two restrooms. Lunch is not included, so pack food for the 4 hours.", cited_fact: "Heated enclosed cabin, two restrooms, hot drinks included, lunch not included" }
        ],
        note_if_fewer_than_three: "Only two trips fit. Harbor Kayak Co. has a minimum age of 12. If a child is under 4, only the sled-dog cart ride fits."
      },
      {
        traveler_type: "Serious photographer",
        picks: [
          { product_id: "BL-CRUISE-4H", business: "Bay Light Day Cruises", reason: "Four hours on a cruise built around wildlife and the glacier. It runs in rain, so bring rain cover for your camera.", cited_fact: "Wildlife and glacier cruise" },
          { product_id: "HK-PADDLE-3H", business: "Harbor Kayak Co.", reason: "A 3-hour guided paddle with departures at 8:00 and 13:00. It cancels in wind over 15 knots, so keep a spare day in your plan.", cited_fact: "Departures 8:00 and 13:00" }
        ],
        note_if_fewer_than_three: "Only two trips fit. The facts do not say how much time the sled-dog cart ride allows for photos. Ask Mile 12 Kennel."
      },
      {
        traveler_type: "Cruise ship day visitor with 5 hours ashore",
        picks: [
          { product_id: "BL-CRUISE-4H", business: "Bay Light Day Cruises", reason: "The harbor is a 12-minute walk from the cruise ship dock and the cruise takes 4 hours. Check that the 9:00 or 14:00 departure fits your ship's hours.", cited_fact: "a 12-minute walk from the cruise ship dock" },
          { product_id: "MK-CART-90", business: "Mile 12 Kennel", reason: "The ride takes 90 minutes and the kennel is 15 minutes by car from the harbor. Arrange your ride there first: ask Mile 12 Kennel how guests without a car get there.", cited_fact: "15 minutes by car from the harbor" }
        ],
        note_if_fewer_than_three: "Only two trips fit. Harbor Kayak Co. is left out until we know its meeting point and the travel time from the dock."
      },
      {
        traveler_type: "Couple on a 10-day road trip",
        picks: [
          { product_id: "BL-CRUISE-4H", business: "Bay Light Day Cruises", reason: "A 4-hour wildlife and glacier cruise that runs from May 15 to September 15, with a heated cabin and hot drinks included.", cited_fact: "May 15 to September 15" },
          { product_id: "HK-PADDLE-3H", business: "Harbor Kayak Co.", reason: "A 3-hour guided paddle for ages 12 and up. It cancels in wind over 15 knots, so pick a day early in your 10 days and keep a backup plan.", cited_fact: "Minimum age 12" },
          { product_id: "MK-CART-90", business: "Mile 12 Kennel", reason: "A 90-minute sled-dog cart ride, 15 minutes by car from the harbor, that runs in rain. It fits between drives.", cited_fact: "Summer sled-dog cart ride" }
        ],
        note_if_fewer_than_three: ""
      }
    ],
    settings: {
      title: "Which trip fits you?",
      intro: "Answer three quick questions. You will see up to three trips that fit, each with the reason it made the cut. The trips are run by us and two local partners.",
      closing: "Fictional teaching example: Bay Light Day Cruises, Mile 12 Kennel and Harbor Kayak Co. are invented businesses. Check times and terms with each business before you book.",
      accent: "#176374",
      links: {}
    }
  };
  var BLANK_SETTINGS = {
    title: "Which trip fits you?",
    intro: "Answer three quick questions. You will see up to three trips that fit, each with the reason it made the cut.",
    closing: "Check times and terms with each business before you book.",
    accent: "#176374",
    links: {}
  };

  /* ---------- small helpers ---------- */
  function str(v) { return v === undefined || v === null ? "" : String(v); }
  function clone(o) { return JSON.parse(JSON.stringify(o)); }
  function norm(s) {
    var t = str(s);
    if (t.normalize) t = t.normalize("NFKC");
    return t.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, " ").trim();
  }
  function containsWords(hay, needle) {
    if (!needle) return false;
    return (" " + hay + " ").indexOf(" " + needle + " ") >= 0;
  }
  function esc(s) {
    return str(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }
  function hash(s) {
    var h = 5381, t = str(s);
    for (var i = 0; i < t.length; i++) h = ((h << 5) + h + t.charCodeAt(i)) | 0;
    return (h >>> 0).toString(36);
  }
  function cap(s) { s = str(s); return s.charAt(0).toUpperCase() + s.slice(1); }
  function blankItem() { var o = {}; KEYS.forEach(function (k) { o[k] = ""; }); return o; }
  function cleanItem(it) { var o = {}; KEYS.forEach(function (k) { o[k] = str(it && it[k]).trim(); }); return o; }
  function businesses(items) {
    var seen = {}, out = [];
    (items || []).forEach(function (it) {
      var b = str(it.business).trim();
      if (b && !seen[norm(b)]) { seen[norm(b)] = 1; out.push(b); }
    });
    return out;
  }

  /* ---------- CSV ---------- */
  function detectDelimiter(text) {
    var first = str(text).split(/\r\n|\n|\r/)[0] || "";
    var best = ",", count = (first.match(/,/g) || []).length;
    [";", "\t"].forEach(function (d) {
      var n = first.split(d).length - 1;
      if (n > count) { best = d; count = n; }
    });
    return best;
  }
  function parseCSV(text, delim) {
    text = str(text).replace(/^\uFEFF/, "");
    var d = delim || detectDelimiter(text);
    var rows = [], row = [], field = "", inQ = false, i = 0, c;
    while (i < text.length) {
      c = text.charAt(i);
      if (inQ) {
        if (c === '"') {
          if (text.charAt(i + 1) === '"') { field += '"'; i += 2; continue; }
          inQ = false; i++; continue;
        }
        field += c; i++; continue;
      }
      if (c === '"' && field.trim() === "") { inQ = true; field = ""; i++; continue; }
      if (c === d) { row.push(field); field = ""; i++; continue; }
      if (c === "\r" || c === "\n") {
        row.push(field); rows.push(row); row = []; field = "";
        if (c === "\r" && text.charAt(i + 1) === "\n") i++;
        i++; continue;
      }
      field += c; i++;
    }
    if (field !== "" || row.length) { row.push(field); rows.push(row); }
    return rows.filter(function (r) { return r.some(function (v) { return str(v).trim() !== ""; }); });
  }
  function csvField(v) {
    var s = str(v);
    return /[",\r\n]|^\s|\s$/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }
  function toCSV(rows) {
    return rows.map(function (r) { return r.map(csvField).join(","); }).join("\r\n") + "\r\n";
  }
  function headerKey(h) {
    var n = norm(h);
    for (var i = 0; i < COLUMNS.length; i++) {
      var c = COLUMNS[i];
      if (n === norm(c.key) || n === norm(c.label)) return c.key;
    }
    for (var j = 0; j < COLUMNS.length; j++) {
      if (COLUMNS[j].aliases.some(function (a) { return norm(a) === n; })) return COLUMNS[j].key;
    }
    return null;
  }
  function inventoryFromCSV(text) {
    var rows = parseCSV(text);
    if (!rows.length) return { items: [], error: "No rows found. Check that you picked the right file or pasted the rows." };
    var map = rows[0].map(headerKey);
    var known = map.filter(Boolean);
    if (known.indexOf("product") < 0 && known.indexOf("product_id") < 0) {
      return { items: [], error: "The first line needs column names, such as product_id, business, product. Download inventory-template.csv to see the layout." };
    }
    var ignored = [], items = [], notes = [];
    rows[0].forEach(function (h, i) { if (!map[i] && str(h).trim()) ignored.push(str(h).trim()); });
    rows.slice(1).forEach(function (r) {
      var it = blankItem();
      map.forEach(function (k, i) {
        if (!k) return;
        var v = str(r[i]).trim();
        it[k] = it[k] ? it[k] + " " + v : v;
      });
      if (KEYS.some(function (k) { return it[k]; })) items.push(it);
    });
    var made = 0;
    items.forEach(function (it, i) {
      if (!it.product_id) { it.product_id = "TRIP-" + (i + 1); made++; }
    });
    if (made) notes.push(made + " row(s) had no product_id, so a code like TRIP-1 was added. Change it to your own code.");
    if (ignored.length) notes.push("Ignored columns: " + ignored.join(", ") + ".");
    return { items: items, ignored: ignored, notes: notes, error: items.length ? null : "The file has column names but no trip rows." };
  }
  function inventoryToCSV(items) {
    var rows = [KEYS.slice()];
    (items || []).forEach(function (it) { rows.push(KEYS.map(function (k) { return str(it[k]); })); });
    return toCSV(rows);
  }
  function checkInventory(items) {
    var issues = [], seen = {};
    (items || []).forEach(function (it, i) {
      var id = str(it.product_id).trim(), where = "Trip " + (i + 1);
      if (!id) issues.push({ level: "error", where: where, msg: "has no product_id. Give it a short code, like BL-CRUISE-4H." });
      else if (seen[id.toLowerCase()]) issues.push({ level: "error", where: where, msg: "uses the product_id " + id + " again. Each trip needs its own code." });
      if (id) seen[id.toLowerCase()] = 1;
      if (!str(it.business).trim()) issues.push({ level: "warn", where: where, msg: "has no business name." });
      if (!str(it.product).trim()) issues.push({ level: "warn", where: where, msg: "has no product name." });
    });
    if ((items || []).length > 10) issues.push({ level: "warn", where: "Inventory", msg: "has " + items.length + " trips. Ten is a ceiling, not a target. A shorter list is easier to choose from." });
    return issues;
  }
  function emptyCount(items) {
    var n = 0;
    (items || []).forEach(function (it) { KEYS.forEach(function (k) { if (!str(it[k]).trim()) n++; }); });
    return n;
  }

  /* ---------- prompts ---------- */
  function inventoryBlock(items) {
    return (items || []).map(function (it) {
      var lines = ["[" + (str(it.product_id).trim() || "[FILL]") + "]"];
      COLUMNS.slice(1).forEach(function (c) {
        lines.push(c.label.toLowerCase() + ": " + (str(it[c.key]).trim() || "[FILL]"));
      });
      return lines.join("\n");
    }).join("\n\n");
  }
  function ownerAndPartners(items) {
    var b = businesses(items);
    return { owner: b[0] || "[YOUR BUSINESS]", partners: b.slice(1) };
  }
  function listText(arr) {
    if (!arr.length) return "";
    if (arr.length === 1) return arr[0];
    return arr.slice(0, -1).join(", ") + " and " + arr[arr.length - 1];
  }
  function buildInstructions(items) {
    var op = ownerAndPartners(items);
    var partners = op.partners.length ? " and its partners (" + listText(op.partners) + ")" : " and its partners ([PARTNER NAMES])";
    return [
      "ROLE",
      "You help " + op.owner + " draft a \"Which trip fits you?\" page. It recommends trips run by " + op.owner + partners + " to the traveler types we actually see.",
      "",
      "SOURCES",
      "Use only the inventory pasted in each request and the approved fact sheets in this project's files. Reviews in the files are background only. Do not quote them on the page.",
      "",
      "RULES",
      "1. Pick only trips whose product_id appears in the inventory. Pick at most three per traveler type. If fewer than three fit, say so and do not pad.",
      "2. Give every pick a reason of one or two sentences, and a cited_fact copied word for word from that trip's block in the inventory.",
      "3. Do not invent facts about our business or our partners. Do not mention prices, discounts, availability, reviews, ratings or awards. No superlatives such as \"best\" or \"unforgettable\".",
      "4. Where a missing fact ([FILL]) would change a pick, leave the trip out and add a question for the owner.",
      "5. Safety calls (weather go/no-go, sea and glacier conditions, wildlife distance, first aid) belong to each operator's qualified staff. Do not make them or promise conditions.",
      "6. Never ask for or repeat guest names, emails, phone numbers, payment details or health information.",
      "7. Start every reply with " + DRAFT + ". Each business approves its own lines before anything is published."
    ].join("\n");
  }
  function typeNames(types) {
    return (types || []).map(function (t) { return str(t.name).trim(); }).filter(Boolean);
  }
  function buildRunPrompt(items, types) {
    var op = ownerAndPartners(items);
    var names = typeNames(types);
    var example = names[0] || "Family with children under 10";
    var typeLines = names.length ? names.map(function (n, i) { return (i + 1) + ". " + n; }).join("\n") : "[LIST YOUR TRAVELER TYPES]";
    return [
      ("Draft \"Which trip fits you?\" picks for " + op.owner + (op.partners.length ? " and partners " + listText(op.partners) : "") + ".").replace(/\.\.$/, "."),
      "",
      "INVENTORY (approved facts, one block per trip; the code in brackets is the product_id)",
      (items && items.length ? inventoryBlock(items) : "[PASTE YOUR INVENTORY]"),
      "",
      "TRAVELER TYPES WE ACTUALLY SEE",
      typeLines,
      "",
      "TASK",
      "For each traveler type, choose up to three trips from the inventory only. For each pick, write a reason of one or two sentences that a traveler could check, and copy one supporting fact word for word from that trip's block into cited_fact (for example \"Minimum age 4\" or a phrase from its notes). If fewer than three trips fit, explain why in note_if_fewer_than_three and do not pad. Leave a trip out when a missing fact ([FILL]) decides whether it fits.",
      "Use only the facts above; do not invent facts about any business. No prices, discounts, availability, reviews, ratings, awards or superlatives. Do not make safety calls or promise weather, sea or wildlife conditions.",
      "",
      "OUTPUT, in this order",
      "A. The line " + DRAFT + ".",
      "B. Page copy under 300 words: a one-line intro, then each traveler type with its picks and a \"Why it made the cut\" line under each pick. No prices, availability, discounts, reviews, awards or superlatives.",
      "C. One JSON block inside a ```json fence. Use exactly this shape: one object per traveler type, in the order listed, with traveler_type copied exactly. No comments and no extra fields.",
      "[",
      "  {",
      "    \"traveler_type\": \"" + example.replace(/"/g, "'") + "\",",
      "    \"picks\": [",
      "      { \"product_id\": \"...\", \"business\": \"...\", \"reason\": \"...\", \"cited_fact\": \"...\" }",
      "    ],",
      "    \"note_if_fewer_than_three\": \"\"",
      "  }",
      "]",
      "Use \"\" for note_if_fewer_than_three when a list has three picks.",
      "D. Questions for the owner: each missing fact that would change a pick, with the business it belongs to."
    ].join("\n");
  }

  /* ---------- JSON extraction with readable errors ---------- */
  function lineCol(text, pos) {
    var before = text.slice(0, Math.max(0, pos)), lines = before.split("\n");
    return { line: lines.length, col: lines[lines.length - 1].length + 1 };
  }
  function errorPos(err, candidate) {
    var m = /position (\d+)/i.exec(err && err.message || "");
    if (m) return +m[1];
    m = /line (\d+) column (\d+)/i.exec(err && err.message || "");
    if (m) {
      var lines = candidate.split("\n"), p = 0, ln = +m[1], col = +m[2];
      for (var i = 0; i < ln - 1 && i < lines.length; i++) p += lines[i].length + 1;
      return p + col - 1;
    }
    return -1;
  }
  function tryParse(s) { try { return { ok: true, value: JSON.parse(s) }; } catch (e) { return { ok: false, error: e }; } }
  function repaired(s) {
    var t = s, notes = [];
    if (/[\u201C\u201D\u201E\u201F\u2033]/.test(t)) { t = t.replace(/[\u201C\u201D\u201E\u201F\u2033]/g, '"'); notes.push("Curly quotes were changed to straight quotes so the JSON could be read."); }
    if (/,\s*[}\]]/.test(t)) { t = t.replace(/,(\s*[}\]])/g, "$1"); notes.push("A trailing comma was removed so the JSON could be read."); }
    return { text: t, notes: notes };
  }
  function candidates(text) {
    var out = [], m, fence = /```[ \t]*([A-Za-z]*)[^\n]*\n([\s\S]*?)```/g;
    while ((m = fence.exec(text))) {
      var body = m[2], lang = m[1].toLowerCase();
      if (lang === "json" || /^\s*[\[{]/.test(body)) out.push({ text: body, offset: m.index + m[0].indexOf(body), fenced: true });
    }
    if (out.length) return out;
    var t = text.trim();
    if (/^[\[{]/.test(t)) out.push({ text: t, offset: text.indexOf(t) });
    [/\[\s*\{/g, /\{\s*"/g].forEach(function (re) {
      var mm, n = 0;
      while ((mm = re.exec(text)) && n < 20) {
        var end = closeOf(text, mm.index);
        n++;
        if (end > mm.index) { out.push({ text: text.slice(mm.index, end + 1), offset: mm.index }); re.lastIndex = end + 1; }
      }
    });
    return out;
  }
  /* Index of the bracket that closes the one at text[start], skipping over strings. -1 if none. */
  function closeOf(text, start) {
    var depth = 0, inS = false, c;
    for (var i = start; i < text.length; i++) {
      c = text.charAt(i);
      if (inS) {
        if (c === "\\") i++;
        else if (c === '"') inS = false;
        continue;
      }
      if (c === '"') inS = true;
      else if (c === "[" || c === "{") depth++;
      else if (c === "]" || c === "}") { depth--; if (depth === 0) return i; }
    }
    return -1;
  }
  function extractJSON(text) {
    text = str(text).replace(/\r\n?/g, "\n");
    if (!text.trim()) return { error: { message: "Nothing to check yet. Paste the AI's reply, or just its JSON block." } };
    var cands = candidates(text);
    if (!cands.length) return { error: { message: "No JSON found. The reply needs a block that starts with [ and ends with ]. Ask the AI: \"Give me only the JSON block from part C.\"" } };
    var values = [], notes = [], firstErr = null;
    var fenced = cands[0].fenced;
    for (var i = 0; i < cands.length; i++) {
      var c = cands[i], r = tryParse(c.text);
      if (!r.ok) {
        var rp = repaired(c.text), r2 = tryParse(rp.text);
        if (r2.ok) { r = r2; notes = notes.concat(rp.notes); }
        else if (!firstErr) {
          var p = errorPos(r.error, c.text), lc = p >= 0 ? lineCol(text, c.offset + p) : null;
          firstErr = {
            message: "The JSON could not be read" + (lc ? " near line " + lc.line + ", column " + lc.col + " of what you pasted" : "") +
              ". Look for a missing comma between items, a missing quote mark, or a comment. Or ask the AI to resend only the JSON block.",
            line: lc ? lc.line : null, col: lc ? lc.col : null, detail: str(r.error && r.error.message)
          };
        }
      }
      if (r.ok) {
        values.push(r.value);
        if (!fenced) break;
      }
    }
    if (!values.length) return { error: firstErr || { message: "The JSON could not be read." } };
    var value = values.length === 1 ? values[0] : values.reduce(function (acc, v) { return acc.concat(Array.isArray(v) ? v : [v]); }, []);
    return { value: value, notes: notes };
  }
  function looksLikeList(o) { return o && typeof o === "object" && !Array.isArray(o) && ("traveler_type" in o || "picks" in o); }
  function toLists(value) {
    if (Array.isArray(value)) return { lists: value };
    if (looksLikeList(value)) return { lists: [value] };
    if (value && typeof value === "object") {
      for (var k in value) {
        if (Object.prototype.hasOwnProperty.call(value, k) && Array.isArray(value[k]) && value[k].some(looksLikeList)) return { lists: value[k] };
      }
    }
    return { error: "The JSON was read, but it is not a list of traveler types. Expected [ { \"traveler_type\": ..., \"picks\": [...], \"note_if_fewer_than_three\": ... } ]." };
  }

  /* ---------- number guard and word checks ---------- */
  function numbersIn(s) {
    var out = [], m, re = /\d+(?:[.,:]\d+)*/g, t = str(s);
    while ((m = re.exec(t))) {
      var n = m[0];
      if (/^\d{1,3}(,\d{3})+$/.test(n)) n = n.replace(/,/g, "");
      out.push(n);
    }
    return out;
  }
  function numberSet(texts) {
    var set = {};
    texts.forEach(function (t) {
      numbersIn(t).forEach(function (n) {
        set[n] = 1;
        var h = /^(\d{1,2}):\d{2}$/.exec(n);
        if (h) set[String(+h[1])] = 1;
      });
    });
    return set;
  }
  function inSet(set, n) { return set[n] === 1; }
  var WORD_RULES = [
    { kind: "price", re: /\$\s?\d+(?:[.,]\d+)*|\bUSD\b|\bprice[sd]?\b|\bcosts?\b|\bfees?\b|\bdiscounts?\b|\bdeals?\b|\bcoupons?\b|\bon sale\b|\bcheap(er|est)?\b|\bfree\b|\bpromo\b/i, msg: "mentions price or money" },
    { kind: "availability", re: /\bavailab(le|ility)\b|\bsold out\b|\b(spots?|seats?|places?) left\b|\bbook now\b|\blast chance\b|\bopenings?\b/i, msg: "mentions availability" },
    { kind: "superlative", re: /\bbest\b|\bunforgettable\b|\bworld[- ]class\b|\bstunning\b|\bperfect\b|\bamazing\b|\bbreathtaking\b|\bonce[- ]in[- ]a[- ]lifetime\b|\bguarantee[ds]?\b|\bmust[- ]see\b|\bmost popular\b/i, msg: "uses a generic claim or promise" },
    { kind: "reviews", re: /\bawards?\b|\baward-winning\b|\brated\b|\b\d(\.\d)?\s?stars?\b|\b5-star\b|\btripadvisor\b|\breviewers?\b/i, msg: "mentions reviews, ratings or awards" }
  ];
  /* open template slots such as [FILL] or [PARTNER NAMES]; product codes like [BL-CRUISE-4H] are not matched */
  var PLACEHOLDER = /\[(?:FILL|[A-Z]+(?: [A-Z]+)+)\]/;
  function wordFlags(s) {
    var out = [];
    WORD_RULES.forEach(function (r) { var m = r.re.exec(str(s)); if (m) out.push({ kind: r.kind, word: m[0], msg: r.msg }); });
    return out;
  }
  function luhn(d) {
    var sum = 0, alt = false;
    for (var i = d.length - 1; i >= 0; i--) {
      var n = +d.charAt(i);
      if (alt) { n *= 2; if (n > 9) n -= 9; }
      sum += n; alt = !alt;
    }
    return d.length >= 13 && sum % 10 === 0;
  }
  function findPII(s) {
    var hits = [], m, t = str(s);
    var email = /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi;
    while ((m = email.exec(t))) hits.push({ kind: "an email address", text: m[0] });
    var phone = /(?:\+?1[\s.-]?)?(?:\(\d{3}\)|\b\d{3})[\s.-]?\d{3}[\s.-]?\d{4}\b/g;
    while ((m = phone.exec(t))) hits.push({ kind: "a phone number", text: m[0] });
    var card = /\b\d(?:[ -]?\d){12,18}\b/g;
    while ((m = card.exec(t))) { if (luhn(m[0].replace(/\D/g, ""))) hits.push({ kind: "a card number", text: m[0] }); }
    return hits;
  }
  function mask(s) { s = str(s); return s.length <= 4 ? "****" : s.slice(0, 3) + "***"; }

  /* ---------- the validator ---------- */
  function rowTexts(it) {
    var plain = [], labeled = [];
    COLUMNS.forEach(function (c) {
      var v = str(it[c.key]).trim();
      if (!v) return;
      plain.push(v);
      labeled.push(c.label + " " + v);
    });
    return { plain: norm(plain.join(" | ")), labeled: norm(labeled.join(" | ")), all: plain.join(" ") };
  }
  function factInRow(fact, it) {
    var f = norm(fact), r = rowTexts(it);
    return containsWords(r.plain, f) || containsWords(r.labeled, f);
  }
  function validatePicks(text, items, types) {
    var res = { ok: false, errors: [], warnings: [], infos: [], lists: [], pickCount: 0 };
    function err(where, msg) { res.errors.push({ level: "error", where: where, msg: msg }); }
    function warn(where, msg) { res.warnings.push({ level: "warn", where: where, msg: msg }); }
    function info(where, msg) { res.infos.push({ level: "info", where: where, msg: msg }); }
    items = (items || []).map(cleanItem);
    var names = typeNames(types);
    if (!items.length) { err("Inventory", "is empty. Add your trips in step 1 first."); return res; }

    var ex = extractJSON(text);
    if (ex.error) { err("JSON", ex.error.message); res.parseError = ex.error; return res; }
    (ex.notes || []).forEach(function (n) { info("JSON", n); });
    var tl = toLists(ex.value);
    if (tl.error) { err("JSON", tl.error); return res; }

    var byId = {}, byIdLower = {};
    items.forEach(function (it) { if (it.product_id) { byId[it.product_id] = it; byIdLower[it.product_id.toLowerCase()] = it; } });
    var ids = items.map(function (it) { return it.product_id; }).filter(Boolean);
    var allTexts = [];
    /* numbers inside product codes (the 3 in HK-PADDLE-3H) are not facts, so the number guard skips the product_id column */
    var FACT_KEYS = KEYS.filter(function (k) { return k !== "product_id"; });
    items.forEach(function (it) { FACT_KEYS.forEach(function (k) { allTexts.push(it[k]); }); });
    var typeTexts = names.slice();
    tl.lists.forEach(function (l) { if (l && typeof l.traveler_type === "string") typeTexts.push(l.traveler_type); });
    var allNums = numberSet(allTexts.concat(typeTexts));

    var seenTypes = {};
    tl.lists.forEach(function (l, li) {
      var where = "List " + (li + 1);
      if (!l || typeof l !== "object" || Array.isArray(l)) { err(where, "is not an object with traveler_type, picks and note_if_fewer_than_three."); return; }
      var tt = typeof l.traveler_type === "string" ? l.traveler_type.trim() : "";
      if (!tt) { err(where, "has no traveler_type."); }
      else {
        where = where + " (" + tt + ")";
        if (seenTypes[norm(tt)]) warn(where, "appears twice. The picker will show both lists.");
        seenTypes[norm(tt)] = 1;
        if (names.length && !names.some(function (n) { return norm(n) === norm(tt); })) {
          warn(where, "is not one of your traveler types in step 2, so the picker shows it for any answers. Match the name exactly, or add it in step 2.");
        }
      }
      if (!Array.isArray(l.picks)) { err(where, "has no picks list (\"picks\": [ ... ])."); return; }
      if (l.picks.length > 3) err(where, "has " + l.picks.length + " picks. The limit is three. Ask the AI to cut it to the three strongest.");
      var note = l.note_if_fewer_than_three;
      if (note !== undefined && note !== null && typeof note !== "string") { warn(where, "has a note_if_fewer_than_three that is not text."); note = str(note); }
      note = str(note).trim();
      if (!("note_if_fewer_than_three" in l)) warn(where, "has no note_if_fewer_than_three field. Use \"\" when there are three picks.");
      else if (l.picks.length < 3 && !note) warn(where, "has fewer than three picks and no note saying why.");
      if (l.picks.length === 0) warn(where, "has no picks. That is allowed if nothing fits; the picker will show the note only.");

      var listTypeNums = numberSet([tt]);
      var seenIds = {}, outPicks = [];
      l.picks.forEach(function (p, pi) {
        var pw = where + ", pick " + (pi + 1);
        if (!p || typeof p !== "object" || Array.isArray(p)) { err(pw, "is not an object with product_id, business, reason and cited_fact."); return; }
        var pid = str(p.product_id).trim();
        var row = byId[pid];
        if (!pid) { err(pw, "has no product_id."); return; }
        if (!row && byIdLower[pid.toLowerCase()]) {
          row = byIdLower[pid.toLowerCase()];
          info(pw, "product_id " + pid + " differs in capital letters from " + row.product_id + ". Treated as the same trip.");
        }
        if (!row) { err(pw, "product_id " + pid + " is not in your inventory. Your codes are: " + ids.join(", ") + "."); return; }
        pw = pw + " (" + row.product_id + ")";
        if (seenIds[row.product_id]) err(pw, "repeats a trip already picked in this list.");
        seenIds[row.product_id] = 1;
        if (p.business && norm(p.business) !== norm(row.business)) warn(pw, "says the business is \"" + str(p.business) + "\" but your inventory says \"" + row.business + "\". The picker uses the inventory name.");
        var reason = str(p.reason).trim(), fact = str(p.cited_fact).trim();
        if (!reason) err(pw, "has no reason.");
        else if (reason.length > 320) warn(pw, "has a long reason (" + reason.length + " characters). Two short sentences read better on a phone.");
        if (!fact) err(pw, "has no cited_fact.");
        else if (!factInRow(fact, row)) {
          var other = items.filter(function (it) { return it !== row && factInRow(fact, it); })[0];
          err(pw, "cites \"" + fact + "\", which is not in that trip's row" + (other ? " (it is in " + other.product_id + ")" : "") + ". Copy a phrase from the row, such as \"Minimum age " + (row.minimum_age || "[FILL]") + "\".");
        } else if (/^[\d\s.,:]+$/.test(fact) || norm(fact).length < 4) {
          warn(pw, "cites only \"" + fact + "\". Name the column too, like \"Minimum age " + (row.minimum_age || "4") + "\", so a reader knows what it means.");
        }
        var rowNums = numberSet(FACT_KEYS.map(function (k) { return row[k]; }).concat([tt]));
        numbersIn(reason).forEach(function (n) {
          if (inSet(rowNums, n) || inSet(listTypeNums, n)) return;
          if (inSet(allNums, n)) warn(pw, "the reason uses the number " + n + ", which belongs to a different trip's row. Check it.");
          else warn(pw, "the reason uses the number " + n + ", which is not in your inventory or traveler types. Check it or remove it.");
        });
        wordFlags(reason + " " + fact).forEach(function (f) { warn(pw, "the reason " + f.msg + " (\"" + f.word + "\"). The picker leaves out prices, availability and claims."); });
        var ph = PLACEHOLDER.exec(reason + " " + fact);
        if (ph) warn(pw, "still has an open placeholder " + ph[0] + ". Fill in the fact in step 1 and ask the AI again, or remove the pick.");
        outPicks.push({ product_id: row.product_id, business: row.business, product: row.product, reason: reason, cited_fact: fact });
      });
      numbersIn(note).forEach(function (n) {
        if (!inSet(allNums, n)) warn(where, "the note uses the number " + n + ", which is not in your inventory or traveler types. Check it or remove it.");
      });
      wordFlags(note).forEach(function (f) { warn(where, "the note " + f.msg + " (\"" + f.word + "\")."); });
      var nph = PLACEHOLDER.exec(note);
      if (nph) warn(where, "the note still has an open placeholder " + nph[0] + ". Rewrite it before publishing.");
      res.pickCount += outPicks.length;
      res.lists.push({ traveler_type: tt || ("List " + (li + 1)), picks: outPicks, note_if_fewer_than_three: note });
    });

    names.forEach(function (n) {
      if (!seenTypes[norm(n)]) warn("Traveler type \"" + n + "\"", "has no list in the JSON. Ask the AI for it, or remove the type in step 2.");
    });
    var pii = findPII(text);
    if (pii.length) warn("Personal data", "the paste contains what looks like " + pii.map(function (h) { return h.kind + " (" + mask(h.text) + ")"; }).join(", ") + ". Remove it. Guest data does not belong in this tool.");
    if (!/DRAFT/.test(str(text))) info("Draft marker", "no DRAFT marker found. That is fine for the JSON alone. Keep the AI's page copy marked " + DRAFT + " until each business approves it.");
    res.ok = res.errors.length === 0 && res.lists.length > 0;
    if (!res.lists.length && !res.errors.length) err("JSON", "contains no traveler types.");
    return res;
  }

  /* ---------- the picker snippet ---------- */
  function safeUrl(u) {
    u = str(u).trim();
    return /^https?:\/\/[^\s"'<>`]+$/i.test(u) ? u : "";
  }
  function safeColor(c) { return /^#[0-9a-f]{6}$/i.test(str(c)) ? str(c).toLowerCase() : "#176374"; }
  function textOn(hex) {
    var n = parseInt(hex.slice(1), 16), rgb = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map(function (v) {
      v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    });
    var L = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2];
    return (1.05 / (L + 0.05)) >= ((L + 0.05) / 0.05) ? "#ffffff" : "#111111";
  }
  function routeFor(types, name) {
    var t = (types || []).filter(function (x) { return norm(x.name) === norm(name); })[0];
    var r = {};
    QKEYS.forEach(function (k) { r[k] = t ? str(t[k]) : ""; });
    return r;
  }
  /* This function is copied into the snippet as text. Keep it self-contained and plain ES5. */
  function pickerRuntime(id) {
    var root = document.getElementById(id);
    if (!root || root.getAttribute("data-ready")) return;
    root.setAttribute("data-ready", "1");
    var form = root.querySelector(".tfp-q"), status = root.querySelector(".tfp-status");
    var lists = Array.prototype.slice.call(root.querySelectorAll(".tfp-list"));
    var allBtn = root.querySelector(".tfp-all"), clearBtn = root.querySelector(".tfp-clear");
    var keys = ["who", "time", "matters"];
    /* "Who is traveling?" counts three times as much as the other answers, so a family is not sent to a list meant for "Any" group over its own list. */
    var weight = { who: 3, time: 1, matters: 1 };
    if (!form || !status || !lists.length) return;
    form.hidden = false; status.hidden = false;
    var nojs = root.querySelector(".tfp-nojs");
    if (nojs) nojs.hidden = true;
    function answer(k) {
      var c = form.querySelector('input[data-q="' + k + '"]:checked');
      return c ? c.value : "";
    }
    function show(which) {
      lists.forEach(function (l) { l.hidden = which.indexOf(l) < 0; });
    }
    function update() {
      var a = {}, any = false;
      keys.forEach(function (k) { a[k] = answer(k); if (a[k]) any = true; });
      if (!any) { show([]); status.textContent = "Answer the questions to see the trips that fit."; return; }
      var best = -1, win = [];
      lists.forEach(function (l) {
        var s = 0;
        keys.forEach(function (k) {
          var r = l.getAttribute("data-" + k) || "";
          if (!a[k] || !r) s += weight[k]; else if (r === a[k]) s += 2 * weight[k];
        });
        if (s > best) { best = s; win = [l]; } else if (s === best) win.push(l);
      });
      show(win);
      var names = win.map(function (l) { return l.getAttribute("data-name"); });
      status.textContent = win.length === 1 ? "Your list: " + names[0] + "." : win.length + " lists fit your answers: " + names.join("; ") + ".";
    }
    form.addEventListener("change", update);
    form.addEventListener("submit", function (e) { e.preventDefault(); update(); });
    if (allBtn) allBtn.addEventListener("click", function () { show(lists); status.textContent = "Showing all " + lists.length + " lists."; });
    if (clearBtn) clearBtn.addEventListener("click", function () {
      Array.prototype.forEach.call(form.querySelectorAll("input:checked"), function (c) { c.checked = false; });
      update();
    });
    update();
  }

  function pickerCSS(id, accent, approved) {
    var on = textOn(accent), s = "#" + id;
    return [
      s + "{font:inherit;color:inherit;line-height:1.5;max-width:46rem;margin:1.5rem auto;text-align:left}",
      s + " *{box-sizing:border-box}",
      s + " [hidden]{display:none!important}",
      s + " .tfp-title{font-size:1.6em;line-height:1.2;margin:0 0 .4em}",
      s + " .tfp-intro{margin:0 0 1em}",
      approved ? "" : s + " .tfp-draft{border:2px dashed #b00020;color:#b00020;background:#fff5f5;padding:.5em .8em;font-weight:700;margin:0 0 1em}",
      s + " fieldset{border:1px solid rgba(127,127,127,.45);border-radius:8px;padding:.5em 1em .7em;margin:0 0 .8em;min-width:0}",
      s + " legend{font-weight:700;padding:0 .3em}",
      s + " label{display:flex;gap:.55em;align-items:flex-start;padding:.3em 0;cursor:pointer;font-weight:400;margin:0}",
      s + " input[type=radio]{accent-color:" + accent + ";width:1.15em;height:1.15em;margin:.2em 0 0;flex:none}",
      s + " .tfp-btns{display:flex;flex-wrap:wrap;gap:.6em;margin:.4em 0 1em}",
      s + " button{background:" + accent + ";color:" + on + ";border:2px solid " + accent + ";border-radius:6px;padding:.5em 1em;font:inherit;font-weight:700;cursor:pointer}",
      s + " button.tfp-clear{background:transparent;color:inherit}",
      s + " button:focus-visible," + s + " input:focus-visible," + s + " a:focus-visible{outline:3px solid " + accent + ";outline-offset:2px}",
      s + " .tfp-status{font-weight:700;margin:.4em 0 .8em}",
      s + " .tfp-list{border-left:4px solid " + accent + ";padding:.1em 0 .1em 1em;margin:0 0 1.4em}",
      s + " .tfp-list h3{font-size:1.15em;margin:.2em 0 .5em}",
      s + " .tfp-list ol{margin:0;padding-left:1.4em}",
      s + " .tfp-list li{margin:0 0 .8em}",
      s + " .tfp-biz{opacity:.85}",
      s + " .tfp-why{display:block}",
      s + " .tfp-list a{display:inline-block;margin-top:.2em}",
      s + " .tfp-meta{display:block;font-weight:700}",
      s + " .tfp-fact{display:block;font-size:.9em;opacity:.8}",
      s + " .tfp-nojs{font-style:italic;margin:0 0 1em}",
      s + " .tfp-note{font-style:italic;margin:.3em 0 0}",
      s + " .tfp-foot{font-size:.9em;opacity:.85;margin:1em 0 0}"
    ].filter(Boolean).join("\n");
  }
  /* Duration and minimum age come straight from the inventory row, so a family sees an age limit even on a list meant for adults. */
  function pickMeta(it) {
    var bits = [];
    if (str(it && it.duration).trim()) bits.push("Duration: " + str(it.duration).trim());
    if (str(it && it.minimum_age).trim()) bits.push("Minimum age: " + str(it.minimum_age).trim());
    return bits.join(" · ");
  }
  function buildPicker(opts) {
    var lists = opts.lists || [], items = (opts.items || []).map(cleanItem), types = opts.types || [];
    var q = opts.questions || DEMO.questions, st = opts.settings || BLANK_SETTINGS;
    var accent = safeColor(st.accent), links = st.links || {};
    var id = "tfp-" + hash(JSON.stringify([lists, q, types, st, !!opts.approved]));
    var byId = {};
    items.forEach(function (it) { byId[it.product_id] = it; });
    var out = [];
    out.push("<!-- \"Which trip fits you?\" picker, made with the ATIA AI Take-Home Kit, tool 1.b (preig.github.io/atiakit/1b/). -->");
    out.push("<!-- Self-contained: no outside files, no tracking, no prices or availability. If scripts are blocked, visitors still see every list. -->");
    if (!opts.approved) out.push("<!-- " + DRAFT + ". Each business approves its own lines before this goes live. -->");
    out.push('<div class="tfp" id="' + id + '">');
    out.push("<style>\n" + pickerCSS(id, accent, !!opts.approved) +"\n</style>");
    out.push('<h2 class="tfp-title">' + esc(st.title || "Which trip fits you?") + "</h2>");
    if (str(st.intro).trim()) out.push('<p class="tfp-intro">' + esc(st.intro) + "</p>");
    if (!opts.approved) out.push('<p class="tfp-draft" role="note">' + DRAFT + ". Each business approves its own lines before this goes live.</p>");
    out.push('<p class="tfp-nojs">Every list is shown below. Find the one that fits your group, and check the minimum age for each trip.</p>');
    out.push('<form class="tfp-q" hidden>');
    QKEYS.forEach(function (k) {
      var opts2 = (q[k] || []).filter(function (o) { return str(o).trim(); });
      if (!opts2.length) return;
      out.push("<fieldset><legend>" + esc(QUESTION_TEXT[k]) + "</legend>");
      opts2.forEach(function (o) {
        out.push('<label><input type="radio" name="' + id + "-" + k + '" data-q="' + k + '" value="' + esc(o) + '"> ' + esc(o) + "</label>");
      });
      out.push("</fieldset>");
    });
    out.push('<div class="tfp-btns"><button type="button" class="tfp-all">Show all lists</button><button type="button" class="tfp-clear">Clear answers</button></div>');
    out.push("</form>");
    out.push('<p class="tfp-status" role="status" aria-live="polite" hidden></p>');
    lists.forEach(function (l) {
      var r = routeFor(types, l.traveler_type);
      out.push('<section class="tfp-list" data-name="' + esc(l.traveler_type) + '" data-who="' + esc(r.who) + '" data-time="' + esc(r.time) + '" data-matters="' + esc(r.matters) + '">');
      out.push("<h3>" + esc(l.traveler_type) + "</h3>");
      if (l.picks.length) {
        out.push("<ol>");
        l.picks.forEach(function (p) {
          var it = byId[p.product_id] || {}, biz = it.business || p.business, url = safeUrl(links[biz]);
          var meta = pickMeta(it);
          var li = "<li><strong>" + esc(it.product || p.product || p.product_id) + "</strong> <span class=\"tfp-biz\">&middot; " + esc(biz) + "</span>" +
            (meta ? '<span class="tfp-meta">' + esc(meta) + "</span>" : "") +
            '<span class="tfp-why">Why it made the cut: ' + esc(p.reason) + "</span>" +
            '<span class="tfp-fact">From the fact sheet: ' + esc(cap(p.cited_fact)) + "</span>";
          if (url) li += '<a href="' + esc(url) + '" target="_blank" rel="noopener">Details from ' + esc(biz) + "</a>";
          out.push(li + "</li>");
        });
        out.push("</ol>");
      }
      if (l.note_if_fewer_than_three) out.push('<p class="tfp-note">' + esc(l.note_if_fewer_than_three) + "</p>");
      out.push("</section>");
    });
    if (str(st.closing).trim()) out.push('<p class="tfp-foot">' + esc(st.closing) + "</p>");
    out.push("<script>\n(" + pickerRuntime.toString() + ')("' + id + '");\n</script>');
    out.push("</div>");
    return out.join("\n");
  }
  function buildPlainText(opts) {
    var lists = opts.lists || [], items = (opts.items || []).map(cleanItem), st = opts.settings || BLANK_SETTINGS;
    var byId = {};
    items.forEach(function (it) { byId[it.product_id] = it; });
    var out = [];
    if (!opts.approved) out.push(DRAFT + ". Each business approves its own lines. Delete this line once they have.", "");
    out.push(st.title || "Which trip fits you?");
    if (str(st.intro).trim()) out.push(st.intro.replace(/^Answer three quick questions\.\s*/, "Find your group below. "));
    lists.forEach(function (l) {
      out.push("", l.traveler_type.toUpperCase());
      l.picks.forEach(function (p, i) {
        var it = byId[p.product_id] || {};
        out.push((i + 1) + ". " + (it.product || p.product_id) + ", " + (it.business || p.business));
        var meta = pickMeta(it);
        if (meta) out.push("   " + meta);
        out.push("   Why it made the cut: " + p.reason);
        out.push("   From the fact sheet: " + cap(p.cited_fact));
      });
      if (l.note_if_fewer_than_three) out.push("   " + l.note_if_fewer_than_three);
    });
    if (str(st.closing).trim()) out.push("", st.closing);
    return out.join("\n") + "\n";
  }
  function previewDoc(snippet) {
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">' +
      "<title>Picker preview</title><style>body{margin:0;padding:0;font:16px/1.5 Arial,Helvetica,sans-serif;color:#222;background:#fff}#pv-root{padding:12px 16px;display:flow-root}</style></head><body><div id=\"pv-root\">" +
      snippet +
      "</div><script>(function(){var r=document.getElementById(\"pv-root\");function h(){try{parent.postMessage({tfpHeight:Math.ceil(r.getBoundingClientRect().height)},\"*\");}catch(e){}}" +
      "if(window.ResizeObserver){new ResizeObserver(h).observe(r);}window.addEventListener(\"load\",h);document.addEventListener(\"change\",function(){setTimeout(h,30);});document.addEventListener(\"click\",function(){setTimeout(h,30);});setTimeout(h,60);})();</script>" +
      "</body></html>";
  }
  function demoReply() {
    return [
      DRAFT,
      "(Fictional teaching example: Bay Light Day Cruises, Seward, with partners Mile 12 Kennel and Harbor Kayak Co.)",
      "",
      "B. PAGE COPY",
      "Which trip fits you? Three quick questions, then up to three trips that fit, each with the reason it made the cut.",
      "",
      "Family with children under 10",
      "1. Summer sled-dog cart ride, Mile 12 Kennel. Why it made the cut: ages 2 and up, 90 minutes, and it runs in rain.",
      "2. Wildlife and glacier cruise, Bay Light Day Cruises. Why it made the cut: ages 4 and up, heated cabin, two restrooms. Pack lunch.",
      "Only two trips fit: Harbor Kayak Co. starts at age 12.",
      "",
      "(Serious photographer, cruise ship day visitor and couple on a road trip follow the same pattern.)",
      "",
      "C. JSON",
      "```json",
      JSON.stringify(DEMO.picks, null, 2),
      "```",
      "",
      "D. QUESTIONS FOR THE OWNER",
      "1. Mile 12 Kennel: departure times and exact season dates? How do guests without a car get there?",
      "2. Harbor Kayak Co.: season dates, meeting point, travel time from the cruise ship dock, and the rain policy?"
    ].join("\n");
  }

  return {
    COLUMNS: COLUMNS, KEYS: KEYS, QKEYS: QKEYS, QUESTION_TEXT: QUESTION_TEXT, DRAFT: DRAFT,
    DEMO: DEMO, BLANK_SETTINGS: BLANK_SETTINGS,
    clone: clone, norm: norm, esc: esc, hash: hash, blankItem: blankItem, cleanItem: cleanItem, businesses: businesses,
    parseCSV: parseCSV, toCSV: toCSV, inventoryFromCSV: inventoryFromCSV, inventoryToCSV: inventoryToCSV,
    checkInventory: checkInventory, emptyCount: emptyCount,
    inventoryBlock: inventoryBlock, buildInstructions: buildInstructions, buildRunPrompt: buildRunPrompt, typeNames: typeNames,
    extractJSON: extractJSON, toLists: toLists, numbersIn: numbersIn, wordFlags: wordFlags, findPII: findPII, factInRow: factInRow,
    validatePicks: validatePicks,
    safeUrl: safeUrl, safeColor: safeColor, textOn: textOn, pickerRuntime: pickerRuntime,
    pickMeta: pickMeta, buildPicker: buildPicker, buildPlainText: buildPlainText, previewDoc: previewDoc, demoReply: demoReply
  };
});
