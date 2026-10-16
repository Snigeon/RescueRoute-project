import json
from datetime import timedelta
from pathlib import Path

from matching import format_minutes, format_time
from scheduler import STRATEGY_FIFO, STRATEGY_GREEDY

URGENT_MINUTES = 60

METRIC_LABELS = {
    "received": "Donations received",
    "assigned": "Donations assigned",
    "unassigned": "Donations unassigned",
    "quantity_rescued": "Food quantity rescued (simulated servings)",
    "quantity_at_risk": "Food quantity at risk (servings)",
    "urgent_rescue_rate": "Urgent rescue rate",
    "recipient_utilization": "Recipient capacity utilization",
    "volunteer_utilization": "Volunteer capacity utilization",
}

PERCENT_METRICS = {
    "urgent_rescue_rate", "recipient_utilization", "volunteer_utilization"
}

RULE = (
    "Greedy urgency-first rule: schedule the donation with the least available "
    "slack first, where available slack is the time between a donation's expiry "
    "and the earliest delivery any same-area volunteer could achieve. Ties break "
    "on the earlier expiry, then the larger quantity, then arrival order."
)

STRATEGIES = {
    STRATEGY_FIFO: "FIFO baseline",
    STRATEGY_GREEDY: "Greedy urgency-first",
}

def compute_metrics(results, donations, recipients, volunteers, now,
                    urgent_minutes=URGENT_MINUTES):

    quantity = {d.donation_id: d.quantity for d in donations}
    expiry = {d.donation_id: d.expires_at for d in donations}

    rescued = 0
    urgent_total = 0
    urgent_rescued = 0
    for result in results:
        amount = quantity.get(result.donation_id, 0)
        if (expiry.get(result.donation_id, now) - now) <= timedelta(minutes=urgent_minutes):
            urgent_total += amount
        if result.status == "assigned":
            rescued += amount
            if (expiry.get(result.donation_id, now) - now) <= timedelta(minutes=urgent_minutes):
                urgent_rescued += amount

    assigned = len([r for r in results if r.status == "assigned"])
    offered = sum(d.quantity for d in donations)
    capacity = sum(r.capacity for r in recipients)
    pickups = sum(v.max_pickups for v in volunteers)

    return {
        "received": len(results),
        "assigned": assigned,
        "unassigned": len(results) - assigned,
        "quantity_rescued": rescued,
        "quantity_at_risk": offered - rescued,
        "urgent_rescue_rate": urgent_rescued / urgent_total if urgent_total else 1.0,
        "recipient_utilization": rescued / capacity if capacity else 0.0,
        "volunteer_utilization": assigned / pickups if pickups else 0.0,
        "total_quantity": offered,
    }

def compare(fifo, greedy, donations):

    quantity = {d.donation_id: d.quantity for d in donations}

    fifo_status = {r.donation_id: r.status for r in fifo}
    greedy_status = {r.donation_id: r.status for r in greedy}

    only_greedy = [d for d in fifo_status
                   if fifo_status[d] != "assigned" and greedy_status.get(d) == "assigned"]
    only_fifo = [d for d in fifo_status
                 if fifo_status[d] == "assigned" and greedy_status.get(d) != "assigned"]

    fifo_rescued = sum(quantity.get(r.donation_id, 0)
                       for r in fifo if r.status == "assigned")
    greedy_rescued = sum(quantity.get(r.donation_id, 0)
                         for r in greedy if r.status == "assigned")

    if only_greedy:
        explanation = (
            f"Greedy rescued {', '.join(only_greedy)}, which FIFO had to reject "
            "because the capacity and pickups these needed were already spent on "
            "less urgent donations that arrived earlier."
        )
    elif only_fifo:
        explanation = (
            f"Greedy deferred {', '.join(only_fifo)}, which still had more time "
            "left, and spent the scarce capacity on food closer to expiring."
        )
    else:
        explanation = "Both strategies made the same decisions; no donation was contested."

    return {
        "quantity_rescued": greedy_rescued - fifo_rescued,
        "rescued_only_by_greedy": only_greedy,
        "rescued_only_by_fifo": only_fifo,
        "explanation": explanation,
    }

