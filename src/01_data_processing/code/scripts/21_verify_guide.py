# -*- coding: utf-8 -*-
"""Check the specific claims made in the 讲解文档 (plain-language guide)."""
import os
import sys

import duckdb
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ANA = os.path.join(ROOT, "data", "bts", "analysis")
GLOB = os.path.join(ROOT, "data", "bts", "clean", "otp_*.parquet").replace("\\", "/")
con = duckdb.connect()
con.execute("PRAGMA threads=6")

print("=" * 74)
print("FIG2  month x weekday  — best / worst CELLS")
print("=" * 74)
mw = pd.read_csv(os.path.join(ANA, "month_weekday.csv"))
mw["r"] = mw.delay_rate * 100
MN = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep",
      "Oct", "Nov", "Dec"]
DW = ["", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
best = mw.loc[mw.r.idxmax()]
worst = mw.loc[mw.r.idxmin()]
print(f"  worst cell : {MN[int(best.Month)]} {DW[int(best.DayOfWeek)]} = {best.r:.1f}%")
print(f"  best  cell : {MN[int(worst.Month)]} {DW[int(worst.DayOfWeek)]} = {worst.r:.1f}%")
print("  Jul row    :", " ".join(
    f"{DW[int(r.DayOfWeek)]}={r.r:.0f}" for _, r in mw[mw.Month == 7].iterrows()))
print("  top-5 rows by peak cell:")
for m in mw.groupby("Month").r.max().sort_values(ascending=False).head(5).index:
    print(f"    {MN[int(m)]}  peak={mw[mw.Month==m].r.max():.1f}%")
print("  bottom-3 rows by best cell:")
for m in mw.groupby("Month").r.min().sort_values().head(3).index:
    print(f"    {MN[int(m)]}  best={mw[mw.Month==m].r.min():.1f}%")

print()
print("=" * 74)
print("WEEKDAY / HOURLY margins")
print("=" * 74)
dow = mw.groupby("DayOfWeek").apply(
    lambda g: (g.delay_rate * g.flights).sum() / g.flights.sum(),
    include_groups=False) * 100
print("  by weekday:", {DW[int(k)]: round(v, 1) for k, v in dow.items()})
h = pd.read_csv(os.path.join(ANA, "hourly.csv"))
hh = h.groupby("CRSDepHour").apply(
    lambda g: (g.delay_rate * g.flights).sum() / g.flights.sum(),
    include_groups=False) * 100
for hr in (5, 8, 12, 16, 19):
    print(f"  {hr:02d}:00 = {hh.loc[hr]:.1f}%")

print()
print("=" * 74)
print("TOP-10 BUSIEST AIRPORTS — is DFW really the worst?")
print("=" * 74)
ap = pd.read_csv(os.path.join(ANA, "airport.csv"))
top10 = ap.nlargest(10, "flights").copy()
top10["r"] = top10.delay_rate * 100
print(top10[["airport", "city", "flights", "r"]].to_string(index=False))
print(f"  worst among top-10: {top10.loc[top10.r.idxmax(), 'airport']} "
      f"{top10.r.max():.1f}%")

print()
print("=" * 74)
print("2024-07-19 single day")
print("=" * 74)
r = con.execute(f"""
    SELECT count(*), round(100.0*avg(Cancelled),1), round(100.0*avg(ArrDel15),1)
    FROM read_parquet('{GLOB}') WHERE FlightDate = DATE '2024-07-19'
""").fetchone()
print(f"  flights={r[0]:,}  cancel={r[1]}%  delay={r[2]}%")

print()
print("=" * 74)
print("CARRIER COUNTS / AIRPORT COUNTS / LONG TAIL")
print("=" * 74)
r = con.execute(f"""
    SELECT count(DISTINCT Reporting_Airline), count(DISTINCT Origin),
           count(*) FILTER (WHERE ArrDelay > 180)
    FROM read_parquet('{GLOB}')
""").fetchone()
print(f"  carriers={r[0]}  airports={r[1]}  flights arriving >180min late={r[2]:,}")

print()
print("=" * 74)
print("FIGURE-8 CAUSE PROFILE — verify the guide's claims")
print("=" * 74)
ac = pd.read_csv(os.path.join(ANA, "airport_cause.csv"))
piv = ac.pivot(index="airport", columns="cause", values="minutes").fillna(0)
sh = (piv.div(piv.sum(axis=1), axis=0) * 100)
for a in ("DFW", "PHX", "LAS", "LGA", "BOS", "ATL", "DEN"):
    print(f"  {a}: weather={sh.loc[a,'WeatherDelay']:.1f}% "
          f"NAS={sh.loc[a,'NASDelay']:.1f}% "
          f"carrier={sh.loc[a,'CarrierDelay']:.1f}% "
          f"lateAC={sh.loc[a,'LateAircraftDelay']:.1f}%")
print(f"  weather max : {sh.WeatherDelay.idxmax()} {sh.WeatherDelay.max():.1f}%")
print(f"  weather min : {sh.WeatherDelay.idxmin()} {sh.WeatherDelay.min():.1f}%")
print(f"  NAS max     : {sh.NASDelay.idxmax()} {sh.NASDelay.max():.1f}%")
print(f"  carrier max : {sh.CarrierDelay.idxmax()} {sh.CarrierDelay.max():.1f}%")
