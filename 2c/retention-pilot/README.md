# Retention pilot (ATIA kit, tool 2.c)

A small program that runs a careful test of post-booking messages:

1. **Score** open bookings with rules you can read (lead time, rate type, channel, add-ons).
2. **Assign** the most exposed bookings at random to *treatment* (gets messages) or *holdout* (gets nothing extra). The draw is stored once and never redone.
3. **Draft** one of three approved messages for each treatment booking: A, a confidence note; B, one add-on; C, a lock-in offer on terms you write. Drafts go to a spreadsheet with status PENDING.
4. **A person** reads every draft, fixes it, and sends it from the booking platform. This program cannot send anything.
5. **Report** treatment versus holdout: in-window changes and cancellations, with honest error bars.

Bay Light Day Cruises, Seward is a FICTIONAL TEACHING BUSINESS. All data in this folder is fictional.

**Who it is for:** operators with roughly 1,500 or more bookings a season on a booking platform with an API or a good CSV export, and a developer or vendor to connect it. Smaller operators: the demo still teaches the method, and the free post-booking calendar from the session does most of the good with no code.

## AI drafts. You approve.

Every draft starts with `DRAFT - PENDING OWNER REVIEW`. The local checks flag problems, but checks are not approval and a model checking itself is not verification. A person approves or rejects every message.

## The rules this pilot follows

