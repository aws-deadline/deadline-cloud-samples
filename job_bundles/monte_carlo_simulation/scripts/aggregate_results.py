# Aggregate per-position Monte Carlo pricing results into a portfolio summary.
#
# Part of the "Pricing Financial Derivatives" sample, adapted from:
#   http://mikejuniperhill.blogspot.com/2019/11/quantlib-python-heston-monte-carlo.html
#   https://ec2spotworkshops.com/monte-carlo-with-batch.html

"""Aggregate per-position Monte Carlo pricing results into a portfolio summary."""
import argparse
import glob
import json
import os


def main():
    parser = argparse.ArgumentParser(description="Aggregate Monte Carlo position results.")
    parser.add_argument("--results-dir", required=True, help="Directory containing result_*.json files")
    args = parser.parse_args()

    files = sorted(glob.glob(os.path.join(args.results_dir, "result_*.json")))
    if not files:
        print(f"No result_*.json files found in {args.results_dir}")
        return

    positions = []
    for f in files:
        with open(f) as fh:
            positions.append(json.load(fh))

    positions.sort(key=lambda p: p["position_index"])
    total_pv = sum(p["pv"] for p in positions)

    summary = {"total_pv": total_pv, "position_count": len(positions), "positions": positions}
    out_path = os.path.join(args.results_dir, "portfolio_summary.json")
    with open(out_path, "w") as fh:
        json.dump(summary, fh, indent=2)

    print(f"{'Pos':>4}  {'Strike':>10}  {'Barrier':>10}  {'Notional':>12}  {'PV':>14}")
    print("-" * 58)
    for p in positions:
        print(f"{p['position_index']:>4}  {p['strike']:>10.2f}  {p['barrier']:>10.2f}  {p['notional']:>12.2f}  {p['pv']:>14.4f}")
    print("-" * 58)
    print(f"{'Total':>4}  {'':>10}  {'':>10}  {'':>12}  {total_pv:>14.4f}")
    print(f"\n{len(positions)} positions aggregated -> {out_path}")


if __name__ == "__main__":
    main()
