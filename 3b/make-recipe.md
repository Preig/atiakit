# Partner circle kits in Make: the recipe

From the ATIA AI Take-Home Kit, tool 3.b: https://preig.github.io/atiakit/3b/
Teaching data is fictional (Bay Light Day Cruises, Seward, and its partners). Times and costs are estimates.

**What you build:** two scenarios. Scenario 1 adds each new booking to a queue sheet with a `send_date` 30 days before arrival. Scenario 2 runs every morning, drafts a trip kit for each row that is due, saves it as a **Gmail draft**, and logs it in the sheet. A person checks every draft and presses Send.

**What you do not build:** a waiting step. Make's sleep module waits minutes, not weeks, and a booking held inside a scenario for a month cannot be seen, changed or canceled. The queue sheet does the waiting, and you can read it.

**Module names change.** The names below are generic. The line "Look for" says roughly what the module is called today. Check Make's help (https://help.make.com/) if you cannot find one. No blueprint file is included: it would be tied to someone else's connections.

---

## Before you start (about 30 minutes)

1. **A Make plan** with enough operations (credits) for a daily scenario. Roughly $20 to $30 a month for a small operator (estimate; check current plans). Each kit uses a few operations.
2. **Google account** with Google Sheets and Gmail, for the business mailbox that sends kits. Read Make's help page on connecting Gmail first: for some account types it asks you to set up your own Google Cloud connection.
3. **An AI step.** The Anthropic Claude app, either with your own API key or through its simple text prompt module that runs on Make credits (no key), or the OpenAI or Gemini apps. Check that provider's business data terms first. **Contractual** (the provider's terms).
4. **The partner agreement** signed or at least agreed (`partner-agreement-template.md`).

## Set up the spreadsheet (about 20 minutes)

Make one Google Sheet called `Partner circle kits` with two tabs.

**Tab `queue`.** Paste the header row and the five fictional test rows from `kit-queue-template.csv`. Columns A to N: booking_ref, booked_on, arrival, departure, send_date, party, ages, product, status, drafted_on, draft_link, approved_by, sent_date, notes.

- booking_ref never goes to the AI step.
- ages holds ages only, for example "2 adults; children 6 and 9". No names.
- status is one of: queued, drafted, sent, canceled.

Select columns B to E and M, then Format, Number, Custom date and time, and pick `YYYY-MM-DD`. Make's date functions then read them the same way every time.

**Tab `facts`.** Row 1 headers: `id`, `shared_fact_sheet`, `month_notes`. Row 2: `current` in A2, the fact sheet text from the 3.b page ("Copy fact sheet text") in B2, and your month notes in C2. When a partner updates a block, paste the new text into B2. The next morning's kits use it.

Share the sheet only with people who already see bookings. **Policy choice.**

---

## Scenario 1: new booking to queue row (about 30 minutes)

Start simple: for the first month, a person can type each row from the booking confirmation, about 2 minutes per booking. Build Scenario 1 once the rest works.

1. **Trigger: a new booking.**
   Look for: your booking platform's own Make app and a "watch new bookings" or "watch orders" module. If it has none, use Gmail "watch emails" on a label that holds the confirmations, then a text parser to pull out the fields.
2. **Add the row.**
   Look for: Google Sheets, "Add a Row", tab `queue`. Map booking_ref, booked_on, arrival, departure, party, ages, product. Type `queued` into status.
   For send_date, use the formula: `formatDate(addDays(parseDate(ARRIVAL; "YYYY-MM-DD"); -30); "YYYY-MM-DD")`, where ARRIVAL is the mapped arrival field.
   **Do not map** guest name, email, phone, address, payment or notes fields. **Policy choice.**

Run it once with one fictional booking, then delete that row.

## Scenario 2: daily kit drafts (2 to 3 hours)

1. **Schedule: every day, early morning.**
   Look for: the scenario's schedule setting, "Every day", at a time such as 06:00. Check the time zone in your Make profile or organization settings: it is the time zone the schedule uses.
2. **Read the facts.**
   Look for: Google Sheets, "Search Rows" on tab `facts` where `id` equals `current` (or "Get a Cell" for B2 and C2). This gives you `shared_fact_sheet` and `month_notes`.
