# btc-cent-forecast-01

Forecast Bitcoin's US-dollar price 240 minutes ahead, from the 72 hours of
1-minute closes up to each checkpoint. Entry for the make.fun competition
`btc-cent-forecast-01`.

## Program

`main.py` (Python 3.13, standard library only, offline, deterministic) reads
every `<id>.in` in `$MAKEFUN_INPUT_DIR` (default `/input`) and writes
`<id>.out` to `$MAKEFUN_OUTPUT_DIR` (default `/output`):

```json
{"forecasts": [{"case": "p00", "price": 74757.97937}]}
```

## Method

The score is mean absolute error, so the best point forecast is the median
of the predictive distribution. The guess is the checkpoint close moved by a
shrunk estimate of the median 240-minute log drift, averaging two
independent drift estimators in log space:

1. **Median of non-overlapping 240-minute log returns** over the trailing
   2880 minutes (12 disjoint blocks). Disjoint blocks keep the samples
   near-independent, so the median is a far less noisy drift estimate than
   the median of overlapping windows.
2. **Half the log-price trend slope** over the trailing 720 minutes,
   extrapolated 240 minutes, shrunk by 0.5 — a 12-hour trend rarely
   survives a full 4-hour horizon intact.

The forecast move is capped at 5% as a guard against pathological fits.
No momentum term: walk-forward checks inside the practice window showed
extrapolating the last hour's move made the score worse. With too little
history either estimator returns 0 and the guess falls back to the
checkpoint close (persistence).

## Local practice grade

Scored on practice cases p00–p04 (each case's actual is the next case's
checkpoint close; p05's target is outside the kit):

| | mean abs error (cents) |
|---|---|
| this entry | **42,312.25** |
| house baseline (persistence) | 47,054.66 |

The entry beats the house baseline on the five locally scoreable practice
cases. The full six-case practice baseline per the kit is 44,521.58 cents.

## Run locally

```sh
mkdir -p out
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Runs all six practice cases in ~0.1 s; two runs produce byte-identical
output.
