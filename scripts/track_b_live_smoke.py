"""Small post-deploy smoke check for Track B.

The full regression suite uses an isolated database and can safely create carts
and orders. A live production URL does not currently expose a safe test-data
setup path, so this script checks that the service is up and that the expected
contract paths are present in OpenAPI.
"""

from __future__ import annotations

import argparse
import sys

import httpx


CORE_PATHS = {
    "/health",
    "/customers",
    "/customers/{customer_id}",
    "/customers/{customer_id}/balance",
    "/customers/{customer_id}/ledger",
    "/checkout",
    "/orders/{order_id}/cancel",
}

KNOWN_NOT_DELIVERED_PATHS = {
    "/fulfillment",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("base_url", help="Base URL, for example http://127.0.0.1:8000")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    with httpx.Client(timeout=10.0) as client:
        health = client.get(f"{base_url}/health")
        health.raise_for_status()
        if health.json() != {"status": "ok"}:
            print("FAIL: /health did not return {'status': 'ok'}")
            return 1

        openapi = client.get(f"{base_url}/openapi.json")
        openapi.raise_for_status()
        paths = set(openapi.json().get("paths", {}).keys())

    missing = sorted(CORE_PATHS - paths)
    if missing:
        print("FAIL: missing required contract paths:")
        for path in missing:
            print(f"- {path}")
        return 1

    known_missing = sorted(KNOWN_NOT_DELIVERED_PATHS - paths)
    print("PASS: live service is reachable and core Track B contract paths exist.")
    if known_missing:
        print("Known gap: fulfillment is not delivered yet:")
        for path in known_missing:
            print(f"- {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
