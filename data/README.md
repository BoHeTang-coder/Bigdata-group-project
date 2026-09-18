# 数据目录说明

## 目录内容

- `aggregated/` —— 分析底表（月 × 起飞小时 × 航司 × 起飞机场 聚合，24MB CSV，**日常分析用这个**，秒级加载）

## 清洗后全量原始数据（不在仓库里）

3 个 parquet 文件（2023 / 2024 / 2025，每个约 190MB，共约 570MB）超过 GitHub 单文件 100MB 上限，**请从 Release 下载**：

👉 https://github.com/BoHeTang-coder/Bigdata-group-project/releases/tag/v0.1-data

| 文件 | 覆盖范围 | 行数 |
|---|---|---|
| `otp_2023.parquet` | 2023-01 ~ 2023-12 | 6,847,899 |
| `otp_2024.parquet` | 2024-01 ~ 2024-12 | 7,079,061 |
| `otp_2025.parquet` | 2025-01 ~ 2025-12 | 7,001,619 |

- 合计 20,928,579 条航班记录 × 114 列
- 字段含义见 `../docs/02_数据字典.md`，口径说明见 `../docs/08_附_数据下载与口径说明.md`
- 全量数据仅供并行计算实验与航线级分析使用；

## 数据来源

美国交通部运输统计局（BTS）On-Time Performance 官方数据：https://www.transtats.bts.gov/DL_SelectFields.aspx?gnoyr_VQ=FGJ
