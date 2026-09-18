# -*- coding: utf-8 -*-
"""
构建"分析底表"：从成员1的 3 个 parquet（2093万行明细）聚合出
  年 × 月 × 计划起飞小时 × 航司 × 起飞机场 粒度的统计表。
只读取原始 parquet，不改任何原始数据；输出一个小 CSV 供后续分析复用。

用法:
  python build_base_table.py
输出:
  agg_month_hour_airline_origin.csv  (与本脚本同目录)
"""
import os
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.dataset as ds
import pyarrow.parquet as pq

BASE = r"C:\Users\Chen_\Desktop\其他\cityu\sema\bigdata\project\交付包_成员1\交付包_成员1\06_数据"
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_CSV = os.path.join(OUT_DIR, "agg_month_hour_airline_origin.csv")

NEED_COLS = [
    "Year", "Month", "CRSDepHour", "Reporting_Airline", "Origin",
    "Cancelled", "Diverted", "ArrDel15", "ArrDelayMinutes",
    "CarrierDelay", "WeatherDelay", "NASDelay", "SecurityDelay", "LateAircraftDelay",
]

dataset = ds.dataset([os.path.join(BASE, f"otp_{y}.parquet") for y in ("2023", "2024", "2025")],
                     format="parquet")
table = dataset.to_table(columns=NEED_COLS)
print("读取完成:", table.num_rows, "行")

year = table["Year"]
executed = pc.and_(pc.equal(table["Cancelled"], 0), pc.equal(table["Diverted"], 0))
delayed = pc.and_(executed, pc.equal(table["ArrDel15"], 1))

tbl = table.append_column("executed", pc.cast(executed, pa.int64()))
tbl = tbl.append_column("delayed", pc.cast(delayed, pa.int64()))

# CRSDepHour 如有缺失填 -1，保证分组不丢行
dep_hour = pc.fill_null(tbl["CRSDepHour"], -1)
tbl = tbl.set_column(tbl.schema.get_field_index("CRSDepHour"),
                     pa.field("CRSDepHour", dep_hour.type), dep_hour)

keys = ["Year", "Month", "CRSDepHour", "Reporting_Airline", "Origin"]
agg = tbl.group_by(keys).aggregate([
    ("executed", "sum"),
    ("delayed", "sum"),
    ("Cancelled", "sum"),
    ("Diverted", "sum"),
    ("ArrDelayMinutes", "sum"),
    ("CarrierDelay", "sum"),
    ("WeatherDelay", "sum"),
    ("NASDelay", "sum"),
    ("SecurityDelay", "sum"),
    ("LateAircraftDelay", "sum"),
])
# flights 总数 = executed + cancelled + diverted（取消与备降互斥）
total = pc.add(pc.add(agg["executed_sum"], agg["Cancelled_sum"]), agg["Diverted_sum"])
agg = agg.append_column("flights", total)

# 整理列顺序与命名，并按年月排序
agg = agg.select([
    "Year", "Month", "CRSDepHour", "Reporting_Airline", "Origin",
    "flights", "executed_sum", "delayed_sum", "Cancelled_sum", "Diverted_sum",
    "ArrDelayMinutes_sum", "CarrierDelay_sum", "WeatherDelay_sum",
    "NASDelay_sum", "SecurityDelay_sum", "LateAircraftDelay_sum",
])
agg = agg.rename_columns([
    "year", "month", "dep_hour", "airline", "origin",
    "flights", "executed", "delayed", "cancelled", "diverted",
    "arr_delay_min", "carrier_delay_min", "weather_delay_min",
    "nas_delay_min", "security_delay_min", "late_aircraft_delay_min",
])
agg = agg.sort_by([("year", "ascending"), ("month", "ascending"),
                   ("dep_hour", "ascending"), ("airline", "ascending"),
                   ("origin", "ascending")])

pq.write_table(agg, OUT_CSV.replace(".csv", ".parquet"), compression="snappy")
import csv
with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(agg.column_names)
    cols = [agg[c].to_pylist() for c in agg.column_names]
    for row in zip(*cols):
        writer.writerow(row)

print("聚合完成:", agg.num_rows, "行 ×", agg.num_columns, "列")
print("输出:", OUT_CSV, "(%.1f MB)" % (os.path.getsize(OUT_CSV) / 1e6))
print("输出:", OUT_CSV.replace(".csv", ".parquet"), "(%.1f MB)" % (os.path.getsize(OUT_CSV.replace('.csv', '.parquet')) / 1e6))

# 自检：总数与成员1文档对账
print("总航班数 =", pc.sum(agg["flights"]).as_py(), "(应为 20,928,579)")
print("执行航班 =", pc.sum(agg["executed"]).as_py())
print("延误航班 =", pc.sum(agg["delayed"]).as_py(), "(应为 4,371,303)")
