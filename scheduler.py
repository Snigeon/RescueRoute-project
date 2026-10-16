from matching import TRIP_TIME, find_match, format_minutes
from models import Assignment

STRATEGY_FIFO = "fifo"
STRATEGY_GREEDY = "greedy"

def create_state(recipients, volunteers):

    recipient_ids = [r.recipient_id for r in recipients]
    volunteer_ids = [v.volunteer_id for v in volunteers]

    if len(recipient_ids) != len(set(recipient_ids)):
        raise ValueError("Recipient ids must be unique")
    if len(volunteer_ids) != len(set(volunteer_ids)):
        raise ValueError("Volunteer ids must be unique")
    if any(r.capacity < 0 for r in recipients):
        raise ValueError("Recipient capacity cannot be negative")
    if any(v.vehicle_capacity < 0 for v in volunteers):
        raise ValueError("Volunteer vehicle capacity cannot be negative")

    return {
        "remaining_capacity": {
            r.recipient_id: r.capacity for r in recipients
        },
        "pickups_used": {
            v.volunteer_id: 0 for v in volunteers
        },
        "next_available": {
            v.volunteer_id: v.available_from for v in volunteers
        },
    }

def greedy_priority(donation, state, volunteers, now):
    """The urgency-first priority key. Smallest key is scheduled first.

    1. available slack - minutes between the earliest delivery any same-area
       volunteer could achieve and the donation's expiry. This is the real
       measure of how close the food is to being lost, because it accounts for
       when a volunteer is actually free.
    2. earlier absolute expiry.
    3. larger quantity.
    4. arrival order, which needs no term because sorted() is stable.
    """
    earliest_pickup = max(now, donation.ready_at)
    free_times = [
        max(earliest_pickup, volunteer.available_from,
            state["next_available"][volunteer.volunteer_id])
        for volunteer in volunteers
        if volunteer.area == donation.pickup_area
    ]
    earliest_delivery = (min(free_times) if free_times else earliest_pickup) + TRIP_TIME
    slack = (donation.expires_at - earliest_delivery).total_seconds() / 60.0
    return (slack, donation.expires_at, -donation.quantity)

def schedule(donations, recipients, volunteers, now, strategy=STRATEGY_FIFO):
    donation_ids = [d.donation_id for d in donations]
    if len(donation_ids) != len(set(donation_ids)):
        raise ValueError("Donation ids must be unique")
    if any(d.quantity <= 0 for d in donations):
        raise ValueError("Donation quantity must be positive")

    state = create_state(recipients, volunteers)
    results = []

    total = len(donations)
    for position, donation in enumerate(donations, start=1):
        match, reason = find_match(
            donation, recipients, volunteers, state, now,
            "first" if strategy == STRATEGY_FIFO else "best",
        )

        if strategy == STRATEGY_GREEDY:
            slack = greedy_priority(donation, state, volunteers, now)[0]
            order = (
                f"Greedy urgency-first considered this donation at position "
                f"{position} of {total} because it had {format_minutes(slack)} "
                f"of available slack until expiry, less than the donations "
                f"after it and more than the ones before it. "
            ) if position > 1 else (
                f"Greedy urgency-first considered this donation first of "
                f"{total} because it had the least available slack, "
                f"{format_minutes(slack)} until expiry. "
            )
        else:
            order = (
                f"FIFO processes the input in arrival order; this is donation "
                f"{position} of {total}. "
            )

        reason = order + reason

        if match is None:
            results.append(Assignment(donation_id=donation.donation_id,
                           status = "unassigned",
                           reason = reason))
            continue

        recipient_id = match["recipient_id"]
        volunteer_id = match["volunteer_id"]
        results.append(Assignment(
            donation_id=donation.donation_id,
            status = "assigned",
            reason = reason,
            recipient_id = recipient_id,
            volunteer_id = volunteer_id,
            scheduled_at = match["pickup_time"],
            delivery_at = match["delivery_time"],))

        state["remaining_capacity"][recipient_id] -= donation.quantity
        state["pickups_used"][volunteer_id] += 1
        state["next_available"][volunteer_id] = match["delivery_time"]
    return results

def run_fifo(donations, recipients, volunteers, now):
    return schedule(donations, recipients, volunteers, now, STRATEGY_FIFO)

def run_greedy(donations, recipients, volunteers, now):
    state = create_state(recipients, volunteers)
    sorted_donations = sorted(
        donations, key=lambda d: greedy_priority(d, state, volunteers, now)
    )
    return schedule(sorted_donations, recipients, volunteers, now, STRATEGY_GREEDY)

def run_both(donations, recipients, volunteers, now):
    """Run both strategies over the same input data.

    Each run builds its own state, so neither strategy inherits capacity,
    pickups or volunteer time that the other one spent.
    """
    return {
        STRATEGY_FIFO: run_fifo(donations, recipients, volunteers, now),
        STRATEGY_GREEDY: run_greedy(donations, recipients, volunteers, now),
    }
