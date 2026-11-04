# -*- coding: utf-8 -*-
"""
Build the data dictionary for the cleaned dataset.

Combines three sources so nothing is invented:
  1. column names + physical types  <- the Parquet files themselves
  2. null rate                      <- computed over all 20,928,579 rows
  3. official English definitions   <- readme.html shipped inside the BTS archive
  4. what we changed and how        <- the type maps in 11_clean.py (single source
                                       of truth, imported rather than copied)

Outputs:
  data/bts/clean/DATA_DICTIONARY.md
  data/bts/clean/DATA_DICTIONARY.csv
"""
import importlib.util
import json
import os
import re
import sys

import duckdb

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BTS = os.path.join(ROOT, "data", "bts")
OUTDIR = os.path.join(BTS, "clean")
SAMPLE = os.path.join(BTS, "clean", "otp_*.parquet").replace("\\", "/")
README_MD = os.path.join(BTS, "docs", "BTS_Ontime_field_dictionary.md")

# import 11_clean.py (module name starts with a digit -> load by path).
# This is the single source of truth for how each column was transformed.
_spec = importlib.util.spec_from_file_location(
    "clean_mod", os.path.join(ROOT, "scripts", "11_clean.py"))
clean_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(clean_mod)


def change_of(col):
    """Answer「这个字段被我改过吗？怎么改的？」for one column."""
    if col in clean_mod.DERIVED:
        how = {
            "CRSDepHour": "由 `CRSDepTime` 计算：`(hhmm // 100) % 24`，处理 2400 跨夜",
            "CRSArrHour": "由 `CRSArrTime` 计算：`(hhmm // 100) % 24`",
            "Route": "由 `Origin` 与 `Dest` 拼接：`Origin || '-' || Dest`",
            "IsWeekend": "由 `DayOfWeek` 计算：`DayOfWeek IN (6,7)`",
            "TotalCauseDelay": "五项 `*Delay` 求和；五项全为 NULL 时结果保留 NULL",
        }[col]
        return f"**改过** — 新增列：{how}"
    if col in clean_mod.FLAG01:
        return '**改过** — 类型：字符串 `"0.00"`/`"1.00"` → TINYINT `0`/`1`（取值含义不变）'
    if col in clean_mod.DATE:
        return "**改过** — 类型：字符串 → DATE（取值不变）"
    if col in clean_mod.HHMM:
        return "**改过** — 类型：字符串 hhmm → SMALLINT（数值不变，`2400` 原样保留）"
    if col in clean_mod.SMALLINT:
        return "**改过** — 类型：字符串 → SMALLINT（取值不变）"
    if col in clean_mod.INTEGER:
        return "**改过** — 类型：字符串 → INTEGER（取值不变）"
    if col in clean_mod.DOUBLE:
        return "**改过** — 类型：字符串 → DOUBLE（取值不变）"
    if col in clean_mod.VARCHAR:
        return "没改 — 原样保留（仅编码与空值处理）"
    return "没改 — 原样保留"

