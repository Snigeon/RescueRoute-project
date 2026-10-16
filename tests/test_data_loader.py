from __future__ import annotations
import itertools
import json
from pathlib import Path
import pytest
from data_loader import FOOD_TYPES, _load_records, load_data, load_json_file, parse_time, validate_data
from models import Donation
from conftest import at, donation, recipient, volunteer

VALID = {'donation_id': 'D-1', 'donor_name': 'Test Donor', 'food_type': 'produce', 'quantity': 10, 'expires_at': '2026-10-13T12:00:00+00:00', 'pickup_area': 'Central', 'ready_at': '2026-10-13T10:00:00+00:00'}
RECIPIENT = {'recipient_id': 'R-1', 'organization_name': 'Test Shelter', 'accepted_food_types': ['produce'], 'capacity': 20, 'area': 'Central', 'closes_at': '2026-10-13T13:00:00+00:00'}
VOLUNTEER = {'volunteer_id': 'V-1', 'vehicle_capacity': 20, 'area': 'Central', 'available_from': '2026-10-13T10:00:00+00:00', 'available_until': '2026-10-13T13:00:00+00:00', 'max_pickups': 2}
COUNTER = itertools.count()
RECORDS_DIR = Path(__file__).resolve().parent / '.tmp-records'


def write_folder(folder, donations=None, recipients=None, volunteers=None):
    folder.mkdir(parents=True, exist_ok=True)
    payloads = {'donations.json': [VALID] if donations is None else donations, 'recipients.json': [RECIPIENT] if recipients is None else recipients, 'volunteers.json': [VOLUNTEER] if volunteers is None else volunteers}
    for name, payload in payloads.items():
        (folder / name).write_text(json.dumps(payload), encoding='utf-8')
    return folder


def load_records(records):
    import shutil
    case = RECORDS_DIR / f'case-{next(COUNTER)}'
    shutil.rmtree(case, ignore_errors=True)
    case.mkdir(parents=True, exist_ok=True)
    path = case / 'donations.json'
    path.write_text(json.dumps(records), encoding='utf-8')
    try:
        return _load_records(path, Donation, ('expires_at', 'ready_at'))
    finally:
        shutil.rmtree(case, ignore_errors=True)


@pytest.mark.parametrize('value,expected', [('2026-10-13T12:00:00+02:00', '2026-10-13T10:00:00+00:00'), ('2026-10-13T12:00:00+00:00', '2026-10-13T12:00:00+00:00')])
def test_time_is_normalised_to_utc(value, expected):
    assert parse_time(value, 'test').isoformat() == expected


@pytest.mark.parametrize('value,message', [('2026-10-13T12:00:00', 'must include a timezone'), ('tomorrow-ish', 'valid ISO 8601'), (1234, 'valid ISO 8601')])
def test_bad_times_are_rejected(value, message):
    with pytest.raises(ValueError, match=message):
        parse_time(value, 'test')


@pytest.mark.parametrize('text,message', [('', None), ('   \n ', None), ('[{', 'Invalid json file'), ('{"donation_id": "D-1"}', 'must contain a JSON list')])
def test_json_file_shapes(tmp_path, text, message):
    path = tmp_path / 'input.json'
    path.write_text(text, encoding='utf-8')
    if message is None:
        assert load_json_file(path) == []
    else:
        with pytest.raises(ValueError, match=message):
            load_json_file(path)


def test_missing_file_is_reported(tmp_path):
    with pytest.raises(ValueError, match='does not exist'):
        load_json_file(tmp_path / 'absent.json')


def test_utf8_bom_is_tolerated(tmp_path):
    path = tmp_path / 'bom.json'
    path.write_text(json.dumps([VALID]), encoding='utf-8-sig')
    assert load_json_file(path) == [VALID]


def test_records_become_dataclasses():
    objects = load_records([VALID])
    assert isinstance(objects[0], Donation)
    assert objects[0].expires_at.isoformat() == '2026-10-13T12:00:00+00:00'


@pytest.mark.parametrize('records,message', [([{k: v for k, v in VALID.items() if k != 'quantity'}], 'missing fields: quantity'), ([dict(VALID, shelf_life_minutes=1)], 'unknown fields'), (['D-1'], 'must be a JSON object'), ([VALID, {k: v for k, v in VALID.items() if k != 'donor_name'}], 'record 2')])
def test_malformed_records_are_rejected(records, message):
    with pytest.raises(ValueError, match=message):
        load_records(records)


