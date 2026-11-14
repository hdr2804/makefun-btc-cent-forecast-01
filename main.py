#!/usr/bin/env python3
"""btc-cent-forecast-01: forecast BTC/USD 240 minutes ahead.

Reads one case file per run (MAKEFUN_INPUT_DIR, default /input):
  {"schema": "makefun/btc-cent-case/v1", "case": <id>, "at": ..., "horizon_minutes": 240,
   "markets": [{"id": "btc-usdc", "prices": [4320 one-minute closes ...]}]}
Writes one output per case (MAKEFUN_OUTPUT_DIR, default /output):
  {"forecasts": [{"case": <id>, "price": <guess>}]}

Method (stdlib only, offline, deterministic): the point forecast for a mean
absolute error score is the median of the predictive distribution, so the
guess is the checkpoint close moved by a shrunk estimate of the median
240-minute log drift. Two independent drift estimators are averaged in
log space:

  1. Median of the NON-overlapping 240-minute log returns over the trailing
     2880 minutes (12 disjoint blocks). Non-overlapping blocks keep the
     samples near-independent, so the median is a far less noisy drift
     estimate than the median of overlapping windows.
  2. Half the slope of log price against time over the trailing 720 minutes,
     extrapolated 240 minutes: a local linear-trend estimate, shrunk by 0.5
     because a 12-hour trend rarely survives a full 4-hour horizon intact.

The two moves are averaged with equal weight. No momentum term: on
walk-forward checks inside the practice window, extrapolating the last
hour's move made the score worse, so the forecast uses only drift
estimates that survived both the practice cases and the walk-forward set.
With too little history either estimator returns 0 and the guess falls
back to the checkpoint close (persistence).
"""

import json
import math
import os
import statistics

INPUT_DIR = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
OUTPUT_DIR = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")

HORIZON = 240            # minutes ahead to forecast
MEDIAN_WINDOW = 2880     # minutes of non-overlapping 240-min blocks
SLOPE_WINDOW = 720       # minutes for the log-price trend fit
SLOPE_SHRINK = 0.5       # shrink on the trend extrapolation
BLEND = 0.5              # weight of estimator 1 (median) vs estimator 2 (slope)

MIN_PRICE = 0.00001
MAX_PRICE = 9_999_999.99999
# A 4-hour move beyond 5% is outside anything the drift estimators are
# meant to extrapolate; cap the forecast move so a pathological fit (a
# flat or gapped series, a bad slope) can never throw the guess far away.
MAX_MOVE = 0.05


def _median(xs):
    return statistics.median(xs)


def _logret(a, b):
    """log(b / a), or None when either price is not a finite positive number."""
    if a <= 0 or b <= 0:
        return None
    return math.log(b / a)


def _median_drift(prices):
    """Median of the non-overlapping HORIZON-minute log returns."""
    n = len(prices)
    if n <= HORIZON:
        return 0.0
    rets = []
    t = n - 1
    earliest = max(0, n - MEDIAN_WINDOW)
    while t - HORIZON >= earliest:
        r = _logret(prices[t - HORIZON], prices[t])
        if r is not None:
            rets.append(r)
        t -= HORIZON
    return _median(rets) if rets else 0.0


def _slope_drift(prices):
    """Log-price trend slope over the trailing window, times HORIZON."""
    n = len(prices)
    if n < 2:
        return 0.0
    lo = max(0, n - SLOPE_WINDOW)
    xs = range(lo, n)
    ys = []
    for p in prices[lo:]:
        if p <= 0:
            return 0.0
        ys.append(math.log(p))
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        return 0.0
    return (num / den) * HORIZON


def _price5(x):
    return round(min(MAX_PRICE, max(MIN_PRICE, x)) * 1e5) / 1e5


def forecast(prices):
    if not prices:
        raise ValueError("empty price series")
    last = prices[-1]
    if not (isinstance(last, (int, float)) and math.isfinite(last)) or last <= 0:
        raise ValueError("last price is not a finite positive number")
    move = BLEND * _median_drift(prices) + (1.0 - BLEND) * SLOPE_SHRINK * _slope_drift(prices)
    move = max(-MAX_MOVE, min(MAX_MOVE, move))
    return _price5(last * math.exp(move))


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    inputs = sorted(f for f in os.listdir(INPUT_DIR) if f.endswith(".in"))
    for name in inputs:
        case_id = name[: -len(".in")]
        with open(os.path.join(INPUT_DIR, name), "r", encoding="utf-8") as fh:
            case = json.load(fh)
        markets = case.get("markets")
        if not isinstance(markets, list) or len(markets) != 1:
            raise ValueError(f"{name} does not hold exactly one market")
        price = forecast(markets[0]["prices"])
        out = {"forecasts": [{"case": case_id, "price": price}]}
        with open(os.path.join(OUTPUT_DIR, f"{case_id}.out"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps(out) + "\n")


if __name__ == "__main__":
    main()
