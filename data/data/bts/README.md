# 美国航班准点率数据集 (BTS On-Time Performance, 2023-2025)

> 生成时间: 2026-09-16 00:33:11  
> 数据来源: 美国交通部运输统计局 (BTS) TranStats 官方月更数据  
> 下载入口: <https://www.transtats.bts.gov/DL_SelectFields.aspx?gnoyr_VQ=FGJ&QO_fu146_anzr=b0-gvzr>  
> 数据表: *Reporting Carrier On-Time Performance (1987-present)*

## 1. 本次交付概览

| 项目 | 数值 |
|---|---|
| 覆盖月份 | 36 / 36 (2023-01 ~ 2025-12) |
| 总记录数 | 20,928,579 条 |
| 字段数 | 109 列 (官方全字段) |
| 压缩包体积 | 0.98 GB |
| 解压后 CSV | 8.82 GB |
| 格式异常行 | 0 行 |

### 分年统计

| 年份 | 月份数 | 记录数 | CSV 体积 |
|---|---|---|---|
| 2023 | 12 | 6,847,899 | 2.88 GB |
| 2024 | 12 | 7,079,061 | 2.98 GB |
| 2025 | 12 | 7,001,619 | 2.95 GB |
| **合计** | **36** | **20,928,579** | **8.82 GB** |

## 2. 目录结构

```
5488/
├── data/bts/
│   ├── raw/<年>/On_Time_Reporting_Carrier_..._<年>_<月>.zip   # BTS 官方原始包 (含 readme.html)
│   ├── extracted/<年>/On_Time_Reporting_Carrier_..._<年>_<月>.csv
│   ├── docs/BTS_Ontime_field_dictionary.md   # 官方字段字典 (从 readme.html 抽取)
│   ├── docs/schema_check.json                # 表单字段 vs CSV 表头一致性核验
│   ├── manifest.json                         # 每个文件的 SHA-256 / 字节数 / 行数
│   ├── inventory.csv                         # 上表的 CSV 版本, 便于 Excel 查看
│   └── README.md                             # 本文件
└── scripts/
    ├── 00_probe.py         # 探测官网表结构 / 各月文件可用性
    ├── 00b_fields.py       # 从官网表单抽取 109 个字段名
    ├── 01_download.py      # 并发下载 + 断点续传 + 重试 + zip 完整性校验
    ├── 02_extract.py       # 解压 + 逐文件行数/列数核验
    ├── 03_docs.py          # 抽取官方字段字典 + 表头一致性核验
    ├── 04_report.py        # 生成本 README 与 inventory.csv
    ├── 05_smoke.py         # 端到端冒烟测试 (抽样出延误率排名)
    ├── 06_quality.py       # 数据质量审计 (验证下面第 4 节的所有坑)
    └── _explore/           # 一次性诊断脚本 (环境/带宽/字段结构探测)
```

## 3. 数据字段与三个研究问题的对应关系

| 研究问题 | 主要字段 |
|---|---|
| Q1 延误的总体规律（时间维度） | `FlightDate`, `Year/Quarter/Month/DayOfMonth/DayOfWeek`, `CRSDepTime`, `DepTime`, `CRSArrTime`, `ArrTime` |
| Q2 哪些机场/航司/时段最易延误 | `Origin`, `OriginAirportID`, `OriginCityMarketID`, `OriginState`, `Dest*`, `Reporting_Airline`, `DOT_ID_Reporting_Airline`, `DepTimeBlk`, `ArrTimeBlk` |
| Q3 延误原因归因 | `CarrierDelay`, `WeatherDelay`, `NASDelay`, `SecurityDelay`, `LateAircraftDelay`, `CancellationCode` |
| 延误度量 | `DepDelay`, `DepDelayMinutes`, `DepDel15`, `ArrDelay`, `ArrDelayMinutes`, `ArrDel15`, `TaxiOut`, `TaxiIn`, `AirTime`, `Distance` |
| 航班是否真正执行 | `Cancelled`, `Diverted`, `CancellationCode`, `Div*` |

## 4. 使用前必须知道的坑（重要，均已在数据上实测验证）

1. **行尾多余逗号 + 表头带引号**：BTS 每行末尾多一个逗号，`csv.reader` 会解析出 **110 个字段**（最后一列为空），必须丢掉末列才是 109 个真实字段。编码为 **latin-1 / CP1252**，不是 UTF-8。实测 36 个文件共 20,928,579 行，**异常行 0**。

2. **五个延误原因字段「当且仅当」`ArrDel15 == 1` 时填写**。在 2023-06 上实测：`ArrDel15=1` 的 152,268 行原因字段 **全部非空**，`ArrDel15=0` 的 424,994 行原因字段 **全部为空**，零违例。