# ------------------------------------------------------------------ Chinese
CN = {
    "Year": "年份", "Quarter": "季度(1-4)", "Month": "月份(1-12)",
    "DayofMonth": "日(1-31)", "DayOfWeek": "星期(1=周一, 7=周日)",
    "FlightDate": "航班日期",
    "Reporting_Airline": "报告承运人代码(分析跨年统一口径)",
    "DOT_ID_Reporting_Airline": "承运人 DOT 编号",
    "IATA_CODE_Reporting_Airline": "承运人 IATA 代码(跨年可能重复)",
    "Tail_Number": "飞机尾号",
    "Flight_Number_Reporting_Airline": "航班号",
    "OriginAirportID": "起飞机场 DOT 编号(跨年稳定)",
    "OriginAirportSeqID": "起飞机场时序编号(属性变化时变化)",
    "OriginCityMarketID": "起飞城市市场编号(可合并同城多机场)",
    "Origin": "起飞机场三字码", "OriginCityName": "起飞城市名",
    "OriginState": "起飞州缩写", "OriginStateFips": "起飞州 FIPS 码",
    "OriginStateName": "起飞州全名", "OriginWac": "起飞地世界区域码",
    "DestAirportID": "到达机场 DOT 编号", "DestAirportSeqID": "到达机场时序编号",
    "DestCityMarketID": "到达城市市场编号", "Dest": "到达机场三字码",
    "DestCityName": "到达城市名", "DestState": "到达州缩写",
    "DestStateFips": "到达州 FIPS 码", "DestStateName": "到达州全名",
    "DestWac": "到达地世界区域码",
    "CRSDepTime": "计划起飞时间(本地 hhmm)",
    "DepTime": "实际起飞时间(本地 hhmm, 2400=次日零点)",
    "DepDelay": "起飞延误(分钟, 负=提前)",
    "DepDelayMinutes": "起飞延误分钟(负值截断为0)",
    "DepDel15": "起飞是否延误≥15分钟(1/0)",
    "DepartureDelayGroups": "起飞延误分组(-2..12)",
    "DepTimeBlk": "计划起飞时段(如 0800-0859)",
    "TaxiOut": "滑出时间(分钟)", "WheelsOff": "实际离地时间(hhmm)",
    "WheelsOn": "实际接地时间(hhmm)", "TaxiIn": "滑入时间(分钟)",
    "CRSArrTime": "计划到达时间(本地 hhmm)",
    "ArrTime": "实际到达时间(本地 hhmm, 2400=次日零点)",
    "ArrDelay": "到达延误(分钟, 负=提前)",
    "ArrDelayMinutes": "到达延误分钟(负值截断为0)",
    "ArrDel15": "到达是否延误≥15分钟(1/0)【核心因变量】",
    "ArrivalDelayGroups": "到达延误分组(-2..12)",
    "ArrTimeBlk": "计划到达时段",
    "Cancelled": "是否取消(1/0)",
    "CancellationCode": "取消原因(A=承运人 B=天气 C=空管 D=安全)",
    "Diverted": "是否备降(1/0)",
    "CRSElapsedTime": "计划航程时间(分钟)",
    "ActualElapsedTime": "实际航程时间(分钟)",
    "AirTime": "空中飞行时间(分钟)",
    "Flights": "航班计数(恒为1, 用于加权求和)",
    "Distance": "航段距离(英里)",
    "DistanceGroup": "距离分组(1..11, 每250英里一档)",
    "CarrierDelay": "延误原因：承运人自身(分钟)",
    "WeatherDelay": "延误原因：极端天气(分钟)",
    "NASDelay": "延误原因：国家空域系统/空管(分钟)",
    "SecurityDelay": "延误原因：安检/安保(分钟)",
    "LateAircraftDelay": "延误原因：前序航班晚到(分钟)",
    "FirstDepTime": "本架飞机当日首次起飞时间(hhmm)",
    "TotalAddGTime": "本架飞机当日累计额外地面时间(分钟)",
    "LongestAddGTime": "本架飞机单次最长额外地面时间(分钟)",
    "DivAirportLandings": "备降次数",
    "DivReachedDest": "备降后是否最终抵达目的地(1/0)",
    "DivActualElapsedTime": "含备降的实际航程时间(分钟)",
    "DivArrDelay": "含备降的到达延误(分钟)",
    "DivDistance": "备降额外飞行距离(英里)",
    # derived
    "CRSDepHour": "【派生】计划起飞小时(0-23)",
    "CRSArrHour": "【派生】计划到达小时(0-23)",
    "Route": "【派生】航线 = 起飞机场-到达机场",
    "IsWeekend": "【派生】是否周末(周六/周日)",
    "TotalCauseDelay": "【派生】五项原因延误之和(分钟)",
}

DIV_CN = {
    "Airport": "第{n}备降机场三字码", "AirportID": "第{n}备降机场 DOT 编号",
    "AirportSeqID": "第{n}备降机场时序编号", "WheelsOn": "第{n}备降接地时间(hhmm)",
    "TotalGTime": "第{n}备降累计地面时间(分钟)",
    "LongestGTime": "第{n}备降最长地面时间(分钟)",
    "WheelsOff": "第{n}备降后离地时间(hhmm)", "TailNum": "第{n}备降航班尾号",
}