3. **Find every queued row.**
   Look for: Google Sheets, "Search Rows" on tab `queue` where `status` equals `queued`. Each row comes out as its own bundle, and the modules after it run once per bundle.
4. **Filter: only rows that are due.**
   Look for: a filter on the link after step 3. Condition: `parseDate(send_date; "YYYY-MM-DD")`, date operator **earlier than or equal to**, `now`. That means "today or earlier", so late bookings and missed mornings are caught.
5. **AI step: draft the kit.**
   Look for: Anthropic Claude, "Create a Prompt" (your own key), or Anthropic Claude, "Simple Text Prompt" (no key; runs on Make credits), or the OpenAI or Gemini equivalent.
   Paste the prompt from Step 4 of the 3.b page ("Copy prompt"). Then delete each `{{placeholder}}` and map the matching item:
   - `{{shared_fact_sheet}}` and `{{month_notes}}`: from step 2
   - `{{arrival}}`, `{{departure}}`, `{{party}}`, `{{ages}}`, `{{product}}`: from the bundle of step 3
   Map nothing else. No booking_ref, no notes. **Policy choice.**
6. **Optional guard filter.**
   Continue only if the AI text **contains** `DRAFT - PENDING OWNER REVIEW`. Rows that stop here stay queued.
7. **Create a Gmail draft. Never a send module.**
   Look for: Gmail, "Create a Draft".
   - To: leave empty. The approver adds the guest's address from the booking system, which is also a final check that the kit is for the right guest. If the step will not save without a To address, use your own business address and replace it when you approve.
   - Subject: `Your trip kit: arriving ` then map arrival.
   - Content: the AI text, as plain text.
8. **Log it.**
   Look for: Google Sheets, "Update a Row". Row number: from the bundle of step 3. Set status `drafted`, drafted_on `formatDate(now; "YYYY-MM-DD")`, draft_link the draft id from step 7.
9. **Errors.**
   Look for: right-click the AI module and the Gmail module, "Add error handler", then "Ignore" or "Break". One bad row then does not stop the others; the failed row stays `queued` and the next morning tries it again. If the Gmail step worked but the log step (8) failed, the next morning makes a second draft for that booking: delete the extra one. Turn on email notifications for errors in your Make settings.

**Running cost** (estimate): about 4 operations per kit (search bundle, AI, Gmail, update) plus a few per morning. At 300 bookings a season that is roughly 1,200 to 1,500 operations, plus the AI step's cost per kit. Check your plan's limit.

---

## Test with five fictional bookings (about 1 hour)

1. In the `queue` tab, set send_date on TEST-001 to TEST-004 to today's date. Leave TEST-005 as `canceled`.
2. Put a fact sheet (the fictional one is fine) in `facts`.
3. Open Scenario 2 and click "Run once".
4. **Expect:** four Gmail drafts, nothing in Sent. TEST-005 untouched. Four rows now say `drafted` with a date and a draft id.
5. Click "Run once" again. **Expect:** no new drafts.
6. Paste each draft into "Check the draft" on the 3.b page, and go through the approval checklist. TEST-001 has children aged 6 and 9, so the kayak (minimum age 12) should be left out. The June and August kits should ask for a month note.
7. Delete the test drafts and the TEST rows. Then switch Scenario 1 on for real bookings, and switch Scenario 2's schedule on.

## Every kit: one person approves

Open Gmail Drafts. For each kit: run the approval checklist from the 3.b page, answer or delete every [FILL], delete the QUESTIONS FOR THE OWNER list and both DRAFT lines, add the guest's address, and send. In the sheet, write your initials in `approved_by`, the date in `sent_date`, and set status to `sent`. **Policy choice:** one named person approves each kit, and nothing is sent automatically.

## Every month

- Ask each partner for its code counts by the 5th. Paste them into the reconciliation helper on the 3.b page.
- Kits sent that month: count rows with a `sent_date` in that month.
- Re-check any fact-sheet block older than 60 days.

## Changes and cancellations

- Changed dates: update arrival and send_date. If a draft exists, delete it and set status back to `queued`.
- Canceled: set status to `canceled` and delete any draft.

*AI drafts. A person approves.*
