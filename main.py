"""Run a small, fixed-time FIFO example using simulated Python objects."""

from datetime import datetime, timedelta, timezone

from models import Donation, Recipient, Volunteer
from scheduler import run_fifo


def main():
    now = datetime(2026, 10, 13, 10, 0, tzinfo=timezone.utc)

    # File/list order represents arrival order, not urgency order.
    donations = [
        Donation(
            donation_id="D-100",
            donor_name="Campus Dining",
            food_type="prepared_meals",
            quantity=40,
            expires_at=now + timedelta(minutes=120),
            pickup_area="Central",
            ready_at=now,
        ),
        Donation(
            donation_id="D-101",
            donor_name="Garden Market",
            food_type="produce",
            quantity=25,
            expires_at=now + timedelta(minutes=30),
            pickup_area="Central",
            ready_at=now,
        ),
        Donation(
            donation_id="D-102",
            donor_name="Campus Event",
            food_type="prepared_meals",
            quantity=10,
            expires_at=now + timedelta(minutes=90),
            pickup_area="Central",
            ready_at=now,
        ),
    ]
    recipients = [
        Recipient(
            recipient_id="R-1",
            organization_name="Community Shelter",
            accepted_food_types=["prepared_meals", "produce"],
            capacity=40,
            area="Central",
            closes_at=now + timedelta(minutes=180),
        ),
        Recipient(
            recipient_id="R-2",
            organization_name="Community Shelter 2",
            accepted_food_types=["prepared_meals", "produce"],
            capacity=40,
            area="Central",
            closes_at=now + timedelta(minutes=180),
        )
    ]
    volunteers = [
        Volunteer(
            volunteer_id="V-1",
            vehicle_capacity=50,
            area="Central",
            available_from=now,
            available_until=now + timedelta(minutes=180),
            max_pickups=3,
        ),
    ]

    results = run_fifo(donations, recipients, volunteers, now)
    for result in results:
        print(f"{result.status.upper()}: {result.reason}\n")

    quantities = {d.donation_id: d.quantity for d in donations}
    assigned = [result for result in results if result.status == "assigned"]
    rescued = sum(quantities[result.donation_id] for result in assigned)
    print(f"Received: {len(donations)}")
    print(f"Assigned: {len(assigned)}")
    print(f"Unassigned: {len(donations) - len(assigned)}")
    print(f"Rescued: {rescued} simulated servings")
    print("\nFIFO used shelter capacity before considering the more urgent donation.")


if __name__ == "__main__":
    main()