# --------------------------------------------------------------- groupings
Q1 = {"FlightDate", "Year", "Quarter", "Month", "DayofMonth", "DayOfWeek",
      "IsWeekend", "CRSDepHour", "CRSArrHour", "DepTimeBlk", "ArrTimeBlk"}
Q2 = {"Origin", "OriginAirportID", "OriginAirportSeqID", "OriginCityMarketID",
      "OriginCityName", "OriginState", "OriginStateFips", "OriginStateName",
      "OriginWac", "Dest", "DestAirportID", "DestAirportSeqID", "DestCityMarketID",
      "DestCityName", "DestState", "DestStateFips", "DestStateName", "DestWac",
      "Route", "Reporting_Airline", "DOT_ID_Reporting_Airline",
      "IATA_CODE_Reporting_Airline"}
CAUSES_ORDER = ["CarrierDelay", "WeatherDelay", "NASDelay", "SecurityDelay",
                "LateAircraftDelay"]
Q3 = {"CarrierDelay", "WeatherDelay", "NASDelay", "SecurityDelay",
      "LateAircraftDelay", "TotalCauseDelay", "CancellationCode"}
MEASURE = {"DepDelay", "DepDelayMinutes", "DepDel15", "DepartureDelayGroups",
           "ArrDelay", "ArrDelayMinutes", "ArrDel15", "ArrivalDelayGroups",
           "CRSElapsedTime", "ActualElapsedTime", "AirTime", "TaxiOut", "TaxiIn",
           "Distance", "DistanceGroup", "CRSDepTime", "DepTime", "CRSArrTime",
           "ArrTime", "WheelsOff", "WheelsOn", "Flights"}
STATUS = {"Cancelled", "Diverted", "DivAirportLandings", "DivReachedDest"}
AIRCRAFT = {"Tail_Number", "Flight_Number_Reporting_Airline", "FirstDepTime",
            "TotalAddGTime", "LongestAddGTime"}


def cn_of(col):
    if col in CN:
        return CN[col]
    m = re.match(r"Div([1-5])(.+)$", col)
    if m:
        n, k = m.group(1), m.group(2)
        return DIV_CN.get(k, "备降明细").format(n=n)
    return ""


def group_of(col):
    if col in Q1:
        return "研究问题1 时间规律"
    if col in Q2:
        return "研究问题2 机场/航司/时段"
    if col in Q3:
        return "研究问题3 延误原因"
    if col in STATUS:
        return "运行状态"
    if col.startswith("Div"):
        return "备降明细"
    if col in AIRCRAFT:
        return "飞机与机组"
    if col in MEASURE:
        return "延误度量"
    return "其他"


def parse_official_defs(path):
    """The BTS readme lists fields as '<TAB>FieldName<TAB>Description'."""
    txt = open(path, encoding="utf-8").read()
    defs = {}
    for line in txt.splitlines():
        if "\t" not in line:
            continue
        parts = [p.strip() for p in line.split("\t") if p.strip()]
        if len(parts) < 2:
            continue
        name, desc = parts[0], " ".join(parts[1:]).strip()
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name) and desc:
            defs.setdefault(name, desc)
    return defs


