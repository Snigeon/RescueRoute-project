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
    arrival_index: int

@dataclass
class Recipient:
    recipient_id: str
    organization_name: str
    accepted_food_types: set[str]
    capacity: int
    area: str
    closest_at: datetime

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
    volunteer_id: str
    quantity: int
    reason: str
    donation_id: str | None = None
    recipient_id: str | None = None
    delivery_at: datetime | None = None
    scheduled_at: datetime | None = None
