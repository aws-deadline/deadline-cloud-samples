# Autocallable note pricing using QuantLib's Heston stochastic volatility model.
#
# Based on Mikael Katajamäki's QuantLib autocallable valuation example:
#   http://mikejuniperhill.blogspot.com/2019/11/quantlib-python-heston-monte-carlo.html
#
# Adapted from the "Pricing Financial Derivatives with AWS Batch" workshop:
#   https://ec2spotworkshops.com/monte-carlo-with-batch.html

import argparse
import json
import os
import numpy as np
import scipy.optimize as opt
import QuantLib as ql


VALUATION_DATE = ql.Date(20, 11, 2019)
CALENDAR = ql.TARGET()
DAY_COUNTER = ql.Actual360()
SPOT = 3550.0
RATE = 0.01
DIVIDEND = 0.0
COUPON_BARRIER = 0.8
PROTECTION_BARRIER = 0.6
COUPON = 0.05
HAS_MEMORY = True

EXPIRATION_DATES = [
    ql.Date(19, 6, 2020), ql.Date(18, 12, 2020), ql.Date(18, 6, 2021),
    ql.Date(17, 12, 2021), ql.Date(17, 6, 2022), ql.Date(16, 12, 2022),
    ql.Date(15, 12, 2023), ql.Date(20, 12, 2024), ql.Date(19, 12, 2025),
    ql.Date(18, 12, 2026),
]

STRIKES = [3075, 3200, 3350, 3550, 3775, 3950, 4050]

VOL_DATA = [
    [0.1753, 0.1631, 0.1493, 0.1320, 0.1160, 0.1080, 0.1052],
    [0.1683, 0.1583, 0.1470, 0.1334, 0.1212, 0.1145, 0.1117],
    [0.1673, 0.1597, 0.1517, 0.1428, 0.1346, 0.1290, 0.1262],
    [0.1659, 0.1601, 0.1541, 0.1474, 0.1417, 0.1381, 0.1363],
    [0.1678, 0.1634, 0.1588, 0.1537, 0.1493, 0.1467, 0.1455],
    [0.1678, 0.1644, 0.1609, 0.1572, 0.1541, 0.1522, 0.1513],
    [0.1694, 0.1666, 0.1638, 0.1608, 0.1584, 0.1569, 0.1562],
    [0.1701, 0.1680, 0.1660, 0.1640, 0.1623, 0.1614, 0.1610],
    [0.1715, 0.1698, 0.1682, 0.1667, 0.1654, 0.1648, 0.1645],
    [0.1724, 0.1710, 0.1697, 0.1684, 0.1675, 0.1671, 0.1669],
]

HESTON_BOUNDS = [(0.01, 1.0), (0.01, 10.0), (0.01, 1.0), (-1.0, 1.0), (0.01, 1.0)]


def calibrate_heston(curve_handle, dividend_handle):
    v0, kappa, theta, sigma, rho = 0.01, 0.01, 0.01, 0.01, 0.01
    process = ql.HestonProcess(
        curve_handle, dividend_handle,
        ql.QuoteHandle(ql.SimpleQuote(SPOT)),
        v0, kappa, theta, sigma, rho,
    )
    model = ql.HestonModel(process)
    engine = ql.AnalyticHestonEngine(model)

    helpers = []
    for i, expiration in enumerate(EXPIRATION_DATES):
        days = expiration - VALUATION_DATE
        period = ql.Period(days, ql.Days)
        for j, strike in enumerate(STRIKES):
            helper = ql.HestonModelHelper(
                period, CALENDAR, SPOT, strike,
                ql.QuoteHandle(ql.SimpleQuote(VOL_DATA[i][j])),
                curve_handle, dividend_handle,
            )
            helper.setPricingEngine(engine)
            helpers.append(helper)

    def cost(x):
        model.setParams(ql.Array(list(x)))
        return np.sqrt(np.sum(np.abs([h.calibrationError() for h in helpers])))

    opt.differential_evolution(cost, HESTON_BOUNDS)
    return process


def generate_paths(dates, process, n_paths):
    t = np.array([DAY_COUNTER.yearFraction(dates[0], d) for d in dates])
    n_grid = (t.shape[0] - 1) * 2
    seq = ql.GaussianRandomSequenceGenerator(
        ql.UniformRandomSequenceGenerator(n_grid, ql.UniformRandomGenerator())
    )
    gen = ql.GaussianMultiPathGenerator(process, t, seq, False)
    paths = np.zeros((n_paths, t.shape[0]))
    for i in range(n_paths):
        paths[i, :] = np.array(list(gen.next().value()[0]))
    return paths


