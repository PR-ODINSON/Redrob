"""
main.py — Full pipeline orchestration for the Redrob candidate ranking challenge.

Usage:
    python main.py                          # full run on candidates.jsonl
    python main.py --candidates <path>      # specify alternate candidates file
    python main.py --output <path>          # specify output CSV path
    python main.py --no-semantic            # skip semantic scoring (fast test)

Output: submission.csv matching the spec (100 rows, candidate_id/rank/score/reasoning)
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Redrob candidate ranker")
    parser.add_argument(
        "--candidates",
        default=None,
        help="Path to candidates file (.jsonl or .jsonl.gz). "
             "Auto-detects candidates.jsonl / candidates.jsonl.gz in cwd.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output CSV path (default: submission.csv)",
    )
    parser.add_argument(
        "--no-semantic",
        action="store_true",
        help="Skip semantic scoring (useful for rapid iteration; lower quality)",
    )
    parser.add_argument(
        "--prescreen-cutoff",
        type=int,
        default=None,
        help="Override PRESCREEN_CUTOFF from config.py",
    )
    return parser.parse_args()


def find_candidates_file(override: str | None) -> Path:
    """Auto-detect candidates file if not specified."""
    if override:
        p = Path(override)
        if not p.exists():
            raise FileNotFoundError(f"Specified candidates file not found: {p}")
        return p

    for name in ["candidates.jsonl.gz", "candidates.jsonl"]:
        p = Path(name)
        if p.exists():
            return p

    raise FileNotFoundError(
        "No candidates file found. Expected 'candidates.jsonl' or 'candidates.jsonl.gz' "
        "in the current directory."
    )


def _fmt_time(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{seconds/60:.1f}min"


def main() -> None:
    args = parse_args()

    # ── Apply config overrides ────────────────────────────────────────────
    import config
    if args.prescreen_cutoff:
        config.PRESCREEN_CUTOFF = args.prescreen_cutoff
        print(f"Override: PRESCREEN_CUTOFF = {config.PRESCREEN_CUTOFF}")

    output_path = args.output or config.OUTPUT_CSV

    wall_start = time.time()
    print("=" * 60)
    print("Redrob Candidate Ranking Pipeline")
    print("=" * 60)

    # ── Step 0: Load data ─────────────────────────────────────────────────
    t0 = time.time()
    candidates_path = find_candidates_file(args.candidates)
    print(f"\nStep 0: Loading data from {candidates_path} ...")

    from data_loader import (
        load_candidates,
        load_candidates_from_json,
        load_job_description,
        load_schema,
    )

    # Load candidates
    if candidates_path.suffix == ".json":
        candidates = load_candidates_from_json(candidates_path)
    else:
        candidates = load_candidates(candidates_path)

    load_time = time.time() - t0
    print(f"  Loaded {len(candidates):,} candidates in {load_time:.2f}s")

    # Load job description
    from config import JD_DOCX, SCHEMA_JSON
    jd_path = Path(JD_DOCX)
    if not jd_path.exists():
        raise FileNotFoundError(f"Job description not found: {jd_path}")

    jd_data = load_job_description(jd_path)
    print(f"  JD: '{jd_data['title']}' at {jd_data['company']}")
    print(f"  JD experience range: {jd_data['experience_range']}")

    schema_path = Path(SCHEMA_JSON)
    schema = load_schema(schema_path) if schema_path.exists() else {}

    # ── Step 1–N: Run ranking pipeline ───────────────────────────────────
    semantic_model = None
    if not args.no_semantic:
        print("\nLoading sentence-transformer model (offline cache)...")
        t_model = time.time()
        try:
            from semantic_scorer import load_model
            semantic_model = load_model()
            print(f"  Model loaded in {time.time() - t_model:.2f}s")
        except Exception as e:
            print(f"  WARNING: Could not load semantic model: {e}")
            print("  Falling back to structured-only scoring.")
            semantic_model = None

    from final_ranker import run_ranking_pipeline, write_submission_csv

    top_records, reasoning_map, stats = run_ranking_pipeline(
        candidates=candidates,
        jd_data=jd_data,
        semantic_model=semantic_model,
        verbose=True,
    )

    # ── Write output ──────────────────────────────────────────────────────
    out_path = write_submission_csv(top_records, reasoning_map, output_path)
    print(f"\nOutput written to: {out_path}")

    # ── Summary stats ─────────────────────────────────────────────────────
    wall_total = time.time() - wall_start
    print("\n" + "=" * 60)
    print("PIPELINE SUMMARY")
    print("=" * 60)
    print(f"  Total candidates processed : {stats['total_input']:,}")
    print(f"  Honeypots detected         : {stats['honeypots_found']:,} "
          f"({stats['honeypot_pct']:.2f}%)")
    print(f"  Honeypot rules fired       : {stats['honeypot_rules']}")
    print(f"  Clean candidates           : {stats['clean_candidates']:,}")
    print(f"  Pre-screen cutoff score    : {stats['prescreen_cutoff_score']:.4f}")
    print(f"  Pre-screen top score       : {stats['prescreen_top_score']:.4f}")
    print(f"  Honeypots in top-100 (pre) : {stats['honeypot_in_top100_preexclusion']} "
          f"({stats['honeypot_rate_top100']:.1%})")
    print(f"  Final #1 score             : {stats['final_top_score']:.4f}")
    print(f"  Final #100 score           : {stats['final_100th_score']:.4f}")
    print()
    print("  Stage timings:")
    for stage, t in stats["timings"].items():
        print(f"    {stage:<25} {_fmt_time(t)}")
    print(f"    {'(data load)':<25} {_fmt_time(load_time)}")
    print(f"  ─────────────────────────────────────────")
    print(f"    {'TOTAL WALL TIME':<25} {_fmt_time(wall_total)}")
    print()

    if wall_total > 300:
        print(f"[!] WARNING: Total time {_fmt_time(wall_total)} exceeds 5-minute budget.")
        print("    Consider reducing PRESCREEN_CUTOFF or EMBEDDING_BATCH_SIZE.")
    else:
        print(f"[OK] Within 5-minute compute budget ({_fmt_time(wall_total)} / 5min)")

    # ── Print first 10 rows ───────────────────────────────────────────────
    print("\nFirst 10 rows of submission:")
    print(f"{'Rank':<6} {'candidate_id':<14} {'Score':<8} Reasoning")
    print("-" * 80)
    for record in top_records[:10]:
        cid = record.candidate.get("candidate_id", "?")
        score_str = f"{record.final_score:.4f}"
        reasoning = reasoning_map.get(cid, "")
        truncated = reasoning[:60] + "..." if len(reasoning) > 60 else reasoning
        rank_idx = top_records.index(record) + 1
        print(f"{rank_idx:<6} {cid:<14} {score_str:<8} {truncated}")

    print(f"\nRun validate_submission.py to verify format:")
    print(f"  python validate_submission.py {out_path}")


if __name__ == "__main__":
    main()
