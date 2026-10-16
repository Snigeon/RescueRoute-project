from __future__ import annotations
import json
import pytest
from matching import TRIP_TIME, best_match, find_match, find_matches, format_minutes
from models import Assignment
from reports import METRIC_LABELS, URGENT_MINUTES, compare, compute_metrics, render_report, write_outputs
from scheduler import STRATEGY_FIFO, STRATEGY_GREEDY, greedy_priority, run_both, run_fifo, run_greedy
from conftest import at, donation, recipient, state_for, volunteer

QUANTITY = {'D-1': 10, 'D-2': 5, 'D-OLD': 10, 'D-NEW': 10, 'D-FIRST': 30, 'D-URGENT': 20, 'D-BIG': 40, 'D-LARGE': 30, 'D-TINY-URGENT': 24}


def metrics_for(results, donations, recipients, volunteers, urgent_minutes=URGENT_MINUTES):
    return compute_metrics(results, donations, recipients, volunteers, at(10, 0), urgent_minutes)


def status(results):
    return {r.donation_id: r.status for r in results}


def contested():
    donors = [donation('D-1', expires_at=at(13, 0)), donation('D-3', expires_at=at(12, 30)), donation('D-2', expires_at=at(11, 5)), donation('D-4', food_type='bakery', expires_at=at(11, 30))]
    recipients = [recipient('R-1', capacity=10, accepted_food_types=['prepared_meals']), recipient('R-2', capacity=10, accepted_food_types=['prepared_meals'], organization_name='Harbor Pantry'), recipient('R-3', capacity=10, accepted_food_types=['bakery']), recipient('R-4', capacity=30, accepted_food_types=['prepared_meals'], area='North')]
    volunteers = [volunteer('V-1', vehicle_capacity=12, max_pickups=2), volunteer('V-2', vehicle_capacity=10, max_pickups=1)]
    return donors, recipients, volunteers


def test_normal_compatible_match_is_assigned():
    results = run_fifo([donation('D-1')], [recipient('R-1', capacity=50)], [volunteer('V-1')], at(10, 0))
    result = results[0]
    assert result.status == 'assigned' and result.recipient_id == 'R-1' and result.volunteer_id == 'V-1'
    assert result.scheduled_at == at(10, 0) and result.delivery_at == at(10, 0) + TRIP_TIME


def test_rejection_states_the_expiry():
    results = run_fifo([donation('D-OLD', expires_at=at(9, 55), ready_at=at(9, 20))], [recipient()], [volunteer()], at(10, 0))
    assert results[0].status == 'unassigned'
    assert 'expired at 2026-10-13T09:55+00:00' in results[0].reason


def test_rejection_states_every_blocking_constraint():
    donors = [donation('D-BIG', quantity=40, food_type='produce')]
    recipients = [recipient('R-1', capacity=30, accepted_food_types=['produce']), recipient('R-2', accepted_food_types=['dairy'])]
    results = run_fifo(donors, recipients, [volunteer('V-1', vehicle_capacity=10)], at(10, 0))
    reason = results[0].reason
    assert 'does not accept produce' in reason
    assert 'has 30 servings of capacity left but the donation needs 40' in reason


def test_arrival_order_is_respected():
    results = run_fifo([donation('D-FIRST', quantity=30, expires_at=at(13, 0)), donation('D-URGENT', quantity=20, expires_at=at(10, 30))], [recipient('R-1', capacity=30)], [volunteer('V-1', max_pickups=1)], at(10, 0))
    assert status(results) == {'D-FIRST': 'assigned', 'D-URGENT': 'unassigned'}


def test_competing_donations_exhaust_the_last_capacity():
    results = run_fifo([donation('D-1', quantity=15), donation('D-2', quantity=15, expires_at=at(13, 0))], [recipient('R-1', capacity=20)], [volunteer()], at(10, 0))
    assert status(results) == {'D-1': 'assigned', 'D-2': 'unassigned'}
    assert 'capacity left but the donation needs 15' in results[1].reason


def test_volunteer_limits_are_enforced():
    donors = [donation('D-1', quantity=5, expires_at=at(12, 0)), donation('D-2', quantity=5, expires_at=at(12, 30))]
    pickups = run_fifo(donors, [recipient()], [volunteer('V-1', max_pickups=1)], at(10, 0))
    assert status(pickups) == {'D-1': 'assigned', 'D-2': 'unassigned'}
    assert 'already used 1 of 1 pickups' in pickups[1].reason
    vehicle = run_fifo([donation('D-BIG', quantity=40)], [recipient('R-1', capacity=100)], [volunteer('V-1', vehicle_capacity=20)], at(10, 0))
    assert 'can carry 20 servings but the donation is 40' in vehicle[0].reason


def test_no_recipients_or_volunteers_or_donations():
    assert 'has no recipients' in run_fifo([donation('D-1')], [], [volunteer()], at(10, 0))[0].reason
    assert 'has no volunteers' in run_fifo([donation('D-1')], [recipient()], [], at(10, 0))[0].reason
    assert run_fifo([], [recipient()], [volunteer()], at(10, 0)) == []


