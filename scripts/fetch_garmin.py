#!/usr/bin/env python3
"""Fetch cycling evidence through Garmin Connect's private read-only API.

This is an agent-neutral CLI.  It deliberately uses ``garminconnect`` only for
authentication, token refresh, and HTTP transport; the Garmin Connect endpoint
paths used by the analysis are declared and called explicitly in this file.

Garmin Connect's private endpoints are unofficial and may change without
notice.  Approved business integrations should use Garmin's official Activity
and Health APIs instead.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import zipfile
from datetime import date, datetime, timezone
from getpass import getpass
from io import BytesIO
from pathlib import Path
from typing import Any, Protocol

SCHEMA_VERSION = "1.0"
DEFAULT_TOKEN_STORE = "~/.garminconnect"

ACTIVITIES_ENDPOINT = "/activitylist-service/activities/search/activities"
ACTIVITY_ENDPOINT = "/activity-service/activity"
FIT_DOWNLOAD_ENDPOINT = "/download-service/files/activity"
HEART_RATE_ZONES_ENDPOINT = "/biometric-service/heartRateZones"
CYCLING_FTP_ENDPOINT = (
    "/biometric-service/biometric/latestFunctionalThresholdPower/CYCLING"
)
LACTATE_THRESHOLD_ENDPOINT = "/biometric-service/biometric/latestLactateThreshold"
MAX_METRICS_ENDPOINT = "/metrics-service/metrics/maxmet/daily"
TRAINING_STATUS_ENDPOINT = "/metrics-service/metrics/trainingstatus/aggregated"
USER_SETTINGS_ENDPOINT = "/userprofile-service/userprofile/user-settings"
RESTING_HR_ENDPOINT = "/userstats-service/wellness/daily"


class GarminTransport(Protocol):
    """Small surface required from an authenticated garminconnect client."""

    def connectapi(self, path: str, **kwargs: Any) -> Any: ...

    def download(self, path: str, **kwargs: Any) -> bytes: ...


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _activity_id(value: str) -> int:
    return _positive_int(value)


def _iso_date(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must use YYYY-MM-DD") from exc


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return {"byte_length": len(value)}
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return str(value)


def _find_first_key(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        if value.get(key) is not None:
            return value[key]
        for child in value.values():
            found = _find_first_key(child, key)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_first_key(child, key)
            if found is not None:
                return found
    return None


def envelope(kind: str, data: Any, *, is_cn: bool = False) -> dict[str, Any]:
    """Wrap backend output in the stable, agent-neutral exchange contract."""
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": kind,
        "source": {
            "backend": "garmin-connect-private-api",
            "official": False,
            "read_only": True,
            "region": "CN" if is_cn else "GLOBAL",
            "retrieved_at_utc": _utc_now(),
        },
        "data": _json_safe(data),
        "caveats": [
            "Unofficial Garmin Connect endpoints may change without notice.",
            "This backend and garmin_mcp are alternate transports for the same Garmin source, not independent physiological evidence.",
        ],
    }


class DirectGarminBackend:
    """Explicit, read-only calls over an authenticated Garmin transport."""

    def __init__(self, transport: GarminTransport):
        self.transport = transport

    def activities(
        self,
        *,
        start_date: str,
        end_date: str,
        activity_type: str = "cycling",
        page_size: int = 100,
        max_pages: int | None = None,
    ) -> dict[str, Any]:
        if start_date > end_date:
            raise ValueError("start_date must not be after end_date")
        page_size = min(page_size, 200)
        items: list[dict[str, Any]] = []
        page = 0
        while max_pages is None or page < max_pages:
            params = {
                "startDate": start_date,
                "endDate": end_date,
                "start": str(page * page_size),
                "limit": str(page_size),
            }
            if activity_type:
                params["activityType"] = activity_type
            batch = self.transport.connectapi(ACTIVITIES_ENDPOINT, params=params) or []
            if not isinstance(batch, list):
                raise TypeError("Garmin activities endpoint returned a non-list payload")
            items.extend(item for item in batch if isinstance(item, dict))
            page += 1
            if len(batch) < page_size:
                break
        complete = not (max_pages is not None and page >= max_pages and len(batch) == page_size)
        return {
            "date_range": {"start": start_date, "end": end_date},
            "activity_type": activity_type or None,
            "page_size": page_size,
            "pages_fetched": page,
            "complete": complete,
            "count": len(items),
            "activities": items,
        }

    def activity(self, activity_id: int) -> Any:
        return self.transport.connectapi(f"{ACTIVITY_ENDPOINT}/{activity_id}")

    def splits(self, activity_id: int) -> Any:
        return self.transport.connectapi(f"{ACTIVITY_ENDPOINT}/{activity_id}/splits")

    def hr_time_in_zones(self, activity_id: int) -> Any:
        return self.transport.connectapi(
            f"{ACTIVITY_ENDPOINT}/{activity_id}/hrTimeInZones"
        )

    def details(
        self, activity_id: int, *, max_chart_size: int = 2000, max_polyline_size: int = 0
    ) -> Any:
        return self.transport.connectapi(
            f"{ACTIVITY_ENDPOINT}/{activity_id}/details",
            params={
                "maxChartSize": str(max_chart_size),
                "maxPolylineSize": str(max_polyline_size),
            },
        )

    def fit_bytes(self, activity_id: int) -> bytes:
        payload = self.transport.download(f"{FIT_DOWNLOAD_ENDPOINT}/{activity_id}")
        if not payload:
            raise RuntimeError(f"no original activity file returned for {activity_id}")
        return bytes(payload)

    def derived_metrics(self, metric_date: str) -> dict[str, Any]:
        try:
            user_settings = self.transport.connectapi(USER_SETTINGS_ENDPOINT)
        except Exception as exc:  # noqa: BLE001 - preserve partial independent metrics.
            user_settings = {"error": type(exc).__name__, "message": str(exc)}
        requests = {
            "heart_rate_zones": (HEART_RATE_ZONES_ENDPOINT, {}),
            "cycling_ftp": (CYCLING_FTP_ENDPOINT, {}),
            "lactate_threshold_raw": (LACTATE_THRESHOLD_ENDPOINT, {}),
            "max_metrics": (
                f"{MAX_METRICS_ENDPOINT}/{metric_date}/{metric_date}",
                {},
            ),
            "training_status": (
                f"{TRAINING_STATUS_ENDPOINT}/{metric_date}",
                {},
            ),
        }
        result: dict[str, Any] = {
            "metric_date": metric_date,
            "user_settings": user_settings,
            "sport_warning": (
                "Garmin's latestLactateThreshold payload is commonly running-derived. "
                "Verify heartRateCycling or explicit sport provenance before using it for cycling."
            ),
        }
        for name, (path, kwargs) in requests.items():
            try:
                result[name] = self.transport.connectapi(path, **kwargs)
            except Exception as exc:  # noqa: BLE001 - preserve partial independent metrics.
                result[name] = {"error": type(exc).__name__, "message": str(exc)}
        display_name = _find_first_key(user_settings, "displayName")
        if display_name:
            try:
                result["resting_heart_rate"] = self.transport.connectapi(
                    f"{RESTING_HR_ENDPOINT}/{display_name}",
                    params={
                        "fromDate": metric_date,
                        "untilDate": metric_date,
                        "metricId": 60,
                    },
                )
            except Exception as exc:  # noqa: BLE001 - preserve partial independent metrics.
                result["resting_heart_rate"] = {
                    "error": type(exc).__name__,
                    "message": str(exc),
                }
        else:
            result["resting_heart_rate"] = {
                "error": "displayName unavailable; endpoint not called"
            }
        return result


def _payload_format(payload: bytes) -> str:
    if payload.startswith(b"PK\x03\x04"):
        return "zip"
    if payload.startswith(b"\x1f\x8b"):
        return "gzip"
    if len(payload) >= 12 and payload[8:12] == b".FIT":
        return "fit"
    return "unknown"


def extract_fit_bytes(payload: bytes) -> tuple[bytes, str]:
    """Return raw FIT bytes from Garmin's FIT, ZIP, or gzip response."""
    detected = _payload_format(payload)
    if detected == "zip":
        with zipfile.ZipFile(BytesIO(payload)) as archive:
            members = [name for name in archive.namelist() if name.lower().endswith(".fit")]
            if not members:
                raise RuntimeError("Garmin ZIP contained no .fit file")
            return archive.read(members[0]), detected
    if detected == "gzip":
        return gzip.decompress(payload), detected
    return payload, detected


