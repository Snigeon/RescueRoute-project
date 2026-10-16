from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Donation:
    donation_id: str
    donor_name: str
    food_type: str
    quantity: int
    expires_at: datetime
    pickup_area: str
    ready_at: datetime

@dataclass
class Recipient:
    recipient_id: str
    organization_name: str
    accepted_food_types: list[str]
    capacity: int
    area: str
    closes_at: datetime

@dataclass
class Volunteer:
    volunteer_id: str
    vehicle_capacity: int
    area: str
    available_from: datetime
    available_until: datetime
    max_pickups: int

@dataclass
class Assignment:
    donation_id: str
    status: str
    reason: str
    recipient_id: str | None = None
    volunteer_id: str | None = None
    scheduled_at: datetime | None = None
    delivery_at: datetime | None = None
