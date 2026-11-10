"""Post-deployment smoke test.

Run explicitly with:
    python scripts/smoke_test.py [BASE_URL]

This module is intentionally import-safe so pytest collection never performs HTTP calls.
"""
import sys
import urllib.request


def run(base_url="http://127.0.0.1:8080"):
    base_url = base_url.rstrip("/")
    for path in ("/health/live", "/api/trains?snap=0"):
        with urllib.request.urlopen(base_url + path, timeout=30) as response:
            if response.status != 200:
                raise RuntimeError(f"{path}: HTTP {response.status}")
    print("smoke test OK")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080")
