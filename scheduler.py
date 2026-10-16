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
    if any(v.capacity < 0 for v in volunteers):
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

