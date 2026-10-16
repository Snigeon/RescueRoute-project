import argparse
import sys
from pathlib import Path

from data_loader import load_data,parse_time
from matching import TRIP_TIME
from scheduler import run_fifo, run_greedy

DEFAULT_NOW = "2026-10-13T10:00:00+00:00"
DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data"

def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="rescueroute",
        description=(
            "RescueRoute matches food donations to recipients and volunteers, and "
            "compares a FIFO baseline with a greedy urgency-first strategy. "
            "Every assignment, rejection and deferral is explained."
        ),
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Folder containing donations.json, recipients.json, volunteers.json "
        f"(default: {DEFAULT_DATA_DIR}).",
    )
    parser.add_argument(
        "--strategy",
        choices=(STRATEGY_FIFO, STRATEGY_GREEDY, "compare"),
        default="compare",
        help="Run one strategy or compare both (default: compare).",
    )
    parser.add_argument(
        "--now",
        default=DEFAULT_NOW,
        help=f"Timezone-aware ISO 8601 simulation start (default: {DEFAULT_NOW}).",
    )
    parser.add_argument(
        "--urgent-minutes",
        type=int,
        default=DEFAULT_URGENT_MINUTES,
        help="A donation is urgent when it expires within this many minutes of the "
        f"simulation start (default: {DEFAULT_URGENT_MINUTES}).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Optional folder for results.json, comparison.md and console_report.txt.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Do not print the report (useful together with --output-dir).",
    )
    return parser.parse_args(argv)

def _parse_urgent_minutes(value: int) -> int:
    if value < 0:
        raise ValueError("--urgent-minutes cannot be negative.")
    return value

def main(argv=None) -> int:
    args = parse_args(argv)

    try:
        now = parse_time(args.now, "--now")
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    try:
        urgent_minutes = _parse_urgent_minutes(args.urgent_minutes)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    try:
        donations, recipients, volunteers = load_data(args.data_dir)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if args.strategy == STRATEGY_FIFO:
        results = {STRATEGY_FIFO: run_fifo(donations, recipients, volunteers, now)}
    elif args.strategy == STRATEGY_GREEDY:
        results = {STRATEGY_GREEDY: run_greedy(donations, recipients, volunteers, now)}
    else:
        results = run_both(donations, recipients, volunteers, now)

    metrics = {
        strategy: compute_metrics(result, donations, recipients, volunteers, now, urgent_minutes)
        for strategy, result in results.items()
    }

    console_text = render_console(results, metrics, str(args.data_dir), now, urgent_minutes)

    if not args.quiet:
        print(console_text)

    if args.output_dir:
        try:
            written = write_outputs(
                args.output_dir,
                results,
                metrics,
                str(args.data_dir),
                now,
                urgent_minutes,
                console_text,
            )
        except OSError as error:
            print(f"error: could not write output: {error}", file=sys.stderr)
            return 2
        print("Wrote:")
        for path in written:
            print(f"  {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())