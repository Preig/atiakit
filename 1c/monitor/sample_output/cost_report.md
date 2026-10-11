# Cost report

DRAFT - PENDING OWNER REVIEW

Measured from the usage each provider reported, times the prices set in your .env. Your provider billing pages are the actual bill. Mock runs are listed but cost nothing.

| Month | Mode | Provider | Answers | Input tokens | Output tokens | Searches | Cost | Answers without a price |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 2026-10 | mock | anthropic | 32 | 408,400 | 24,340 | 38 | $2.50 (not spent) | 0 |
| 2026-10 | mock | gemini | 32 | 136,800 | 16,380 | 34 | n/a (price not set) | 32 |
| 2026-10 | mock | openai | 32 | 254,600 | 19,520 | 32 | n/a (price not set) | 32 |

**Spent this month (2026-10, live and dry runs):** $0.00 of a $25.00 MONTHLY_BUDGET.

No priced live answers yet, so there is no projection. Run `python monitor.py run --dry-run` after setting prices in .env.
- Prices not set for openai: OPENAI_PRICE_INPUT_PER_MTOK, OPENAI_PRICE_OUTPUT_PER_MTOK
- Prices not set for gemini: GEMINI_PRICE_INPUT_PER_MTOK, GEMINI_PRICE_OUTPUT_PER_MTOK
