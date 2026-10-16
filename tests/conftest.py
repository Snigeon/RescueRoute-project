from __future__ import annotations
from datetime import datetime, timedelta, timezone
import pytest
from models import Donation, Recipient, Volunteer
NOW = datetime(2026, 10, 13, 10, 0, tzinfo=timezone.utc)
TRIP_MINUTES = 15

def at(hour, minute=0):
    return datetime(2026, 10, 13, hour, minute, tzinfo=timezone.utc)

def minutes_later(base, minutes):
    return base + timedelta(minutes=minutes)

def state_for(volunteers, recipients=None):
    from scheduler import create_state
    return create_state(recipients or [], volunteers)

def donation(donation_id='D-1', quantity=10, food_type='prepared_meals', area='Central', ready_at=None, expires_at=None, donor_name='Test Donor'):
    return Donation(donation_id=donation_id, donor_name=donor_name, food_type=food_type, quantity=quantity, expires_at=expires_at or at(12, 0), pickup_area=area, ready_at=ready_at or at(10, 0))

def recipient(recipient_id='R-1', capacity=50, accepted_food_types=None, area='Central', closes_at=None, organization_name='Test Shelter'):
    accepted = ['prepared_meals', 'produce', 'bakery'] if accepted_food_types is None else list(accepted_food_types)
    return Recipient(recipient_id=recipient_id, organization_name=organization_name, accepted_food_types=accepted, capacity=capacity, area=area, closes_at=closes_at or at(13, 0))

def volunteer(volunteer_id='V-1', vehicle_capacity=50, area='Central', available_from=None, available_until=None, max_pickups=3):
    return Volunteer(volunteer_id=volunteer_id, vehicle_capacity=vehicle_capacity, area=area, available_from=available_from or at(10, 0), available_until=available_until or at(13, 0), max_pickups=max_pickups)

@pytest.fixture
def now():
    return NOW