| Rule | Label |
|---|---|
| Nothing sends without a person. There is no sending code in this folder; a test fails if any is added. | Policy choice (this kit's design) |
| No competitor price matching, and no chasing every cancellable booking. | Policy choice |
| Drafts use only `approved_facts.md`, `approved_addons.csv` and the owner's lock-in terms. Gaps stay as [FILL]. | Recommendation |
| No guest names, emails, phones, addresses or payment data enter the pilot. The adapter drops those columns and logs it. | Policy choice. Contractual: check your booking platform's API or export terms and your own privacy policy. |
| If you use a model API, only non-personal booking fields and approved facts are sent to it. | Contractual: check the model provider's API and data terms. |
| Messages B and C are promotional, so by default they go only to direct bookings. | Contractual: check your OTA supplier agreement (and any hotel-desk agreement) before contacting their guests with promotions. |
| Commercial email (B and C sent by email) must have an honest subject line, your postal address, a working opt-out and, unless the guest agreed to receive it, a clear note that it is an ad. Opt-outs must be honored. | Legal mandate: CAN-SPAM Act, 15 U.S.C. 7701 to 7713, and FTC rule 16 CFR Part 316. Marketing texts sent with automated tools generally need prior express written consent: TCPA, 47 U.S.C. 227 and 47 CFR 64.1200. Ask your platform how its messaging handles this. Not legal advice. |
| Lodging offers that show a price must show the total price, including mandatory fees. | Legal mandate for short-term lodging: 16 CFR Part 464 (FTC rule on unfair or deceptive fees). It does not cover tours. |
| Weather, water, wildlife and go/no-go wording is owned by a qualified person (for Bay Light, the captain). | Policy choice for safety-critical content |
| Holdout guests still get every normal service message (confirmation, safety, weather). Only the pilot's extra messages are held back. | Recommendation |
| Stop the pilot if complaints or opt-outs rise. | Recommendation |

## What you need

- Python 3.10 or newer. To check, open a terminal and type `python --version` (on a Mac, `python3 --version`). Free from python.org.
- Nothing else for the demo, dry runs, reports or the power command. No keys, no internet.

## Five-minute demo

1. Unzip `retention-pilot.zip`.
2. Open a terminal in the `retention-pilot` folder. (Windows: open the folder, click the address bar, type `cmd`, press Enter. Mac: right-click the folder, then New Terminal at Folder.)
3. Type:

```
python pilot.py demo
```

(On a Mac, type `python3` instead of `python`.)

It scores 300 fictional bookings, assigns the top 30, drafts messages for the treatment group, reports on simulated outcomes, and prints the sample size you would need. Then open `demo_output/output/approval_queue.csv` in Excel or Google Sheets, and `demo_output/output/report.md` in any text editor.

Do not want to run anything? The `sample_output/` folder has the same results, plus `example-drafts.md` with one draft of each type and a bad draft with the flags the checks raise.

## The files

| File | What it is |
|---|---|
| `pilot.py` | The program. Commands: demo, score, assign, draft, report, power |
| `rules.json` | Your rules: scoring points, eligible share, holdout share and seed, message order, lock-in terms, banned phrases, power settings. Plain text. |
| `approved_facts.md` | The only facts a draft may use. One `- key: value` per line. |
| `approved_addons.csv` | Add-ons message B may suggest, with `fits_when` (for example `departure_time==9:00`) and who approved each line |
| `templates/` | The approved wording for A, B and C, with `{{fact.key}}`, `{{booking.key}}` and `{{addon.key}}` blanks |
| `data/` | Fictional bookings and simulated outcomes (see `data/README.md`) |
| `adapters/csv_adapter.py` | Reads a CSV export, keeps allow-listed columns only, logs what it drops |
| `adapters/platform_stubs.py` | Empty shapes for FareHarbor, Peek, Checkfront and Cloudbeds. Not built; their APIs are not verified here. |
| `providers/` | Optional model APIs for drafting: mock (default), anthropic, openai, gemini |
| `.env.example` | Settings for real model drafts. Copy to `.env` only if you use them. |
| `tests/` | Automated checks |
| `tools/` | Rebuild the mock data and the example drafts |

The program creates `state/` (scores and the stored assignments), `output/` (approval queue and report) and `logs/` (what the adapter dropped).

## Using your own bookings

1. **Export open bookings** as a CSV. The pilot keeps only these columns and drops everything else: `booking_id, booked_date, trip_date, departure_time, product, rate_type, channel, party_size, addons_count, price_alert_flag, booking_value_usd, status`. Common names such as "Booking ID", "Activity Date" or "Guests" are recognized. Better still, leave personal columns out of the export.
2. **Replace** `approved_facts.md`, `approved_addons.csv` and the templates with your own approved wording.
3. **Edit** `rules.json`. Start with 50/50 (`"share": 0.5`). Write lock-in terms only if you want message C.
4. Run:

```
python pilot.py score --bookings my-export.csv
python pilot.py assign
python pilot.py draft --dry-run
```

5. **Review** `output/approval_queue.csv`. For each row: fill every [FILL], fix the wording, set `status` to APPROVED or REJECTED, and put your name in `approved_by`. Send approved messages from your booking platform yourself, then set `status` to SENT_BY_STAFF.
6. Run score, assign and draft again whenever you export new bookings. Earlier bookings keep their arm, and drafts already in the queue are not redone.
7. **After the season**, export outcomes as `booking_id, outcome, outcome_date` using the codes in `data/README.md`, then:

```
python pilot.py report --outcomes my-outcomes.csv --bookings my-export.csv
```

## Real model drafts (optional)

Dry runs fill the templates and are enough to run a pilot. If you want a model to improve the wording:

1. `pip install anthropic` (or `openai`, or `google-genai`; those two are not tested against a live API in this kit).
2. Copy `.env.example` to `.env`. Set `PROVIDER=anthropic` and your key. Keep `.env` private; it is listed in `.gitignore`.
3. Check the model name in `.env` against the provider's current model list.
4. Start small: `python pilot.py draft --max-calls 5`. The default cap is 25 calls per run.

Each draft is one short call. Cost is roughly 1 to 5 cents per draft at current list prices (estimate; check your provider's pricing page). The model sees only approved facts, the template and non-personal booking fields. With the Anthropic provider, if the model declines a request for a safety reason, the API retries it on a fallback model (`ANTHROPIC_FALLBACKS=default`; set it to `off` to turn that off). Declined or failed drafts still appear in the queue, with no text and a NO DRAFT note, so a person can write them. Run `draft` again to retry them; rows a person has reviewed are never redrafted.

## Reading the report

- **Number 4** = bookings changed or cancelled inside the free-cancellation window, divided by bookings with an outcome. Flexible and non-refundable are shown separately.
- Bookings are compared by assigned arm, whether or not a draft was approved and sent.
- Operator cancellations (a marine warning) are left out.
- Each rate has a Wilson 95% interval. If the treatment and holdout intervals overlap a lot, there is no clear difference.
- Labels: NO DATA, TOO SMALL TO READ (under 30 in an arm), DIRECTIONAL ONLY (below the sample size from the power command), SAMPLE SIZE REACHED.

## How many bookings you need

```
python pilot.py power --bookings-per-season 1500
python pilot.py power --holdout-share 0.2 --bookings-per-season 1500
```

To detect a drop from 15% to 12% in-window changes and cancellations (two-proportion test, alpha 0.05, power 0.8), a 50/50 split needs 2,036 bookings per arm, 4,072 in all. An 80/20 split needs about 6,212 in all, roughly 1.5 times as many (the rule of thumb says 1.56 times). A 1,500-booking operator with the top 10% eligible has about 150 eligible bookings a season. So a single operator gets a directional read: worth having, not evidence to scale on. A firmer answer needs several seasons, or operators pooling the same design and sharing counts (never guest data) through ATIA. Pooling needs a written data-sharing agreement (Contractual).

## Tests

From this folder:

```
python -m unittest
```

or `python -m pytest` if you have pytest installed. The tests use fake model clients; they never call a real API and need no key.

## Limits

- The mock outcomes are simulated. They show how the report reads, not what will happen.
- The scoring weights are a starting guess to test, not a prediction model.
- Platform adapters are not built. A real connection takes weeks; plan 4 to 8 weeks for the whole pilot with a developer (estimate).
- The OpenAI and Gemini providers are written from their public SDK patterns but not tested against a live API here.

ATIA 2026 Annual Convention · Small Business Focus: Leveraging AI Solutions · Pascual Reig-Munoz, Alaska SBDC. Use your own approved facts, terms and responsible review. Effort, cost and time figures are estimates.