def setup_model():
    """Calibrate the Heston model once. Returns (process, curve_handle, coupon_dates)."""
    ql.Settings.instance().evaluationDate = VALUATION_DATE

    curve_handle = ql.YieldTermStructureHandle(
        ql.FlatForward(VALUATION_DATE, RATE, DAY_COUNTER)
    )
    dividend_handle = ql.YieldTermStructureHandle(
        ql.FlatForward(VALUATION_DATE, DIVIDEND, DAY_COUNTER)
    )

    process = calibrate_heston(curve_handle, dividend_handle)

    start_date = VALUATION_DATE
    coupon_dates = np.array([
        CALENDAR.advance(start_date, ql.Period(y, ql.Years)) for y in range(1, 8)
    ])

    return process, curve_handle, coupon_dates


def price_autocallable(notional, strike, barrier, num_paths, process, curve_handle, coupon_dates):
    dates = np.hstack((np.array([VALUATION_DATE]), coupon_dates))
    paths = generate_paths(dates, process, num_paths)[:, 1:]

    expiration_date = coupon_dates[-1]
    auto_call_barrier = barrier
    has_memory = int(HAS_MEMORY)

    global_pv = []
    for path in paths:
        payoff_pv = 0.0
        unpaid = 0
        auto_called = False
        for date, index in zip(coupon_dates, path / strike):
            if auto_called:
                break
            payoff = 0.0
            if date == expiration_date:
                if index >= COUPON_BARRIER:
                    payoff = notional * (1 + COUPON * (1 + unpaid * has_memory))
                elif index >= PROTECTION_BARRIER:
                    payoff = notional
                else:
                    payoff = notional * min(1.0, (index * strike) / strike)
            else:
                if index >= auto_call_barrier:
                    payoff = notional * (1 + COUPON * (1 + unpaid * has_memory))
                    auto_called = True
                elif index >= COUPON_BARRIER:
                    payoff = notional * COUPON * (1 + unpaid * has_memory)
                    unpaid = 0
                else:
                    unpaid += 1
            if date > VALUATION_DATE:
                payoff_pv += payoff * curve_handle.discount(date)
        global_pv.append(payoff_pv)

    return float(np.mean(np.array(global_pv)))


def parse_contiguous_range(s):
    """Parse a contiguous range like '0-4' or '7-7' into (start, end) inclusive."""
    parts = s.split("-")
    return int(parts[0]), int(parts[1])


def main():
    parser = argparse.ArgumentParser(description="Price autocallable note positions")
    parser.add_argument("--portfolio", required=True, help="Path to portfolio.json")
    parser.add_argument("--results-dir", required=True, help="Directory to write result JSON")
    parser.add_argument("--position-range", required=True, help="Contiguous range e.g. '0-4' or '7-7'")
    parser.add_argument("--num-paths", type=int, default=10000, help="Number of MC paths")
    args = parser.parse_args()

    start_idx, end_idx = parse_contiguous_range(args.position_range)
    count = end_idx - start_idx + 1

    with open(args.portfolio) as f:
        portfolio = json.load(f)

    print(f"Portfolio: {len(portfolio['positions'])} positions total")
    print(f"Pricing positions {start_idx}-{end_idx} ({count} position{'s' if count > 1 else ''})")
    print(f"Monte Carlo paths: {args.num_paths}")
    print()

    print("Calibrating Heston stochastic volatility model...")
    process, curve_handle, coupon_dates = setup_model()
    print("Calibration complete.")
    print()

    os.makedirs(args.results_dir, exist_ok=True)
    print(f"{'Pos':>4}  {'Strike':>8}  {'Barrier':>8}  {'Notional':>12}  {'PV':>14}")
    print("-" * 52)
    for idx in range(start_idx, end_idx + 1):
        pos = portfolio["positions"][idx]
        notional, strike, barrier = pos["notional"], pos["strike"], pos["barrier"]

        pv = price_autocallable(notional, strike, barrier, args.num_paths, process, curve_handle, coupon_dates)

        result = {
            "position_index": idx,
            "strike": strike,
            "barrier": barrier,
            "notional": notional,
            "pv": pv,
        }
        out_path = os.path.join(args.results_dir, f"result_{idx}.json")
        with open(out_path, "w") as f:
            json.dump(result, f, indent=2)

        print(f"{idx:>4}  {strike:>8}  {barrier:>8.2f}  {notional:>12,.0f}  {pv:>14,.2f}")

    print("-" * 52)
    print(f"Wrote {count} result file{'s' if count > 1 else ''} to {args.results_dir}")


if __name__ == "__main__":
    main()
