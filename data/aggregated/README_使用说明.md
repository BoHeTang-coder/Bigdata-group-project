# 分析底表 — 使用说明（给成员2/3）

## 文件

| 文件 | 大小 | 用途 |
|---|---|---|
| `agg_month_hour_airline_origin.csv` | 24.3 MB | Excel/pandas 直接打开，**进 GitHub 用这个** |
| `agg_month_hour_airline_origin.parquet` | 5.6 MB | pandas/DuckDB 读取更快，本地分析用这个 |
| `build_base_table.py` | — | 重新生成底表的脚本（以后加 2026 年数据改一行即可重跑） |

## 列说明（16 列）

| 列 | 含义 |
|---|---|
| year, month | 年、月（1–12） |
| dep_hour | 计划起飞小时 0–23（-1 = 原数据缺失，仅极少量） |
| airline | 航司代码（Reporting_Airline） |
| origin | 起飞机场三字码 |
| flights | 总航班数 |
| executed | 实际执行航班数（= flights − cancelled − diverted） |
| delayed | 到达延误 ≥15 分钟的航班数（仅对 executed 航班计） |
| cancelled / diverted | 取消 / 备降航班数 |
| arr_delay_min | 延误总分钟数（延误航班的 ArrDelayMinutes 之和） |
| carrier_delay_min 等 5 列 | 五类延误原因的分钟数（仅延误航班有值） |

## 常用计算（口径与成员1交付包一致）

```python
import pandas as pd
df = pd.read_csv("agg_month_hour_airline_origin.csv")

# 延误率 = delayed / executed（分母是执行航班，不是 flights！）
df["delay_rate"] = df.delayed / df.executed

# 原因占比：分母是五类原因分钟总和，不是全部航班
cause_cols = ["carrier_delay_min","weather_delay_min","nas_delay_min",
              "security_delay_min","late_aircraft_delay_min"]
df["weather_share"] = df.weather_delay_min / df[cause_cols].sum(axis=1)

# 示例：按月延误率趋势
monthly = df.groupby(["year","month"]).apply(
    lambda g: g.delayed.sum()/g.executed.sum(), include_groups=False)
```

## 注意事项

1. 底表**不含**到达机场、航线、距离等字段——需要航线级/到达侧分析时，仍要用成员1的原始 parquet（或让成员1把 Route 维度加进底表）。
2. dep_hour = -1 的行是原始数据缺失，量极少，分析时段规律时先过滤掉。
3. 建议把 `agg_month_hour_airline_origin.csv`（24MB）+ `build_base_table.py` 一起进 GitHub；原始 parquet 不进（超 100MB 限制）。
