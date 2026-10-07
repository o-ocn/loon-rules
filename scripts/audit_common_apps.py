#!/usr/bin/env python3
"""Audit public service-host samples against current dist; no phone/FINAL claims."""
import argparse
import csv
import json
import os
import sys

import simulate_hit

CONTRACT = os.path.join(simulate_hit.BASE_DIR, "config", "common_app_contract.json")


def audit(contract, rules):
    rows = []
    for service in contract["services"]:
        samples = {s["host"]: s["ruleset"] for s in service["samples"]}
        for host in sorted(set(samples) | set(service["reference_candidates"])):
            matches = simulate_hit.match_target(host, rules)
            actual = matches[0]["ruleset"] if matches else ""
            expected = samples.get(host, "")
            status = ("PASS" if actual == expected else "REGRESSION") if expected else "CANDIDATE"
            rows.append({"service": service["name"], "host": host,
                         "expected_ruleset": expected, "actual_ruleset": actual,
                         "rule": matches[0]["rule"] if matches else "", "status": status,
                         "limit": "Domain rules only; phone, DNS/IP fallback and private bindings unverified"})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", help="Write CSV to this path; otherwise write CSV to stdout")
    args = parser.parse_args()
    with open(CONTRACT, encoding="utf-8") as handle:
        contract = json.load(handle)
    rows = audit(contract, simulate_hit.load_dist_rules())
    handle = open(args.output, "w", encoding="utf-8-sig", newline="") if args.output else sys.stdout
    try:
        writer = csv.DictWriter(handle, fieldnames=["service", "host", "expected_ruleset", "actual_ruleset", "rule", "status", "limit"])
        writer.writeheader()
        writer.writerows(rows)
    finally:
        if args.output:
            handle.close()
    failures = sum(row["status"] == "REGRESSION" for row in rows)
    print(f"Services={len(contract['services'])}; reference hosts={len({r['host'] for r in rows})}; regressions={failures}; candidates are not auto-admitted.", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())