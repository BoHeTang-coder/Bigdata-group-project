# -*- coding: utf-8 -*-
"""
Render the 8 deliverable figures from data/bts/analysis/*.csv.

Output: figures/fig1..fig8 *.png  +  figures/CAPTIONS.md (one English sentence each)
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ANA = os.path.join(ROOT, "data", "bts", "analysis")
FIG = os.path.join(ROOT, "figures")
os.makedirs(FIG, exist_ok=True)

DPI = 300          # 交付要求：PNG 图片 300 dpi
plt.rcParams.update({
    "figure.dpi": 110, "savefig.dpi": DPI, "savefig.bbox": "tight",
    "font.size": 10, "axes.titlesize": 13, "axes.titleweight": "bold",
    "axes.labelsize": 10.5, "axes.grid": True, "grid.alpha": 0.25,
    "grid.linewidth": 0.7, "axes.spines.top": False, "axes.spines.right": False,
    "figure.facecolor": "white", "axes.axisbelow": True,
    "legend.frameon": False, "xtick.labelsize": 9.5, "ytick.labelsize": 9.5,
})

C = {"main": "#1f4e79", "accent": "#c0392b", "warm": "#e67e22",
     "cool": "#2980b9", "green": "#27ae60", "grey": "#7f8c8d"}
CAUSE_COLORS = {"LateAircraftDelay": "#c0392b", "CarrierDelay": "#e67e22",
                "NASDelay": "#2980b9", "WeatherDelay": "#27ae60",
                "SecurityDelay": "#95a5a6"}
CAUSE_LABEL = {"LateAircraftDelay": "Late aircraft", "CarrierDelay": "Carrier",
               "NASDelay": "National airspace (NAS)", "WeatherDelay": "Weather",
               "SecurityDelay": "Security"}

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

CARRIER_NAME = {
    "9E": "Endeavor", "AA": "American", "AS": "Alaska", "B6": "JetBlue",
    "DL": "Delta", "F9": "Frontier", "G4": "Allegiant", "HA": "Hawaiian",
    "MQ": "Envoy", "NK": "Spirit", "OH": "PSA", "OO": "SkyWest",
    "UA": "United", "WN": "Southwest", "YX": "Republic",
}

overview = json.load(open(os.path.join(ANA, "overview.json"), encoding="utf-8"))[0]
captions = []

# 交付要求「每张图三件套」的第三件：这张图在报告里支撑的论点（中文，给写作岗）。
ARGUMENTS = {
    "fig1_delay_distribution.png":
        "延误不是「普遍小幅晚点」，而是「多数准点 + 少数极端延误」的长尾结构。"
        "因此报告必须把「延误率（频次）」与「延误严重度（时长）」分开度量——"
        "只看平均值会严重误导（平均 +7.4 分钟，但中位数其实是提前 6 分钟）。",
    "fig2_month_weekday_heatmap.png":
        "延误呈**单峰**结构，不是双峰：夏季 6–7 月是绝对高峰（月均 29.0% / 26.7%，"
        "最糟格子 7 月周日 32.5%），秋季 9–11 月是低谷（16.3–16.9%）。"
        "周内呈「周五、周日高（23–24%），周二低（17.9%）」的节律。"
        "这说明延误是可预测的系统负荷函数，而非随机噪声，为「按日历提前调配运力」提供依据。",
    "fig5_airline_ranking.png":
        "航司间准点率差距接近 2 倍（14.9% vs 29.3%），且与商业模式高度相关："
        "低成本/超低成本承运人（F9、B6、NK）显著垫底。这支持「延误主要源于航司自身的"
        "运力调度与航班波结构，而非单纯天气」这一判断。",
    "fig6_worst_airports.png":
        "延误风险在地理上高度集中：佛罗里达机场系统性进入最差榜单"
        "（FLL/MIA/SFB/MCO/PBI），反映雷暴带与高密度休闲客流的叠加效应；"
        "同时 DFW 作为全美第三大枢纽同样高危，说明「枢纽规模大」并不等于「准点率高」。",
    "fig7_delay_causes.png":
        "天气只占延误分钟的 5.9%，而「前序航班晚到 + 航司自身」合计 74.3%，"
        "说明延误主因是系统内部传导而非外部冲击。但须强调：前序航班晚到中有相当部分是"
        "天气的间接后果，因此不应把「天气」与「系统」对立，而应刻画传导链条。"
        "三年构成稳定（各原因波动 ≤4 个百分点）进一步证明这是结构性问题，不是偶发。",
    "fig3_hourly_pattern.png":
        "延误在一天内近乎单调累积，从 05:00 的 8.9% 升至 19:00 的三年均值 30.5%"
        "（2025 年最高达 32.6%），且三年曲线形状几乎重合。这证明「延误是运力在日内"
        "被逐步耗尽的结果」，为「通过调整航班波结构提升准点率」提供直接依据。",
    "fig4_monthly_trend.png":
        "延误率是**季节性、可预测**的（夏季单峰 29.6%，秋季低谷 13.2%）；"
        "取消率是**事件驱动、不可预测**的（2024-07-19 CrowdStrike 单日取消 16.5%，"
        "为全期最惨）。两者生成机制不同，报告必须分开论述。"
        "另需注意：12 月整体只是年均水平（21.2%），但内部差异极大——"
        "12 月 25 日仅 11.4%（全年最好之一），而 12 月 26–29 日高达 30–33%，"
        "是典型的节后返程高峰效应。",
    "fig8_airport_cause_profile.png":
        "不同枢纽的延误成因结构显著不同：DFW 天气占比最高（8.1%），"
        "LGA/BOS 空管占比最高（25%），ATL 航司自身占比最高（45.1%）。"
        "这说明「一刀切」的延误治理政策无效，应按机场类型差异化施策。",
}


def save(fig, name, caption):
    p = os.path.join(FIG, name)
    fig.savefig(p)
    plt.close(fig)
    captions.append((name, caption, ARGUMENTS.get(name, "")))
    print(f"  {name:38s} ok")


def src_note(fig, extra=""):
    fig.text(0.005, -0.02,
             "Source: U.S. DOT/BTS On-Time Performance, 2023-2025 "
             f"({overview['total_flights']:,} flights). {extra}".strip(),
             fontsize=7.5, color=C["grey"], ha="left", va="top")


# ---------------- FIGURE 1
def chart_delay_distribution():
    d = pd.read_csv(os.path.join(ANA, "delay_hist.csv"))
    main = d[(d.bucket >= -60) & (d.bucket <= 180)]
    lo = int(d[d.bucket == -61].flights.sum())
    hi = int(d[d.bucket == 181].flights.sum())

    fig, ax = plt.subplots(figsize=(11, 6))
    ax.bar(main.bucket, main.flights, width=1.0, color=C["main"], linewidth=0)
    ax.set_yscale("log")
    ax.axvline(15, color=C["accent"], ls="--", lw=1.6)
    ax.text(17, ax.get_ylim()[1] * 0.45, "15-min\nDOT delay\nthreshold",
            color=C["accent"], fontsize=9, fontweight="bold", va="top")
    ax.axvline(0, color=C["grey"], lw=1.1)
    ax.set_title("Arrival delay distribution — most flights are early, a long tail is very late")
    ax.set_xlabel("Arrival delay (minutes, relative to schedule)")
    ax.set_ylabel("Number of flights (log scale)")
    ax.set_xlim(-62, 182)

    txt = (f"median  {overview['median_arr_delay']:+.0f} min\n"
           f"mean    {overview['mean_arr_delay']:+.1f} min\n"
           f"≥15 min late  {overview['delay_rate']*100:.1f}% of operated flights")
    ax.text(0.985, 0.95, txt, transform=ax.transAxes, ha="right", va="top",
            fontsize=9.5, family="monospace",
            bbox=dict(boxstyle="round,pad=0.5", fc="#f4f6f7", ec="#d5dbdb"))
    ax.text(-60, ax.get_ylim()[0] * 1.6, f"← earlier than −60 min\n({lo:,} flights)",
            fontsize=8, color=C["grey"], ha="left", va="bottom")
    ax.text(180, ax.get_ylim()[0] * 1.6, f"later than +180 min →\n({hi:,} flights)",
            fontsize=8, color=C["grey"], ha="right", va="bottom")
    src_note(fig)
    save(fig, "fig1_delay_distribution.png",
         "Arrival delays are strongly right-skewed: the median flight arrives 6 minutes "
         "early, yet 21.2% of flights arrive 15 or more minutes late, producing a long tail "
         "beyond three hours.")


# ---------------- FIGURE 2
def chart_month_weekday_heatmap():
    d = pd.read_csv(os.path.join(ANA, "month_weekday.csv"))
    piv = d.pivot(index="Month", columns="DayOfWeek", values="delay_rate") * 100
    piv = piv.reindex(index=range(1, 13), columns=range(1, 8))

    fig, ax = plt.subplots(figsize=(10.5, 7))
    im = ax.imshow(piv.values, cmap="YlOrRd", aspect="auto",
                   vmin=piv.values.min(), vmax=piv.values.max())
    ax.set_xticks(range(7), DOW)
    ax.set_yticks(range(12), MONTHS)
    ax.set_xlabel("Day of week")
    ax.set_ylabel("Month")
    ax.set_title("Share of flights arriving ≥15 min late, by month and day of week")
    ax.grid(False)
    mid = (piv.values.min() + piv.values.max()) / 2
    for i in range(12):
        for j in range(7):
            v = piv.values[i, j]
            ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=8.5,
                    color="white" if v > mid else "#333333",
                    fontweight="bold" if v == piv.values.max() else "normal")
    cb = fig.colorbar(im, ax=ax, pad=0.02)
    cb.set_label("% of flights ≥15 min late")
    src_note(fig)
    save(fig, "fig2_month_weekday_heatmap.png",
         "Delay risk is dominated by a single summer peak (the worst July cells reach 32-33% "
         "late against a 12% best cell in October), and across the whole period Friday and "
         "Sunday are the worst days to fly (23-24% late) while Tuesday is the most reliable "
         "(17.9%).")


# ---------------- FIGURE 5
def chart_airline_ranking():
    d = pd.read_csv(os.path.join(ANA, "airline.csv")).sort_values("delay_rate")
    d = d.assign(label=[f"{c}  {CARRIER_NAME.get(c, '')}" for c in d.carrier],
                 rate=d.delay_rate * 100)

    fig, ax = plt.subplots(figsize=(10.5, 7))
    colors = plt.cm.RdYlGn_r(np.linspace(0.12, 0.88, len(d)))
    bars = ax.barh(d.label, d.rate, color=colors, edgecolor="white", linewidth=0.8)
    ax.axvline(overview["delay_rate"] * 100, color=C["main"], ls="--", lw=1.5)
    ax.text(overview["delay_rate"] * 100 + 0.25, -0.9,
            f"all-carrier average {overview['delay_rate']*100:.1f}%",
            color=C["main"], fontsize=9, fontweight="bold", va="center")
    for b, r, n in zip(bars, d.rate, d.flights):
        ax.text(b.get_width() + 0.3, b.get_y() + b.get_height() / 2,
                f"{r:.1f}%   ({n/1000:,.0f}k flights)",
                va="center", fontsize=8.5, color="#333333")
    ax.set_xlim(0, d.rate.max() * 1.32)
    ax.set_xlabel("% of flights arriving ≥15 min late")
    ax.set_title("On-time performance ranking by reporting carrier, 2023-2025")
    ax.invert_yaxis()
    src_note(fig)
    save(fig, "fig5_airline_ranking.png",
         "Low-cost carriers Frontier, JetBlue and Spirit are the least punctual at 25-29% "
         "late arrivals, whereas Delta, Endeavor and Republic keep late arrivals below 19%.")


# ---------------- FIGURE 6
def chart_worst_airports():
    d = pd.read_csv(os.path.join(ANA, "airport.csv")).nlargest(15, "delay_rate")
    d = d.assign(rate=d.delay_rate * 100,
                 label=[f"{a}  {c.split(',')[0]}" for a, c in zip(d.airport, d.city)])

    fig, ax = plt.subplots(figsize=(10.5, 7))
    colors = plt.cm.YlOrRd(np.linspace(0.35, 0.95, len(d)))
    bars = ax.barh(d.label, d.rate, color=colors, edgecolor="white", linewidth=0.8)
    ax.axvline(overview["delay_rate"] * 100, color=C["main"], ls="--", lw=1.5)
    ax.text(overview["delay_rate"] * 100 + 0.2, -0.9,
            f"national average {overview['delay_rate']*100:.1f}%",
            color=C["main"], fontsize=9, fontweight="bold", va="center")
    for b, r, n in zip(bars, d.rate, d.flights):
        ax.text(b.get_width() + 0.25, b.get_y() + b.get_height() / 2,
                f"{r:.1f}%   ({n/1000:,.0f}k flights)",
                va="center", fontsize=8.5, color="#333333")
    ax.set_xlim(0, d.rate.max() * 1.30)
    ax.set_xlabel("% of flights arriving ≥15 min late")
    ax.set_title("The 15 least punctual US airports, 2023-2025 "
                 "(airports with ≥20,000 departures)")
    ax.invert_yaxis()
    src_note(fig)
    save(fig, "fig6_worst_airports.png",
         "Florida airports dominate the worst-punctuality list, with Fort Lauderdale, Miami "
         "and Orlando all above 25% late arrivals, while Dallas/Fort Worth is the worst "
         "major hub among the ten busiest airports.")


# ---------------- FIGURE 7
def chart_delay_causes():
    tot = pd.read_csv(os.path.join(ANA, "causes_total.csv")).sort_values("minutes")
    byy = pd.read_csv(os.path.join(ANA, "causes_by_year.csv"))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 5.6),
                                   gridspec_kw={"width_ratios": [1.05, 1]})
    lab = [CAUSE_LABEL[c] for c in tot.cause]
    col = [CAUSE_COLORS[c] for c in tot.cause]
    bars = ax1.barh(lab, tot.share * 100, color=col, edgecolor="white", linewidth=0.8)
    for b, s, m in zip(bars, tot.share * 100, tot.minutes):
        ax1.text(b.get_width() + 0.7, b.get_y() + b.get_height() / 2,
                 f"{s:.1f}%   ({m/1e6:,.0f}M min)", va="center", fontsize=9, color="#333333")
    ax1.set_xlim(0, tot.share.max() * 100 * 1.42)
    ax1.set_xlabel("Share of total delay minutes (%)")
    ax1.set_title("What causes the delay minutes")

    piv = byy.pivot(index="cause", columns="Year", values="share").reindex(tot.cause) * 100
    x = np.arange(len(piv))
    w = 0.26
    for k, yr in enumerate(piv.columns):
        ax2.bar(x + (k - 1) * w, piv[yr], w, label=str(yr),
                color=[C["cool"], C["warm"], C["green"]][k], edgecolor="white", linewidth=0.6)
    ax2.set_xticks(x, [CAUSE_LABEL[c] for c in piv.index], rotation=18, ha="right")
    ax2.set_ylabel("Share of delay minutes (%)")
    ax2.set_title("The mix is stable across the three years")
    ax2.legend(title="", ncols=3, fontsize=9)
    for i, c in enumerate(piv.index):
        ax2.text(i, max(piv.loc[c]) + 1.2, f"{piv.loc[c].max()-piv.loc[c].min():.1f} pp spread",
                 ha="center", fontsize=7.5, color=C["grey"])
    ax2.set_ylim(0, max(piv.max()) * 1.25)
    src_note(fig, "Cause fields cover only flights arriving ≥15 min late.")
    save(fig, "fig7_delay_causes.png",
         "Late-arriving aircraft (39.9%) and carrier-internal problems (34.4%) together "
         "account for three quarters of all delay minutes, whereas weather is directly "
         "blamed for only 5.9% — and this mix barely moves across 2023-2025.")


# ---------------- FIGURE 3
def chart_hourly_pattern():
    d = pd.read_csv(os.path.join(ANA, "hourly.csv"))
    vol = d.groupby("CRSDepHour").flights.sum()
    night_share = vol.loc[0:4].sum() / vol.sum() * 100

    fig, ax = plt.subplots(figsize=(11, 6))
    ymin = d.delay_rate.min() * 100
    ymax = d.delay_rate.max() * 100
    ax.set_ylim(ymin - 5.0, ymax + 4.0)

    ax.axvspan(-0.5, 4.5, color="#ecf0f1", zorder=0)
    ax.text(2.0, ymin - 4.2, f"red-eye window\n00:00-04:00, only {night_share:.1f}% of flights",
            ha="center", va="bottom", fontsize=8.2, color=C["grey"], linespacing=1.35)

    cols = {2023: C["cool"], 2024: C["warm"], 2025: C["green"]}
    for yr, g in d.groupby("Year"):
        g = g.sort_values("CRSDepHour")
        ax.plot(g.CRSDepHour, g.delay_rate * 100, marker="o", ms=4, lw=2.2,
                color=cols[yr], label=str(yr), zorder=3)

    mx = d.loc[d.delay_rate.idxmax()]
    ax.annotate(f"19:00 peak — {mx.delay_rate*100:.1f}% late ({int(mx.Year)})",
                xy=(mx.CRSDepHour, mx.delay_rate * 100),
                xytext=(int(mx.CRSDepHour) - 1.0, ymax + 1.6),
                fontsize=9.5, color=C["accent"], fontweight="bold", ha="right",
                arrowprops=dict(arrowstyle="->", color=C["accent"], lw=1.4,
                                shrinkA=2, shrinkB=3))

    ax.set_xticks(range(0, 24))
    ax.set_xlabel("Scheduled departure hour (local time)")
    ax.set_ylabel("% of flights arriving ≥15 min late")
    ax.set_title("Delay risk compounds through the operating day")
    ax.legend(title="Year", fontsize=9.5, loc="center left", bbox_to_anchor=(0.02, 0.78))
    ax.set_xlim(-0.5, 23.5)
    src_note(fig)
    # 3-year volume-weighted rate per hour, plus the single worst hour-year cell
    wt = (d.groupby("CRSDepHour")
            .apply(lambda g: (g.delay_rate * g.flights).sum() / g.flights.sum(),
                   include_groups=False) * 100)
    save(fig, "fig3_hourly_pattern.png",
         f"Punctuality deteriorates almost monotonically from {wt.loc[5]:.1f}% late for "
         f"05:00 departures to a three-year average of {wt.loc[19]:.1f}% at 19:00 "
         f"(peaking at {mx.delay_rate*100:.1f}% in {int(mx.Year)}), and the pattern is nearly "
         f"identical in all three years (the separate 00:00-04:00 red-eye group, only "
         f"{night_share:.1f}% of flights, runs at 17-27% late).")


# ---------------- FIGURE 4
def chart_monthly_trend():
    d = pd.read_csv(os.path.join(ANA, "monthly.csv"))
    d["t"] = pd.to_datetime(dict(year=d.Year, month=d.Month, day=1))
    fig, ax = plt.subplots(figsize=(12.5, 6))
    ax.bar(d.t, d.cancel_rate * 100, width=20, color="#d6dbdf",
           label="Cancellation rate (right axis)", zorder=1)
    ax.set_ylabel("Cancellation rate (%)", color=C["grey"])
    ax.tick_params(axis="y", labelcolor=C["grey"])
    ax.set_ylim(0, d.cancel_rate.max() * 100 * 3.4)

    ax2 = ax.twinx()
    ax2.plot(d.t, d.delay_rate * 100, marker="o", ms=4.5, lw=2.4,
             color=C["accent"], label="Late arrival rate (left axis)", zorder=3)
    ax2.set_ylabel("% of flights arriving ≥15 min late", color=C["accent"])
    ax2.tick_params(axis="y", labelcolor=C["accent"])
    ax2.grid(False)
    ax2.set_ylim(0, d.delay_rate.max() * 100 * 1.28)

    for _, r in d.iterrows():
        if r.delay_rate == d.delay_rate.max():
            ax2.annotate(f"Jul 2024 peak\n{r.delay_rate*100:.1f}% late",
                         xy=(r.t, r.delay_rate * 100), xytext=(-70, 12),
                         textcoords="offset points", fontsize=9, color=C["accent"],
                         arrowprops=dict(arrowstyle="->", color=C["accent"], lw=1.4))
        if r.cancel_rate == d.cancel_rate.max():
            ax.annotate(f"Jan 2024\n{r.cancel_rate*100:.1f}% cancelled",
                        xy=(r.t, r.cancel_rate * 100), xytext=(6, 34),
                        textcoords="offset points", fontsize=9, color="#566573",
                        arrowprops=dict(arrowstyle="->", color="#566573", lw=1.3))
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=9.5)
    ax.set_title("Monthly late-arrival and cancellation rates, January 2023 – December 2025")
    ax.set_xlabel("")
    src_note(fig)
    save(fig, "fig4_monthly_trend.png",
         "Delay rates follow a single sharp summer peak (29.6% in July 2024) and an autumn "
         "trough (13.2% in October 2024), while December's elevation comes almost entirely "
         "from the 26-29 December post-Christmas window; cancellation spikes are instead "
         "event-driven, the worst single day of the whole period being 19 July 2024 "
         "(16.5% of flights cancelled), the day of the CrowdStrike IT outage.")


# ---------------- FIGURE 8
def chart_airport_cause_profile():
    d = pd.read_csv(os.path.join(ANA, "airport_cause.csv"))
    vol = pd.read_csv(os.path.join(ANA, "airport.csv")).set_index("airport").flights
    order = (d.groupby("airport").minutes.sum().sort_values(ascending=False).index.tolist())
    piv = (d.pivot(index="airport", columns="cause", values="minutes")
             .reindex(order).fillna(0))
    share = piv.div(piv.sum(axis=1), axis=0) * 100
    share = share[["LateAircraftDelay", "CarrierDelay", "NASDelay",
                   "WeatherDelay", "SecurityDelay"]]

    fig, ax = plt.subplots(figsize=(11.5, 7))
    left = np.zeros(len(share))
    y = np.arange(len(share))
    for c in share.columns:
        v = share[c].values
        ax.barh(y, v, left=left, color=CAUSE_COLORS[c], label=CAUSE_LABEL[c],
                edgecolor="white", linewidth=0.7)
        for i, (l, w) in enumerate(zip(left, v)):
            if w >= 6:
                ax.text(l + w / 2, i, f"{w:.0f}", ha="center", va="center",
                        fontsize=8, color="white", fontweight="bold")
        left += v
    labels = [f"{a}  ({vol.get(a, 0)/1000:,.0f}k flights)" for a in share.index]
    ax.set_yticks(y, labels)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Share of the airport's total delay minutes (%)")
    ax.set_title("Delay-cause mix at the 12 busiest US airports: weather vs. system effects")
    ax.legend(ncols=5, loc="upper center", bbox_to_anchor=(0.5, -0.09), fontsize=9)
    ax.invert_yaxis()
    src_note(fig)
    save(fig, "fig8_airport_cause_profile.png",
         "Delay-cause mixes are broadly similar across the busiest hubs, but Dallas/Fort "
         "Worth carries the largest direct weather share (8.1% vs. 2.5-2.8% at Phoenix and "
         "Las Vegas), New York LaGuardia and Boston lean hardest on national-airspace "
         "restrictions (25%), and Atlanta's delays are the most carrier-driven (45.1%).")


def main():
    print(f"rendering figures at {DPI} dpi ...")
    chart_delay_distribution()
    chart_month_weekday_heatmap()
    chart_hourly_pattern()
    chart_monthly_trend()
    chart_airline_ranking()
    chart_worst_airports()
    chart_delay_causes()
    chart_airport_cause_profile()

    # ---- CAPTIONS.md : English caption only, ready to paste under each figure
    md = ["# Figure captions\n",
          f"BTS On-Time Performance, 2023-2025 ({overview['total_flights']:,} flights). "
          "One-sentence English caption per figure, ready for the report.\n"]
    for i, (name, cap, _arg) in enumerate(captions, 1):
        md.append(f"## Figure {i} — `{name}`\n\n{cap}\n")
    with open(os.path.join(FIG, "CAPTIONS.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    # ---- FIGURE_GUIDE.md : the three-piece set (PNG / caption / argument)
    from PIL import Image
    g = ["# 图表三件套 — 编号顺序、英文图注、支撑论点\n",
         "> 交付要求：每张图 = **PNG（300 dpi）+ 一句英文图注 + 这张图支撑的论点**。",
         "> **文件名编号 = Figure 编号 = 报告出现顺序**，三者完全一致，按 1→8 依次插入即可。",
         "> 顺序逻辑：先「是什么」(Fig 1)，再按三个研究问题推进 —— "
         "Q1 时间规律 (Fig 2–4) → Q2 机场/航司 (Fig 5–6) → Q3 原因归因 (Fig 7–8)。\n",
         "| Figure | 文件 | 图像规格 |", "|---|---|---|"]
    for i, (name, _c, _a) in enumerate(captions, 1):
        p = os.path.join(FIG, name)
        with Image.open(p) as im:
            w, h = im.size
            dpi = im.info.get("dpi", ("?", "?"))[0]
        kb = os.path.getsize(p) / 1024
        g.append(f"| **Figure {i}** | `{name}` | {w}×{h} px ｜ {dpi} dpi ｜ {kb:.0f} KB |")
    g.append("")
    for i, (name, cap, arg) in enumerate(captions, 1):
        g.append(f"---\n\n## Figure {i} — `{name}`\n")
        g.append(f"**English caption**\n\n> {cap}\n")
        g.append(f"**这张图支撑的论点**\n\n{arg}\n")
    with open(os.path.join(FIG, "FIGURE_GUIDE.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(g))

    print(f"\nwrote {len(captions)} figures @ {DPI}dpi")
    print(f"wrote {os.path.relpath(os.path.join(FIG, 'CAPTIONS.md'), ROOT)}")
    print(f"wrote {os.path.relpath(os.path.join(FIG, 'FIGURE_GUIDE.md'), ROOT)}")


if __name__ == "__main__":
    main()
