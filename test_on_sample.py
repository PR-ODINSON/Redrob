"""
test_on_sample.py — Fast iteration test using sample_candidates.json (50 candidates).

Run this after any code change to validate the full pipeline before running on 100k.
Produces sample_submission.csv (not the real submission file).

Usage:
    python test_on_sample.py
    python test_on_sample.py --no-semantic    # skip embedding for fastest iteration
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test pipeline on 50-candidate sample")
    parser.add_argument("--no-semantic", action="store_true",
                        help="Skip semantic scoring (fastest iteration)")
    parser.add_argument("--output", default="output/sample_submission.csv",
                        help="Output CSV path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print("=" * 60)
    print("TEST RUN — sample_candidates.json (50 candidates)")
    print("=" * 60)

    t_wall = time.time()

    # ── Load sample candidates ────────────────────────────────────────────
    from config import JD_DOCX, SAMPLE_CANDIDATES_JSON
    from data_loader import load_candidates_from_json, load_job_description

    sample_path = Path(SAMPLE_CANDIDATES_JSON)
    if not sample_path.exists():
        raise FileNotFoundError(f"Sample file not found: {sample_path}")

    print(f"\nLoading {sample_path} ...")
    candidates = load_candidates_from_json(sample_path)
    print(f"  Loaded {len(candidates)} candidates")

    jd_data = load_job_description(Path(JD_DOCX))
    print(f"  JD: '{jd_data['title']}' at {jd_data['company']}")

    # ── Load semantic model ───────────────────────────────────────────────
    semantic_model = None
    if not args.no_semantic:
        print("\nLoading sentence-transformer model...")
        try:
            from semantic_scorer import load_model
            semantic_model = load_model()
            print("  Model loaded OK")
        except Exception as e:
            print(f"  WARNING: {e}")
            print("  Continuing without semantic scoring.")

    # ── Run pipeline ──────────────────────────────────────────────────────
    # For the sample run, override PRESCREEN_CUTOFF to be ≤ number of candidates
    import config
    original_cutoff = config.PRESCREEN_CUTOFF
    config.PRESCREEN_CUTOFF = min(original_cutoff, len(candidates))
    config.REASONING_POOL = min(config.REASONING_POOL, len(candidates))
    config.TOP_N = min(config.TOP_N, len(candidates))

    print(f"\nPipeline settings for sample run:")
    print(f"  PRESCREEN_CUTOFF = {config.PRESCREEN_CUTOFF}")
    print(f"  TOP_N            = {config.TOP_N}")

    from final_ranker import run_ranking_pipeline, write_submission_csv

    top_records, reasoning_map, stats = run_ranking_pipeline(
        candidates=candidates,
        jd_data=jd_data,
        semantic_model=semantic_model,
        verbose=True,
    )

    # ── Write output ──────────────────────────────────────────────────────
    out_path = write_submission_csv(top_records, reasoning_map, args.output)
    print(f"\nSample output written to: {out_path}")

    # ── Restore config ────────────────────────────────────────────────────
    config.PRESCREEN_CUTOFF = original_cutoff
    config.REASONING_POOL = 150
    config.TOP_N = 100

    # ── Print all candidates with scores ─────────────────────────────────
    wall_total = time.time() - t_wall
    sep = "-" * 80
    print(f"\n{sep}")
    print(f"SAMPLE RUN RESULTS ({len(top_records)} candidates ranked)")
    print(sep)
    print(f"{'Rank':<5} {'CandID':<14} {'Final':>6} {'Struct':>6} {'Sem':>6} "
          f"{'Beh':>5} {'Gate':>5} {'HP':>3} Reasoning")
    print(sep)

    for rank, record in enumerate(top_records, 1):
        cid = record.candidate.get("candidate_id", "?")
        f = record.final_score
        s = record.structured.structured_score
        sem = record.semantic_score
        b = record.behavioral.behavioral_score
        g = record.gate.gate_score
        hp = "YES" if record.honeypot.is_honeypot else "-"
        reasoning = reasoning_map.get(cid, "")
        short_reason = reasoning[:55] + "..." if len(reasoning) > 55 else reasoning
        print(f"{rank:<5} {cid:<14} {f:>6.3f} {s:>6.3f} {sem:>6.3f} "
              f"{b:>5.3f} {g:>5.3f} {hp:>3} {short_reason}")

    # ── Honeypot details ──────────────────────────────────────────────────
    print(f"\nHoneypot summary:")
    print(f"  Total flagged : {stats['honeypots_found']} / {stats['total_input']}")
    print(f"  Rules fired   : {stats['honeypot_rules']}")

    # Show honeypot details
    from honeypot_filter import check_honeypot
    all_hp = [(c, check_honeypot(c)) for c in candidates if check_honeypot(c).is_honeypot]
    for c, hp_result in all_hp[:5]:
        print(f"  {c['candidate_id']}: {' | '.join(hp_result.reasons)}")

    # ── Validation ────────────────────────────────────────────────────────
    print(f"\nValidating output format ...")
    print(f"  NOTE: Row-count / rank-range errors are EXPECTED for sample runs")
    print(f"  (sample has {len(top_records)} candidates, spec requires exactly 100).")
    from validate_submission import validate_submission
    errors = validate_submission(str(out_path))
    real_errors = [e for e in errors
                   if "100 data rows" not in e and "missing:" not in e]
    if real_errors:
        print(f"  FORMAT ERRORS ({len(real_errors)}):")
        for e in real_errors:
            print(f"    - {e}")
    else:
        print("  [OK] No format errors (row-count/rank errors excluded as expected in sample mode)")

    print(f"\nTotal wall time: {wall_total:.2f}s")
    print("\nIf this looks correct, run the full pipeline:")
    print("  python main.py")


if __name__ == "__main__":
    main()
