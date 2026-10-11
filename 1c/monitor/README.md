# AI answer monitor

Part of the ATIA AI Take-Home Kit, tool 1.c (advanced rung). https://preig.github.io/atiakit/1c/

Every week this script asks Claude, ChatGPT (through the OpenAI API) and Gemini the same traveler
questions, with live web search switched on. For every answer it records two of the four checks from
the AI visibility audit:

- **Appear:** is your business named in the answer?
- **Cited:** is your website among the sources the answer cites?

The other two checks stay with a person:

- **Described:** right category, place and promise?
- **Current:** today's prices and policies?

The weekly report lists the answers to read by hand for those two.

The sample data is fictional: Bay Light Day Cruises, Mile 12 Kennel and Harbor Kayak Co. are teaching
businesses in Seward, and every `.example` web address is reserved and leads nowhere.

**AI drafts. You approve.** The reports are marked DRAFT - PENDING OWNER REVIEW. A person reads them
before anything is shared or acted on.

## Try it in two minutes, with no keys and no internet

You need Python 3.10 or newer (python.org). Open a terminal in this folder and run:

```
python monitor.py run --mock
python monitor.py run --mock --fixtures fixtures/week2
python monitor.py diff --mock
python monitor.py cost --mock
```

Mock mode replays recorded, fictional answers. Nothing is sent anywhere and nothing is spent. Open
`output_mock/weekly_diff.md` to see the weekly report. Finished examples are in `sample_output/`.

## Set it up for real

1. **Install the provider libraries** for the tools you will use:
   `pip install -r requirements.txt`
2. **Copy `.env.example` to a new file named `.env`** in this folder. Open it in a text editor.
3. **Add your API keys** (one per provider: Anthropic Console, OpenAI Platform, Google AI Studio).
   Leave a key blank to skip that provider. Keys stay in `.env` on your computer.
   Recommendation: never paste a key into a chat, an email or a shared document.
4. **Check the prices.** Claude prices are filled in as of 2026-10-10. OpenAI and Gemini token prices
   are blank on purpose: copy them from each provider's pricing page for the model you use. The
   budget stop cannot count spending without them, so a provider without prices is skipped.
5. **Check the model and tool names.** Providers rename models often. The defaults are in `.env.example`.
   Compare them with each provider's current model list, then run:
   `python monitor.py check`
   It makes one tiny call per provider and tells you if a model or search tool name was rejected
   (for Claude it also tries the older search tool versions and tells you which one works).
6. **Try two prompts:** `python monitor.py run --dry-run` (about 6 answers; cents, not dollars).
7. **Run everything:** `python monitor.py run`, then `python monitor.py diff` and `python monitor.py cost`.

## Every week

```
python monitor.py run
python monitor.py diff
```

Read `output/weekly_diff.md`. It lists:

- who was named and cited this run and last run;
- mentions gained and lost (same question, same tool);
- sources cited for the first time, and the most-cited sources (often listing sites: keep those current);
- the answers to read by hand for Described and Current;
- the **quarterly trend**, which is the table to act on.

## What to expect, honestly

- **One week is noise.** Ask the same question twice and you can get a different answer. Report the
  quarterly trend, not week-to-week moves, and do not infer ranking or bookings from one answer.
- **API answers are a proxy panel.** The consumer apps a traveler uses add their own settings, location,
  history and features. The API answers move in the same direction over time; they are not a screenshot
  of what any one traveler sees.
- **Cost scales with prompts, not with businesses.** One answer is checked for every name in `names.csv`,
  so watching 300 member businesses costs about the same as watching one. That is why an association
  (for example ATIA) can run it once for all members.
- **Costs are measured, not guessed.** After each answer the script multiplies the usage the provider
  reported by your prices. Your provider billing page is the real bill.

## Change the questions or the names

- **`prompts.csv`**: one traveler question per row (`prompt_id, prompt, intent, locale`). Keep them
  generic: no traveler names, emails, phone numbers, booking details or other personal data. Keep the
  same questions for a whole quarter so the trend means something; add new ones with new IDs.
- **`names.csv`**: one business per row:
  - `name`: the business name as travelers would see it;
  - `aliases`: other spellings, separated by `|` (for example `Bay Light|Bay Light Cruises`).
    Avoid aliases that are ordinary words or road markers;
  - `domains`: your website, separated by `|`. Add a listing page with its path, for example
    `ota.example/tours/bay-light`, to count citations of that one listing;
  - `is_member`: 1 or 0 (useful when an association also watches non-members).

