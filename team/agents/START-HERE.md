# ATIA team assistants: start here

Version 1.1 · October 10, 2026

**Status: draft instructions, not yet tested in a live account; test with fictional data first.**

Two instruction sets for Alaska tourism businesses, from the session "Small Business Focus: Leveraging AI Solutions" (Pascual Reig-Munoz, Alaska SBDC) at the ATIA 2026 Annual Convention, Wedgewood Resort, Fairbanks, October 14, 2026. The web page that goes with this package is https://preig.github.io/atiakit/team/

| Assistant | What it produces |
|---|---|
| **ATIA Staff Procedure Coach** | A one-page procedure and a ten-line quick card for one job that lives in one person's head, written so a new seasonal hire can follow it. MONEY, SAFETY and PERMIT/LICENSE steps are flagged where they happen. Safety-critical steps are marked "VERIFY: qualified person". |
| **ATIA Campaign Builder** | A short social campaign for one season (summer cruise, winter aurora or shoulder): posting calendar, complete Instagram, Facebook and LinkedIn posts, a writing prompt and an image prompt per post, then images. Text comes first, images in a separate step. Optional translations, each marked for native-speaker review. |

The durable take-home is not the assistants. It is the **12-line context block** (`shared/business-context-template.md`) and **one staff procedure**. Both work in any capable chat assistant.

## What has and has not been tested

None of the following has been run yet: a hosted assistant built from these files, the opening checks in `SETUP.md`, the tourism rules below in a live conversation, the translated output, the image stage, or a voice session. Treat both assistants as drafts. Expect to correct the first outputs.

Test first with the fictional teaching business, Bay Light Day Cruises in Seward (on the web page above), or with your own facts and no guest data. Then report what breaks.

## Three ways to use them

1. **Paste and go (no setup).** Open a new chat in the assistant you already use (Claude, ChatGPT or Gemini). Paste the full contents of `staff-procedure-coach/hosted-instructions.txt` or `campaign-builder/hosted-instructions.txt`, then your 12-line context block, then one of the conversation starters.
2. **Build your own private assistant.** See `SETUP.md`: a custom GPT in ChatGPT, a Project in Claude, or a Gem in Gemini. About ten minutes per assistant in an account that supports them.
3. **Use only the context block.** Fill in the 12 lines once and paste them at the start of any AI conversation about the business. This alone improves most answers.

No private assistant links are shared in this package. Build your own copy, in your own account.

## AI drafts. You approve.

Every output is a draft until the owner approves it. Safety-critical content is drafted by the tool and owned by a qualified person. A tool that critiques its own draft is not verification: a person checks the facts.

## The rules built into the assistants, by source

| Rule | Source |
|---|---|
| No fake, invented or AI-generated reviews or testimonials, ever | **Legal mandate**: FTC Rule on the Use of Consumer Reviews and Testimonials, 16 CFR Part 465 (effective October 21, 2024) |
| Lodging prices shown as the total price, including known mandatory fees | **Legal mandate**: FTC Rule on Unfair or Deceptive Fees, 16 CFR Part 464 (effective May 12, 2025; covers short-term lodging, not tours) |
| AI voice calls need prior express consent; automated marketing texts fall under consent rules | **Legal mandate**: TCPA, 47 U.S.C. 227; FCC Declaratory Ruling FCC 24-17. Which consent tier applies: check with counsel |
| No AI images presented as real photos of Alaska places, wildlife, aurora or the property; label AI illustrations | **Policy choice** built into the assistant. Reason (**Recommendation**): authenticity is the product for a nature destination, and being caught faking the place costs trust |
| No aurora or wildlife guarantees | **Recommendation**: sightings vary; a promise you cannot keep costs refunds and trust |
| Translations marked for native-speaker review | **Recommendation**: machine translation errors in prices, terms or safety wording are the owner's exposure |
| Safety-critical steps (bear and wildlife, water and boats, glacier and ice, weather or road go/no-go, aviation, firearms, CPR and first aid, cold exposure, vehicle operation) marked "VERIFY: qualified person" | **Recommendation**, built into the assistant: the tool drafts, the qualified operator decides. Guide licensing (AS 08.54, Big Game Commercial Services Board) and ADF&G sport fishing guide and business registration are **legal mandates** and not delegable |
| No guest records, staff records, passwords, codes or license numbers pasted in | **Recommendation**. If guest personal information you hold is ever exposed, the Alaska Personal Information Protection Act, AS 45.48, sets breach-notice duties (**legal mandate**) |
| The owner publishes manually; the assistants never post, send or schedule | **Policy choice** built into both assistants |

Nothing in this package is legal advice.

## Files

| File | Use |
|---|---|
| `START-HERE.md` | This page |
| `SETUP.md` | Set up a private assistant in your own account, and the first checks to run |
| `shared/business-context-template.md` | The 12-line tourism context block, shared by both assistants |
| `staff-procedure-coach/hosted-instructions.txt` | Full instructions for ATIA Staff Procedure Coach (under 8,000 characters) |
| `staff-procedure-coach/conversation-starters.txt` | Four opening requests, one per paragraph |
| `staff-procedure-coach/procedure-output-template.md` | Output shape: procedure, quick card, review and corrections |
| `campaign-builder/hosted-instructions.txt` | Full instructions for ATIA Campaign Builder (under 8,000 characters) |
| `campaign-builder/conversation-starters.txt` | Four opening requests, one per paragraph |

Alaska Small Business Development Center, University of Alaska Anchorage Business Enterprise Institute. We grow small business.
