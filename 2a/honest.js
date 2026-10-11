/* 2.a The honest picture, from your reviews: page logic.
 * Everything runs in this browser. Nothing you paste is sent anywhere, and nothing goes into a URL.
 * The pure functions (parsing, cleaning, counts, quote checker) are also exported for tests in Node.
 * Teaching data is fictional: Bay Light Day Cruises, Seward.
 */
(function (root) {
  "use strict";
  var H = {};

  /* ---------- fictional teaching data (same text as baylight-reviews.csv) ---------- */
  /* [review_id, stars, platform, date, text]. Reviews 1 to 6 are the Prompt Kit's six, word for word. */
  H.REVIEWS50 = [[1, 5, "Google", "2026-09-12", "Saw humpbacks and the glacier calving. Cabin was warm."], [2, 4, "Tripadvisor", "2026-09-10", "Wonderful crew. Wish we had known lunch was not included; the kids were hungry by noon."], [3, 3, "Google", "2026-09-07", "Rough water on the way back and two in our group were seasick. Crew handled it well."], [4, 4, "Google", "2026-09-05", "The walk from the cruise ship was longer than we expected with a stroller."], [5, 5, "Tripadvisor", "2026-09-03", "Rained the whole time and we still saw otters and puffins. Bring a real rain jacket."], [6, 2, "Viator", "2026-08-31", "Booked through a third party and the pickup instructions conflicted with the email from the company."], [7, 5, "Google", "2026-08-29", "Humpback whales right next to the boat and a glacier at the end. The naturalist knew every bird."], [8, 4, "Tripadvisor", "2026-08-27", "Great trip, but bring your own lunch. Hot drinks only on board, and four hours is long for kids."], [9, 5, "Google", "2026-08-24", "We saw orcas, sea otters and a bald eagle. The captain kept us posted on everything over the speaker."], [10, 3, "Viator", "2026-08-22", "The ride back was choppy and my husband felt queasy for an hour. Wish we had taken something before we left."], [11, 5, "Facebook", "2026-08-19", "Rain all morning and it did not matter. The heated cabin and hot chocolate kept us happy between sightings."], [12, 4, "Google", "2026-08-17", "Walked from the cruise ship with a stroller. It took us closer to 20 minutes, not 12. Leave extra time."], [13, 2, "Viator", "2026-08-15", "Our tour company said there was a pickup at the ship. There was no pickup and we nearly missed the boat."], [14, 5, "Tripadvisor", "2026-08-12", "Calving glacier, puffins, and a crew that clearly loves the bay. Worth every penny."], [15, 4, "Google", "2026-08-10", "Lovely cruise. Lunch is not included, which we only found out on board. Pack snacks."], [16, 5, "Google", "2026-08-08", "Saw a mother humpback and calf. The crew turned off the engine so we could hear them breathe."], [17, 3, "Tripadvisor", "2026-08-05", "Cold and windy on the outside deck. Dress in layers, more than you think."], [18, 5, "Google", "2026-08-03", "Two restrooms on board made it easy with three kids. Warm cabin, big windows, great views of the glacier."], [19, 1, "Tripadvisor", "2026-08-01", "We cancelled 36 hours before because of a family emergency and got no refund. The policy was in the email but we missed it."], [20, 4, "Google", "2026-07-29", "Rough water near the mouth of the bay. The crew handed out ginger candy and kept checking on people."], [21, 5, "Facebook", "2026-07-27", "Sea lions on the rocks, otters everywhere, a whale tail at the end. The kids talked about it all night."], [22, 4, "Google", "2026-07-25", "Beautiful trip. The meeting point is at the small-boat harbor, not the cruise dock. Read the email twice."], [23, 5, "Tripadvisor", "2026-07-22", "Rained the whole time and we still saw whales. Bring a real rain jacket and waterproof pants."], [24, 5, "Google", "2026-07-20", "Best part of our Alaska trip. The glacier was huge and the captain explained how fast it is retreating."], [25, 3, "Viator", "2026-07-18", "Booked on a third-party site and the voucher listed the wrong departure time. We almost cancelled. The company sorted it out at the dock."], [26, 4, "Google", "2026-07-15", "Hot drinks were included, but there is no food for sale on board. We were starving by the end."], [27, 5, "Tripadvisor", "2026-07-13", "Puffins, eagles, porpoises and a calving glacier in one afternoon. Fantastic naturalist."], [28, 2, "Google", "2026-07-11", "Seasick most of the way back. The crew was kind, but I wish the website had said the afternoon trip is often rougher."], [29, 4, "Viator", "2026-07-08", "The walk from the cruise ship was fine for us, but an older relative struggled. A taxi would have been smarter."], [30, 5, "Google", "2026-07-06", "Heated cabin, clean restrooms, and the crew made coffee all trip. Saw otters and a humpback."], [31, 3, "Tripadvisor", "2026-07-04", "Foggy morning, so the glacier was hard to see. The crew was honest about it before we left the harbor."], [32, 5, "Facebook", "2026-07-01", "Our kids are 5 and 7 and loved every minute. Glacier, seals, and a whale."], [33, 4, "Google", "2026-06-29", "Good cruise. We wished we had known there is no lunch. The kids were hungry by the glacier."], [34, 2, "Viator", "2026-06-26", "The confirmation from the third-party site and the email from the company gave two different meeting times. Stressful start."], [35, 5, "Google", "2026-06-24", "Rain, wind and big smiles. We saw orcas! Bring gloves."], [36, 4, "Tripadvisor", "2026-06-22", "Took the 9:00 trip with a stroller. The harbor ramp is steep at low tide, so plan for that."], [37, 5, "Google", "2026-06-19", "A calm, sunny day, whales and a glacier. Perfect."], [38, 3, "Google", "2026-06-17", "Worth doing, but it got crowded in the cabin when everyone came in from the cold."], [39, 5, "Viator", "2026-06-15", "The crew spotted a bear on the shore through binoculars. Lots of otters too."], [40, 1, "Google", "2026-06-12", "The boat went out in rough seas and half of the passengers were sick. Not for anyone prone to seasickness."], [41, 4, "Tripadvisor", "2026-06-10", "Plan your day: the cruise is four hours plus check-in. We were late for our train because we had not planned for the walk back."], [42, 5, "Facebook", "2026-06-08", "Hot chocolate, a warm cabin, and a humpback breaching. Even in the drizzle it was magic."], [43, 4, "Google", "2026-06-05", "Lunch is on you, so eat before the 9:00 boat or bring something. Wonderful views."], [44, 5, "Tripadvisor", "2026-06-03", "The captain slowed down for every sea otter. Our daughter counted twenty-three."], [45, 3, "Google", "2026-06-01", "We could not hear the naturalist over the engine from the back of the cabin. Good trip otherwise."], [46, 5, "Google", "2026-05-29", "Booked direct on the website, easy check-in, whales and a glacier."], [47, 2, "Tripadvisor", "2026-05-27", "It rained, the windows fogged up, and we saw very little from inside. Disappointing for the price."], [48, 4, "Viator", "2026-05-25", "Our 3-year-old could not come because the minimum age is 4. We missed that in the listing. Her grandmother watched her and the rest of us loved it."], [49, 5, "Facebook", "2026-05-22", "Out to the glacier and back with humpbacks, otters and puffins. The crew made it feel personal."], [50, 3, "Google", "2026-05-20", "The afternoon wind made the deck too cold for photos. A morning trip might be better."]];  /* @generated: filled from baylight-reviews.csv */

  /* A deliberately messy, fictional example so you can watch the cleaner work. example.com addresses and 555-01xx numbers are reserved for examples. */
  H.MESSY = [
    "1. (5 stars) Captain Dana and deckhand Luis were great! Email me at kim.example@example.com for the photos.",
    "2. (2 stars) Nobody answered when I called. Call me back at (907) 555-0142 about booking 48213377.",
    "3. (4 stars) Loved it. Our photos are at www.example.com/ourtrip and https://example.org/album. Thanks, Marcy"
  ].join("\n");

  /* ---------- keyword hints: transparent, simple, and only hints ---------- */
  H.THEMES = [
    { id: "lunch", label: "Lunch, food", words: "lunch, food, snack, hungry, meal, eat, starving",
      re: /\b(lunch|food|snacks?|hungry|meals?|eat|starving)\b/ },
    { id: "seasick", label: "Seasick, rough water", words: "seasick, queasy, nausea, rough, choppy, swell",
      re: /\b(sea-?sick\w*|sea sick\w*|queasy|nause\w*|rough|rougher|choppy|swells?|motion sickness)\b/ },
    { id: "walk", label: "Walk, stroller, distance", words: "walk, stroller, wheelchair, ramp, stairs, distance, taxi",
      re: /\b(walk\w*|strollers?|wheelchairs?|ramps?|stairs|distance|taxi)\b/ },
    { id: "rain", label: "Rain, cold, wind, fog", words: "rain, wet, drizzle, fog, cold, chilly, wind",
      re: /\b(rain|rained|raining|rainy|wet|drizzle|fog|foggy|fogged|cold|chilly|wind|windy)\b/ },
    { id: "pickup", label: "Pickup, meeting point, third party", words: "pickup, third party, voucher, meeting point, meeting time, booked through",
      re: /\b(pick-?up|pick(ed)? us up|third[- ]party|vouchers?|meeting points?|meeting times?|booked through)\b/ },
    { id: "cancel", label: "Cancellation, refund", words: "cancel, refund, reschedule",
      re: /\b(cancel\w*|refund\w*|reschedul\w*)\b/ },
    { id: "wildlife", label: "Wildlife", words: "whale, humpback, orca, otter, puffin, seal, sea lion, eagle, porpoise, bear, bird, wildlife",
      re: /\b(whales?|humpbacks?|orcas?|otters?|puffins?|seals?|sea lions?|eagles?|porpoises?|bears?|birds?|wildlife)\b/ },
    { id: "glacier", label: "Glacier", words: "glacier, calving, iceberg",
      re: /\b(glaciers?|calving|calved|icebergs?)\b/ },
    { id: "crew", label: "Crew, captain, naturalist", words: "crew, captain, skipper, naturalist, deckhand, staff",
      re: /\b(crew|captain|skipper|naturalist|deckhands?|staff)\b/ },
    { id: "cabin", label: "Cabin, restrooms, hot drinks", words: "cabin, heated, warm, restroom, coffee, hot chocolate, hot drinks",
      re: /\b(cabin|heated|warm|restrooms?|bathrooms?|hot drinks?|coffee|hot chocolate)\b/ }
  ];

  /* ---------- small helpers ---------- */
  function str(s) { return String(s == null ? "" : s); }
  function nl(s) { return str(s).replace(/\r\n?/g, "\n"); }
  function escRe(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }
  H.escRe = escRe;
  function words(s) { var m = str(s).match(/[A-Za-z0-9][A-Za-z0-9'’-]*/g); return m ? m.length : 0; }
  H.countWords = words;

  /* ---------- CSV ---------- */
  function detectDelim(firstLine) {
    var best = ",", bestN = -1;
    [",", ";", "\t"].forEach(function (d) {
      var n = 0, q = false;
      for (var i = 0; i < firstLine.length; i++) { var c = firstLine[i]; if (c === '"') q = !q; else if (!q && c === d) n++; }
      if (n > bestN) { best = d; bestN = n; }
    });
    return best;
  }
  H.parseCSV = function (text, delim) {
    text = nl(text).replace(/^﻿/, "");
    delim = delim || detectDelim(text.split("\n")[0] || "");
    var rows = [], row = [], field = "", q = false;
    for (var i = 0; i < text.length; i++) {
      var c = text[i];
      if (q) {
        if (c === '"') { if (text[i + 1] === '"') { field += '"'; i++; } else q = false; }
        else field += c;
      } else if (c === '"') q = true;
      else if (c === delim) { row.push(field); field = ""; }
      else if (c === "\n") { row.push(field); rows.push(row); row = []; field = ""; }
      else field += c;
    }
    if (field !== "" || row.length) { row.push(field); rows.push(row); }
    return rows.filter(function (r) { return r.some(function (f) { return f.trim() !== ""; }); });
  };

  var COL = {
    id: /^(review[ _-]?id|id|#|no\.?|number)$/,
    text: /^(text|review|review[ _-]?text|reviews|comment|comments|body|content|feedback|message|description)$/,
    stars: /^(stars?|rating|ratings|score|star[ _-]?rating|overall|overall[ _-]?rating)$/,
    platform: /^(platform|source|site|channel|website)$/,
    date: /^(date|review[ _-]?date|created|created[ _-]?at|published|posted|time)$/,
    drop: /(name|author|reviewer|user|email|e-mail|phone|mobile|guest|customer|profile|avatar|photo|url|link|booking|order|ref|address)/
  };
  function starsFrom(v) {
    v = str(v).trim();
    if (!v) return null;
    var full = (v.match(/★/g) || []).length;
    if (full) return full;
    var m = v.match(/([1-5](?:\.\d+)?)/);
    return m ? parseFloat(m[1]) : null;
  }
  H.rowsToReviews = function (rows) {
    var res = { reviews: [], dropped: [], ignored: [], header: false };
    if (!rows.length) return res;
    var head = rows[0].map(function (h) { return str(h).trim().toLowerCase(); });
    var map = {}, known = 0;
    head.forEach(function (h, i) {
      var hit = false;
      ["id", "text", "stars", "platform", "date"].forEach(function (k) { if (!hit && !(k in map) && COL[k].test(h)) { map[k] = i; hit = true; } });
      if (hit) known++;
      else if (COL.drop.test(h)) res.dropped.push(rows[0][i].trim());
      else if (h) res.ignored.push(rows[0][i].trim());
    });
    var data = rows;
    if (known > 0 || res.dropped.length) { res.header = true; data = rows.slice(1); }
    else { res.dropped = []; res.ignored = []; }
    if (!("text" in map)) {
      // no text column named: use the column with the longest values that was not dropped
      var cols = rows[0].length, bestI = 0, bestL = -1;
      for (var c = 0; c < cols; c++) {
        if (res.header && (res.dropped.indexOf(rows[0][c].trim()) >= 0 || c === map.id || c === map.stars || c === map.platform || c === map.date)) continue;
        var L = data.reduce(function (a, r) { return a + str(r[c]).length; }, 0);
        if (L > bestL) { bestL = L; bestI = c; }
      }
      map.text = bestI;
      if (res.header) res.ignored = res.ignored.filter(function (n) { return n !== rows[0][bestI].trim(); });
    }
    data.forEach(function (r, i) {
      var t = str(r[map.text]).replace(/\s*\n\s*/g, " ").trim();
      if (!t) return;
      res.reviews.push({
        id: "id" in map && str(r[map.id]).trim() ? str(r[map.id]).trim() : String(i + 1),
        stars: "stars" in map ? starsFrom(r[map.stars]) : null,
        platform: "platform" in map ? str(r[map.platform]).trim() : "",
        date: "date" in map ? str(r[map.date]).trim() : "",
        text: t
      });
    });
    return res;
  };

  /* ---------- plain text: "1. (5 stars, Google, 2026-09-12) text", one per line, or blank-line paragraphs ---------- */
  var RE_NUMLINE = /^\s*#?(\d{1,4})[.):]\s+/;
  function parseMeta(meta, r) {
    var parts = meta.split(/[,;·|]/);
    parts.forEach(function (p) {
      p = p.trim();
      if (!p) return;
      if (/★|\bstars?\b|\/\s*5|rating/i.test(p)) { var s = starsFrom(p); if (s != null) r.stars = s; }
      else if (/^\d{4}-\d{2}-\d{2}$|^\d{1,2}\/\d{1,2}\/\d{2,4}$/.test(p)) r.date = p;
      else if (!r.platform) r.platform = p;
    });
  }
  H.parseLine = function (b, seq) {
    var r = { id: String(seq), stars: null, platform: "", date: "", text: "" }, m;
    b = str(b).trim();
    m = b.match(RE_NUMLINE);
    if (m) { r.id = m[1]; b = b.slice(m[0].length); }
    m = b.match(/^\s*[(\[]([^)\]]{1,80})[)\]]\s*[:.-]?\s*/);
    if (m && /★|star|rating|\d\s*\/\s*5/i.test(m[1])) { parseMeta(m[1], r); b = b.slice(m[0].length); }
    else if ((m = b.match(/^\s*(★{1,5})☆*\s*[:.-]?\s*/))) { r.stars = m[1].length; b = b.slice(m[0].length); }
    else if ((m = b.match(/^\s*(?:rating:?\s*)?([1-5](?:\.\d)?)\s*(?:stars?|\/\s*5)\b\s*[:.,-]?\s*/i))) { r.stars = parseFloat(m[1]); b = b.slice(m[0].length); }
    r.text = b.trim();
    return r;
  };
  H.parseText = function (text) {
    text = nl(text);
    var lines = text.split("\n"), blocks = [], skipped = 0;
    var numbered = lines.filter(function (l) { return RE_NUMLINE.test(l); }).length;
    if (numbered >= 2) {
      var started = false;
      lines.forEach(function (l) {
        if (RE_NUMLINE.test(l)) { blocks.push(l.trim()); started = true; }
        else if (l.trim()) { if (started) blocks[blocks.length - 1] += " " + l.trim(); else skipped++; }
      });
    } else if (/\n[ \t]*\n/.test(text.trim())) {
      blocks = text.trim().split(/\n[ \t]*\n+/).map(function (p) { return p.replace(/\s*\n\s*/g, " "); });
    } else blocks = lines;
    blocks = blocks.map(function (b) { return b.trim(); }).filter(Boolean);
    return { reviews: blocks.map(function (b, i) { return H.parseLine(b, i + 1); }).filter(function (r) { return r.text; }), skipped: skipped };
  };

  /* ---------- either format ---------- */
  H.looksLikeCSV = function (text) {
    var first = nl(text).replace(/^﻿/, "").split("\n")[0].toLowerCase();
    if (!/[,;\t]/.test(first)) return false;
    return /(^|[,;\t"])\s*(text|review|reviews|review[ _-]?text|comment|comments|body|content|stars?|rating)\s*("|[,;\t]|$)/.test(first);
  };
  H.parseInput = function (text) {
    text = str(text);
    if (!text.trim()) return { reviews: [], format: "none", dropped: [], ignored: [], skipped: 0 };
    if (H.looksLikeCSV(text)) {
      var r = H.rowsToReviews(H.parseCSV(text));
      r.format = "csv"; r.skipped = 0; return r;
    }
    var t = H.parseText(text);
    return { reviews: t.reviews, format: "lines", dropped: [], ignored: [], skipped: t.skipped };
  };

  H.formatLine = function (r, text) {
    var meta = [r.stars == null ? "no rating" : (Math.round(r.stars * 10) / 10) + (r.stars === 1 ? " star" : " stars")];
    if (r.platform) meta.push(r.platform);
    if (r.date) meta.push(r.date);
    return r.id + ". (" + meta.join(", ") + ") " + (text == null ? r.text : text);
  };

  /* ---------- de-identification: a first pass on this device, not a guarantee ---------- */
  var RE_EMAIL = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g;
  var RE_URL = /\b(?:https?:\/\/|www\.)[^\s<>"]+/gi;
  var RE_DOMAIN = /\b(?:[a-z0-9-]+\.)+(?:com|net|org|io|co|us|info|biz|travel|app|me|ly|tours|ca|uk)\b(?:\/[^\s<>"]*)?/gi;
  var KEEP_DOMAINS = /^(?:www\.)?(booking|hotels|expedia|viator|tripadvisor|getyourguide|airbnb|vrbo|google)\.com$/i;
  var RE_PHONE = /(?:\+?1[\s.-]?)?(?:\(\d{3}\)\s?|\b\d{3}[\s.-]?)\d{3}[\s.-]?\d{4}\b/g;
  var RE_INTL = /\+\d{1,3}(?:[\s.-]?\d{2,4}){2,5}\b/g;
  var RE_LONGNUM = /\b\d{8,19}\b|\b\d{4}(?:[ -]\d{4}){2,3}(?:[ -]\d{1,4})?\b/g;
  /* a house number, one to three capitalized words, then a street type: "123 Main St", "4410 Old Harbor Road" */
  var RE_ADDR = /\b\d{1,5}\s+(?:[A-Z][A-Za-z'’]*\.?\s+){1,3}(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Way|Ct|Court|Pl|Place|Loop|Cir|Circle|Hwy|Highway|Pkwy|Parkway|Ter|Terrace)\b\.?/g;
  function trimUrl(u) { var m = u.match(/[.,;:!?)\]]+$/); return m ? [u.slice(0, -m[0].length), m[0]] : [u, ""]; }

  H.deidentify = function (text) {
    var c = { email: 0, phone: 0, url: 0, number: 0, address: 0 };
    var t = str(text);
    t = t.replace(RE_EMAIL, function () { c.email++; return "[EMAIL REMOVED]"; });
    t = t.replace(RE_URL, function (u) { var p = trimUrl(u); c.url++; return "[LINK REMOVED]" + p[1]; });
    t = t.replace(RE_DOMAIN, function (u) { var p = trimUrl(u); if (KEEP_DOMAINS.test(p[0])) return u; c.url++; return "[LINK REMOVED]" + p[1]; });
    t = t.replace(RE_ADDR, function () { c.address++; return "[ADDRESS REMOVED]"; });
    t = t.replace(RE_INTL, function () { c.phone++; return "[PHONE REMOVED]"; });
    t = t.replace(RE_PHONE, function () { c.phone++; return "[PHONE REMOVED]"; });
    t = t.replace(RE_LONGNUM, function () { c.number++; return "[NUMBER REMOVED]"; });
    return { text: t, counts: c, total: c.email + c.phone + c.url + c.number + c.address };
  };
  H.emptyCounts = function () { return { email: 0, phone: 0, url: 0, number: 0, address: 0 }; };
  H.countTotal = function (c) { return c.email + c.phone + c.url + c.number + (c.address || 0); };
  /* "1 email, 2 phone numbers and 1 link", or "nothing" */
  H.countsText = function (c) {
    var parts = [[c.email, "email", "emails"], [c.phone, "phone number", "phone numbers"], [c.url, "link", "links"],
      [c.number, "long number", "long numbers"], [c.address || 0, "street address", "street addresses"]]
      .filter(function (p) { return p[0] > 0; }).map(function (p) { return p[0] + " " + (p[0] === 1 ? p[1] : p[2]); });
    if (!parts.length) return "nothing";
    return parts.length === 1 ? parts[0] : parts.slice(0, -1).join(", ") + " and " + parts[parts.length - 1];
  };

  /* likely names: capitalized words in mid-sentence, and any word after a title such as Captain or deckhand */
  var TITLES = /^(captain|capt|cpt|skipper|mr|mrs|ms|miss|dr|guide|naturalist|deckhand|host|hostess|driver|server|mate|chef|owner|manager|agent|thanks|thank|hi|hello|dear|cheers)$/i;
  var STOP = {};
  ("i i'm i've i'd i'll alaska alaskan seward kenai fjords fjord national park resurrection bay light day cruise cruises " +
   "anchorage fairbanks juneau ketchikan sitka skagway whittier homer valdez talkeetna denali exit glacier aialik holgate " +
   "harding icefield prince william sound google tripadvisor viator facebook instagram expedia booking getyourguide airbnb " +
   "vrbo uber lyft mile kennel harbor kayak co princess holland america royal caribbean norwegian celebrity carnival " +
   "january february march april may june july august september october november december monday tuesday wednesday " +
   "thursday friday saturday sunday mom dad grandma grandpa thanks thank wow ok okay usa us american americans english " +
   "canada canadian pacific gulf north south east west highly great best amazing awesome definitely loved love excellent " +
   "fantastic wonderful beautiful recommend recommended worth tour tours trip boat crew captain dock harbor removed name " +
   "email phone link number check owner draft pending review christmas easter covid hwy highway").split(" ").forEach(function (w) { STOP[w] = 1; });

  H.findNames = function (reviews, ignore) {
    ignore = ignore || {};
    var found = {}, order = [];
    reviews.forEach(function (r) {
      var t = str(r.text), re = /[A-Za-z][A-Za-z'’]*/g, m, last = 0, prev = "";
      while ((m = re.exec(t))) {
        var between = t.slice(last, m.index);
        var start = last === 0 || /[.!?"“(\n]\s*$/.test(between) || /[.!?]\s*["”)]?\s*$/.test(between);
        last = m.index + m[0].length;
        var w = m[0].replace(/['’]s$/, "");
        var prevWord = prev; prev = w;
        if (!/^[A-Z][a-z'’]+$|^[A-Z][a-z]+[A-Z][a-z]+$/.test(w) || w.length < 2) continue;
        if (t.charAt(m.index - 1) === "[") continue;
        var low = w.toLowerCase();
        var afterTitle = TITLES.test(prevWord) && !STOP[low];
        if (STOP[low] || ignore[w]) continue;
        if (start && !afterTitle) continue;
        if (!found[w]) { found[w] = []; order.push(w); }
        if (found[w].indexOf(r.id) < 0) found[w].push(r.id);
      }
    });
    return order.map(function (w) { return { word: w, ids: found[w] }; });
  };

  /* ---------- counts ---------- */
  H.stats = function (reviews) {
    var by = { 5: 0, 4: 0, 3: 0, 2: 0, 1: 0, none: 0 }, sum = 0, n = 0, plat = {};
    reviews.forEach(function (r) {
      if (r.stars == null || isNaN(r.stars)) by.none++;
      else { var s = Math.min(5, Math.max(1, Math.round(r.stars))); by[s]++; sum += r.stars; n++; }
      if (r.platform) plat[r.platform] = (plat[r.platform] || 0) + 1;
    });
    var themes = H.THEMES.map(function (t) {
      var ids = [], low = 0;
      reviews.forEach(function (r) {
        if (t.re.test(str(r.text).toLowerCase())) { ids.push(r.id); if (r.stars != null && r.stars <= 3) low++; }
      });
      return { id: t.id, label: t.label, words: t.words, count: ids.length, low: low, ids: ids };
    });
    return { total: reviews.length, byStars: by, rated: n, avg: n ? sum / n : null, platforms: plat, themes: themes };
  };
  H.hintsText = function (st) {
    if (!st.total) return "";
    var lines = ["Stars: " + [5, 4, 3, 2, 1].map(function (s) { return s + (s === 1 ? " star: " : " stars: ") + st.byStars[s]; }).join(", ") +
      (st.byStars.none ? ", no rating: " + st.byStars.none : "") + "."];
    st.themes.forEach(function (t) {
      if (!t.count) return;
      lines.push("- " + t.label + ": " + t.count + " of " + st.total + " reviews (" + t.low + " at 3 stars or fewer). Reviews " + t.ids.join(", ") + ".");
    });
    return lines.join("\n");
  };

  /* ---------- quote checker ---------- */
  function norm(s) {
    return str(s).toLowerCase().replace(/[’‘`´]/g, "'").replace(/[^a-z0-9']+/g, " ").replace(/(^|\s)'+|'+(\s|$)/g, " ").replace(/\s+/g, " ").trim();
  }
  H.norm = norm;
  var IGNORE_Q = ["what to expect honestly", "draft pending owner review", "draft pending staff review", "escalate to owner",
    "none", "ask us", "check with owner", "captain or owner to confirm", "what to expect"];

  H.extractQuotes = function (text) {
    var out = [], re = /"([^"\n]{2,500})"|“([^”\n]{2,500})”/g, m;
    while ((m = re.exec(str(text)))) out.push((m[1] !== undefined ? m[1] : m[2]).trim());
    return out;
  };
  /* sources: [{label, texts:[raw, cleaned]}] */
  H.findQuote = function (quote, sources) {
    var frags = str(quote).split(/\.\.\.|…|\[[^\]]*\]/).map(norm).filter(function (f) { return f.length > 0; });
    var hits = [];
    if (!frags.length) return { found: false, where: [], frags: 0 };
    sources.forEach(function (s) {
      var ok = s.texts.some(function (t) {
        var hay = " " + norm(t) + " ";
        return frags.every(function (f) { return hay.indexOf(" " + f + " ") >= 0; });
      });
      if (ok) hits.push(s.label);
    });
    return { found: hits.length > 0, where: hits, frags: frags.length };
  };
  H.closest = function (quote, sources) {
    var qw = norm(quote).split(" ").filter(Boolean);
    if (!qw.length) return null;
    var best = null;
    sources.forEach(function (s) {
      var set = {};
      s.texts.forEach(function (t) { norm(t).split(" ").forEach(function (w) { set[w] = 1; }); });
      var hit = qw.filter(function (w) { return set[w]; }).length / qw.length;
      if (!best || hit > best.pct) best = { label: s.label, pct: hit };
    });
    return best;
  };
  H.checkQuotes = function (output, sources) {
    var res = { checked: [], skipped: [] };
    H.extractQuotes(output).forEach(function (q) {
      var n = norm(q);
      if (!n || IGNORE_Q.indexOf(n) >= 0 || n.split(" ").length < 2) { res.skipped.push(q); return; }
      var f = H.findQuote(q, sources);
      var item = { quote: q, found: f.found, where: f.where };
      if (!f.found) item.closest = H.closest(q, sources);
      res.checked.push(item);
    });
    return res;
  };

  /* ---------- the "What to expect, honestly" section inside an answer ---------- */
  H.findSection = function (text) {
    text = nl(text);
    var re = /^[ \t#*_>"“]*what to expect,?\s*honestly/gim, m, at = -1;
    while ((m = re.exec(text))) at = m.index + m[0].length;
    if (at < 0) { var re2 = /what to expect,?\s*honestly/gi; while ((m = re2.exec(text))) at = m.index + m[0].length; }
    if (at < 0) return null;
    var rest = text.slice(at).replace(/^[^\n]*/, function (l) { return l.replace(/^["”*_:)\s-]+/, ""); });
    // A DRAFT marker right under the heading is not the end of the section; one after the content is.
    var mk = new RegExp(RE_DRAFT.source, "gi"), mm, cut = -1;
    while ((mm = mk.exec(rest))) { if (words(rest.slice(0, mm.index)) >= 10) { cut = mm.index; break; } }
    if (cut >= 0) rest = rest.slice(0, cut);
    rest = rest.replace(new RegExp(RE_DRAFT.source, "gi"), " ").replace(/^[\s()*_:-]+/, "");
    var nextHead = rest.slice(20).search(/\n\s*(#{1,6}\s|\*\*[^*\n]+\*\*\s*\n|---)/);
    if (nextHead >= 0) rest = rest.slice(0, nextHead + 20);
    return rest.trim();
  };

  var MARKETING = ["unforgettable", "amazing", "breathtaking", "stunning", "spectacular", "incredible", "magical", "magic",
    "awesome", "perfect", "best", "world-class", "once-in-a-lifetime", "once in a lifetime", "must-see", "must-do", "epic",
    "ultimate", "premier", "luxury", "luxurious", "unparalleled", "unbeatable", "majestic", "pristine", "hidden gem",
    "bucket list", "bucket-list", "jaw-dropping", "awe-inspiring", "paradise"];
  var PROMISES = ["guarantee", "guaranteed", "guarantees", "will see", "you'll see", "always", "never", "promise",
    "definitely", "certainly", "rest assured", "don't worry", "do not worry", "no need to worry", "nothing to worry", "100%"];
  function findTerms(text, list) {
    var low = " " + norm(text) + " ", raw = str(text).toLowerCase(), out = [];
    list.forEach(function (w) {
      var hit = /[^a-z' ]/.test(w) ? raw.indexOf(w) >= 0 : low.indexOf(" " + norm(w) + " ") >= 0;
      if (hit) out.push(w);
    });
    return out;
  }
  H.findTerms = findTerms;
  /* Numbers with their unit, so "3-hour" is not excused by "3-year-old": [{key, bare, label}] */
  var RE_NUM = /(\$?)(\d+(?:[.:,]\d+)?)(?:\s*-\s*|\s+)?(hours?|hrs?|minutes?|mins?|miles?|days?|weeks?|months?|years?|people|guests|passengers|knots|feet|ft|degrees|percent|%)?(?![A-Za-z0-9])/gi;
  function numbersIn(text) {
    var out = [], m; RE_NUM.lastIndex = 0;
    var t = str(text);
    while ((m = RE_NUM.exec(t))) {
      var unit = (m[3] || "").toLowerCase().replace(/^(hr|min)s?$/, function (u) { return u.indexOf("h") === 0 ? "hour" : "minute"; }).replace(/s$/, "");
      if (unit === "%") unit = "percent";
      out.push({ key: m[1] + m[2] + (unit ? " " + unit : ""), bare: m[1] + m[2], label: m[0].trim(), unit: unit });
    }
    return out;
  }
  H.newNumbers = function (text, sourceText) {
    var keys = {}, bare = {};
    numbersIn(sourceText).forEach(function (n) { keys[n.key] = 1; bare[n.bare] = 1; });
    var out = [];
    numbersIn(text).forEach(function (n) {
      var ok = n.unit ? keys[n.key] : bare[n.bare];
      if (!ok && out.indexOf(n.label) < 0) out.push(n.label);
    });
    return out;
  };
  function stripQuotes(text) { return str(text).replace(/"[^"\n]{2,500}"|“[^”\n]{2,500}”/g, " "); }
  H.stripQuotes = stripQuotes;

  var RE_DRAFT = /DRAFT\s*[-\u2013\u2014:]?\s*PENDING\s+(OWNER|STAFF)\s+REVIEW/gi;
  var RE_OFFER = /\b(refund\w*|credits?|credited|free (trip|tour|cruise|ride|ticket|tickets|upgrade|seat|seats)|discount\w*|vouchers?|coupons?|promo(tion(al)?)? codes?|gift cards?|compensat\w*|complimentary|on the house|on us|reimburs\w*|money back|free of charge|waive[sd]?|off your next \w+)\b|\$\s?\d+(?:\.\d{2})?\s+off\b|\b\d+\s?(?:%|percent)\s+off\b/gi;
  var RE_DISPUTE = /\b(actually|in fact|you should have|as stated|clearly stated|our policy clearly|we disagree|not true|not accurate|contrary to|misunderstood|your mistake|you failed|you were told|as you were told|as noted in|if you had read)\b/gi;
  var RE_EDIT = /\b(remove|delete|change|update|edit|revise|amend|take down|reconsider)\b[^.!?\n]{0,40}\breview\b/gi;
  var RE_TEMPLATE = /\b(apologi[sz]e for any inconvenience|sorry for any inconvenience|we value your feedback|your feedback is important to us|we strive to|we pride ourselves)\b/gi;
  var RE_FIX = /\b(we('ve| have)? (now )?(fixed|updated|changed|added|improved|corrected|clarified|installed|replaced|retrained|trained|addressed|resolved)|we now|going forward|from now on|(this|it) has (now )?been (fixed|resolved|addressed|corrected|updated))\b/gi;

  function uniq(arr) { var o = []; arr.forEach(function (a) { a = a.toLowerCase(); if (o.indexOf(a) < 0) o.push(a); }); return o; }
  function matches(re, text) { re.lastIndex = 0; return uniq(str(text).match(re) || []); }
  H.matches = matches;

  /* ctx: {mode:"s1"|"s2", sources:[{label,texts}], sourceText, fixes} → [{level, title, items}] level: pass|flag|check|info */
  H.checkAnswer = function (output, ctx) {
    var out = [], text = nl(output), bare = stripQuotes(text);
    if (!text.trim()) return [{ level: "info", title: "Paste the AI's answer first.", items: [] }];

    var drafts = (text.match(RE_DRAFT) || []).length;
    out.push(drafts ? { level: "pass", title: "DRAFT marker found (" + drafts + ").", items: [] }
      : { level: "flag", title: "No DRAFT - PENDING OWNER REVIEW marker. Add it before anyone else sees this.", items: [] });

    var q = H.checkQuotes(text, ctx.sources);
    var miss = q.checked.filter(function (c) { return !c.found; });
    if (!q.checked.length) {
      out.push({ level: ctx.mode === "s1" ? "check" : "info", title: ctx.mode === "s1" ? "No quoted review phrases found. Ask the AI to quote each supporting phrase word for word, in double quotes." : "No quoted review phrases to check.", items: [] });
    } else if (miss.length) {
      out.push({ level: "flag", title: miss.length + " of " + q.checked.length + (miss.length === 1 ? " quotes does" : " quotes do") + " not appear word for word in your reviews. Fix or delete " + (miss.length === 1 ? "it." : "them."),
        items: miss.map(function (c) { return "“" + c.quote + "”" + (c.closest && c.closest.pct >= 0.5 ? ": closest is " + c.closest.label + " (" + Math.round(c.closest.pct * 100) + "% of the words). Reworded?" : ": not found in any review."); }) });
    } else {
      out.push({ level: "pass", title: (q.checked.length === 1 ? "The quote appears" : "All " + q.checked.length + " quotes appear") + " word for word in your reviews. Still read " + (q.checked.length === 1 ? "it" : "each one") + " in context.", items: [] });
    }

    var pii = H.deidentify(text);
    if (pii.total) out.push({ level: "flag", title: "Contact details in the answer: remove them before you save or share it.", items: [H.countsText(pii.counts) + "."] });

    if (ctx.mode === "s1") {
      var sec = H.findSection(text);
      if (sec === null) out.push({ level: "check", title: "Could not find the “What to expect, honestly” section. Is it in the answer?", items: [] });
      else {
        var wc = words(sec);
        out.push(wc <= 150 ? { level: "pass", title: "Section is about " + wc + " words (target: under 150).", items: [] }
          : { level: "flag", title: "Section is about " + wc + " words. The target is under 150: ask the AI to cut it.", items: [] });
        var mk = findTerms(stripQuotes(sec), MARKETING);
        if (mk.length) out.push({ level: "check", title: "Marketing words in the section. Replace each with a checkable fact.", items: [mk.join(", ")] });
        var pr = findTerms(stripQuotes(sec), PROMISES);
        if (pr.length) out.push({ level: "check", title: "Promise words in the section. Keep them only if they are a fact you can stand behind.", items: [pr.join(", ")] });
        var nn = H.newNumbers(sec, ctx.sourceText);
        if (nn.length) out.push({ level: "check", title: "Numbers in the section that are not in your reviews or facts. Check each one.", items: [nn.join(", ")] });
        else out.push({ level: "pass", title: "Every number in the section appears in your reviews or facts.", items: [] });
      }
    } else {
      var off = matches(RE_OFFER, bare);
      out.push(off.length ? { level: "flag", title: "Mentions refunds, credits, discounts or freebies. The reply rules say none of these in a public reply: delete it. If the owner wants to make something right, the owner does it privately.", items: [off.join(", ")] }
        : { level: "pass", title: "No refunds, credits, discounts or free trips offered.", items: [] });
      var ed = matches(RE_EDIT, bare);
      if (ed.length) out.push({ level: "flag", title: "Asks the guest to change or remove the review. Delete that.", items: [ed.join("; ")] });
      var dp = matches(RE_DISPUTE, bare);
      if (dp.length) out.push({ level: "check", title: "Phrases that can sound like disputing the guest.", items: [dp.join(", ")] });
      var tp = matches(RE_TEMPLATE, bare);
      if (tp.length) out.push({ level: "check", title: "Template phrases. Name the guest's specific issue instead.", items: [tp.join(", ")] });
      var fx = matches(RE_FIX, bare), fixes = str(ctx.fixes).trim();
      if (fx.length) {
        var none = !fixes || /^none\.?$/i.test(fixes);
        out.push(none ? { level: "flag", title: "Claims a fix, but your confirmed fixes list is “none”. Delete the claim.", items: [fx.join(", ")] }
          : { level: "check", title: "Claims a fix. Check each claim against your confirmed fixes: " + fixes, items: [fx.join(", ")] });
      }
      var long = [];
      text.replace(RE_DRAFT, " ").split(/\n[ \t]*\n/).forEach(function (p) {
        var lines = p.trim().split("\n");
        if (lines.length > 1 && words(lines[0]) <= 8) lines.shift();
        var body = lines.join(" "), n = words(body);
        if (n > 60) long.push("“" + body.slice(0, 40).trim() + "…” has " + n + " words");
      });
      if (long.length) out.push({ level: "check", title: "Replies over 60 words. Shorten them.", items: long });
      var nn2 = H.newNumbers(bare.replace(RE_DRAFT, " "), ctx.sourceText);
      if (nn2.length) out.push({ level: "check", title: "Numbers in the replies that are not in your reviews or facts. Check each one, or delete it.", items: [nn2.join(", ")] });
      var esc = (text.match(/ESCALATE TO OWNER/gi) || []).length;
      if (esc) out.push({ level: "info", title: esc + " review(s) marked ESCALATE TO OWNER. The owner handles these directly; do not post an AI draft.", items: [] });
    }
    var open = (text.match(/\[(CHECK WITH OWNER|CAPTAIN OR OWNER TO CONFIRM)[^\]]*\]/gi) || []).length;
    if (open) out.push({ level: "info", title: open + " item(s) marked for the owner or captain to answer before anything is published.", items: [] });
    return out;
  };

  if (typeof module !== "undefined" && module.exports) { module.exports = H; return; }
  root.HONEST = H;
  if (typeof document === "undefined") return;

  /* ====================================================================================== */
  /* Page wiring (browser only). Runs after kit.js, which is loaded first with defer.       */
  /* ====================================================================================== */
  var KIT = root.KIT || {};
  var store = KIT.store || { get: function () { return null; }, set: function () { }, del: function () { } };
  var SK = "atiakit:2a:";
  function $(id) { return document.getElementById(id); }
  function el(tag, attrs, text) {
    var e = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) { if (k === "class") e.className = attrs[k]; else e.setAttribute(k, attrs[k]); });
    if (text != null) e.textContent = text;
    return e;
  }
  function say(target, msg) { if (KIT.say) KIT.say(target, msg); }
  function debounce(fn, ms) { var t; return function () { clearTimeout(t); t = setTimeout(fn, ms); }; }
  /* Save a field in this browser only; an empty field (or the default "none") leaves nothing behind. */
  function save(k, v) { if (!v || (k === "fixes" && v === "none")) store.del(SK + k); else store.set(SK + k, v); }

  var state = { a: null, cleanA: [], s2: [], ignore: {} };

  function demoSix() { return (KIT.demo && KIT.demo.reviews) || H.REVIEWS50.slice(0, 6).map(function (r) { return r[0] + ". (" + r[1] + " stars) " + r[4]; }).join("\n"); }
  function fifty() {
    return H.REVIEWS50.map(function (r) { return H.formatLine({ id: String(r[0]), stars: r[1], platform: r[2], date: r[3], text: r[4] }); }).join("\n");
  }

  function cleanList(reviews) {
    var tot = H.emptyCounts();
    var list = reviews.map(function (r) {
      var d = H.deidentify(r.text);
      Object.keys(tot).forEach(function (k) { tot[k] += d.counts[k]; });
      return { id: r.id, stars: r.stars, platform: r.platform, date: r.date, text: d.text, raw: r.text };
    });
    return { list: list, counts: tot };
  }

  function renderNames(names) {
    var box = $("names");
    box.textContent = "";
    if (!names.length) return;
    box.appendChild(el("p", { class: "hint" }, "Possible names. The page did not remove these: check each one."));
    var ul = el("ul", { class: "namelist" });
    names.slice(0, 30).forEach(function (n) {
      var li = el("li");
      li.appendChild(el("b", null, n.word));
      li.appendChild(document.createTextNode(" in review" + (n.ids.length > 1 ? "s " : " ") + n.ids.join(", ") + " "));
      var rep = el("button", { type: "button", class: "ghost small", "data-name": n.word, "data-act": "replace" }, "Replace with [NAME]");
      var keep = el("button", { type: "button", class: "ghost small", "data-name": n.word, "data-act": "keep" }, "Not a name");
      li.appendChild(rep); li.appendChild(keep);
      ul.appendChild(li);
    });
    box.appendChild(ul);
    if (names.length > 30) box.appendChild(el("p", { class: "hint" }, (names.length - 30) + " more not shown. Fix these first, then check again."));
  }

  function renderStats(st) {
    var sum = $("stats-summary"), tb = $("stars-body"), th = $("themes-body");
    tb.textContent = ""; th.textContent = "";
    if (!st.total) { sum.textContent = "Paste reviews or load the fictional set to see the counts."; $("stats-tables").hidden = true; return; }
    $("stats-tables").hidden = false;
    var plats = Object.keys(st.platforms).map(function (p) { return p + " " + st.platforms[p]; }).join(" · ");
    sum.textContent = st.total + " reviews" + (st.avg != null ? " · average " + st.avg.toFixed(2) + " stars from " + st.rated + " rated" : "") + (plats ? " · " + plats : "") + ".";
    var maxN = Math.max.apply(null, [5, 4, 3, 2, 1].map(function (s) { return st.byStars[s]; }).concat([1]));
    [5, 4, 3, 2, 1, "none"].forEach(function (s) {
      if (s === "none" && !st.byStars.none) return;
      var tr = el("tr"), n = st.byStars[s];
      tr.appendChild(el("th", { scope: "row" }, s === "none" ? "No rating" : s + (s === 1 ? " star" : " stars")));
      tr.appendChild(el("td", { class: "num" }, String(n)));
      var td = el("td", { class: "barcell", "aria-hidden": "true" });
      var bar = el("span", { class: "bar" + (s !== "none" && s <= 3 ? " low" : "") });
      bar.style.width = Math.round((n / maxN) * 100) + "%";
      td.appendChild(bar); tr.appendChild(td);
      tb.appendChild(tr);
    });
    st.themes.forEach(function (t) {
      var tr = el("tr");
      var c1 = el("th", { scope: "row" });
      c1.appendChild(document.createTextNode(t.label));
      c1.appendChild(el("span", { class: "kw" }, "Looks for: " + t.words));
      tr.appendChild(c1);
      tr.appendChild(el("td", { class: "num", "data-label": "Reviews" }, String(t.count)));
      tr.appendChild(el("td", { class: "num", "data-label": "At 3 stars or fewer" }, String(t.low)));
      tr.appendChild(el("td", { class: "ids", "data-label": "Which reviews" }, t.ids.length ? t.ids.join(", ") : "none"));
      th.appendChild(tr);
    });
  }

  function renderS1() {
    var vals = {
      count: state.cleanA.length ? String(state.cleanA.length) : "",
      reviews: state.cleanA.map(function (r) { return H.formatLine(r, r.text); }).join("\n"),
      facts: $("facts").value,
      hints: state.a && state.a.stats.total ? H.hintsText(state.a.stats) : ""
    };
    $("out-s1").textContent = KIT.render(KIT.tplText("tpl-s1"), vals);
  }

  function updateA() {
    var raw = $("rv").value;
    save("rv", raw);
    var p = H.parseInput(raw);
    var c = cleanList(p.reviews);
    var names = H.findNames(c.list, state.ignore);
    state.cleanA = c.list;
    state.a = { parsed: p, stats: H.stats(p.reviews), names: names, counts: c.counts };
    var rep = $("clean-report");
    if (!p.reviews.length) rep.textContent = "No reviews yet.";
    else {
      var bits = [p.reviews.length + (p.reviews.length === 1 ? " review" : " reviews") + " read" + (p.format === "csv" ? " from CSV" : "") + ".",
        "Removed in the prompt, on this device: " + H.countsText(c.counts) + "."];
      if (p.dropped && p.dropped.length) bits.push("Left out these columns: " + p.dropped.join(", ") + ".");
      if (p.ignored && p.ignored.length) bits.push("Not used: " + p.ignored.join(", ") + ".");
      if (p.skipped) bits.push("Skipped " + p.skipped + " line(s) before review 1.");
      bits.push(names.length ? names.length + " possible name(s) to check below." : "No likely names found. Still read them once.");
      rep.textContent = bits.join(" ");
    }
    renderNames(names);
    renderStats(state.a.stats);
    renderS1();
    var warn = $("s1-names");
    if (warn) {
      warn.hidden = !names.length;
      warn.textContent = names.length ? "Check first: " + names.length + " possible name(s) from Step A are still in this prompt (" +
        names.slice(0, 5).map(function (n) { return n.word; }).join(", ") + (names.length > 5 ? " and more" : "") +
        "). Replace each one, or mark it “Not a name”, before you copy." : "";
    }
  }

  function renderS2() {
    var raw = $("s2").value;
    save("s2", raw);
    save("fixes", $("fixes").value);
    save("signoff", $("signoff").value);
    var p = H.parseInput(raw), c = cleanList(p.reviews);
    state.s2 = c.list;
    var vals = {
      replies: c.list.map(function (r) { return H.formatLine(r, r.text); }).join("\n"),
      facts: $("facts").value,
      fixes: $("fixes").value,
      signoff: $("signoff").value
    };
    $("out-s2").textContent = KIT.render(KIT.tplText("tpl-s2"), vals);
    var note = $("s2-note");
    var names2 = H.findNames(c.list, state.ignore);
    if (!p.reviews.length) note.textContent = "";
    else note.textContent = p.reviews.length + " review(s) ready." + (p.reviews.length > 5 ? " The kit suggests 5 at a time, so each reply gets a careful read." : "") +
      (H.countTotal(c.counts) ? " Removed in the prompt: " + H.countsText(c.counts) + "." : "") +
      (names2.length ? " Possible names to check before you copy: " + names2.map(function (n) { return n.word; }).join(", ") + "." : "");
  }

  function sourcesForCheck() {
    var src = [];
    (state.a ? state.a.parsed.reviews : []).forEach(function (r, i) { src.push({ label: "review " + r.id, texts: [r.text, state.cleanA[i] ? state.cleanA[i].text : ""] }); });
    state.s2.forEach(function (r) { src.push({ label: "review " + r.id + " in Step D", texts: [r.raw, r.text] }); });
    return src;
  }

  function runCheck() {
    var mode = (document.querySelector('input[name="mode"]:checked') || {}).value || "s1";
    var src = sourcesForCheck();
    var out = $("check-out");
    out.textContent = "";
    if (!src.length) {
      out.appendChild(el("p", { class: "hint" }, "Load or paste your reviews in Step A first, so there is something to check the quotes against."));
    }
    // Review numbers count as known numbers, so "Review 19" in a reply is not flagged.
    var sourceText = src.map(function (s) { return s.label + " " + s.texts.join(" "); }).join(" ") + " " + $("facts").value;
    var res = H.checkAnswer($("ans").value, { mode: mode, sources: src, sourceText: sourceText, fixes: $("fixes").value });
    var ul = el("ul", { class: "checks" });
    var flags = 0, checks = 0;
    res.forEach(function (r) {
      if (r.level === "flag") flags++;
      if (r.level === "check") checks++;
      var li = el("li", { class: "chk " + r.level });
      li.appendChild(el("span", { class: "pill " + ({ pass: "", flag: "red", check: "amber", info: "teal" })[r.level] }, ({ pass: "Pass", flag: "Fix", check: "Check", info: "Note" })[r.level]));
      li.appendChild(document.createTextNode(" " + r.title));
      if (r.items.length) {
        var sub = el("ul");
        r.items.forEach(function (it) { sub.appendChild(el("li", null, it)); });
        li.appendChild(sub);
      }
      ul.appendChild(li);
    });
    out.appendChild(ul);
    $("check-status").textContent = "Checked: " + flags + " to fix, " + checks + " to check. A clean check is not approval: a person still reads every line.";
  }

  function calc() {
    var ids = ["m-rev", "m-rep", "m-inq", "m-book", "m-bk", "m-win"], v = {};
    ids.forEach(function (id) { v[id] = parseFloat($(id).value); save(id, $(id).value); });
    function pct(a, b) { return isFinite(a) && isFinite(b) && b > 0 ? (Math.round((a / b) * 1000) / 10) + "%" : "n/a"; }
    var lines = [
      "Review reply rate: " + pct(v["m-rep"], v["m-rev"]),
      "Inquiry-to-booking rate: " + pct(v["m-book"], v["m-inq"]),
      "In-window changes and cancellations (Number 4): " + pct(v["m-win"], v["m-bk"])
    ];
    $("m-out").textContent = lines.join("\n");
  }

  function loadFile(file) {
    var st = $("file-status");
    if (!file) return;
    if (file.size > 3 * 1024 * 1024) { st.textContent = "That file is over 3 MB. Save just the review columns and try again."; return; }
    var fr = new FileReader();
    fr.onload = function () {
      var text = String(fr.result || "");
      var p = H.parseInput(text);
      if (!p.reviews.length) { st.textContent = "No reviews found in " + file.name + ". It needs a column named text, review or comment, or one review per line."; return; }
      // Put a cleaned, normalized copy in the box: dropped columns (names, emails) and contact details never reach it.
      var removed = H.emptyCounts();
      $("rv").value = p.reviews.map(function (r) {
        var d = H.deidentify(r.text);
        Object.keys(removed).forEach(function (k) { removed[k] += d.counts[k]; });
        return H.formatLine(r, d.text);
      }).join("\n");
      updateA();
      st.textContent = "Loaded " + p.reviews.length + " reviews from " + file.name + "." +
        (p.dropped && p.dropped.length ? " Left out these columns: " + p.dropped.join(", ") + "." : "") +
        (p.ignored && p.ignored.length ? " Not used: " + p.ignored.join(", ") + "." : "") +
        " Removed before it reached the box: " + H.countsText(removed) + ".";
    };
    fr.onerror = function () { st.textContent = "Could not read that file."; };
    fr.readAsText(file);
  }

  document.addEventListener("DOMContentLoaded", function () {
    var saved = store.get(SK + "rv"); if (typeof saved === "string") $("rv").value = saved;
    ["s2", "fixes", "signoff", "facts"].forEach(function (id) { var v = store.get(SK + id); if (typeof v === "string") $(id).value = v; });
    ["m-rev", "m-rep", "m-inq", "m-book", "m-bk", "m-win"].forEach(function (id) { var v = store.get(SK + id); if (typeof v === "string") $(id).value = v; });
    state.ignore = store.get(SK + "ignore") || {};

    var upA = debounce(updateA, 200);
    $("rv").addEventListener("input", upA);
    $("rv-file").addEventListener("change", function (e) { loadFile(e.target.files && e.target.files[0]); e.target.value = ""; });
    $("facts").addEventListener("input", debounce(function () { save("facts", $("facts").value); renderS1(); renderS2(); }, 150));
    ["s2", "fixes", "signoff"].forEach(function (id) { $(id).addEventListener("input", debounce(renderS2, 150)); });
    $("ans").addEventListener("input", function () { $("check-status").textContent = ""; });
    ["m-rev", "m-rep", "m-inq", "m-book", "m-bk", "m-win"].forEach(function (id) { $(id).addEventListener("input", calc); });

    document.addEventListener("click", function (e) {
      var b = e.target.closest ? e.target.closest("button") : null;
      if (!b) return;
      var act = b.id || b.getAttribute("data-act");
      if (act === "load6") { $("rv").value = demoSix(); updateA(); say(b, "Six fictional reviews loaded (the Prompt Kit set)."); }
      else if (act === "load50") { $("rv").value = fifty(); updateA(); say(b, "Fifty fictional reviews loaded."); }
      else if (act === "loadMessy") { $("rv").value = H.MESSY; state.ignore = {}; store.del(SK + "ignore"); updateA(); say(b, "Messy fictional example loaded. Look at what the cleaner caught."); }
      else if (act === "rvClear") { $("rv").value = ""; updateA(); say(b, "Cleared."); }
      else if (act === "cleanBox") {
        if (!state.cleanA.length) { say(b, "Nothing to clean yet."); return; }
        $("rv").value = state.cleanA.map(function (r) { return H.formatLine(r, r.text); }).join("\n");
        updateA(); say(b, "The box now holds the cleaned text, one review per line. Check the names list.");
      }
      else if (act === "replace" || act === "keep") {
        var w = b.getAttribute("data-name");
        if (act === "replace") $("rv").value = $("rv").value.replace(new RegExp("\\b" + H.escRe(w) + "\\b", "g"), "[NAME]");
        else { state.ignore[w] = 1; store.set(SK + "ignore", state.ignore); }
        updateA();
        var rep = $("clean-report");
        rep.textContent = (act === "replace" ? "Replaced “" + w + "” with [NAME]. " : "Kept “" + w + "”. ") + rep.textContent;
        var next = document.querySelector("#names button"); (next || $("rv")).focus();
      }
      else if (act === "loadFacts") { $("facts").value = (KIT.demo && KIT.demo.facts) || ""; save("facts", $("facts").value); renderS1(); renderS2(); say(b, "Fictional facts loaded. They go into both prompts. Use your own approved facts."); }
      else if (act === "factsClear") { $("facts").value = ""; save("facts", ""); renderS1(); renderS2(); say(b, "Cleared."); }
      else if (act === "s2kit") {
        var six = demoSix().split("\n").filter(function (l) { return /^\s*[2346]\./.test(l); });
        $("s2").value = six.join("\n"); $("fixes").value = "none";
        if (!$("signoff").value.trim()) $("signoff").value = "The Bay Light crew (fictional)";
        renderS2(); say(b, "Fictional reviews 2, 3, 4 and 6 loaded.");
      }
      else if (act === "s2lowest") {
        var pool = state.cleanA.filter(function (r) { return r.stars != null; });
        if (!pool.length) { say(b, "Load reviews with star ratings in Step A first."); return; }
        var pick = pool.map(function (r, i) { return { r: r, i: i }; }).sort(function (x, y) { return (x.r.stars - y.r.stars) || (x.i - y.i); }).slice(0, 5).map(function (x) { return x.r; });
        $("s2").value = pick.map(function (r) { return H.formatLine(r, r.text); }).join("\n"); renderS2();
        say(b, pick.length + " lowest-rated reviews copied from Step A, already cleaned.");
      }
      else if (act === "s2Clear") { $("s2").value = ""; $("fixes").value = "none"; renderS2(); say(b, "Cleared."); }
      else if (act === "check") { runCheck(); }
      else if (act === "ansClear") { $("ans").value = ""; $("check-out").textContent = ""; $("check-status").textContent = "Cleared."; }
      else if (act === "dlClean") {
        if (!state.cleanA.length) { say(b, "Nothing to save yet. Load or paste reviews first."); return; }
        var txt = "Reviews, de-identified on this device (" + state.cleanA.length + "). Check for names before sharing.\n\n" + state.cleanA.map(function (r) { return H.formatLine(r, r.text); }).join("\n") + "\n";
        KIT.download("reviews-cleaned.txt", txt, "text/plain"); say(b, "Saved reviews-cleaned.txt to your downloads.");
      }
      else if (act === "copyNums") { KIT.copy(new Date().toISOString().slice(0, 10) + "\n" + $("m-out").textContent, b); }
      else if (act === "forget") {
        ["rv", "s2", "fixes", "signoff", "facts", "ignore", "m-rev", "m-rep", "m-inq", "m-book", "m-bk", "m-win"].forEach(function (k) { store.del(SK + k); });
        ["rv", "s2", "facts", "ans", "signoff", "m-rev", "m-rep", "m-inq", "m-book", "m-bk", "m-win"].forEach(function (id) { $(id).value = ""; });
        $("fixes").value = "none"; state.ignore = {}; $("check-out").textContent = "";
        updateA(); renderS2(); calc(); say(b, "Everything this page saved in this browser is cleared.");
      }
    });

    updateA(); renderS2(); calc();
  });
})(this);