Matching ignores capital letters and only counts whole words: "Bay Light" matches "bay light's" but not
"Bay Lightning".

## Costs and the budget stop

- `MONTHLY_BUDGET` in `.env` (default 25 US dollars). Before each answer the script adds this month's
  measured spend to the expected cost of the next answer. If that would pass the budget, it stops and
  says so. `python monitor.py cost` shows spend by month and provider and a projection.
- Gemini search has a monthly free allowance (set in `.env`); the script counts it.

## Files it writes (in `output/`)

- `results.csv`: one row per answer per watched name. Columns: `run_id, date, provider, model,
  tool_version, user_location, prompt_id, name, appears, first_offset, rank_among_watched,
  mention_count, cited, cited_urls, input_tokens, output_tokens, search_calls, cost_usd_measured,
  error`. Tokens and cost appear once per answer (on the first name's row), so a column total in a
  spreadsheet is the true total. `first_offset` is the character position of the first mention;
  `rank_among_watched` is 1 for the first watched name in the answer.
- `answers.jsonl`: one line per answer with the question, the citations, the search queries, usage,
  cost and (where allowed, see below) the full answer text.
- `weekly_diff.md` and `cost_report.md`.

Both data files are append-only: the history is the point. Back them up.

## Optional: run it automatically every week with GitHub Actions

Recommendation: use a **PRIVATE** repository only, never a public one (and never the public atiakit
site repository). The workflow in `.github/workflows/monitor.yml` first asks GitHub whether the
repository is private, and stops with an error if it is public.

1. Create a new private repository on GitHub and upload this folder's contents to its root
   (including the `.github` folder).
2. Copy `.env.example` to `settings.env`, fill in the prices and names, and **delete the three key
   lines** from it. Commit `settings.env`. Never commit `.env`.
3. In the repository: Settings, Secrets and variables, Actions, New repository secret. Add
   `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` and `GEMINI_API_KEY` (only the ones you use).
4. Open the Actions tab and enable workflows. It runs every Monday morning (Alaska time) and you can
   start it by hand with "Run workflow". Results are committed back to the `output/` folder.

## Rules that come with it

- **Contractual:** if you show stored answers to members, staff or anyone else, show their citations
  with them. Check the Anthropic and OpenAI usage terms for the current wording.
- **Contractual:** check the Gemini API terms (Grounding with Google Search) before storing or showing
  grounded answers, including how Google Search suggestions are displayed.
  `STORE_FULL_TEXT_GEMINI` is off by default; names found, citations and usage are
  still recorded. `STORE_FULL_TEXT_ANTHROPIC` and `STORE_FULL_TEXT_OPENAI` control the others.
- **Recommendation:** keep keys in `.env` or GitHub Secrets only. Run in a private repository.
- **Recommendation:** generic questions only. No traveler or guest data goes into `prompts.csv`.
- **Policy choice:** which businesses you watch (members only, or competitors too) and who sees the
  results. Decide it before the first run and write it down.

## Troubleshooting

- `check` says not_found or bad_request: a model or tool name changed. Update it in `.env` from the
  provider's docs and run `check` again.
- `authentication_failed`: the key is wrong, expired or has no billing set up.
- `BUDGET STOP`: working as intended. Raise `MONTHLY_BUDGET` or wait for next month.
- `skipped: prices not set`: add the provider's prices to `.env`.
- Gemini `sdk_mismatch`: your google-genai version does not have the selected request style. Upgrade
  it (`pip install -U google-genai`) or set `GEMINI_API_STYLE=generate_content`.

## Tests (for developers)

```
python -m unittest        # standard library only
python -m pytest          # if pytest is installed
```

The tests never use the network or real keys. Fake clients and an in-memory HTTP transport stand in
for the providers; where the anthropic or openai library is installed, the tests also check the exact
request the library would send.

## How it is built

- `monitor.py`: commands `check`, `run` (`--dry-run`, `--mock`), `diff`, `cost`
- `providers/anthropic_p.py`, `providers/openai_p.py`, `providers/gemini_p.py`: one file per provider,
  each with its own request, response parsing and error handling
- `matching.py`: names and domains; `report.py`: weekly diff; `costs.py`: cost and budget;
  `storage.py`: the two data files
- `fixtures/week1`, `fixtures/week2`: recorded fictional answers for mock mode and tests

Facts last verified 2026-10-10. Effort, cost and time figures are estimates. Built for the ATIA 2026
Annual Convention session "Small Business Focus: Leveraging AI Solutions" (Alaska SBDC).