def test_cross_area_donation_is_rejected():
    donors = [donation('D-1', area='North', food_type='produce')]
    recipients = [recipient('R-1', area='Central'), recipient('R-2', area='North')]
    results = run_fifo(donors, recipients, [volunteer('V-1', area='Central')], at(10, 0))
    assert 'is in Central, not the North pickup area' in results[0].reason
    assert 'covers Central, not the North pickup area' in results[0].reason


@pytest.mark.parametrize('expires,quantity,expected', [([at(10, 50), at(13, 0)], [10, 10], 35.0), ([at(11, 0), at(11, 0)], [10, 40], 45.0), ([at(11, 0), at(11, 0)], [10, 10], None)])
def test_urgency_priority_orders_by_slack_then_quantity_then_arrival(expires, quantity, expected):
    donors = [donation(f'D-{i}', quantity=q, expires_at=e) for i, (e, q) in enumerate(zip(expires, quantity))]
    volunteers = [volunteer()]
    ordered = sorted(donors, key=lambda d: greedy_priority(d, state_for(volunteers), volunteers, at(10, 0)))
    if expected is None:
        assert [d.donation_id for d in ordered] == ['D-0', 'D-1']
    else:
        assert greedy_priority(ordered[0], state_for(volunteers), volunteers, at(10, 0))[0] == expected
        assert ordered[0].donation_id == 'D-1' if quantity[1] > quantity[0] else ordered[0].donation_id == 'D-0'


def test_a_busy_volunteer_shrinks_the_measured_slack():
    subject = donation('D-1', expires_at=at(11, 0))
    free = [volunteer(available_from=at(10, 0))]
    busy = [volunteer(available_from=at(10, 45))]
    assert greedy_priority(subject, state_for(free), free, at(10, 0))[0] == 45.0
    assert greedy_priority(subject, state_for(busy), busy, at(10, 0))[0] == 0.0


def test_a_volunteer_in_another_area_does_not_count():
    subject = donation('D-1', area='North', expires_at=at(11, 0))
    volunteers = [volunteer('V-1', area='Central')]
    assert greedy_priority(subject, state_for(volunteers), volunteers, at(10, 0))[0] == 45.0


def test_strategies_choose_different_recipients():
    donors = [donation('D-1')]
    recipients = [recipient('R-1', capacity=100), recipient('R-2', capacity=20)]
    volunteers = [volunteer()]
    assert run_fifo(donors, recipients, volunteers, at(10, 0))[0].recipient_id == 'R-1'
    assert run_greedy(donors, recipients, volunteers, at(10, 0))[0].recipient_id == 'R-2'


def test_best_match_prefers_the_earliest_delivery():
    recipients = [recipient('R-1', capacity=100)]
    volunteers = [volunteer('V-1'), volunteer('V-2', vehicle_capacity=15)]
    state = state_for(volunteers, recipients)
    state['next_available']['V-1'] = at(10, 30)
    matches, problems = find_matches(donation('D-1'), recipients, volunteers, state, at(10, 0))
    assert len(matches) == 2 and problems == []
    assert best_match(matches)[0]['volunteer_id'] == 'V-2'


def test_find_match_selects_by_strategy():
    recipients = [recipient('R-1', capacity=10), recipient('R-2', capacity=100)]
    volunteers = [volunteer()]
    state = state_for(volunteers, recipients)
    assert find_match(donation('D-1'), recipients, volunteers, state, at(10, 0), 'first')[0]['recipient_id'] == 'R-1'
    assert find_match(donation('D-1'), recipients, volunteers, state, at(10, 0), 'best')[0]['recipient_id'] == 'R-1'
    assert format_minutes(find_matches(donation('D-1', expires_at=at(11, 0)), recipients, volunteers, state, at(10, 0))[0][0]['slack_minutes']) == '45 minutes'


def test_metrics_report_both_quantities_and_windows():
    donors = [donation('D-1', quantity=10, expires_at=at(12, 0)), donation('D-2', quantity=5, expires_at=at(12, 30))]
    recipients = [recipient('R-1', capacity=10)]
    volunteers = [volunteer('V-1', max_pickups=3)]
    metrics = metrics_for(run_fifo(donors, recipients, volunteers, at(10, 0)), donors, recipients, volunteers)
    assert (metrics['received'], metrics['assigned'], metrics['unassigned']) == (2, 1, 1)
    assert (metrics['quantity_rescued'], metrics['quantity_at_risk']) == (10, 5)
    assert metrics['recipient_utilization'] == pytest.approx(1.0)
    assert metrics['volunteer_utilization'] == pytest.approx(1 / 3)
    assert set(METRIC_LABELS) <= set(metrics)