def main():
    con = duckdb.connect()
    con.execute("PRAGMA threads=6")

    desc = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{SAMPLE}')").fetchall()
    cols = [(d[0], d[1]) for d in desc]
    print(f"columns in parquet: {len(cols)}")

    # null rates over the full dataset, in one pass
    null_expr = ", ".join(
        f'round(100.0*count(*) FILTER (WHERE "{c}" IS NULL)/count(*), 3) AS "{c}"'
        for c, _ in cols)
    row = con.execute(f"SELECT count(*) AS n, {null_expr} FROM read_parquet('{SAMPLE}')").fetchdf()
    nulls = row.iloc[0].to_dict()
    n_rows = int(nulls.pop("n"))
    print(f"row count: {n_rows:,}")

    defs = parse_official_defs(README_MD)
    print(f"official definitions parsed: {len(defs)}")

    rows = []
    missing_cn, missing_def = [], []
    for c, t in cols:
        cn = cn_of(c)
        if not cn:
            missing_cn.append(c)
        off = defs.get(c, "")
        if not off and not c.startswith(("CRSDepHour", "CRSArrHour", "Route",
                                         "IsWeekend", "TotalCauseDelay")):
            missing_def.append(c)
        rows.append({
            "column": c, "dtype": t, "chinese": cn, "group": group_of(c),
            "null_pct": nulls.get(c, 0.0),
            "changed_by_us": change_of(c).replace("**", ""),
            "official_definition_en": off,
        })

    if missing_cn:
        print(f"WARNING missing Chinese labels ({len(missing_cn)}): {missing_cn}")
    if missing_def:
        print(f"WARNING missing official definitions ({len(missing_def)}): {missing_def}")

    # ------------------------------------------------------------- CSV + MD
    import csv as _csv
    csv_path = os.path.join(OUTDIR, "DATA_DICTIONARY.csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = _csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    L = []
    A = L.append
    A("# 数据字典 — BTS On-Time Performance 清洗后数据集\n")
    A("> 数据源：U.S. DOT/BTS TranStats, *Reporting Carrier On-Time Performance "
      "(1987-present)*，2023-01 ~ 2025-12")
    A(f"> 记录数：**{n_rows:,}** 行 ｜ 字段数：**{len(cols)}** 列"
      f"（官方 109 列 + 5 个派生列）")
    A(f"> 物理类型与缺失率由 Parquet 与全量数据实测得出；英文定义逐字取自官方 "
      f"`readme.html`\n")

    A("## 使用口径（务必先读）\n")
    A("- **延误率** = `AVG(ArrDel15)`，分母是 `ArrDel15 IS NOT NULL` 的航班，"
      "即**实际执行的航班**。取消与备降航班的 `ArrDel15` 为 NULL，不计入分母。")
    A("- **取消率** = `AVG(Cancelled)`，分母是全部航班。")
    A("- **延误原因占比** = 各原因分钟数 ÷ 五项原因分钟数之和。"
      "原因字段**仅对 `ArrDel15 = 1` 的航班填写**（已实测 100% 符合）；"
      "其中 4,371,285 条的五项之和精确等于 `ArrDelayMinutes`，"
      "另有 18 条例外，见下文「已知数据质量问题」。")
    A("- `CRSDepTime` 等 hhmm 字段已转为整数，`2400` 表示次日零点；"
      "派生列 `CRSDepHour` 已用 `(hhmm // 100) % 24` 处理跨夜。")
    A("- 编码为 UTF-8（原始 CSV 为 latin-1，已在清洗时转换）。\n")

    A("## 这批数据我改过什么（总览）\n")
    A("**没有任何一行被删除，也没有任何取值被修改。** 本项目的全部改动只有三类：\n")
    A("| # | 改动 | 涉及范围 | 具体做法 | 为什么 |")
    A("|---|---|---|---|---|")
    A("| 1 | **丢弃 1 个空列** | 1 列 × 全部 20,928,579 行<br>（**不删任何一行**） | "
      "BTS 的 CSV 每行末尾都多一个逗号，标准解析会把它当成第 110 个字段。"
      "该字段在表头无名字、在数据里**恒为空**，已丢弃 | 它不是真实字段。"
      "若不丢弃，列数会变成 110 而非 109，数据字典会多记一个根本不存在的列 |")
    A("| 2 | **类型转换（取值不变）** | 108 个原字段 | 字符串 → DATE / SMALLINT / INTEGER / "
      "DOUBLE / TINYINT；`\"0.00\"`/`\"1.00\"` → `0`/`1` | 原始 CSV 全部是文本，"
      "不转类型无法做数值计算，且体积大 16 倍 |")
    A("| 3 | **新增 5 个派生列** | 见下表 | `CRSDepHour` / `CRSArrHour` / `Route` / "
      "`IsWeekend` / `TotalCauseDelay` | 团队做时段、航线、周末对比时反复要用，"
      "预计算可避免每人各写一遍口径 |")
    A("")
    A("另外两项**全局处理**（不改变任何取值）：原始 CSV 为 `latin-1` 编码 → 统一转 UTF-8；"
      "空字符串 `\"\"` → NULL（DuckDB 读入时自动完成，与 BTS 的 NULL 语义一致）。\n")
    A("> 逐字段的「是否改过 / 怎么改」见下方字段清单的 **改动** 列。\n")

    A("### 关于第 1 条「丢弃 1 个空列」的详细说明\n")
    A("这是**唯一一个容易被误解为「动了数据」的改动**，所以单独说清楚。\n")
    A("**BTS 的原始 CSV 长这样**（每行末尾都有一个逗号）：\n")
    A("```")
    A('"Year","Quarter",...,"Div5WheelsOff","Div5TailNum",      ← 表头，末尾一个逗号')
    A('2023,1,1,2,1,2023-01-02,"9E",...,"","","","",           ← 数据行，末尾一个逗号')
    A("```\n")
    A("按 CSV 规范，**每一个逗号都分隔两个字段**，所以 `A,B,C,` 是 **4 个字段**"
      "（第 4 个为空），而不是 3 个。于是：\n")
    A("- 表头行有 109 个逗号 → 解析出 **110 个字段名**，第 110 个是**空名字**")
    A("- 数据行同理 → 解析出 **110 个值**，第 110 个**恒为空字符串**\n")
    A("**主流工具会怎么处理它**（若不主动丢弃）：\n")
    A("| 工具 | 列数 | 第 110 列被命名为什么 | 内容 |")
    A("|---|---|---|---|")
    A("| `pandas.read_csv` | 110 | `Unnamed: 109` | 全部 NaN |")
    A("| DuckDB `read_csv` | 110 | `column109` | 全部 NULL |")
    A("| Python `csv.reader` | 110 | 无名字，`row[-1] == ''` | 全部空字符串 |\n")
    A("**已实测验证**（`scripts/23_verify_trailing_column.py`）："
      "扫描全部 36 个 CSV、**20,928,579 行**，结果：\n")
    A("- 第 110 个字段**非空的行数 = 0**")
    A("- 字段数不等于 110 的行数 = **0**\n")
    A("**结论：丢弃这一列不损失任何信息**（它的每一行都是空的），"
      "但保留它会让所有下游的「字段数」统计多出 1。"
      "注意区分：**这是丢弃 1 个「列」，不是删除任何「行」——行数始终是 20,928,579。**\n")

    A("## 字段清单\n")
    A("| # | 字段名 | 类型 | 中文含义 | 分类 | 缺失率 | 改动 | 官方定义（英文） |")
    A("|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(rows, 1):
        off = (r["official_definition_en"] or "").replace("|", "\\|")
        if len(off) > 200:
            off = off[:197] + "..."
        chg = r["changed_by_us"].replace("|", "\\|")
        A(f"| {i} | `{r['column']}` | {r['dtype']} | {r['chinese']} | {r['group']} "
          f"| {r['null_pct']:.2f}% | {chg} | {off} |")
    A("")

    A("## 缺失率说明\n")
    A("本数据集的缺失**几乎全部是结构性缺失**（某些行本来就不该有值），而不是采集故障。"
      "下表按缺失原因分组，数值为组内字段的实测缺失率区间。\n")
    A("| 缺失原因 | 涉及字段 | 列数 | 缺失率 |")
    A("|---|---|---|---|")
    div_keys = [k for k in DIV_CN]
    GROUPS = [
        ("航班取消，没有实际起飞数据",
         ["DepTime", "DepDelay", "DepDelayMinutes", "DepDel15",
          "DepartureDelayGroups", "TaxiOut", "WheelsOff"]),
        ("航班取消，没有落地时刻",
         ["ArrTime", "WheelsOn", "TaxiIn"]),
        ("航班取消或备降，没有「到达目的地」的延误",
         ["ArrDelay", "ArrDelayMinutes", "ArrDel15", "ArrivalDelayGroups",
          "ActualElapsedTime", "AirTime"]),
        ("航班未取消，因此没有取消原因码", ["CancellationCode"]),
        ("延误原因字段只对到达延误≥15分钟的航班填写",
         [c for c in CAUSES_ORDER]),
        ("备降明细：只有备降航班才有值", [f"Div1{k}" for k in div_keys]),
        ("备降明细：只有发生 2 次以上备降的航班才有值",
         [f"Div{i}{k}" for i in (2, 3, 4, 5) for k in div_keys]),
        ("该字段仅少数承运人上报",
         ["FirstDepTime", "TotalAddGTime", "LongestAddGTime"]),
    ]
    uniq = {c for c, _ in cols}
    listed = set()
    for reason, members in GROUPS:
        members = [m for m in members if m in uniq]
        if not members:
            continue
        listed.update(members)
        vals = [nulls.get(m, 0.0) for m in members]
        field_desc = (f"`{members[0]}`" if len(members) == 1
                      else f"`{members[0]}` … `{members[-1]}`")
        rng = (f"{min(vals):.2f}%" if len(members) == 1
               else f"{min(vals):.2f}% – {max(vals):.2f}%")
        A(f"| {reason} | {field_desc} | {len(members)} | {rng} |")
    A("")
    A("### 其余存在缺失的字段\n")
    A("| 字段 | 缺失率 |")
    A("|---|---|")
    rest = [r for r in rows if r["null_pct"] > 0 and r["column"] not in listed]
    for r in sorted(rest, key=lambda r: -r["null_pct"]):
        A(f"| `{r['column']}` | {r['null_pct']:.3f}% |")
    if not rest:
        A("| — | 无 |")
    A("")

    A("## 已知数据质量问题（实测发现，论文中建议说明）\n")
    A("**有 18 条航班的到达延误≥15分钟，但航司没有报告延误原因**，"
      "占全部延误航班（4,371,303 条）的 **0.0004%**：\n")
    A("| 情况 | 条数 | 航司 | 表现 |")
    A("|---|---|---|---|")
    A("| 报告了原因但全为 0 | 15 | 西南航空 WN（多数为 2025-11） | 五个原因字段均为 `0.0`，"
      "但 `ArrDelayMinutes` 为正 |")
    A("| 完全没有报告原因 | 3 | 精神航空 F9 | 五个原因字段均为 `NULL` |")
    A("")
    A("处置方式：派生列 `TotalCauseDelay` 在五项原因**全为 NULL 时保留 NULL**（不伪装成 0），"
      "因此这 3 条不会污染原因占比的分母；另外 15 条的 0 值无法与「真实零延误」区分，"
      "属于源头数据的固有限制。用 `scripts/19_cause_mismatch.py` 可复现这 18 条清单。\n")

    A("## 派生字段说明（本项目新增，非 BTS 原生）\n")
    A("| 字段 | 计算方式 | 用途 |")
    A("|---|---|---|")
    A("| `CRSDepHour` | `(CRSDepTime // 100) % 24` | 时段规律分析（研究问题1/2），已处理 `2400` 跨夜 |")
    A("| `CRSArrHour` | `(CRSArrTime // 100) % 24` | 到达时段分析 |")
    A("| `Route` | `Origin || '-' || Dest` | 航线级聚合 |")
    A("| `IsWeekend` | `DayOfWeek IN (6,7)` | 周末/工作日对比 |")
    A("| `TotalCauseDelay` | 五项 `*Delay` 之和；**五项全为 NULL 时结果为 NULL** | 延误总分钟数；"
      "在有原因报告的延误航班上等于 `ArrDelayMinutes` |")
    A("")

    md_path = os.path.join(OUTDIR, "DATA_DICTIONARY.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))

    print(f"\nwrote {os.path.relpath(md_path, ROOT)}")
    print(f"wrote {os.path.relpath(csv_path, ROOT)}")
    print(f"rows={len(rows)}  with_chinese={sum(1 for r in rows if r['chinese'])}  "
          f"with_official_def={sum(1 for r in rows if r['official_definition_en'])}")


if __name__ == "__main__":
    main()