def _quantity_line(metrics):
    if not metrics["total_quantity"]:
        return "0 servings"
    share = metrics["quantity_rescued"] / metrics["total_quantity"] * 100
    return f"{metrics['quantity_rescued']} of {metrics['total_quantity']} servings ({share:.1f}%)"

def _metric_lines(metrics):
    lines = []
    for key, label in METRIC_LABELS.items():
        if key in PERCENT_METRICS:
            value = f"{metrics[key] * 100:.1f}%"
        elif key == "quantity_rescued":
            value = _quantity_line(metrics)
        else:
            value = f"{metrics[key]}"
        lines.append(f"  {label} . . . {value}")
    return lines

def _comparison_lines(comparison):
    lines = []
    for key, label, percent in (
        ("quantity_rescued", "Food quantity rescued", False),
        ("urgent_rescue_rate", "Urgent rescue rate", True),
    ):
        if key not in comparison:
            continue
        delta = comparison[key] * 100 if percent else comparison[key]
        unit = " points" if percent else " servings"
        lines.append(f"{label}: greedy {delta:+.1f}{unit} versus FIFO")
    lines.append(comparison["explanation"])
    return lines

def render_report(results, metrics, data_dir, now, urgent_minutes=URGENT_MINUTES,
                  comparison=None):
    lines = [
        "RescueRoute - food rescue matching and scheduling",
        f"Data directory: {data_dir}",
        f"Simulation start: {format_time(now)}",
        f"Urgent threshold: within {format_minutes(urgent_minutes)} of expiry",
        "Trip time: 15 simulated minutes per donor-to-recipient trip",
        "",
    ]
    for strategy, assignments in results.items():
        lines += [STRATEGIES.get(strategy, strategy), "-" * len(strategy)]
        for assignment in assignments:
            lines.append(f"  {assignment.donation_id}: {assignment.status.upper()}")
            lines.append(f"    why: {assignment.reason}")
        lines.append("")

    for strategy, strategy_metrics in metrics.items():
        lines += [f"Metrics for {STRATEGIES.get(strategy, strategy)}", "-" * 78]
        lines += _metric_lines(strategy_metrics)
        lines.append("")

    if comparison:
        lines += ["FIFO versus greedy", "-" * 78, f"  Rule: {RULE}"]
        lines += [f"  {line}" for line in _comparison_lines(comparison)]
        lines.append("")
    return "\n".join(lines)

def write_outputs(output_dir, results, metrics, data_dir, now,
                  urgent_minutes=URGENT_MINUTES, comparison=None):
    """Write results.json and comparison.md. Returns the paths written."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "data_dir": str(data_dir),
        "simulation_start": now.isoformat(),
        "urgent_minutes": urgent_minutes,
        "rule": RULE,
        "comparison": comparison,
        "strategies": {
            strategy: {
                "metrics": metrics[strategy],
                "assignments": [a.__dict__ for a in assignments],
            }
            for strategy, assignments in results.items()
        },
    }

    json_path = output_dir / "results.json"
    json_path.write_text(
        json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8"
    )

    lines = [
        "# RescueRoute FIFO versus greedy comparison",
        "",
        f"- Data directory: {data_dir}",
        f"- Simulation start: {format_time(now)}",
        f"- Urgent threshold: within {format_minutes(urgent_minutes)} of expiry",
        f"- Rule: {RULE}",
        "",
    ]
    for strategy, strategy_metrics in metrics.items():
        lines += [f"## {STRATEGIES.get(strategy, strategy)}", ""]
        lines += _metric_lines(strategy_metrics)
        lines.append("")
    if comparison:
        lines += ["## What changed", ""]
        lines += [f"- {line}" for line in _comparison_lines(comparison)]
        lines.append("")

    markdown_path = output_dir / "comparison.md"
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return [json_path, markdown_path]
