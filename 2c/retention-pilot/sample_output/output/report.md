# Retention pilot report

Generated 2026-10-10. Holdout share 0.5, seed `baylight-pilot-2027`.

**FICTIONAL TEACHING DATA: Bay Light Day Cruises, Seward. The outcomes were simulated and the booking values are invented.**

## How to read this

- Number 4 = bookings changed or cancelled inside the free-cancellation window, divided by bookings with an outcome. Flexible and non-refundable are shown separately.
- Bookings are compared by assigned arm, whether or not a draft was approved and sent.
- Operator cancellations (for example a marine warning) are left out of the rate.
- The 95% interval is a Wilson interval. If the treatment and holdout intervals overlap a lot, there is no clear difference.
- A confirmatory read at a 50/50 treatment/holdout split needs about 2,036 holdout and 2,036 treatment bookings (15.0% to 12.0%, alpha 0.05, power 0.8). Below that, a result is directional: worth noting, not evidence to scale on.

## Results

### All eligible bookings

| Arm | Assigned | Counted (n) | Changed in window | Cancelled in window | Rate | 95% interval | Value of in-window cancellations |
|---|---:|---:|---:|---:|---:|---|---:|
| Treatment | 14 | 14 | 1 | 1 | 14.3% | 4.0% to 39.9% | $149 |
| Holdout | 16 | 13 | 3 | 2 | 38.5% | 17.7% to 64.5% | $1,043 |

**Read: TOO SMALL TO READ: counts only.** -24.2 points (treatment minus holdout)

Left out as operator cancellations: 0 treatment, 3 holdout.

### Flexible rate

| Arm | Assigned | Counted (n) | Changed in window | Cancelled in window | Rate | 95% interval | Value of in-window cancellations |
|---|---:|---:|---:|---:|---:|---|---:|
| Treatment | 14 | 14 | 1 | 1 | 14.3% | 4.0% to 39.9% | $149 |
| Holdout | 16 | 13 | 3 | 2 | 38.5% | 17.7% to 64.5% | $1,043 |

**Read: TOO SMALL TO READ: counts only.** -24.2 points (treatment minus holdout)

Left out as operator cancellations: 0 treatment, 3 holdout.

### Non-refundable rate

| Arm | Assigned | Counted (n) | Changed in window | Cancelled in window | Rate | 95% interval | Value of in-window cancellations |
|---|---:|---:|---:|---:|---:|---|---:|
| Treatment | 0 | 0 | 0 | 0 | n/a | n/a | $0 |
| Holdout | 0 | 0 | 0 | 0 | n/a | n/a | $0 |

**Read: NO DATA.**

## Approval queue

- PENDING: 14

Status values: PENDING (drafted, not reviewed), APPROVED, REJECTED, SENT_BY_STAFF (a person sent it from the booking platform).

## Context: every booking in the file

Use this to choose the baseline rate for the power command.

- Flexible: 29 of 203 bookings changed or cancelled in window (14.3%, 95% interval 10.1% to 19.8%).
- Non-refundable: 2 of 86 bookings changed or cancelled in window (2.3%, 95% interval 0.6% to 8.1%).

This report counts what happened. It does not show why. A person decides what to keep, change or stop.
