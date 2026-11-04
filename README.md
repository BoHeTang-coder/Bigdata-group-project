# Why Is Your Flight Late? — US Flight Delay Analysis (2023–2025)

Analysis of **20.9 million US domestic flights** from the BTS "Reporting Carrier
On-Time Performance" dataset (2023–2025), built for the CityU **CS5488 Big Data
Algorithms and Tech** group project. The pipeline covers data acquisition and
cleaning, exploratory visualization, K-means airport clustering, association rule
mining of delay conditions, and a multiprocessing parallel-aggregation speedup
experiment.

## Key Findings

- **21.23%** of operated flights arrive ≥15 min late; the delay distribution is
  long-tailed (mean +7.4 min vs median −6 min) — a minority of flights drives
  most of the lateness.
- Delays peak in **summer (≈29%)** and around **19:00 departures**; Friday and
  Sunday are the worst weekdays. Low-cost carriers (Frontier 29.3%) and Florida
  airports (Fort Lauderdale 27.3%) rank worst.
- **74.3%** of delay minutes come from late-arriving aircraft + carrier
  operations; weather is directly blamed for only **5.9%** — delays propagate
  through the system rather than being caused by weather.
- K-means splits 101 high-volume airports into 3 groups; the worst group
  (DFW, ORD, CLT, MCO, LGA) has a 23.48% flight-weighted delay rate.
- Strongest association rule: **summer + evening (18:00–23:00) + Southwest**
  → 44.46% delayed, lift 2.15 (validated on held-out 2025 data).
- Parallel multiprocessing aggregation: **158.79 s → 48.29 s** at 8 workers
  (3.29× speedup); the gain flattens per Amdahl's law and disk I/O saturation.

## Repository Structure

```text
flight_delays/
├── data/                          # data docs & small aggregates (Parquet NOT included)
│   └── data/bts/
│       ├── README.md              # download & metric definitions
│       ├── manifest.json          # download history + SHA-256 checksums
│       ├── inventory.csv          # file inventory
│       ├── docs/                  # BTS form snapshot, field dictionary, schema check
│       ├── analysis/              # pre-aggregated CSVs (charts without big data)
│       └── clean/                 # data dictionary & cleaning summary
├── src/
│   ├── 01_data_processing/        # Member 1: download, clean, aggregate, 8 charts
│   ├── 02_data_analysis/          # Member 2: K-means clustering + association rules
│   └── 03_parallel_computing/     # Member 3: multiprocessing speedup experiment
└── report/                        # NOT in this repo (contains member names & IDs)
```

> The final report and slides are excluded from this repository because they
> contain group members' real names and student IDs. The full analysis and all
> numbers above are reproducible from the code in `src/`.

## Data

The dataset is **not** stored in this repo (3 Parquet files, ~570 MB total).
Two ways to get it:

1. **Reproduce the download** (recommended — automated, checksum-verified):
   run `src/01_data_processing/code/scripts/01_download.py`, which fetches the
   36 monthly ZIP files from the BTS TranStats portal with retry + SHA-256
   verification, then clean them with `11_clean.py` into yearly Parquet.
2. **Manually**: download "Reporting Carrier On-Time Performance" 2023–2025
   from <https://www.transtats.bts.gov/> and place `otp_2023.parquet`,
   `otp_2024.parquet`, `otp_2025.parquet` under `data/`.

Definitions used throughout: a flight is *delayed* if it arrived ≥15 min late
(`ArrDel15 = 1`, the standard DOT threshold); the delay rate divides delayed
flights by *operated* flights (cancelled/diverted excluded).

## Reproduce

```bash
pip install -r requirements.txt
```

### Module 1 — Data processing & visualization

```powershell
cd src/01_data_processing/code
python scripts/01_download.py     # download 36 monthly ZIPs (needs internet)
python scripts/02_extract.py      # unzip + verify row/col counts
python scripts/11_clean.py        # CSV -> yearly Parquet (109 + 5 derived fields)
python scripts/12_aggregate.py    # month/hour/carrier/airport/cause aggregates
python scripts/13_charts.py       # 8 figures at 300 dpi
python scripts/18_verify.py       # acceptance check (needs full data)
```

`data/data/bts/analysis/` already contains the aggregated CSVs, so
`scripts/13_charts.py` regenerates all 8 figures **without** downloading the
big data. See `src/01_data_processing/code/README.md` for the full 31-script
catalog and verification tooling.

### Module 2 — Clustering & association rules

```bash
python src/02_data_analysis/code/member2_analysis.py \
    --data-dir data \
    --output-dir src/02_data_analysis
```

Profiles 362 origin airports, K-means on the 101 high-volume ones (k chosen by
silhouette, k=3), and mines 1–3 item association rules (support ≥0.5%,
≥50,000 antecedent flights, lift ≥1.20) on 2023–2024, then validates on 2025.
Outputs: `figures/` and `files/` under the output dir. Requires the Parquet
files.

### Module 3 — Parallel computing experiment

```bash
cd data   # the script reads otp_20xx.parquet from the current directory
python ../src/03_parallel_computing/code/parallel_experiment.py
```

Splits 20.9M rows into chunks of 150,000 and processes them with a
multiprocessing `Pool.map` (a parallel for loop) at 1/2/4/8 workers, 3 repeats
each. Writes `speedup_results.csv` and `speedup_curve.png` to the current
directory (move them into `src/03_parallel_computing/files|figures/` if you
want them tracked). The delay rate is auto-checked against the 1-worker
baseline to prove parallelization does not change the answer.
