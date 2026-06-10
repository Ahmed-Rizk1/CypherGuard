#!/usr/bin/env python3
"""
SecureNet SOC — Health Check Script

Polls all service /health endpoints and reports status.
Designed for CI/CD smoke tests and operational monitoring.

Usage:
    python scripts/healthcheck.py                    # Check all services
    python scripts/healthcheck.py --json             # JSON output
    python scripts/healthcheck.py --exit-on-failure   # Exit 1 if any unhealthy
"""

import sys
import json
import argparse
import asyncio
from typing import NamedTuple

try:
    import httpx
except ImportError:
    print("ERROR: httpx not installed. Run: pip install httpx")
    sys.exit(1)


class ServiceCheck(NamedTuple):
    name: str
    url: str
    healthy: bool
    status_code: int
    detail: str
    latency_ms: float


SERVICES = [
    ("Gateway", "http://localhost:8000/health"),
    ("Extractor", "http://localhost:8001/health"),
    ("ML Engine", "http://localhost:8002/health"),
    ("LLM Analyzer", "http://localhost:8003/health"),
    ("Firewall", "http://localhost:8004/health"),
    ("Mobile Gateway", "http://localhost:8005/health"),
    ("Decision Engine", "http://localhost:8006/health"),
]


async def check_service(client: httpx.AsyncClient, name: str, url: str) -> ServiceCheck:
    """Check a single service health endpoint."""
    try:
        import time
        start = time.time()
        resp = await client.get(url, timeout=5.0)
        latency = (time.time() - start) * 1000

        data = resp.json()
        status = data.get("status", "unknown")
        healthy = resp.status_code == 200 and status in ("healthy", "ready")

        return ServiceCheck(
            name=name, url=url, healthy=healthy,
            status_code=resp.status_code,
            detail=status, latency_ms=round(latency, 1),
        )
    except httpx.ConnectError:
        return ServiceCheck(name=name, url=url, healthy=False, status_code=0,
                          detail="connection_refused", latency_ms=0)
    except Exception as e:
        return ServiceCheck(name=name, url=url, healthy=False, status_code=0,
                          detail=str(e)[:100], latency_ms=0)


async def run_checks() -> list[ServiceCheck]:
    """Check all services concurrently."""
    async with httpx.AsyncClient() as client:
        tasks = [check_service(client, name, url) for name, url in SERVICES]
        return await asyncio.gather(*tasks)


def print_results(results: list[ServiceCheck], as_json: bool = False):
    if as_json:
        output = [
            {"name": r.name, "healthy": r.healthy, "status_code": r.status_code,
             "detail": r.detail, "latency_ms": r.latency_ms}
            for r in results
        ]
        print(json.dumps(output, indent=2))
        return

    print("\n" + "=" * 60)
    print("  SecureNet SOC — Service Health Report")
    print("=" * 60)

    for r in results:
        icon = "✅" if r.healthy else "❌"
        latency = f"{r.latency_ms:.0f}ms" if r.latency_ms > 0 else "N/A"
        print(f"  {icon}  {r.name:<20}  {r.detail:<25}  {latency}")

    healthy = sum(1 for r in results if r.healthy)
    total = len(results)
    print("-" * 60)
    print(f"  Summary: {healthy}/{total} services healthy")
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="SecureNet health checker")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--exit-on-failure", action="store_true", help="Exit 1 if any unhealthy")
    args = parser.parse_args()

    results = asyncio.run(run_checks())
    print_results(results, as_json=args.json)

    if args.exit_on_failure:
        all_healthy = all(r.healthy for r in results)
        sys.exit(0 if all_healthy else 1)


if __name__ == "__main__":
    main()