def test_urgent_window_and_expired_donations():
    donors = [donation('D-OLD', quantity=10, expires_at=at(9, 55), ready_at=at(9, 20)), donation('D-1', quantity=10, expires_at=at(10, 30)), donation('D-2', quantity=10, expires_at=at(12, 30))]
    recipients = [recipient('R-1', capacity=50)]
    volunteers = [volunteer('V-1', max_pickups=3)]
    results = run_fifo(donors, recipients, volunteers, at(10, 0))
    metrics = metrics_for(results, donors, recipients, volunteers)
    assert metrics['urgent_rescue_rate'] == pytest.approx(0.5)
    assert metrics_for(results, donors, recipients, volunteers, urgent_minutes=1)['urgent_rescue_rate'] == pytest.approx(0.0)
    assert metrics_for([], [], [], [])['urgent_rescue_rate'] == pytest.approx(1.0)


def test_no_volunteers_is_not_a_division_by_zero():
    donors = [donation('D-1')]
    metrics = metrics_for(run_fifo(donors, [recipient()], [], at(10, 0)), donors, [recipient()], [])
    assert metrics['volunteer_utilization'] == 0.0 and metrics['quantity_rescued'] == 0


def test_comparison_finds_the_contested_donation():
    donors, recipients, volunteers = contested()
    results = run_both(donors, recipients, volunteers, at(10, 0))
    differences = compare(results[STRATEGY_FIFO], results[STRATEGY_GREEDY], donors)
    assert differences['quantity_rescued'] == 0
    assert differences['rescued_only_by_greedy'] == ['D-2']
    assert differences['rescued_only_by_fifo'] == ['D-1']
    assert 'D-2' in differences['explanation']


def test_comparison_reports_a_volume_trade_off():
    donors = [donation('D-LARGE', quantity=30, expires_at=at(11, 30)), donation('D-TINY-URGENT', quantity=24, expires_at=at(10, 50))]
    recipients = [recipient('R-1', capacity=30)]
    volunteers = [volunteer('V-1', max_pickups=1)]
    results = run_both(donors, recipients, volunteers, at(10, 0))
    assert metrics_for(results[STRATEGY_FIFO], donors, recipients, volunteers)['quantity_rescued'] == 30
    assert metrics_for(results[STRATEGY_GREEDY], donors, recipients, volunteers)['quantity_rescued'] == 24
    differences = compare(results[STRATEGY_FIFO], results[STRATEGY_GREEDY], donors)
    assert differences['quantity_rescued'] == -6
    assert differences['rescued_only_by_greedy'] == ['D-TINY-URGENT']
    assert differences['rescued_only_by_fifo'] == ['D-LARGE']


def test_comparison_says_so_when_the_strategies_agree():
    donors = [donation('D-1')]
    results = run_both(donors, [recipient()], [volunteer()], at(10, 0))
    assert 'same decisions' in compare(results[STRATEGY_FIFO], results[STRATEGY_GREEDY], donors)['explanation']


def test_printed_slack_matches_the_slack_that_decided_the_order():
    donors = [donation('D-1', expires_at=at(12, 0)), donation('D-2', expires_at=at(11, 0)), donation('D-3', expires_at=at(11, 0))]
    reasons = {r.donation_id: r.reason for r in run_greedy(donors, [recipient()], [volunteer()], at(10, 0))}
    assert '45 minutes of available slack' in reasons['D-2']
    assert '45 minutes of available slack' in reasons['D-3']


def test_report_and_assignment_record_the_decision():
    donors, recipients, volunteers = contested()
    results = run_both(donors, recipients, volunteers, at(10, 0))
    metrics = {s: metrics_for(r, donors, recipients, volunteers) for s, r in results.items()}
    comparison = compare(results[STRATEGY_FIFO], results[STRATEGY_GREEDY], donors)
    text = render_report(results, metrics, 'data', at(10, 0), 60, comparison)
    assert 'FIFO versus greedy' in text and 'why:' in text
    assert all(label in text for label in METRIC_LABELS.values())
    assert 'FIFO versus greedy' not in render_report({STRATEGY_FIFO: results[STRATEGY_FIFO]}, {STRATEGY_FIFO: metrics[STRATEGY_FIFO]}, 'data', at(10, 0))
    assert isinstance(results[STRATEGY_FIFO][0], Assignment)


def test_write_outputs_creates_both_files(tmp_path):
    donors, recipients, volunteers = contested()
    results = run_both(donors, recipients, volunteers, at(10, 0))
    metrics = {s: metrics_for(r, donors, recipients, volunteers) for s, r in results.items()}
    comparison = compare(results[STRATEGY_FIFO], results[STRATEGY_GREEDY], donors)
    written = write_outputs(tmp_path, results, metrics, 'data', at(10, 0), 60, comparison)
    assert sorted(p.name for p in written) == ['comparison.md', 'results.json']
    payload = json.loads(next(p for p in written if p.name == 'results.json').read_text(encoding='utf-8'))
    assert payload['comparison']['explanation'] and payload['rule']
    assert payload['strategies'][STRATEGY_FIFO]['metrics']['quantity_rescued'] == 30
    assert payload['strategies'][STRATEGY_FIFO]['assignments'][0]['donation_id']
    assert 'What changed' in next(p for p in written if p.name == 'comparison.md').read_text(encoding='utf-8')
