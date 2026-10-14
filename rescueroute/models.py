from dataclasses import dataclass
import datetime

@dataclass
class Donation:
    donation_id: str
    donor_name: str
    food_type: str
    quantity: int
    expires_at: datetime.date
    pickup_area: str
    ready_at: datetime.date
    arrival_index: int

@dataclass
class Recipient:
    recipient_id: str
    organization_name: str
    accepted_food_types: list[str]
    capacity: int
    area: str
    closest_at: datetime.date