3. **五个原因字段之和 == `ArrDelayMinutes`（精确相等）**。2023-06 实测 152,268 行 **100.000% 精确匹配**，最大绝对误差 0.00 分钟。因此原因占比的**正确分母是「延误航班（ArrDel15=1）的延误分钟总数」，不是「全部航班」**。用全部航班当分母会系统性低估。

4. **取消/备降航班的延误字段为空**：实测 2023-06 中 `Cancelled=1` 的 12,219 行 `ArrDelay` **全部为空**，`Diverted=1` 的 2,239 行也全部为空，其余 565,043 行无缺失。**计算平均延误前必须先过滤，否则会静默丢样本**（建议口径：仅对正常执行航班统计延误率）。

5. **航班唯一键**：`(FlightDate, Reporting_Airline, Flight_Number_Reporting_Airline, Origin, Dest, CRSDepTime)` 在 2023-06 上 **0 重复**，可作为主键做关联/去重。

6. **本地时间与跨日**：`DepTime`/`ArrTime` 是本地时间 hhmm，可能出现 `2400`；`ArrTime < DepTime` 不代表数据错误（跨时区/跨日）。算时长请用 `ActualElapsedTime` 或 `AirTime`。

7. **口径选择**：本数据集是 **Reporting Carrier（报告承运人）** 口径。若要按「售票航司」归因，应改用 *Marketing Carrier* 表（`On_Time_Marketing_Carrier_On_Time_Performance_Beginning_January_2018_<年>_<月>.zip`，官方同样存在，本仓库未下载）。

8. **2023-2025 三年口径一致**：五个原因字段自 2003-06 起提供，三年均完整，无口径断裂。

9. **关于「119 个字段」**：官方 *Reporting Carrier* 表当前实际提供 **109 个字段**（官网表单勾选框数 = 109，与 CSV 表头 1:1 完全一致，见 `docs/schema_check.json`）。若你看到的资料写 119，可能混入了 Marketing Carrier 表或旧版变量列表，**本项目以 109 为准**。

## 5. 复现方式

```bash
cd "<项目根目录>"
python scripts/01_download.py     # 下载 36 个月官方原始包 (断点续传/重试, 可重复执行)
python scripts/02_extract.py      # 解压为 CSV 并逐文件核验行数/列数
python scripts/03_docs.py         # 导出官方字段字典
python scripts/04_report.py       # 生成本 README 与 inventory.csv
python scripts/05_smoke.py        # 冒烟测试: 抽样跑通三个研究问题的聚合
python scripts/06_quality.py      # 数据质量审计
```

所有脚本都可安全重复运行：已完成的文件按 `manifest.json` 中的字节数 + SHA-256 跳过。
脚本仅依赖 Python 标准库，**无需安装 pandas/numpy** 即可完成下载与核验。

## 6. 抽样验证结果（2023-06，可直接用于写作）

三个研究问题的聚合口径已在 `scripts/05_smoke.py` 中跑通，以下为 2023-06 实测值：

**Q2 — 准点率最差的航司**（按 `ArrDel15`，样本量 ≥2000 班）

| 航司 | 航班数 | 到达延误率 |
|---|---|---|
| F9 (Frontier) | 13,344 | 43.9% |
| NK (Spirit) | 20,353 | 38.9% |
| B6 (JetBlue) | 21,831 | 36.5% |
| UA (United) | 58,791 | 30.9% |
| AA (American) | 79,036 | 30.6% |

**Q2 — 时段规律**：延误率随一天推移单调上升（典型的「延误累积」效应）

| 起飞时段 | 航班数 | 到达延误率 |
|---|---|---|
| 06:00–06:59 | 40,694 | 10.6% |
| 08:00–08:59 | 36,473 | 15.1% |
| 10:00–10:59 | 35,189 | 18.9% |

**Q3 — 延误原因构成**（2023-06，分母 = 延误航班的总延误分钟 11,460,948 分钟）

| 原因 | 延误分钟 | 占比 |
|---|---|---|
| 前序航班晚到 LateAircraftDelay | 4,752,557 | 41.5% |
| 航司自身 CarrierDelay | 4,010,319 | 35.0% |
| 空管 NASDelay | 2,045,265 | 17.8% |
| 天气 WeatherDelay | 630,539 | 5.5% |
| 安检 SecurityDelay | 22,268 | 0.2% |

> 注意：天气占比仅 5.5%，与公众直觉相反 —— 这是 BTS 归因口径下「天气直接导致」的部分，前序航班晚到中相当比例其实由天气间接引发，论文里值得展开讨论。