def parse_fit(payload: bytes) -> dict[str, Any]:
    """Parse full record/lap/session messages without silently downsampling."""
    try:
        from fitparse import FitFile
    except ImportError as exc:
        raise RuntimeError(
            "fitparse is required; install scripts/requirements-garmin-direct.txt"
        ) from exc

    fit_bytes, container_format = extract_fit_bytes(payload)
    fit = FitFile(BytesIO(fit_bytes))

    def messages(name: str) -> list[dict[str, Any]]:
        return [_json_safe(message.get_values()) for message in fit.get_messages(name)]

    records = messages("record")
    return {
        "container_format": container_format,
        "fit_bytes": len(fit_bytes),
        "record_count": len(records),
        "records": records,
        "laps": messages("lap"),
        "sessions": messages("session"),
    }


def authenticate(token_store: Path, *, is_cn: bool) -> None:
    """Interactively create a local token store; never accept password flags."""
    Garmin = _import_garmin()
    email = input("Garmin email: ").strip()
    password = getpass("Garmin password (not stored by this tool): ")
    if not email or not password:
        raise RuntimeError("email and password are required for first authentication")
    client = Garmin(
        email=email,
        password=password,
        is_cn=is_cn,
        prompt_mfa=lambda: input("Garmin MFA code: ").strip(),
    )
    client.login()
    client.client.dump(str(token_store))
    _tighten_token_permissions(token_store)


