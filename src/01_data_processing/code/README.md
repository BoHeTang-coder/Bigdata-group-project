# 数据与可视化

本项目分析美国 BTS 航班准点率数据，覆盖 2023—2025 年的 36 个月。代码完成数据下载、解压校验、数据清洗、统计聚合、8 张分析图生成、数据字典生成和结果核验。

## 1.代码

| 文件 | 工作内容 |
|---|---|
| `scripts/00_probe.py` | 探测 BTS 官网表单结构和 36 个月文件可用性 |
| `scripts/00b_fields.py` | 从已保存的官网表单提取 109 个字段名 |
| `scripts/01_download.py` | 并发下载、断点续传、重试、ZIP 完整性和 SHA-256 校验 |
| `scripts/02_extract.py` | 解压官方 ZIP，核验每个 CSV 的行数和列数 |
| `scripts/03_docs.py` | 提取官方字段字典，核对表单字段与 CSV 表头 |
| `scripts/04_report.py` | 根据 manifest 生成数据说明和 inventory.csv |
| `scripts/05_smoke.py` | 抽取每年一个月，验证三个研究问题的统计流程 |
| `scripts/06_quality.py` | 检查空值、取消/备降、延误原因、时间字段、唯一键等数据质量问题 |

| 文件 | 工作内容 |
|---|---|
| `scripts/11_clean.py` | 将原始 CSV 清洗为分年 Parquet，保留 109 个官方字段并生成 5 个派生字段 |
| `scripts/12_aggregate.py` | 统计月份、星期、小时、航司、机场和延误原因等指标 |
| `scripts/13_charts.py` | 生成 8 张 300 dpi 图、英文图注和图表说明 |
| `scripts/15_dictionary.py` | 生成 114 个字段的数据字典、类型、缺失率和改动说明 |
| `scripts/30_build_bundle.py` | 整理原来的数据与图片交付包 |
| `scripts/31_verify_bundle.py` | 检查原交付包文件、ZIP 和文档中的数字 |

结果核验与诊断代码：

| 文件 | 用途 |
|---|---|
| `scripts/10_probe_duckdb.py` | 探测 DuckDB 读取原始 CSV 的字段与类型 |
| `scripts/14_verify_claims.py` | 检查图注中的关键结论 |
| `scripts/17_null_check.py` | 检查数据字典引用的缺失率 |
| `scripts/18_verify.py` | 验收 Parquet、数据字典和 8 张图 |
| `scripts/19_cause_mismatch.py` | 查找延误原因之和不等于总延误的例外航班 |
| `scripts/20_verify_package.py` | 核对素材包引用的关键数字 |
| `scripts/21_verify_guide.py` | 核对讲解文档引用的关键数字 |
| `scripts/22_december_check.py` | 分析 12 月假期窗口的延误情况 |
| `scripts/23_verify_trailing_column.py` | 全量检查原始 CSV 行尾多余列 |
| `scripts/24_show_trailing_evidence.py` | 展示多余尾列的原始证据和读取差异 |

`scripts/_explore/` 另有 7 个历史辅助脚本：`00c_env.py`、`00d_speed.py`、`00e_concurrency.py`、`00f_variants.py`、`00g_lines.py`、`diag_filenames.py`、`migrate_fig_numbers.py`。它们用于环境检查、下载诊断、原始行结构检查、交付文件诊断和历史图号迁移，不属于常规复现步骤。`00g_lines.py` 的根目录计算沿用了旧目录位置，按当前目录布局直接运行会找不到 manifest；本包保留原样。

## 2. 包内结构与范围

```text
代码提交包_成员1/
├── README.md                  本提交说明和代码定位
├── requirements.txt           原工作区环境中实测的第三方依赖版本
├── 提交校验说明.md             本次执行的验证及其范围
├── 文件清单_SHA256.csv         包内文件大小、SHA-256 和原文件来源
├── 项目原始说明.md             原工作区 README 的原样副本
├── 00讲解文档.md               原项目讲解文档
├── 素材包_成员1交付.md          原项目工作总结
├── probe_form.html            官网表单快照副本，供 00b_fields.py 使用
├── scripts/                   31 个 Python 源文件及 bts_fields_form.json
├── data/bts/
│   ├── README.md               原数据下载与统计口径说明
│   ├── manifest.json           历史下载和解压记录
│   ├── inventory.csv           历史数据文件清单
│   ├── docs/                   官网表单快照、官方字段字典及 schema_check.json
│   ├── analysis/               已有聚合结果，可直接用于重新绘图
│   └── clean/                  字段字典和清洗摘要（不含 Parquet）
└── figures/                   已有图注和图表说明（不含 PNG）
```

本包用于提交源代码及小体积的配套材料，不含 `.venv/`、`__pycache__/`、原始 ZIP、解压 CSV、Parquet、PNG、旧交付 ZIP 和课程 PDF。历史 manifest、inventory 和清洗摘要描述的是原工作区的完整数据，并不表示这些大文件包含在本包内。

`probe_form.html` 由已有的 `data/bts/docs/DL_SelectFields_form_snapshot.html` 原样复制，补齐 `00b_fields.py` 需要的输入路径；没有改动任何原脚本。

## 3. 安装环境与快速验证

在**解压后的本包根目录**打开 PowerShell。原工作区使用 Python 3.12.1；截图中的 00—06 阶段只需 Python 标准库，后续分析与绘图需要第三方库。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

仅利用包内的小体积聚合结果，就可以重新生成全部 8 张图，无需下载大数据：

```powershell
.\.venv\Scripts\python.exe scripts/13_charts.py
```

从已有的表单快照重新提取字段名：

```powershell
.\.venv\Scripts\python.exe scripts/00b_fields.py
```

`requirements.txt` 记录本次读取到的本机版本，不代表已在全新环境中重新安装验证。

## 4. 从头复现完整流程

以下命令需在本包根目录运行。下载步骤需要联网；解压 CSV 约 8.82 GiB，另外还需原始 ZIP、Parquet 和运行临时空间。现有数据也可按原相对路径放回 `data/bts/raw/`、`data/bts/extracted/` 或 `data/bts/clean/`。

```powershell
.\.venv\Scripts\python.exe scripts/01_download.py
.\.venv\Scripts\python.exe scripts/02_extract.py
.\.venv\Scripts\python.exe scripts/03_docs.py
.\.venv\Scripts\python.exe scripts/04_report.py
.\.venv\Scripts\python.exe scripts/05_smoke.py
.\.venv\Scripts\python.exe scripts/06_quality.py
.\.venv\Scripts\python.exe scripts/11_clean.py
.\.venv\Scripts\python.exe scripts/12_aggregate.py
.\.venv\Scripts\python.exe scripts/13_charts.py
.\.venv\Scripts\python.exe scripts/15_dictionary.py
.\.venv\Scripts\python.exe scripts/18_verify.py
```

已有字段表和官网快照随包提供，因此常规复现不需要先运行联网探测脚本 `00_probe.py`。如果需要重新抓取官网表单，则先在本包根目录运行 `00_probe.py`，再运行 `00b_fields.py`。

`18_verify.py` 需要完整 Parquet 和生成后的 PNG，不能在尚未恢复数据的代码包上直接通过。原交付包的重建与验收可在完整数据恢复后运行 `30_build_bundle.py`、`31_verify_bundle.py`。它们操作的是本包根目录下的 `交付包_成员1/` 和对应 ZIP。


