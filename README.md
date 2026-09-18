# Bigdata-group-project

美国航班起飞延误分析（BTS On-Time Performance, 2023–2025）——大数据课程小组项目。

- 数据来源：美国交通部运输统计局（BTS）Reporting Carrier On-Time Performance 官方全量数据
- 覆盖范围：2023-01 ~ 2025-12 共 36 个月，**20,928,579 条航班记录**，109 个官方字段 + 5 个派生字段
- 核心结论速览：全期延误率 21.23%（延误 = 到达晚 ≥15 分钟）；延误呈夏季单峰、日内累积结构；前序航班晚到（39.9%）+ 航司自身（34.4%）是主因，天气直接归因仅 5.9%

## 仓库结构

```
├── data/
│   ├── aggregated/        # ★ 分析底表（42.8万行，24MB CSV）—— 日常分析用这个，秒级可跑
│   └── raw/               # 原始数据不入库（见下方"获取原始数据"）
├── docs/                  # 数据字典、口径说明、讲解文档、分工接续方案
├── figures/               # 8 张 300dpi 图表（成员1产出）
├── scripts/               # 数据下载 / 清洗 / 底表构建脚本
├── notebooks/             # 成员2：聚类、关联规则、预测模型分析
├── src/                   # 成员3：并行计算管道与基准实验
├── report/                # 最终报告
└── slides/                # 展示 slides
```

## 快速开始（成员2/3 看这里）

### 第 0 步：切到你自己的分支

```bash
git clone https://github.com/BoHeTang-coder/Bigdata-group-project.git
cd Bigdata-group-project
git checkout member2-analysis      # 成员2 用这个
git checkout member3-parallel      # 成员3 用这个
```

> 每个人在自己的分支上干活、随时 push，不要直接动 main（main 留给最终验收）。
> 你的分支里已经带了全部文档、8 张图和分析底表，clone 下来即可开工。

### 不想用 git？直接下载底表文件

浏览器打开（需先用你的 GitHub 账号登录并被加入仓库协作）：

- 底表 CSV（24MB，日常分析用这个）：
  <https://github.com/BoHeTang-coder/Bigdata-group-project/raw/member1-deliverables/data/aggregated/agg_month_hour_airline_origin.csv>
- 底表使用说明（列含义 + 口径代码）：
  <https://github.com/BoHeTang-coder/Bigdata-group-project/blob/member1-deliverables/data/aggregated/README_使用说明.md>
- 接续方案（你的任务拆解）：
  <https://github.com/BoHeTang-coder/Bigdata-group-project/blob/member1-deliverables/docs/接续方案_给成员2和3.md>

### 环境准备（一条命令）

```bash
pip install pandas pyarrow matplotlib scikit-learn mlxtend
```

### 用底表做分析（3 行代码起步）

```python
import pandas as pd
df = pd.read_csv("data/aggregated/agg_month_hour_airline_origin.csv")
df["delay_rate"] = df.delayed / df.executed   # 延误率，分母 = 实际执行航班
```

- 列含义与常用口径见 `data/aggregated/README_使用说明.md`；字段级细节见 `docs/02_数据字典.md`。
- ⚠️ 分析口径铁律（详细版见 `docs/00_先读我_讲解文档.md` 第 2、6 章）：
   - 延误率分母 = 实际执行航班（executed），不是全部航班；
   - 五类延误原因只对延误航班填写，原因占比分母 = 延误航班的延误总分钟。

## 获取原始数据（仅成员3 并行实验、航线级分析需要）

原始 parquet（每年约 190MB，共 570MB）**不进 git**（GitHub 单文件上限 100MB）。两种获取方式：

1. 从 BTS 官网下载：https://www.transtats.bts.gov/DL_SelectFields.aspx?gnoyr_VQ=FGJ
2. 运行成员1的下载脚本重建（脚本仅依赖 Python 标准库，支持断点续传）。

原始明细文件结构：`otp_2023/2024/2025.parquet`，读取示例：

```python
import pyarrow.parquet as pq
t = pq.read_table("otp_2024.parquet", columns=["Month","Reporting_Airline","ArrDel15","Cancelled","Diverted"])
```

重建底表：`python scripts/build_base_table.py`

## 分工与进度

| 成员 | 分工 | 状态 |
|---|---|---|
| 成员1 | 数据下载、清洗、8 张基础图表 | ✅ 完成 |
| 成员2 | 进阶数据分析（聚类 / 关联规则 / 预测） | 🚧 进行中，方案见 `docs/接续方案_给成员2和3.md` |
| 成员3 | 并行计算管道 + 加速比基准实验 | 🚧 进行中，方案见 `docs/接续方案_给成员2和3.md` |
| 成员4 | 报告与展示 | 🚧 进行中 |

## 引用

> U.S. Department of Transportation, Bureau of Transportation Statistics, *On-Time Performance*, TranStats, accessed 2026-09. https://www.transtats.bts.gov/DL_SelectFields.aspx?gnoyr_VQ=FGJ