def _tighten_token_permissions(token_store: Path) -> None:
    expanded = token_store.expanduser()
    if expanded.exists() and expanded.is_dir():
        os.chmod(expanded, 0o700)
        for child in expanded.iterdir():
            if child.is_file():
                os.chmod(child, 0o600)
    elif expanded.exists():
        os.chmod(expanded, 0o600)


def _import_garmin() -> Any:
    try:
        from garminconnect import Garmin
    except ImportError as exc:
        raise RuntimeError(
            "garminconnect is required; install scripts/requirements-garmin-direct.txt"
        ) from exc
    return Garmin


def authenticated_transport(token_store: Path, *, is_cn: bool) -> GarminTransport:
    Garmin = _import_garmin()
    client = Garmin(is_cn=is_cn)
    try:
        client.login(str(token_store.expanduser()))
    except Exception as exc:
        raise RuntimeError(
            f"Garmin token login failed ({type(exc).__name__}). Run the auth command first."
        ) from exc
    return client


def _write_json(payload: dict[str, Any], output: Path | None) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)


def _add_common_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output", type=Path, help="write JSON here instead of stdout")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--token-store", type=Path, default=Path(DEFAULT_TOKEN_STORE), help="local token directory or JSON file"
    )
    parser.add_argument("--cn", action="store_true", help="use connect.garmin.cn")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("auth", help="interactive one-time authentication")

    activities = subparsers.add_parser("activities", help="fetch a complete paged activity inventory")
    activities.add_argument("--start-date", required=True, type=_iso_date)
    activities.add_argument("--end-date", required=True, type=_iso_date)
    activities.add_argument("--activity-type", default="cycling")
    activities.add_argument("--page-size", type=_positive_int, default=100)
    activities.add_argument("--max-pages", type=_positive_int)
    _add_common_output(activities)

    for command, help_text in (
        ("activity", "fetch one activity summary"),
        ("splits", "fetch activity laps/splits"),
        ("hr-zones", "fetch activity time in HR zones"),
        ("details", "fetch Garmin chart/detail data"),
        ("fit-json", "download and parse full FIT records"),
        ("bundle", "fetch summary, splits, HR zones, and full FIT records"),
    ):
        child = subparsers.add_parser(command, help=help_text)
        child.add_argument("--activity-id", required=True, type=_activity_id)
        if command == "details":
            child.add_argument("--max-chart-size", type=_positive_int, default=2000)
            child.add_argument("--max-polyline-size", type=int, default=0)
        _add_common_output(child)

    fit_download = subparsers.add_parser("fit-download", help="save the original Garmin activity payload")
    fit_download.add_argument("--activity-id", required=True, type=_activity_id)
    fit_download.add_argument("--output", required=True, type=Path)

    derived = subparsers.add_parser("derived", help="fetch Garmin-derived/configured metrics")
    derived.add_argument(
        "--date", type=_iso_date, default=datetime.now(timezone.utc).date().isoformat()
    )
    _add_common_output(derived)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "auth":
        authenticate(args.token_store, is_cn=args.cn)
        _write_json(
            envelope(
                "authentication",
                {"status": "ok", "token_store": str(args.token_store.expanduser())},
                is_cn=args.cn,
            ),
            None,
        )
        return

    backend = DirectGarminBackend(
        authenticated_transport(args.token_store, is_cn=args.cn)
    )
    output = getattr(args, "output", None)

    if args.command == "activities":
        data = backend.activities(
            start_date=args.start_date,
            end_date=args.end_date,
            activity_type=args.activity_type,
            page_size=args.page_size,
            max_pages=args.max_pages,
        )
    elif args.command == "activity":
        data = backend.activity(args.activity_id)
    elif args.command == "splits":
        data = backend.splits(args.activity_id)
    elif args.command == "hr-zones":
        data = backend.hr_time_in_zones(args.activity_id)
    elif args.command == "details":
        data = backend.details(
            args.activity_id,
            max_chart_size=args.max_chart_size,
            max_polyline_size=args.max_polyline_size,
        )
    elif args.command == "fit-download":
        payload = backend.fit_bytes(args.activity_id)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(payload)
        _write_json(
            envelope(
                "fit-download",
                {
                    "activity_id": args.activity_id,
                    "path": str(output),
                    "bytes": len(payload),
                    "container_format": _payload_format(payload),
                },
                is_cn=args.cn,
            ),
            None,
        )
        return
    elif args.command == "fit-json":
        data = {"activity_id": args.activity_id, **parse_fit(backend.fit_bytes(args.activity_id))}
    elif args.command == "bundle":
        data = {
            "activity_id": args.activity_id,
            "activity": backend.activity(args.activity_id),
            "splits": backend.splits(args.activity_id),
            "hr_time_in_zones": backend.hr_time_in_zones(args.activity_id),
            "fit": parse_fit(backend.fit_bytes(args.activity_id)),
        }
    elif args.command == "derived":
        data = backend.derived_metrics(args.date)
    else:  # pragma: no cover - argparse enforces the command choices.
        raise RuntimeError(f"unsupported command: {args.command}")

    _write_json(envelope(args.command, data, is_cn=args.cn), output)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
