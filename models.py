from __future__ import annotations
from dataclasses import dataclass, field
import datetime
from typing import Literal


@dataclass
class Donation:
    donation_id: str
    donor_name: str
    food_type: str
    quantity: int
    expires_at: datetime.datetime
    pickup_area: str
    ready_at: datetime.datetime
    arrival_index: int

@dataclass
class Recipient:
    recipient_id: str
    organization_name: str
    accepted_food_types: set[str]
    capacity: int
    area: str
    closest_at: datetime.datetime

@dataclass
class Volunteer:
    volunteer_id: str
    vehicle_capacity: int
    area: str
    available_from: datetime.date
    available_until: datetime.date
    max_pickups: int

@dataclass
class Assignment:
    donation_id: str
    recipient_id: str
    volunteer_id: str
    scheduled_at: datetime.datetime
    delivery_at: datetime.datetime
    quantity: int
    reason: str
    status: Literal["assigned"] = "assigned"

