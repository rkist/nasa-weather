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


def build_coordinate_segment_point(latitude: float, longitude: float) -> str:
    return f"{latitude:.6f},{longitude:.6f}"


def build_coordinate_segment_grid(
    lat_min: float,
    lon_min: float,
    lat_max: float,
    lon_max: float,
    lat_step: float,
    lon_step: float,
) -> str:
    # Meteomatics expects: lat_top,lon_left_lat_bottom,lon_right:step_lat,step_lon
    lat_top = max(lat_min, lat_max)
    lat_bottom = min(lat_min, lat_max)
    lon_left = min(lon_min, lon_max)
    lon_right = max(lon_min, lon_max)
    return (
        f"{lat_top:.6f},{lon_left:.6f}_{lat_bottom:.6f},{lon_right:.6f}:"
        f"{lat_step:.6f},{lon_step:.6f}"
    )


def build_url(
    base_url: str,
    time_spec: QueryTimeSpec,
    parameters: str,
    coordinate_segment: str,
    output_format: str,
) -> str:
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

    # Point mode (default) or grid mode (via --bbox and --grid-steps)
    parser.add_argument("--lat", type=float, default=DEFAULT_LATITUDE, help="Latitude (point mode)")
    parser.add_argument("--lon", type=float, default=DEFAULT_LONGITUDE, help="Longitude (point mode)")
    parser.add_argument(
        "--bbox",
        type=str,
        default=None,
        help="Bounding box for grid as lat_min,lon_min,lat_max,lon_max",
    )
    parser.add_argument(
        "--grid-steps",
        type=str,
        default=None,
        help="Grid step as dlat,dlon (e.g., 0.05,0.05)",
    )
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
        help="Hours ahead from now (UTC) to include (ignored if --start/--end provided)",
    )
    parser.add_argument(
        "--start",
        type=str,
        default=None,
        help="Start time ISO8601 (e.g., 2025-10-01T00:00:00Z)",
    )
    parser.add_argument(
        "--end",
        type=str,
        default=None,
        help="End time ISO8601 (e.g., 2025-10-02T00:00:00Z)",
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
        choices=["json", "csv", "netcdf"],
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

    if args.start and args.end:
        time_spec = QueryTimeSpec(start_iso=args.start, end_iso=args.end, interval=args.interval)
    else:
        time_spec = generate_time_spec(hours=args.hours, interval=args.interval)

    if args.bbox and args.grid_steps:
        try:
            lat_min, lon_min, lat_max, lon_max = [float(x) for x in args.bbox.split(",")]
            dlat, dlon = [float(x) for x in args.grid_steps.split(",")]
        except Exception as exc:
            raise SystemExit(f"Invalid --bbox or --grid-steps: {exc}")
        coordinate_segment = build_coordinate_segment_grid(lat_min, lon_min, lat_max, lon_max, dlat, dlon)
    else:
        coordinate_segment = build_coordinate_segment_point(args.lat, args.lon)

    url = build_url(
        base_url=args.base_url,
        time_spec=time_spec,
        parameters=args.parameters,
        coordinate_segment=coordinate_segment,
        output_format=args.output_format,
    )

    username, password = get_credentials(args.username, args.password)

    response = requests.get(url, auth=(username, password), timeout=30)
    if response.status_code != 200:
        print(f"HTTP {response.status_code}: {response.text[:500]}")
        raise SystemExit(1)

    timestamp_label = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    if args.output_format == "json":
        payload = response.json()
        output_path = (
            Path(args.out)
            if args.out
            else Path("data") / f"meteomatics_{timestamp_label}.json"
        )
        save_json(payload, output_path)
        print(f"Saved raw response to {output_path}")
        print()
        print(summarize_response(payload))
    else:
        # For csv/netcdf, save raw bytes/text without summary
        default_ext = "csv" if args.output_format == "csv" else "nc"
        output_path = (
            Path(args.out)
            if args.out
            else Path("data") / f"meteomatics_{timestamp_label}.{default_ext}"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        mode = "wb" if args.output_format in {"netcdf"} else "w"
        if mode == "wb":
            with output_path.open(mode) as f:
                f.write(response.content)
        else:
            with output_path.open(mode, encoding="utf-8") as f:
                f.write(response.text)
        print(f"Saved raw response to {output_path}")


if __name__ == "__main__":
    main()


