# Partner circle kits in Zapier: the recipe

From the ATIA AI Take-Home Kit, tool 3.b: https://preig.github.io/atiakit/3b/
Teaching data is fictional (Bay Light Day Cruises, Seward, and its partners). Times and costs are estimates.

**What you build:** two Zaps. Zap 1 adds each new booking to a queue sheet with a `send_date` 30 days before arrival. Zap 2 runs every morning, drafts a trip kit for each row that is due, saves it as a **Gmail draft**, and logs it in the sheet. A person checks every draft and presses Send.

**What you do not build:** a "delay until 30 days before arrival" step. A delay holds each booking inside Zapier for weeks or months. A booking made far ahead can need a longer wait than Zapier's delay limit allows (check the current limit in Zapier's help), a held booking does not see date changes or cancellations, and you cannot see what is waiting. The queue sheet handles all of this, including late bookings, and you can read it.

**Step names change.** The names below are generic. The line "Look for" says roughly what the step is called today. Check Zapier's help (https://help.zapier.com/) if you cannot find one. No Zap template file is included: it would be tied to someone else's account connections.

---

## Before you start (about 30 minutes)

1. **A Zapier plan that allows multi-step Zaps, filters and a daily schedule.** Roughly $20 to $30 a month (estimate; check current plans). Each kit uses a few tasks.
2. **Google account** with Google Sheets and Gmail, for the business mailbox that sends kits.
3. **An AI step.** Either AI by Zapier (pick a model in the step, or connect your own key), or the Anthropic (Claude), OpenAI or Google AI app with your own API key. Check that provider's business data terms first. **Contractual** (the provider's terms).
4. **The partner agreement** signed or at least agreed (`partner-agreement-template.md`).

## Set up the spreadsheet (about 20 minutes)

Make one Google Sheet called `Partner circle kits` with two tabs.

**Tab `queue`.** Paste the header row and the five fictional test rows from `kit-queue-template.csv`:

| Column | Header | Notes |
|---|---|---|
| A | booking_ref | Your booking number. Never sent to the AI step. |
| B | booked_on | YYYY-MM-DD |
| C | arrival | YYYY-MM-DD |
| D | departure | YYYY-MM-DD |
| E | send_date | arrival minus 30 days |
| F | party | number of people |
| G | ages | for example "2 adults; children 6 and 9". No names. |
| H | product | what was booked, with date and time |
| I | status | queued, drafted, sent, canceled |
| J | drafted_on | filled by Zap 2 |
| K | draft_link | filled by Zap 2 |
| L | approved_by | initials of the one person who approved |
| M | sent_date | filled by that person |
| N | notes | no guest details |

Select columns B to E and M, then Format, Number, Custom date and time, and pick `YYYY-MM-DD`. Both Zapier and people then read the dates the same way.

**Tab `facts`.** Row 1 headers: `id`, `shared_fact_sheet`, `month_notes`. Row 2: `current` in A2, the fact sheet text from the 3.b page ("Copy fact sheet text") in B2, and your month notes in C2. When a partner updates a block, paste the new text into B2. The next morning's kits use it.

Share the sheet only with people who already see bookings. **Policy choice.**

---

## Zap 1: new booking to queue row (about 30 minutes)

Start simple: for the first month, a person can type each row from the booking confirmation, about 2 minutes per booking. Build Zap 1 once the rest works.

1. **Trigger: a new booking.**
   Look for: your booking platform's own Zapier app and a "new booking" or "new order" trigger. If it has none, use Gmail "new email matching search" on the confirmation emails, then a parser step to pull out the fields.
2. **Work out send_date.**
   Look for: Formatter by Zapier, Date / Time, "Add/Subtract Time". Input: the arrival date. Expression: `-30 days`. To format: `YYYY-MM-DD`.
3. **Add the row.**
   Look for: Google Sheets, "Create Spreadsheet Row", tab `queue`. Map booking_ref, booked_on, arrival, departure, the new send_date, party, ages, product. Type `queued` into status.
   **Do not map** guest name, email, phone, address, payment or notes fields. **Policy choice.**

Test it with one fictional booking, then delete that row.

## Zap 2: daily kit drafts (2 to 3 hours)

1. **Trigger: every day, early morning.**
   Look for: Schedule by Zapier, "Every Day". Pick a time such as 6:00, and check that your Zapier time zone setting is Alaska time.
2. **Read the facts.**
   Look for: Google Sheets, "Lookup Spreadsheet Row". Tab `facts`, lookup column `id`, value `current`. This gives you `shared_fact_sheet` and `month_notes`.
3. **Work out tomorrow's date** (used for "today or earlier").
   Look for: Formatter by Zapier, Date / Time, "Add/Subtract Time". Input: the run date from step 1. Expression: `+1 day`. To format: `YYYY-MM-DD`.