## 7. 逐月清单

| 月份 | 记录数 | ZIP | CSV | 异常行 | SHA-256 (前16位) |
|---|---|---|---|---|---|
| 2023-01 | 538,837 | 25.8 MB | 232 MB | 0 | `327924faa362d360` |
| 2023-02 | 502,749 | 23.6 MB | 216 MB | 0 | `bfa6eb7bebb53f10` |
| 2023-03 | 580,322 | 27.6 MB | 250 MB | 0 | `1a61dce7c50e5c4f` |
| 2023-04 | 561,441 | 26.7 MB | 242 MB | 0 | `adf3ecf6e3763a55` |
| 2023-05 | 579,958 | 27.0 MB | 250 MB | 0 | `aec2e926b11e55f8` |
| 2023-06 | 577,262 | 27.7 MB | 249 MB | 0 | `67dc6b993ba2e7c2` |
| 2023-07 | 601,866 | 28.8 MB | 260 MB | 0 | `b1b73635dcb2add3` |
| 2023-08 | 602,987 | 28.2 MB | 260 MB | 0 | `d374aa3ec2b844d4` |
| 2023-09 | 569,338 | 26.7 MB | 245 MB | 0 | `4e7bc3f76857accd` |
| 2023-10 | 598,968 | 28.1 MB | 258 MB | 0 | `a92cc51c6bb1e7fc` |
| 2023-11 | 563,777 | 26.3 MB | 243 MB | 0 | `9ad54595568704a1` |
| 2023-12 | 570,394 | 27.5 MB | 246 MB | 0 | `c8391a3f06749b6e` |
| 2024-01 | 547,271 | 26.3 MB | 235 MB | 0 | `fe089b45523f9d4a` |
| 2024-02 | 519,221 | 23.9 MB | 224 MB | 0 | `8463683d100504a9` |
| 2024-03 | 591,767 | 28.0 MB | 255 MB | 0 | `e2c5021406f480e8` |
| 2024-04 | 582,185 | 27.2 MB | 251 MB | 0 | `d8b1e88626a7375d` |
| 2024-05 | 609,743 | 29.7 MB | 264 MB | 0 | `03e4ae26c2d1247d` |
| 2024-06 | 611,132 | 29.8 MB | 264 MB | 0 | `4f329439fd6892aa` |
| 2024-07 | 634,613 | 32.8 MB | 274 MB | 0 | `4d992fee134137b3` |
| 2024-08 | 619,025 | 29.4 MB | 267 MB | 0 | `58d651379af90cc4` |
| 2024-09 | 582,622 | 27.1 MB | 251 MB | 0 | `c0df7503b0050ca4` |
| 2024-10 | 615,497 | 28.1 MB | 265 MB | 0 | `a417136d6c166373` |
| 2024-11 | 575,404 | 26.8 MB | 248 MB | 0 | `26b6e89e7c1f6616` |
| 2024-12 | 590,581 | 28.8 MB | 255 MB | 0 | `a324577aa76d1f0a` |
| 2025-01 | 539,747 | 25.9 MB | 232 MB | 0 | `868387dcedaef1b8` |
| 2025-02 | 504,884 | 24.1 MB | 218 MB | 0 | `12dc8dbdb3c8b3c2` |
| 2025-03 | 600,872 | 29.1 MB | 259 MB | 0 | `9c80fbc2112cdbf3` |
| 2025-04 | 583,950 | 28.0 MB | 252 MB | 0 | `f3718431e988e2af` |
| 2025-05 | 605,648 | 29.4 MB | 262 MB | 0 | `17c3419d7169b313` |
| 2025-06 | 611,575 | 29.7 MB | 265 MB | 0 | `087b75e4e059516c` |
| 2025-07 | 631,428 | 30.7 MB | 273 MB | 0 | `74309a3a734d5104` |
| 2025-08 | 602,378 | 29.4 MB | 260 MB | 0 | `405668b8a8072662` |
| 2025-09 | 562,439 | 26.8 MB | 242 MB | 0 | `adc722b1c1494445` |
| 2025-10 | 605,844 | 29.3 MB | 262 MB | 0 | `05d14d3fd67fa3e0` |
| 2025-11 | 570,550 | 27.5 MB | 246 MB | 0 | `6d5b68eea3ebb25f` |
| 2025-12 | 582,304 | 28.9 MB | 252 MB | 0 | `a2af96d186bc9997` |

## 8. 引用

> U.S. Department of Transportation, Bureau of Transportation Statistics, *On-Time Performance*, TranStats, accessed 2026-09-16. https://www.transtats.bts.gov/DL_SelectFields.aspx?gnoyr_VQ=FGJ
