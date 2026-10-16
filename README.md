RESCUEROUTE

Repository: https://github.com/Snigeon/RescueRoute-project

Matches food donations to recipients and volunteer drivers, validates the input,
and compares a FIFO baseline against a greedy urgency-first strategy. Every
assignment, rejection and deferral is explained in a sentence.


ARCHITECTURE

    main.py           CLI: arguments, wiring, exit codes, output
    data_loader.py    JSON reading, timestamp parsing, validation
    models.py         Donation, Recipient, Volunteer, Assignment
    matching.py       feasibility, candidate generation and ordering
    scheduler.py      allocation state, the priority rule, the two strategies
    reports.py        metrics, comparison, console/JSON/Markdown output
    tests/            conftest.py plus 40 test functions (67 cases)
    run_tests.py      runner for environments without pytest

Requires Python 3.11+. The application uses only the standard library.

    python main.py                              both strategies, compared
    python main.py --strategy fifo              FIFO baseline only
    python main.py --strategy greedy            greedy only
    python main.py --data-dir data_fifo_vs_greedy
    python main.py --output-dir output          writes results.json, comparison.md
    python run_tests.py                         67 tests, no pytest needed
    python -m pytest                            the same suite

    --data-dir PATH       folder with the three JSON files (default: ./data)
    --strategy {fifo,greedy,compare}            (default: compare)
    --now ISO8601         timezone-aware simulation start
                          (default: 2026-10-13T10:00:00+00:00)
    --urgent-minutes N    urgent if it expires within N minutes (default: 60)
    --output-dir PATH     also write results.json and comparison.md
    --quiet               do not print the report

Exit status is 0 on success, 2 for a bad argument, missing file or invalid data.

Sample data: data/ (8 donations across 3 areas, including an expired donation, a
food type nobody accepts, an unreachable area, and a donation too large for any
vehicle); data_fifo_vs_greedy/ (built so the two strategies cannot agree).


DATA MODEL

All times are ISO 8601 strings with a timezone, normalised to UTC. A timestamp
without a timezone is rejected rather than guessed.

    Donation     donation_id, donor_name, food_type, quantity, expires_at,
                 pickup_area, ready_at
    Recipient    recipient_id, organization_name, accepted_food_types,
                 capacity, area, closes_at
    Volunteer    volunteer_id, vehicle_capacity, area, available_from,
                 available_until, max_pickups
    Assignment   donation_id, status, reason, recipient_id, volunteer_id,
                 scheduled_at, delivery_at

food_type is one of prepared_meals, produce, bakery, dairy, canned_goods.

A donation can be assigned to a recipient/volunteer pair only when all of the
following hold. Every failure is recorded with a human-readable reason.

    1. The donation has not already expired at the simulation start.
    2. The recipient accepts the food type.
    3. Donation, recipient and volunteer are all in the same area. No
       inter-area travel time is modelled, so cross-area moves are refused.
    4. The recipient still has enough capacity left. Capacity promised to an
       earlier donation is never promised twice.
    5. The volunteer has a pickup left (pickups_used < max_pickups) and a
       vehicle large enough for the quantity.
    6. A trip fits the calendar: pickup at the latest of the simulation start,
       the donation's ready time, the volunteer's available_from and the time
       that volunteer frees up; delivery 15 simulated minutes later, strictly
       before the donation expires, before the recipient closes, and no later
       than the volunteer's available_until.

Validation is strict: unknown fields, missing fields, duplicate IDs,
unsupported food types, negative quantities and naive timestamps are all
collected and reported together, so an input file can be fixed in one pass.


GREEDY RULE

FIFO baseline: donations are processed in arrival order, which is their order in
donations.json, and the first feasible recipient/volunteer pairing is taken. It
never looks ahead and never asks whether a donation is urgent.

Greedy urgency-first:

    Schedule the donation with the smallest available slack first. Available
    slack is the time between a donation's expiry and the earliest delivery any
    same-area volunteer could achieve, once that volunteer's availability and
    already-committed trips are taken into account.

    Ties break in this order: smaller slack, earlier absolute expiry, larger
    quantity, then arrival order (sorted() is stable, so the last needs no term).

For the chosen donation the pairing is picked by earliest delivery, then the
tightest remaining capacity that still fits, then the recipient that closes
soonest, then the smallest vehicle that still fits, then the IDs.


COMPLEXITY

With n donations, R recipients and V volunteers:

    Loading and validation          O(n + R + V)
    Greedy ordering                 O(n*V + n log n)
    Feasibility scan per donation   O(R * V) worst case
    Full schedule                   O(n * R * V) worst case
    Metrics and comparison          O(n)

Memory is O(n + R + V). The practical limit is that the pair scan is quadratic
in the number of organisations in an area; indexing recipients by area and
accepted food type would remove most of it.


LIMITATIONS

Arrival order is the order of records in donations.json; there is no separate
arrived_at field. This defines the FIFO baseline.

Time is simulated. --now fixes the clock; there is no live clock, no
persistence and no real-time dispatch.

Trip time is a constant 15 minutes and trips are independent. No routing,
traffic, distance, loading time or multi-stop consolidation.

Area matching is all or nothing; cross-area moves are refused rather than
costed. A real deployment would need travel times.

One recipient per donation; splitting a donation is not modelled.

The schema is strict. Extra or missing fields are fatal, which catches typos but
rejects an otherwise valid file that adds, say, a notes field.

No optimality claim. Neither strategy is proven optimal; an integer program or
local search would likely beat both on volume and on urgent rescue rate.

No fairness guarantee. Urgency always beats size, so a consistent low-urgency
donor can be de-prioritised indefinitely; a quota or rotation would be needed to
bound that. The rule is also myopic: it never revisits a decision, so it can
spend the last pickup on a donation that a different choice would have rescued
with room to spare.

Food safety beyond food type and expiry is out of scope.


REFERENCES

Feeding America and similar food-rescue logistics material, used to frame the
problem and the perishability constraint.

The EPA Wasted Food Scale, in particular the "rescue food for people" tier that
motivates matching rather than disposal.

Python standard library documentation for dataclasses, datetime, json, argparse
and pathlib; pytest documentation for the test layout and fixtures.

Greedy and FIFO scheduling are standard textbook material; any introductory
algorithms text covering greedy heuristics and their optimality counterexamples
applies to the rule above. Neither strategy here is claimed to be optimal.
