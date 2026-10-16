import json
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path
from models import Donation, Recipient, Volunteer

FOOD_TYPES = {
    "prepared_meals",
    "produce",
    "bakery",
    "dairy",
    "canned_goods"
}

def parse_time(value, label="time"):
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be a valid ISO 8601 timestamp string.") from error

    if parsed.utcoffset() is None:
        raise ValueError(f"{label} must include a timezone, such as +00:00.")

    return parsed.astimezone(timezone.utc)

def load_json_file(path):

    path = Path(path)

    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError as error:
        raise ValueError(f"{path} does not exist") from error
    except (OSError, UnicodeDecodeError) as error:
        raise ValueError(f"{path} is not a valid json file") from error
    if not text.strip():
        return []
    try:
        records = json.loads(text)
    except json.decoder.JSONDecodeError as error:
        raise ValueError(f"Invalid json file: {path}") from error
    if not isinstance(records, list):
        raise ValueError(f"{path} must contain a JSON list of records.")
    return records

def _load_records(path, model, time_fields):

    records = load_json_file(path)
    required = {field.name for field in fields(model)}
    objects = []

    for position, record in enumerate(records, start=1):
        label = f"{path}, record {position}"
        if not isinstance(record, dict):
            raise ValueError(f"{label} must be a JSON object.")
        missing = required - record.keys()
        extra = record.keys() - required
        if missing:
            raise ValueError(f"{label} is missing fields: {', '.join(sorted(missing))}.")
        if extra:
            raise ValueError(f"{label} has unknown fields: {', '.join(sorted(extra))}.")
        values = record.copy()
        for name in time_fields:
            values[name] = parse_time(values[name], f"{label}: {name}")
        objects.append(model(**values))
    return objects

def load_data(folder):

    folder = Path(folder)
    donations = _load_records(
        folder / "donations.json", Donation, ("expires_at", "ready_at")
    )
    recipients = _load_records(
        folder / "recipients.json", Recipient, ("closes_at",)
    )
    volunteers = _load_records(
        folder / "volunteers.json", Volunteer, ("available_from", "available_until")
    )
    errors = validate_data(donations, recipients, volunteers)
    if errors:
        raise ValueError("Input validation failed:\n- " + "\n- ".join(errors))
    return donations, recipients, volunteers

def _check_text(value, label, errors):
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label} must be a nonempty string.")
        return False
    if value != value.strip():
        errors.append(f"{label} cannot have leading or trailing whitespace.")
        return False
    return True


def _check_integer(value, label, errors, positive=False):
    # bool is a subclass of int, so use type(...) rather than isinstance(...).
    if type(value) is not int:
        errors.append(f"{label} must be a whole number, not a boolean or string.")
    elif positive and value <= 0:
        errors.append(f"{label} must be positive.")
    elif not positive and value < 0:
        errors.append(f"{label} cannot be negative.")


def _check_time(value, label, errors):
    if not isinstance(value, datetime) or value.utcoffset() is None:
        errors.append(f"{label} must be a timezone-aware datetime.")
        return False
    return True

def validate_data(donations, recipients, volunteers):
    """Return all schema/value errors. A valid but expired donation is not an error."""
    errors = []
    groups = (
        ("Donation", Donation, donations, "donation_id"),
        ("Recipient", Recipient, recipients, "recipient_id"),
        ("Volunteer", Volunteer, volunteers, "volunteer_id"),
    )
    for name, model, records, id_field in groups:
        seen = set()
        for record in records:
            if not isinstance(record, model):
                errors.append(f"Every {name.lower()} must be a {name} object.")
                continue
            value = getattr(record, id_field)
            if _check_text(value, f"{name} ID", errors):
                if value in seen:
                    errors.append(f"{name} IDs must be unique; duplicate ID {value!r}.")
                seen.add(value)

    for donation in donations:
        if not isinstance(donation, Donation):
            continue
        label = f"Donation {donation.donation_id}"
        _check_text(donation.donor_name, f"{label} donor name", errors)
        _check_text(donation.pickup_area, f"{label} pickup area", errors)
        if _check_text(donation.food_type, f"{label} food type", errors):
            if donation.food_type not in FOOD_TYPES:
                errors.append(f"{label} has an unsupported food type: {donation.food_type}.")
        _check_integer(donation.quantity, f"{label} quantity", errors, positive=True)
        ready_valid = _check_time(donation.ready_at, f"{label} ready time", errors)
        expiry_valid = _check_time(donation.expires_at, f"{label} expiry", errors)
        if ready_valid and expiry_valid and donation.ready_at > donation.expires_at:
            errors.append(f"{label} ready time cannot be after its expiry.")

    for recipient in recipients:
        if not isinstance(recipient, Recipient):
            continue
        label = f"Recipient {recipient.recipient_id}"
        _check_text(recipient.organization_name, f"{label} organization name", errors)
        _check_text(recipient.area, f"{label} area", errors)
        _check_integer(recipient.capacity, f"{label} capacity", errors)
        _check_time(recipient.closes_at, f"{label} closing time", errors)
        accepted = recipient.accepted_food_types
        if not isinstance(accepted, list) or not accepted:
            errors.append(f"{label} accepted food types must be a nonempty list.")
        else:
            seen_foods = set()
            for food in accepted:
                if not _check_text(food, f"{label} accepted food type", errors):
                    continue
                if food not in FOOD_TYPES:
                    errors.append(f"{label} has an unsupported accepted food type: {food}.")
                if food in seen_foods:
                    errors.append(f"{label} accepted food types cannot contain duplicates.")
                seen_foods.add(food)

    for volunteer in volunteers:
        if not isinstance(volunteer, Volunteer):
            continue
        label = f"Volunteer {volunteer.volunteer_id}"
        _check_text(volunteer.area, f"{label} area", errors)
        _check_integer(volunteer.vehicle_capacity, f"{label} vehicle capacity", errors)
        _check_integer(volunteer.max_pickups, f"{label} maximum pickups", errors)
        start_valid = _check_time(volunteer.available_from, f"{label} availability start", errors)
        end_valid = _check_time(volunteer.available_until, f"{label} availability end", errors)
        if start_valid and end_valid and volunteer.available_until < volunteer.available_from:
            errors.append(f"{label} availability end cannot be before its start.")

    return errors