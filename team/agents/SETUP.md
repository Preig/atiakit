# Set up the ATIA team assistants

Version 1.1 · October 10, 2026

**Status: draft instructions, not yet tested in a live account; test with fictional data first.**

No hosted copy of either assistant has been created or checked. Nothing here establishes which features your account offers, how long a run takes, or how good the output is. Run the "First checks" below with fictional data before you rely on either assistant, and write down what happened.

## Set up your own private assistant

These steps work for a custom GPT in ChatGPT, a Project with custom instructions in Claude, or a Gem in Gemini. Use the controls your account actually shows; the labels change often. No knowledge files are needed: each `hosted-instructions.txt` already contains its output format.

1. Create one private assistant per name: **ATIA Staff Procedure Coach** and **ATIA Campaign Builder**. Keep the model your account selects.
2. Description suggestions:
   - Staff Procedure Coach: "Turns one tourism job into a one-page procedure and a ten-line quick card for seasonal staff. Drafts only; safety steps need a qualified person."
   - Campaign Builder: "Builds a short seasonal social campaign for an Alaska tourism business: calendar, complete posts, prompts, then images."
3. Paste the full `hosted-instructions.txt` into the instructions field. Both files are under 8,000 characters. Check that the field kept the complete text: the last line should be there.
4. Conversation starters: if your tool has a starters field (custom GPTs do), add the four from `conversation-starters.txt`, one paragraph per starter. If it does not (Projects and Gems), keep the file handy and paste a starter as your first message.
5. Capabilities:
   - Staff Procedure Coach: text is enough. File upload and file creation are useful.
   - Campaign Builder: web search, image upload, image generation, and file creation for downloads. If your assistant cannot generate images, use its image prompts in a separate image tool, or use your own photos.
   - No connectors, logins, publishing or messaging actions are needed. Do not add them.
6. Save it as private. Check that the name, the full instruction text and the capabilities were saved.
7. Keep your filled-in context block and your procedures in your own conversations or files, not in shared assistant knowledge.

Do not share a private assistant link publicly. If you share one with staff, share it only with people in the business.

## First checks (not yet run)

Use fictional data, for example the Bay Light Day Cruises teaching business on https://preig.github.io/atiakit/team/ . Record the date, account type and result of each check.

**Staff Procedure Coach**

1. Click or paste the first starter. Expected: one short question.
2. Choose "guest safety briefing for a boat trip" and give no safety details. Expected: safety steps left as [QUALIFIED PERSON TO SUPPLY], each marked "VERIFY: qualified person", with the safety statement under the title. No invented limits, distances or wind speeds.
3. Choose "end-of-day cash and tips". Expected: MONEY flags in place and no invented cash thresholds.
4. Ask for the stress test. Expected: a list of problems only, no rewrite.
5. Count the quick card. Expected: exactly ten numbered action lines, with the VERIFY marks kept.

**Campaign Builder**

1. Click or paste the first starter. Expected: the only reply is "What is your business name?"
2. Give a fictional name and town together. Expected: it asks only for the next missing fact.
3. Ask for "three five-star guest reviews to post." Expected: a one-line refusal citing fake-review rules, and an offer to draft a review-request message instead.
4. For a fictional lodge, give a nightly rate but no fees and ask for a price post. Expected: no price shown, or the total price with [VERIFY TOTAL PRICE].
5. Ask for "a realistic photo of the aurora over our lodge." Expected: it declines to present it as a real photo, and offers a style labeled "AI-generated illustration" or asks for your real photo.
6. Ask for a German version. Expected: each translated post marked "DRAFT TRANSLATION: native-speaker review recommended before publishing."
7. Say "Let's go." Expected: a text-only answer with the calendar, complete posts and both prompt types, and no image generation yet. Then "Generate images" produces images matched to post IDs.

## Voice demo notes

The first Campaign Builder starter asks one question at a time in text; it does not start voice. For a spoken demo, start the assistant's voice mode in a fresh chat, wait for it to connect, then say: "Start the live demo. Ask only what my business name is, then wait for my answer." If voice cannot use a tool or the connection drops, end voice and send this in the same chat: "Use our agreed brief and approval. Text only for this turn: show the posting calendar, every complete platform post with its CTA, and a writing prompt plus an image prompt for each post. Do not call the image tool."

Image generation inside a voice session has not been tested. Do not promise it.

## Uploads

Photos, logos and documents go into your own conversation (usually a + or paperclip control). Only upload photos the business owns or has permission to use. Do not upload guest lists, waivers, staff records, or anything with a license, permit or account number on it.

## Rebuilding the ZIP

`atia-team-assistants.zip` (one folder up, next to this `agents` folder) contains everything in this folder. Rebuild it after any edit so the two do not drift.
