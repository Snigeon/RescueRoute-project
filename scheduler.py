from matching import find_match
from models import Assignment

def create_state(recipients, volunteers):

    recipient_ids = [r.recipient_id for r in recipients]
    volunteer_ids = [v.volunteer_id for v in volunteers]

    if len(recipient_ids) != len(set(recipient_ids)):
        raise ValueError("Recipient ids must unique")
    if len(volunteer_ids) != len(set(volunteer_ids)):
        raise ValueError("Volunteer ids must unique")
    if any(r.capacity < 0 for r in recipients):
        raise ValueError("Recipient capacity must be positive")
    if any(v.vehicle_capacity < 0 for v in volunteers):
        raise ValueError("Volunteer capacity must be positive")

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

def schedule(donations, recipients, volunteers, now):
    donation_ids = [d.donation_id for d in donations]
    if len(donation_ids) != len(set(donation_ids)):
        raise ValueError("Donation ids must unique")
    if any(d.quantity <= 0 for d in donations):
        raise ValueError("Donation quantity must be positive")

    state = create_state(recipients, volunteers)
    results = []

    for position, donation in enumerate(donations, start=1):
        match, reason = find_match(donation, recipients, volunteers, state, now)
        reason = f"Processing position {position}: {reason}"

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
    results = schedule(donations, recipients, volunteers, now)
    for result in results:
        result.reason = "FIFO uses input arrival order. " + result.reason
    return results

def run_greedy(donations, recipients, volunteers, now):
    sorted_donations = sorted(donations,key=lambda d: (d.expires_at, -d.quantity))

    results = schedule(sorted_donations,recipients,volunteers,now)

    for result in results:
        result.reason = (
            "Greedy prioritizes earlier expiry, then larger quantity, "
            "then original arrival order. "
            + result.reason
        )

    return results