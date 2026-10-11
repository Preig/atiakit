# Example drafts (dry run, fictional)

Bay Light Day Cruises, Seward is a FICTIONAL TEACHING BUSINESS. These were made by `python tools/make_samples.py` from the templates, approved_facts.md and approved_addons.csv. No model was called. Each [FILL] is a fact the owner has not supplied yet.

Example booking: BL-26-DEMO, trip Tuesday, July 14, 2026 at 9:00, flexible rate, booked direct, party of 2, no add-ons.

## Message A: Confidence note

```text
DRAFT - PENDING OWNER REVIEW
Subject: Your 4-hour wildlife and glacier cruise on Tuesday, July 14, 2026: what to expect

Hello,

Thank you for booking the 4-hour wildlife and glacier cruise on Tuesday, July 14, 2026 at 9:00. Here is what to expect, so there are no surprises.

What to expect
- Heated enclosed cabin and two restrooms on board.
- Hot drinks are included. Lunch is not included.
- Meeting point: the small-boat harbor, a 12-minute walk from the cruise ship dock.
- Weather: The cruise runs in rain. It cancels only for a marine warning, with a full refund.

If your plans change
- Free cancellation until 48 hours before departure. Inside 48 hours, no refund.
- To review or change your booking, reply to this message or call [FILL: contact person] at [FILL: contact phone]. A person on our team will help you.

Our track record
- [FILL: track record]

See you at the harbor,
The Bay Light Day Cruises team
```

Local checks: 3 open [FILL] item(s): a person fills or removes them

## Message B: One add-on

```text
DRAFT - PENDING OWNER REVIEW
Subject: One idea for your day in Seward on Tuesday, July 14, 2026

Hello,

You are booked on the 4-hour wildlife and glacier cruise on Tuesday, July 14, 2026 at 9:00. Guests often ask what else fits the same day, so here is one option we know well.

Mile 12 Kennel summer sled-dog cart ride (partner)
- 90 minutes, 15 minutes by car from the harbor, ages 2 and up, runs in rain.
- Prices and times come from Mile 12 Kennel directly.
- Book with Mile 12 Kennel and mention referral code BAYLIGHT-K.

It is optional, and your cruise booking stays the same either way. Please check the age limits for your group.

Questions? Reply to this message or call [FILL: contact person] at [FILL: contact phone].

The Bay Light Day Cruises team
[FILL: postal address and opt out]
```

Local checks: 3 open [FILL] item(s): a person fills or removes them

## Message C: Lock-in offer

Only drafted when the owner writes terms into rules.json. The terms below are fictional.

```text
DRAFT - PENDING OWNER REVIEW
Subject: An option for your Tuesday, July 14, 2026 cruise

Hello,

You are booked on a flexible rate for the 4-hour wildlife and glacier cruise on Tuesday, July 14, 2026 at 9:00. Nothing changes unless you choose to.

If you would like to lock in your booking now, here is our offer:
FICTIONAL EXAMPLE TERMS: switch to our non-refundable rate at least 30 days before your trip and we add a printed wildlife guide for each guest. (The owner writes the real terms.)

If you do nothing, your current booking stays as it is. Free cancellation until 48 hours before departure. Inside 48 hours, no refund.

Questions? Reply to this message or call [FILL: contact person] at [FILL: contact phone]. A person on our team will help you decide.

The Bay Light Day Cruises team
[FILL: postal address and opt out]
```

Local checks: 3 open [FILL] item(s): a person fills or removes them

## A draft the checks would stop

If a model wrote this, the queue row would carry these flags. A person still decides.

```text
Subject: Don't cancel!

Hello,

Good news: we'll match any lower price you find, and for $99 more you get a private charter.
You will see whales, guaranteed. Call 907-555-0142 to lock it in.
```

- missing the DRAFT marker
- number(s) not in the approved sources: 99, 907, 555, 0142
- banned phrase: 'match any'
- banned phrase: 'guarantee'
- promise wording, check it: 'will see'
- promise wording, check it: 'guaranteed'
- a phone number that is not in the approved facts

The phone number above is a fictional 555 number used only to show the check.
