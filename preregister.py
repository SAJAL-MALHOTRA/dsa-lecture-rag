#!/usr/bin/env python3
"""Pre-registration lock for the single test-split evaluation.

The test split only means something if you decide WHAT you will run before you see its numbers.
This tool freezes that decision and makes eval_harness.py refuse to run the test split unless
the run matches it.

  python preregister.py template > prereg.config.json     # edit: systems, settings, code files
  python preregister.py lock --config prereg.config.json --golden eval/golden.verified.json \
      --out prereg.lock.json
  python preregister.py verify --lock prereg.lock.json --golden eval/golden.verified.json
  python eval_harness.py --golden eval/golden.verified.json --split test --verified-only \
      --runs bm25=... hybrid=... --prereg prereg.lock.json ...        # the one test run
  python preregister.py status --lock prereg.lock.json

What the lock records: the golden file's SHA-256, the exact evaluation settings, the list of
systems you will report (their names must match --runs), a hash of each code file you list, and
a timestamp. eval_harness.py then refuses the test split if the golden file, the settings, the
system names or any listed code file differ from the lock, or if a test run was already
recorded (override with --allow-rerun, which stamps the report as a re-run).

This is a discipline aid, not a security control: the ledger is a plain file next to the lock
and nothing stops you deleting it. Its value is that skipping it has to be a deliberate act.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

EVAL_KEYS = ("split", "verified_only", "hit_def", "k", "primary_k", "dedup_overlap",
             "lead_tol", "seek_max_frac", "overlap_frac", "overlap_cap")

TEMPLATE = {
    "systems": {
        "bm25": "BM25 over 75s windows, 30s stride",
        "hybrid": "BM25 + dense (all-MiniLM-L6-v2) with reciprocal rank fusion",
        "hybrid_refine": "hybrid, then seek to best-matching segment inside the chunk (w=1, pad=3s)",
    },
    "eval": {"split": "test", "verified_only": True, "hit_def": "both", "k": [1, 3, 5, 10], "primary_k": 3,
             "dedup_overlap": 0.5, "lead_tol": 20.0, "seek_max_frac": 0.5, "overlap_frac": 0.5,
             "overlap_cap": 30.0},
    "code": ["eval_harness.py", "ytrag/retriever.py", "run_experiments.py"],
    "notes": "Write down anything you expect to happen and what would change your mind, before running test.",
}


class PreregError(Exception):
    def __init__(self, problems):
        super().__init__("\n".join(problems))
        self.problems = list(problems)


def sha_file(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_sha(obj) -> str:
    return sha_text(json.dumps(obj, sort_keys=True, separators=(",", ":")))


def _norm(key: str, value):
    if key == "k":
        return sorted(int(x) for x in value)
    if key in ("dedup_overlap", "lead_tol", "seek_max_frac", "overlap_frac", "overlap_cap"):
        return float(value)
    if key == "primary_k":
        return int(value)
    if key == "verified_only":
        return bool(value)
    return value


def make_lock(config: dict, golden_path, now: datetime | None = None) -> dict:
    problems = []
    systems = config.get("systems")
    if not isinstance(systems, dict) or not systems or not all(isinstance(v, str) and v.strip() for v in systems.values()):
        problems.append("'systems' must map each system name to a non-empty description")
    ev = config.get("eval")
    if not isinstance(ev, dict):
        problems.append("'eval' must be an object")
        ev = {}
    missing = [k for k in EVAL_KEYS if k not in ev]
    if missing:
        problems.append(f"'eval' is missing: {', '.join(missing)}")
    if ev.get("split") not in (None, "test"):
        problems.append("eval.split must be 'test' (a lock exists for the single test evaluation)")
    code = config.get("code", [])
    if not isinstance(code, list):
        problems.append("'code' must be a list of file paths")
        code = []
    code_hashes = {}
    for p in code:
        if not Path(p).is_file():
            problems.append(f"code file not found: {p}")
        else:
            code_hashes[str(p)] = sha_file(p)
    if not Path(golden_path).is_file():
        problems.append(f"golden file not found: {golden_path}")
    if problems:
        raise PreregError(problems)
    evn = {k: _norm(k, ev[k]) for k in EVAL_KEYS}
    lock = {"locked_utc": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds"),
            "golden": {"path": str(golden_path), "sha256": sha_file(golden_path)},
            "systems": dict(systems), "eval": evn, "code": code_hashes,
            "notes": str(config.get("notes", ""))}
    lock["config_sha256"] = canonical_sha({"systems": lock["systems"], "eval": lock["eval"],
                                           "code": lock["code"], "golden": lock["golden"]["sha256"]})
    return lock


def load_lock(path) -> dict:
    try:
        lock = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise PreregError([f"cannot read lock file {path}: {e}"]) from None
    need = ("golden", "systems", "eval", "code", "config_sha256", "locked_utc")
    absent = [k for k in need if k not in lock]
    if absent:
        raise PreregError([f"lock file is missing: {', '.join(absent)}"])
    expect = canonical_sha({"systems": lock["systems"], "eval": lock["eval"], "code": lock["code"],
                            "golden": lock["golden"]["sha256"]})
    if expect != lock["config_sha256"]:
        raise PreregError(["lock file was edited after it was written (config hash mismatch)"])
    return lock


def check_lock(lock: dict, golden_path, eval_cfg: dict, run_names) -> list:
    """Problems (empty list = this run matches the lock)."""
    problems = []
    if not Path(golden_path).is_file() or sha_file(golden_path) != lock["golden"]["sha256"]:
        problems.append("golden file differs from the locked version (labels changed after locking)")
    for key in EVAL_KEYS:
        want, got = lock["eval"][key], _norm(key, eval_cfg[key])
        if want != got:
            problems.append(f"setting {key}: locked {want!r}, this run uses {got!r}")
    locked, given = set(lock["systems"]), set(run_names)
    if locked - given:
        problems.append(f"locked systems missing from --runs: {', '.join(sorted(locked - given))}")
    if given - locked:
        problems.append(f"systems not in the lock: {', '.join(sorted(given - locked))}")
    for path, sha in lock["code"].items():
        if not Path(path).is_file():
            problems.append(f"locked code file is missing: {path}")
        elif sha_file(path) != sha:
            problems.append(f"code changed since lock: {path}")
    return problems


def ledger_path(lock_path) -> Path:
    return Path(str(lock_path) + ".ledger.jsonl")


def prior_runs(lock_path) -> list:
    p = ledger_path(lock_path)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def record_run(lock_path, kind: str, report_text: str, run_paths: dict, now: datetime | None = None) -> dict:
    """Append a test-run entry. kind is 'test_run' or 'test_rerun'."""
    entry = {"utc": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds"), "event": kind,
             "report_sha256": sha_text(report_text),
             "runs": {name: sha_file(path) for name, path in run_paths.items()}}
    with open(ledger_path(lock_path), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def banner(lock: dict, prior: list, kind: str) -> list:
    """Report lines describing the registration status of this test run."""
    short = lock["config_sha256"][:12]
    if kind == "test_rerun":
        return [f"**TEST RE-RUN, not pre-registered.** Lock `sha256:{short}` (locked {lock['locked_utc']}); "
                f"earlier test run recorded {prior[0]['utc']}. Report results of the FIRST run as the test result."]
    return [f"pre-registration: lock `sha256:{short}` locked {lock['locked_utc']}; golden file, settings, "
            "system names and code hashes all match; this is the first recorded test run"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("template")
    lk = sub.add_parser("lock")
    lk.add_argument("--config", required=True)
    lk.add_argument("--golden", required=True)
    lk.add_argument("--out", default="prereg.lock.json")
    lk.add_argument("--force", action="store_true")
    for name in ("verify", "status"):
        s = sub.add_parser(name)
        s.add_argument("--lock", required=True)
        s.add_argument("--golden")
    args = ap.parse_args(argv)

    if args.cmd == "template":
        print(json.dumps(TEMPLATE, indent=2))
        return 0
    try:
        if args.cmd == "lock":
            out = Path(args.out)
            if out.exists() and not args.force:
                print(f"{out} exists; refusing to overwrite a lock (use --force, and say why in your write-up).",
                      file=sys.stderr)
                return 2
            config = json.loads(Path(args.config).read_text(encoding="utf-8"))
            lock = make_lock(config, args.golden)
            out.write_text(json.dumps(lock, indent=2), encoding="utf-8")
            print(f"locked at {lock['locked_utc']}  config sha256:{lock['config_sha256'][:12]}")
            print(f"golden sha256:{lock['golden']['sha256'][:12]}, {len(lock['systems'])} systems, "
                  f"{len(lock['code'])} code files hashed")
            print("Now run each system, write the run files, and run eval_harness.py ONCE with --prereg.")
            return 0
        lock = load_lock(args.lock)
        prior = prior_runs(args.lock)
        if args.cmd == "status":
            print(f"lock sha256:{lock['config_sha256'][:12]} locked {lock['locked_utc']}")
            print("systems: " + ", ".join(lock["systems"]))
            print("settings: " + json.dumps(lock["eval"]))
            print(f"test runs recorded: {len(prior)}" + "".join(f"\n  {e['utc']}  {e['event']}" for e in prior))
            return 0
        golden = args.golden or lock["golden"]["path"]
        problems = []
        if not Path(golden).is_file() or sha_file(golden) != lock["golden"]["sha256"]:
            problems.append("golden file differs from the locked version")
        for path, sha in lock["code"].items():
            if not Path(path).is_file():
                problems.append(f"locked code file is missing: {path}")
            elif sha_file(path) != sha:
                problems.append(f"code changed since lock: {path}")
        if problems:
            print("Lock does NOT match the current files:", *problems, sep="\n  - ", file=sys.stderr)
            return 1
        print("OK: golden file and all locked code files match the lock.")
        return 0
    except PreregError as e:
        print("error:", *e.problems, sep="\n  - ", file=sys.stderr)
        return 2
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