4. **Find every queued row.**
   Look for: Google Sheets, "Lookup Spreadsheet Rows (Advanced)" or "Find many rows". Tab `queue`, lookup column `status`, value `queued`. It returns several rows at once.
5. **Repeat for each row.**
   Look for: Looping by Zapier, "Create Loop From Line Items". Loop over the rows from step 4. Steps 6 to 10 run once per row.
6. **Continue only if the row is due.**
   Look for: Filter by Zapier. Condition: `send_date` (Date/time) **before** the date from step 3. That means "today or earlier", so late bookings and missed mornings are caught.
   If date conditions give you trouble, use the "due column" fallback at the end of this file and filter on `due` exactly matches `yes`.
7. **AI step: draft the kit.**
   Look for: AI by Zapier, or the Anthropic (Claude) "Send Message" action, or the OpenAI or Google AI equivalent.
   Paste the prompt from Step 4 of the 3.b page ("Copy prompt"). Then delete each `{{placeholder}}` and insert the matching field with the field picker:
   - `{{shared_fact_sheet}}` and `{{month_notes}}`: from step 2
   - `{{arrival}}`, `{{departure}}`, `{{party}}`, `{{ages}}`, `{{product}}`: from the current loop row
   Map nothing else. No booking_ref, no notes. **Policy choice.**
8. **Optional guard.**
   Look for: Filter by Zapier. Continue only if the AI text **contains** `DRAFT - PENDING OWNER REVIEW`. Rows that stop here stay queued and show in the Zap history.
9. **Create a Gmail draft. Never a send step.**
   Look for: Gmail, "Create Draft".
   - To: leave empty. The approver adds the guest's address from the booking system, which is also a final check that the kit is for the right guest. If the step will not save without a To address, use your own business address and replace it when you approve.
   - Subject: `Your trip kit: arriving ` then map arrival.
   - Body: the AI text. Body type: plain.
10. **Log it.**
   Look for: Google Sheets, "Update Spreadsheet Row". Row: the current loop row's id. Set status `drafted`, drafted_on to the run date, draft_link to the draft id from step 9.

**Errors.** Zapier emails you when a step fails. A failed row stays `queued`, so the next morning tries it again. If the same row fails twice, look at it by hand. If the Gmail step worked but the log step (10) failed, the next morning makes a second draft for that booking: delete the extra one.

**Running cost** (estimate): steps 7, 9 and 10 use a task each per kit, plus a few tasks per morning. At 300 bookings a season that is roughly 1,000 to 1,500 tasks, plus cents per kit for the AI step. Check your plan's task limit.

---

## Test with five fictional bookings (about 1 hour)

1. In the `queue` tab, set send_date on TEST-001 to TEST-004 to today's date. Leave TEST-005 as `canceled`.
2. Put a fact sheet (the fictional one is fine) in `facts`.
3. Run Zap 2 once. Use "Test" on each step, or turn it on and run it.
4. **Expect:** four Gmail drafts, nothing in Sent. TEST-005 untouched. Four rows now say `drafted` with a date and a draft id.
5. Run it again. **Expect:** no new drafts.
6. Paste each draft into "Check the draft" on the 3.b page, and go through the approval checklist. TEST-001 has children aged 6 and 9, so the kayak (minimum age 12) should be left out. The June and August kits should ask for a month note.
7. Delete the test drafts and the TEST rows. Then switch Zap 1 on for real bookings.

## Every kit: one person approves

Open Gmail Drafts. For each kit: run the approval checklist from the 3.b page, answer or delete every [FILL], delete the QUESTIONS FOR THE OWNER list and both DRAFT lines, add the guest's address, and send. In the sheet, write your initials in `approved_by`, the date in `sent_date`, and set status to `sent`. **Policy choice:** one named person approves each kit, and nothing is sent automatically.

## Every month

- Ask each partner for its code counts by the 5th. Paste them into the reconciliation helper on the 3.b page.
- Kits sent that month: count rows with a `sent_date` in that month.
- Re-check any fact-sheet block older than 60 days.

## Changes and cancellations

- Changed dates: update arrival and send_date. If a draft exists, delete it and set status back to `queued`.
- Canceled: set status to `canceled` and delete any draft.

---

## Fallback: a "due" column instead of a date filter

If the date condition in step 6 is awkward, let the sheet work it out. In the `queue` tab, put this in cell O1 (it fills the whole column):

```
={"due"; ARRAYFORMULA(IF(A2:A="", "", IF((I2:I="queued")*(E2:E<>"")*(E2:E<=TODAY()), "yes", "no")))}
```

Then File, Settings, Calculation, Recalculation: "On change and every hour", so TODAY() stays current. In step 4, look up rows where `due` is `yes`, and skip steps 3 and 6. Check that send_date is a real date: it sits right-aligned in its cell.

*AI drafts. A person approves.*
