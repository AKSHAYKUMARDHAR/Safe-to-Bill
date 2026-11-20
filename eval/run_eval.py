"""Score pipelines on a split and log the run.

    python -m eval.run_eval --split dev --pipelines rules,ml,llm,llm1
    python -m eval.run_eval --split holdout --pipelines rules,ml,llm,llm1 --release

The held-out split runs once (--release). A second run is refused unless --rescore is given,
which re-scores cached model answers and is labelled as such in the log.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from safe_to_bill.check import check  # noqa: E402
from safe_to_bill.llm_extractor import PROMPT_VERSION, TEMPERATURE, LLMExtractor  # noqa: E402
from safe_to_bill.mdm import LEVEL_NAMES  # noqa: E402
from safe_to_bill.ml_baseline import MLBaseline, load_jsonl  # noqa: E402
from safe_to_bill.verify import quote_in_note  # noqa: E402

SPLITS = {
    "dev": ROOT / "data" / "handwritten" / "dev.json",
    "holdout": ROOT / "data" / "handwritten" / "holdout.json",
    "holdout2": ROOT / "data" / "handwritten" / "holdout2.json",
    "gen_dev": ROOT / "data" / "generated" / "dev.jsonl",
}
HELD_OUT = ("holdout", "holdout2")
RUNS = ROOT / "eval" / "runs"
RESULTS = ROOT / "eval" / "results"


def load_split(split: str) -> list[dict]:
    path = SPLITS[split]
    return load_jsonl(path) if path.suffix == ".jsonl" else json.loads(path.read_text(encoding="utf-8"))


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centre - half), min(1.0, centre + half))


def score_rows(rows: list[dict]) -> dict:
    n = len(rows)
    bills = [r for r in rows if r["action"] == "BILL"]
    wrong = [r for r in bills if r["billed_code"] != r["label_code"]]
    correct = [r for r in rows if r["billed_code"] == r["label_code"]]
    over = [r for r in rows if int(r["billed_code"]) > int(r["label_code"])]
    under = [r for r in rows if int(r["billed_code"]) < int(r["label_code"])]
    lo, hi = wilson(len(wrong), len(bills))
    m = {
        "n": n,
        "level_accuracy": round(sum(r["pred_level"] == r["label_level"] for r in rows) / n, 3) if n else 0,
        "decision_accuracy": round(sum(r["action"] == r["label_decision"] for r in rows) / n, 3) if n else 0,
        "auto_bills": len(bills),
        "wrong_auto_bills": len(wrong),
        "wrong_auto_bill_rate_95ci": [round(lo, 3), round(hi, 3)],
        "correct_claims": len(correct),
        "correct_auto_billed": sum(r["action"] == "BILL" for r in correct),
        "automation": round(sum(r["action"] == "BILL" for r in correct) / len(correct), 3) if correct else 0,
        "overcoded": len(over),
        "overcoded_held": sum(r["action"] == "HOLD" for r in over),
        "undercoded": len(under),
        "undercoded_held": sum(r["action"] == "HOLD" for r in under),
        "not_confident": sum(r["reason"] == "not_confident" for r in rows),
        "errors": sum(bool(r["error"]) for r in rows),
        "quotes_not_in_note": sum(r["bad_quotes"] for r in rows),
        "wrong_auto_bill_ids": [r["id"] for r in wrong],
    }
    m["gate"] = {
        "wrong_auto_bills_zero": m["wrong_auto_bills"] == 0,
        "overcoded_held_all_but_one": m["overcoded_held"] >= m["overcoded"] - 1,
        "automation_at_least_50pct": m["automation"] >= 0.5,
        "quotes_all_in_note": m["quotes_not_in_note"] == 0,
    }
    m["gate_pass"] = all(m["gate"].values())
    return m


def run(split: str, pipelines: list[str], limit: int | None, release: bool, rescore: bool,
        cache_only: bool = False, verifier: str = "v3", tag: str = "dev") -> dict:
    recs = load_split(split)[: limit or None]
    llm = (LLMExtractor(cache_only=cache_only or rescore)
           if any(p.startswith("llm") for p in pipelines) else None)
    ml = MLBaseline.load() if "ml" in pipelines else None
    log: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "split": split, "n": len(recs), "release": release, "rescore": rescore,
        "git_commit": _git_commit(),
        "config": {"model": llm.model if llm else None, "prompt_version": PROMPT_VERSION,
                   "temperature": TEMPERATURE, "ml_threshold": ml.threshold if ml else None,
                   "verifier": verifier},
        "pipelines": {},
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    for pipeline in pipelines:
        rows = []
        for rec in recs:
            res = check(rec["note"], rec["patient_type"], rec["billed_code"], pipeline, llm=llm, ml=ml, verifier=verifier)
            d = res["decision"]
            rows.append({
                "id": rec["id"], "billed_code": rec["billed_code"], "label_code": rec["label"]["code"],
                "label_level": rec["label"]["level"], "label_decision": rec["decision"],
                "pred_level": LEVEL_NAMES.get(res["run_levels"][0]) if res["run_levels"] else None,
                "run_levels": "/".join(LEVEL_NAMES[x] for x in res["run_levels"]),
                "mdm": json.dumps(res.get("mdm", {})),
                "action": d["action"], "reason": d["reason"], "supported_code": d["supported_code"],
                "error": res.get("error", ""),
                "bad_quotes": sum(not quote_in_note(e["quote"], rec["note"]) for e in res["elements"]),
            })
            print(f"  {pipeline:5s} {rec['id']}: {d['action']} ({d['reason']})", flush=True)
        with (RESULTS / f"{split}_{tag}_{pipeline}.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        log["pipelines"][pipeline] = score_rows(rows)
    if llm:
        log["llm_calls"], log["llm_cache_hits"] = llm.calls, llm.cache_hits
    return log


def _git_commit() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip() or None
    except Exception:
        return None


def print_table(log: dict) -> None:
    print(f"\n{log['split']} (n={log['n']})  model={log['config']['model']}  prompt={log['config']['prompt_version']}")
    print("| pipeline | level acc | auto-bills | wrong auto-bills (95% CI) | automation | overcoded held | undercoded held | gate |")
    print("|---|---|---|---|---|---|---|---|")
    for name, m in log["pipelines"].items():
        ci = m["wrong_auto_bill_rate_95ci"]
        print(f"| {name} | {m['level_accuracy']:.0%} | {m['auto_bills']} | {m['wrong_auto_bills']} "
              f"({ci[0]:.0%}-{ci[1]:.0%}) | {m['correct_auto_billed']}/{m['correct_claims']} "
              f"| {m['overcoded_held']}/{m['overcoded']} | {m['undercoded_held']}/{m['undercoded']} "
              f"| {'PASS' if m['gate_pass'] else 'FAIL'} |")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=list(SPLITS), required=True)
    ap.add_argument("--pipelines", default="rules,ml")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--release", action="store_true", help="the one held-out release run")
    ap.add_argument("--rescore", action="store_true",
                    help="re-score cached answers after a release run (cache only, labelled post hoc)")
    ap.add_argument("--cache-only", action="store_true", help="never call the model; a cache miss is held")
    ap.add_argument("--verifier", choices=["v1", "v2", "v3"], default="v3",
                    help="v1 = release run 1; v2 = release run 2 (+ stitched quotes); v3 = current (+ copy-forward guard)")
    args = ap.parse_args()

    if args.split in HELD_OUT:
        done = sorted(RUNS.glob(f"*_{args.split}_release.json"))
        if not (args.release or args.rescore):
            sys.exit(f"The {args.split} split runs only as its release run (--release).")
        if args.release and done:
            sys.exit(f"A release run already exists ({done[-1].name}). Use --rescore to re-score cached answers.")
        if args.rescore and not done:
            sys.exit("Nothing to re-score: this split has no release run yet.")
    tag = "release" if args.release else ("rescore" if args.rescore else "dev")
    if args.rescore:
        tag = f"rescore-{args.verifier}"
    log = run(args.split, args.pipelines.split(","), args.limit, args.release, args.rescore,
              args.cache_only, args.verifier, tag)
    RUNS.mkdir(parents=True, exist_ok=True)
    stamp = log["timestamp"].replace(":", "").replace("-", "")[:15]
    out = RUNS / f"{stamp}_{args.split}_{tag}.json"
    out.write_text(json.dumps(log, indent=2), encoding="utf-8")
    print_table(log)
    print(f"\nlogged: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
