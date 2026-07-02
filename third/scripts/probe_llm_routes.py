"""Probe configured LLM routes without sending business data."""

from __future__ import annotations

import argparse
import json
from typing import Any

try:
    from ..agents.shared.config import load_config
    from ..agents.shared.llm_routes import probe_llm_routes
except ImportError:
    from agents.shared.config import load_config
    from agents.shared.llm_routes import probe_llm_routes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe third LLM provider routes.")
    parser.add_argument("--samples", type=int, default=None, help="Override THIRD_LLM_PROBE_SAMPLES for this run.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--refresh", action="store_true", help="Ignore cached probe results.")
    args = parser.parse_args(argv)

    payload = probe_llm_routes(load_config(), samples=args.samples, refresh=args.refresh)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, default=str, indent=2))
    else:
        _print_human(payload)
    return 0


def _print_human(payload: dict[str, Any]) -> None:
    print(f"route_mode: {payload.get('route_mode')}")
    print(f"fallback_providers: {', '.join(payload.get('fallback_providers') or []) or 'none'}")
    for item in payload.get("results") or []:
        print(
            "{provider}: status={status}, successes={successes}/{samples}, "
            "latency_ms={latency_ms}, error_type={error_type}, message={message}".format(
                provider=item.get("provider"),
                status=item.get("status"),
                successes=item.get("successes"),
                samples=item.get("samples"),
                latency_ms=item.get("latency_ms"),
                error_type=item.get("error_type") or "-",
                message=item.get("message") or "",
            )
        )


if __name__ == "__main__":
    raise SystemExit(main())
