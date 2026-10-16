from datetime import timedelta

from models import Volunteer, Recipient

TRIP_TIME = timedelta(minutes=15)

def format_minutes(minutes):
    minutes = int(round(minutes))
    if minutes < 60:
        return f"{minutes} minutes"
    hours, rest = divmod(minutes, 60)
    return f"{hours} h {rest} min" if rest else f"{hours} h"

def format_time(value):
    return value.isoformat(timespec="minutes")

def find_match(donation, recipients, volunteers, state, now):
    if donation.expires_at <= now:
        return None, (
            f"Donation {donation.donation_id} is already expired"
            f"expiry was {donation.expires_at.isoformat(timespec='minutes')}"
        )
    problems = []
    if not recipients:
        return None, f"Donation {donation.donation_id} has no recipients"

    if not volunteers:
        return None, f"Donation {donation.donation_id} has no volunteers"

    for recipient in recipients:
        remaining = state["remaining_capacity"][recipient.recipient_id]

        if donation.food_type not in recipient.accepted_food_types:
            problems.append(
                f"{recipient.organization_name} does not accept {donation.food_type}"
            )
            continue

        if recipient.area != donation.pickup_area:
            problems.append(
                f"{recipient.organization_name} is outside pickup area"
                f"{donation.pickup_area}"
            )
            continue

        if remaining < donation.quantity:
            problems.append(
                f"{recipient.organization_name} has {remaining} remaining"
                f",but the donation needs {donation.quantity}"
            )
            continue

        for volunteer in volunteers:
            volunteer_id = volunteer.volunteer_id

            if volunteer.area != donation.pickup_area:
                problems.append(
                    f"volunteer {volunteer_id} does not accept is outside pickup area"
                    f"{donation.pickup_area}"
                )
                continue

            if volunteer.vehicle_capacity < donation.quantity:
                problems.append(
                    f"volunteer{volunteer_id} capacity{volunteer.vehicle_capacity} is less than {donation.quantity}"
                )
                continue

            if state["pickups_used"][volunteer_id] >= volunteer.vehicle_capacity:
                problems.append(
                    f"volunteer {volunteer_id} has reached maximum of"
                    f"{volunteer.vehicle_capacity} pickups"
                )
                continue

            pickup_time = max(
                now,
                donation.ready_at,
                volunteer.available_from,
                state["next_available"][volunteer_id],
            )

            delivery_time = pickup_time + TRIP_TIME

            time_problems = []
            if delivery_time >= donation.expires_at:
                time_problems.append(
                    f"a trip with {volunteer_id} to {recipient.organization_name} "
                    "cannot finish before the donation's simulated expiry"
                )

            if delivery_time >= recipient.closes_at:
                time_problems.append(
                    f"a trip with {volunteer_id} cannot reach {recipient.organization_name} "
                    f"before its closing time"
                )

            if delivery_time > volunteer.available_until:
                time_problems.append(
                    f"a trip to {recipient.organization_name} cannot finish "
                    f"within volunteer {volunteer_id}'s availability"
                )

            if time_problems:
                problems.extend(time_problems)
                continue


            match = {
                "recipient_id": recipient.recipient_id,
                "volunteer_id": volunteer_id,
                "pickup_time": pickup_time,
                "delivery_time": delivery_time,
            }

            reason = (
                f"Donation {donation.donation_id} from {donation.donor_name} was "
                f"assigned to {recipient.organization_name} with volunteer "
                f"{volunteer_id} because the recipient accepts "
                f"{donation.food_type}, has {remaining} servings of remaining "
                f"capacity for {donation.quantity} servings, and the vehicle can "
                f"carry {volunteer.vehicle_capacity} servings. All are in "
                f"{donation.pickup_area}. Pickup is "
                f"{pickup_time.isoformat(timespec='minutes')}; delivery is "
                f"{delivery_time.isoformat(timespec='minutes')}, before simulated "
                "expiry and closing, and within the volunteer's availability "
                "and pickup limit."
            )

            return match, reason

    unique_problems = list(dict.fromkeys(problems))

    reason = (
        f"Donation {donation.donation_id} could not be assigned."
        "No recipient-volunteer pair satisfied all constraints: "
        + "; ".join(unique_problems)
        + "."
    )

    return None, reason