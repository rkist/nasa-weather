#!/usr/bin/env python3
"""
Fetch weather data from Meteomatics API and print a concise summary.

By default, retrieves 24 hours of hourly data for Berlin (Germany) for
parameters: 2 m temperature, hourly precipitation, and 10 m wind speed.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests


DEFAULT_PARAMETERS = "t_2m:C,precip_1h:mm,wind_speed_10m:ms"
DEFAULT_LATITUDE = 52.520551
DEFAULT_LONGITUDE = 13.461804
DEFAULT_INTERVAL = "PT1H"
DEFAULT_HOURS = 24
DEFAULT_OUTPUT_FORMAT = "json"
DEFAULT_BASE_URL = "https://api.meteomatics.com"


@dataclass
class QueryTimeSpec:
    start_iso: str
    end_iso: str
    interval: str

    def to_path_segment(self) -> str:
        return f"{self.start_iso}--{self.end_iso}:{self.interval}"


def generate_time_spec(hours: int, interval: str) -> QueryTimeSpec:
    now_utc = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    end_utc = now_utc + timedelta(hours=hours)
    start_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_iso = end_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    return QueryTimeSpec(start_iso=start_iso, end_iso=end_iso, interval=interval)


def build_url(
    base_url: str,
    time_spec: QueryTimeSpec,
    parameters: str,
    latitude: float,
    longitude: float,
    output_format: str,
) -> str:
    coordinate_segment = f"{latitude:.6f},{longitude:.6f}"
    return (
        f"{base_url.rstrip('/')}/"
        f"{time_spec.to_path_segment()}/"
        f"{parameters}/"
        f"{coordinate_segment}/"
        f"{output_format}"
    )


def get_credentials(
    username_arg: str | None,
    password_arg: str | None,
) -> Tuple[str, str]:
    username = username_arg or os.getenv("METEOMATICS_USERNAME")
    password = password_arg or os.getenv("METEOMATICS_PASSWORD")
    if not username or not password:
        raise SystemExit(
            "Missing credentials. Set METEOMATICS_USERNAME and METEOMATICS_PASSWORD "
            "environment variables or pass --username/--password."
        )
    return username, password


def save_json(content: Dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(content, f, ensure_ascii=False, indent=2)


def summarize_response(payload: Dict[str, Any]) -> str:
    lines: List[str] = []

    status = payload.get("status")
    version = payload.get("version")
    date_generated = payload.get("dateGenerated")
    lines.append(f"Status: {status} | API version: {version} | Generated: {date_generated}")

    data = payload.get("data", [])
    if not isinstance(data, list) or not data:
        lines.append("No 'data' array found in response.")
        return "\n".join(lines)

    for parameter_entry in data:
        parameter_name = parameter_entry.get("parameter", "<unknown>")
        coordinates = parameter_entry.get("coordinates", [])
        if not coordinates:
            lines.append(f"Parameter {parameter_name}: no coordinates returned")
            continue

        coord = coordinates[0]
        lat = coord.get("lat")
        lon = coord.get("lon")
        dates = coord.get("dates", [])

        values: List[float] = []
        timestamps: List[str] = []
        for d in dates:
            timestamps.append(d.get("date"))
            value = d.get("value")
            if isinstance(value, (int, float)):
                values.append(float(value))

        count = len(dates)
        ts_first = timestamps[0] if timestamps else "<none>"
        ts_last = timestamps[-1] if timestamps else "<none>"
        v_min = f"{min(values):.3f}" if values else "<na>"
        v_max = f"{max(values):.3f}" if values else "<na>"
        sample = (
            ", ".join(
                [
                    f"{timestamps[i]}={dates[i].get('value')}"
                    for i in range(min(3, count))
                ]
            )
            if count
            else "<no samples>"
        )

        lines.append(
            " | ".join(
                [
                    f"Parameter: {parameter_name}",
                    f"Lat/Lon: {lat},{lon}",
                    f"Count: {count}",
                    f"Range: {ts_first} → {ts_last}",
                    f"Min/Max: {v_min}/{v_max}",
                    f"Samples: {sample}",
                ]
            )
        )

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch and summarize Meteomatics weather data",
    )

    parser.add_argument("--lat", type=float, default=DEFAULT_LATITUDE, help="Latitude")
    parser.add_argument("--lon", type=float, default=DEFAULT_LONGITUDE, help="Longitude")
    parser.add_argument(
        "--parameters",
        type=str,
        default=DEFAULT_PARAMETERS,
        help="Comma-separated parameter list (e.g., t_2m:C,precip_1h:mm)",
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=DEFAULT_HOURS,
        help="Hours ahead from now (UTC) to include",
    )
    parser.add_argument(
        "--interval",
        type=str,
        default=DEFAULT_INTERVAL,
        help="ISO-8601 interval step (e.g., PT1H)",
    )
    parser.add_argument(
        "--format",
        dest="output_format",
        type=str,
        default=DEFAULT_OUTPUT_FORMAT,
        choices=["json"],
        help="Response format",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=DEFAULT_BASE_URL,
        help="Meteomatics API base URL",
    )
    parser.add_argument(
        "--username",
        type=str,
        default=None,
        help="API username (overrides METEOMATICS_USERNAME)",
    )
    parser.add_argument(
        "--password",
        type=str,
        default=None,
        help="API password (overrides METEOMATICS_PASSWORD)",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Path to save the raw JSON (defaults to data/meteomatics_<timestamp>.json)",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    time_spec = generate_time_spec(hours=args.hours, interval=args.interval)
    url = build_url(
        base_url=args.base_url,
        time_spec=time_spec,
        parameters=args.parameters,
        latitude=args.lat,
        longitude=args.lon,
        output_format=args.output_format,
    )

    username, password = get_credentials(args.username, args.password)

    response = requests.get(url, auth=(username, password), timeout=30)
    if response.status_code != 200:
        print(f"HTTP {response.status_code}: {response.text[:500]}")
        raise SystemExit(1)

    payload = response.json()

    timestamp_label = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = (
        Path(args.out)
        if args.out
        else Path("data") / f"meteomatics_{timestamp_label}.json"
    )
    save_json(payload, output_path)

    print(f"Saved raw response to {output_path}")
    print()
    print(summarize_response(payload))


if __name__ == "__main__":
    main()