def test_load_data_reads_all_three_files(tmp_path):
    donations, recipients, volunteers = load_data(write_folder(tmp_path / 'data'))
    assert [d.donation_id for d in donations] == ['D-1']
    assert [r.recipient_id for r in recipients] == ['R-1']
    assert [v.volunteer_id for v in volunteers] == ['V-1']


def test_empty_files_load_as_empty_lists(tmp_path):
    donations, recipients, volunteers = load_data(write_folder(tmp_path / 'data', donations=[], recipients=[], volunteers=[]))
    assert donations == [] and recipients == [] and volunteers == []


def test_duplicate_donation_id_is_reported(tmp_path):
    with pytest.raises(ValueError) as info:
        load_data(write_folder(tmp_path / 'data', donations=[VALID, dict(VALID)]))
    assert "duplicate ID 'D-1'" in str(info.value)


def test_missing_file_in_folder_is_reported(tmp_path):
    folder = write_folder(tmp_path / 'data')
    (folder / 'volunteers.json').unlink()
    with pytest.raises(ValueError, match='does not exist'):
        load_data(folder)


def test_valid_records_produce_no_errors():
    assert validate_data([donation('D-1')], [recipient('R-1')], [volunteer('V-1')]) == []


def test_expired_donation_is_not_a_validation_error():
    expired = donation('D-EXPIRED', ready_at=at(8, 0), expires_at=at(9, 0))
    assert validate_data([expired], [recipient()], [volunteer()]) == []


@pytest.mark.parametrize('donations,recipients,volunteers,message', [
    ([donation('D-1', quantity=-5)], [], [], 'quantity must be positive'),
    ([donation('D-1', quantity=0)], [], [], 'quantity must be positive'),
    ([donation('D-1', quantity=True)], [], [], 'must be a whole number'),
    ([donation('D-1', food_type='sushi')], [], [], 'unsupported food type'),
    ([donation('D-1', ready_at=at(12, 30))], [], [], 'ready time cannot be after its expiry'),
    ([donation('D-1', donor_name='  ')], [], [], 'donor name must be a nonempty string'),
    ([donation(' D-1 ')], [], [], 'leading or trailing whitespace'),
    ([donation('D-1'), donation('D-1')], [], [], "duplicate ID 'D-1'"),
    ([], [recipient('R-1', capacity=-1)], [], 'capacity cannot be negative'),
    ([], [recipient('R-1', accepted_food_types=[])], [], 'accepted food types must be a nonempty list'),
    ([], [recipient('R-1', accepted_food_types=['produce', 'produce'])], [], 'cannot contain duplicates'),
    ([], [recipient('R-1', accepted_food_types=['sushi'])], [], 'unsupported accepted food type'),
    ([], [recipient('R-1'), recipient('R-1')], [], "duplicate ID 'R-1'"),
    ([], [], [volunteer('V-1', vehicle_capacity=-3)], 'vehicle capacity cannot be negative'),
    ([], [], [volunteer('V-1', max_pickups=-1)], 'maximum pickups cannot be negative'),
    ([], [], [volunteer('V-1', available_from=at(12, 0), available_until=at(10, 0))], 'availability end cannot be before its start'),
    ([], [], [volunteer('V-1'), volunteer('V-1')], "duplicate ID 'V-1'"),
])
def test_invalid_values_are_rejected(donations, recipients, volunteers, message):
    errors = validate_data(donations, recipients, volunteers)
    assert any(message in error for error in errors)


def test_every_problem_is_collected_at_once():
    errors = validate_data([donation('D-1', quantity=0, food_type='sushi')], [recipient('R-1', capacity=-1)], [volunteer('V-1', max_pickups=-2)])
    assert len(errors) >= 4


def test_wrong_entity_type_is_reported():
    assert any('must be a Donation object' in error for error in validate_data(['not a donation'], [], []))


def test_supported_food_types_are_a_set():
    assert isinstance(FOOD_TYPES, set) and len(FOOD_TYPES) == 5
