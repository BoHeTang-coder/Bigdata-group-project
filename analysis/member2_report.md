# CS5488 成员 2：数据分析素材包与结果说明

分析版本：2026-09-18。数据取自小组仓库 `member1-clean` 分支所链接的 [Release v0.1-data](https://github.com/BoHeTang-coder/Bigdata-group-project/releases/tag/v0.1-data)：`otp_2023.parquet`、`otp_2024.parquet`、`otp_2025.parquet`。脚本在运行前核对三个文件的 SHA-256、必要字段和年度行数。本文是供小组写作和答辩使用的分析材料，不把探索性关联解释为因果。

## 1. 做了什么

在 **20,928,579** 条 2023–2025 年计划航班记录上完成两项分析：

- **起飞机场画像与聚类。** 对全部 362 个起飞机场计算延误率、取消率、延误严重度和原因构成。对三年计划航班至少 30,000 架次的 101 个机场做 KMeans 聚类，覆盖全体计划航班的 **91.82%**。
- **到达延误关联规则。** 以到达延误至少 15 分钟为后件，系统枚举季节、计划起飞时段、工作日/周末、航段距离、承运人和起飞州这六个维度中最多三项条件的已出现组合。共检查 **12,757** 个候选条件组合，按照 2023–2024 年数据筛得 **107** 条规则，并用 2025 年记录检查其时间稳定性。

## 2. 为什么这样做、具体口径是什么

**延误率统一口径。** `ArrDel15=1` 表示到达至少晚 15 分钟。延误率分母为 `Cancelled=0`、`Diverted=0` 且 `ArrDel15` 非空的航班；取消率分母为所有计划航班。全期延误率分子 **4,371,303**、分母 **20,588,134**，即 **21.2321%**。另有 2 条未取消、未备降但 `ArrDel15` 缺失的记录，不纳入延误率分母。此口径与组员 1 数据字典中对有效 `ArrDel15` 求平均的定义一致。

**机场画像。** 五项聚类特征是到达延误率、取消率、延误航班的平均到达延误分钟数、前序飞机晚到分钟占全部原因分钟的比例、天气分钟占全部原因分钟的比例。后两项只依据有原因记录的延误航班解释；它们描述延误原因分钟构成，不是“天气导致的航班比例”。特征标准化后比较 `k=2…6` 的 silhouette score，并要求每组至少 5 个机场。`k=3` 得分 **0.265**，但 `k=2` 为 **0.261**、`k=6` 为 **0.261**，因此三组只是可解释的探索性画像，不能视为唯一真实分类。

30,000 架次门槛在探索时发现低量机场 ASE 单独成簇之后确定，应如实视为分析选择。其统计上的理由是：30,000 条记录对应简单比例在最保守的 50% 情况下约 ±0.57 个百分点的 95% 二项近似误差。门槛敏感性检查显示，20,000 架次时会出现 1 个机场的孤立组；30,000 与 50,000 门槛下共同机场的分组一致性（ARI）为 **0.829**。完整诊断见 `cluster_k_diagnostics.csv` 和 `cluster_sensitivity.csv`。

**规则挖掘。** 所有前件均是计划起飞前已知的属性，避免将实际延误原因等结果信息放入前件。候选是六个维度中一至三维的观察到的组合；本版在 2023–2024 年要求联合支持度至少 **0.5%**、前件航班数至少 **50,000**、lift 至少 **1.20**。`support=P(前件且延误)`，`confidence=P(延误|前件)`，`lift=confidence/总体延误率`。2025 年不参与本版规则排序，但此前的探索已经看过该年份，因此应称为**时间稳健性检查**，而非完全盲测的外部验证。

## 3. 关键结果和建议引用的图

### 年度概览

| 年份 | 计划航班 | 延误率分母 | 到达延误≥15分钟 | 延误率 | 取消率 |
|---|---:|---:|---:|---:|---:|
| 2023 | 6,847,899 | 6,743,403 | 1,386,699 | 20.56% | 1.28% |
| 2024 | 7,079,061 | 6,965,247 | 1,449,966 | 20.82% | 1.36% |
| 2025 | 7,001,619 | 6,879,484 | 1,534,638 | 22.31% | 1.47% |

### 机场聚类

下表前五个比率/时长指标为**组内机场的简单平均**；最右两列先合并各机场分子和分母再求比率，因此是航班加权结果。编号只是算法标签。机场画像按**起飞机场的航班到达表现**计算，不能直接归因于机场管理本身。

| 组 | 机场数 | 代表性高量机场 | 机场平均延误率 | 平均取消率 | 平均延误分钟¹ | 前序晚到分钟占比¹ | 天气分钟占比¹ | 航班加权延误率 | 航班加权取消率 |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 37 | DEN、LAX、PHX、LAS、SEA | 18.65% | 1.02% | 63.2 | 43.69% | 3.80% | 20.30% | 1.01% |
| 2 | 30 | ATL、DTW、MSP、SLC、IAD | 18.72% | 1.33% | 78.6 | 34.72% | 7.99% | 19.16% | 1.14% |
| 3 | 34 | DFW、ORD、CLT、MCO、LGA | 21.76% | 1.75% | 78.6 | 42.72% | 4.90% | 23.48% | 1.78% |

¹ 这些也是各机场指标的简单平均。第 3 组的延误、取消频率较高；第 2 组与第 1 组的延误频率接近，但已延误航班的时长和天气分钟占比更高。建议报告使用 `airport_clusters.png` 并注明图是标准化特征的二维 PCA 投影，二维距离不是原始 5 维距离。

### 规则：三个有代表性的发现

2023–2024 年总体到达延误率为 **20.69%**，2025 年为 **22.31%**。下列规则均先根据前两年的指标挑选，再报告 2025 年的表现；前件之间存在包含和重叠关系，不应相加。

| 前件 → 到达延误≥15分钟 | 2023–24 前件航班数 | support | confidence | lift | 2025 confidence | 2025 lift |
|---|---:|---:|---:|---:|---:|---:|
| 夏季、18–23 点计划起飞、承运人 WN | 178,590 | 0.58% | **44.46%** | **2.15** | **42.98%** | **1.93** |
| 夏季、18–23 点计划起飞（不限定航司） | 836,298 | 2.34% | **38.39%** | **1.86** | **39.42%** | **1.77** |
| 18–23 点计划起飞、佛罗里达州出发 | 294,884 | 0.78% | **36.41%** | **1.76** | **34.54%** | **1.55** |

广义的夏季晚间规则在三个年份的 confidence 分别为 **37.85%、38.91%、39.42%**。进一步在**同一年、同一夏季月份、同一起飞机场、同一承运人**内部比较晚间与其他时段，并只保留两组各至少 30 架次的分层，晚间的航班加权风险差在 2023、2024、2025 年分别为 **+15.18、+16.03、+15.90 个百分点**；2025 年比较覆盖夏季晚间航班的 **93.21%**。这是更严格的描述性对比，但仍未控制航线与天气等全部因素，不能解释为晚间出发的因果效应。建议报告放入 `rule_support_confidence.png`，并用 `association_rules.png` 展示 2025 年 lift 是否维持。

## 4. 遇到的坑、怎么解决、还有什么限制

1. **仓库分支没有清洗后的全量 Parquet。** 从 Release 下载三份文件，核对 SHA-256；脚本在每次运行时重复检查。仓库 `data/aggregated/` 的说明与当前实际文件列表不一致，本分析直接读取 Release 数据。
2. **取消与备降不属于到达延误率分母。** 统一使用 `ArrDel15` 有效记录；两条状态正常但结果缺失的记录也明确排除。
3. **低量机场可能主导 KMeans。** 没有隐藏 ASE 异常，而是报告门槛选择和 20,000/50,000 架次的敏感性结果；三组仅作为探索性画像。
4. **大量候选规则容易出现偶然高 lift 和重复规则。** 明确搜索空间、训练期门槛和 2025 时间检查，报告前件航班数；仍需谨慎解释，尤其是 WN 规则与广义夏季晚间规则重叠。
5. **观测数据不能直接识别原因。** 机场、航司、航线、时段、天气和客流相互关联；分层检查减少了部分构成差异，但没有消除所有混杂。结果不应外推到数据覆盖范围之外。

## 5. 交付物与复现方法

| 文件 | 内容 |
|---|---|
| `member2_analysis.ipynb` | 完整可运行、已保存输出和图像的自包含 notebook |
| `member2_analysis.py` | 同一分析的命令行实现，含数据检查和运行计时 |
| `member2_requirements.txt` | 所需 Python 包 |
| `member2_results/data_audit.csv`、`yearly_overview.csv` | 数据核验、年度口径 |
| `member2_results/airport_profiles_all.csv`、`airport_clusters.csv`、`cluster_summary.csv` | 362 个机场的画像、101 个机场的组别、组别汇总 |
| `member2_results/cluster_k_diagnostics.csv`、`cluster_sensitivity.csv` | k 选择和门槛稳健性 |
| `member2_results/association_rules.csv`、`rule_mining_audit.csv` | 107 条筛选规则与搜索空间审计 |
| `member2_results/summer_evening_by_year.csv`、`stratified_evening_check.csv` | 跨年及分层检查 |
| `member2_results/airport_clusters.png`、`association_rules.png`、`rule_support_confidence.png` | 可直接插入报告的 PNG 图 |
| `member2_results/runtime_profile.csv` | 各阶段本机计时，供组内讨论计算热点 |

把三个 Parquet 放到 notebook 同级 `data/`，安装 `member2_requirements.txt` 后运行 notebook；也可运行 `python member2_analysis.py --data-dir data --output-dir member2_results`。三份大数据文件保留在 GitHub Release，不提交进普通 Git 分支。脚本本机热缓存下，交易条件计数表扫描约 **1.18–1.21 秒**、机场聚合约 **0.66 秒**；这只是本机参考时间，不能用来宣称并行加速比。

## 6. 给报告写作同学的三句话

1. 基于约 2,093 万条航班记录，101 个高量起飞机场形成三个**探索性运营画像**；其中第 3 组的航班加权到达延误率 **23.48%**、取消率 **1.78%**，均高于其余两组。
2. 系统枚举一至三项起飞前条件后，最强的高支持规则之一是夏季晚间 WN 航班：2023–2024 年到达延误率 **44.46%**、lift **2.15**，2025 年分别为 **42.98%**、**1.93**；广义夏季晚间规则也跨年保持较高风险。
3. 聚类和规则是可复核的描述性发现；报告应展示门槛敏感性、2025 时间检查和分层结果，同时明确这些发现不证明机场、航司或晚间起飞本身造成延误。

## 可直接供英文报告改写的段落

**Methods.** We analyzed 20,928,579 scheduled flights from the 2023–2025 BTS Reporting Carrier On-Time Performance release. Arrival-delay rates used flights that were neither cancelled nor diverted and had a nonmissing `ArrDel15` indicator. We profiled 362 departure airports and clustered 101 airports with at least 30,000 scheduled flights using standardized delay frequency, cancellation frequency, delayed-flight severity, and two delay-cause minute shares. We compared KMeans solutions with two to six clusters and examined volume-threshold sensitivity. Separately, we enumerated observed one- to three-condition itemsets across six predeparture dimensions. Rules were ranked using 2023–2024 data and checked against 2025 data.

**Results.** Three airport groups provided an interpretable but moderately separated description (silhouette 0.265). The group containing DFW, ORD, CLT, MCO and LGA had a flight-weighted arrival-delay rate of 23.48% and a cancellation rate of 1.78%. Among 12,757 observed candidate itemsets, 107 met the training-period support, volume and lift thresholds. Flights scheduled to depart on summer evenings had a 38.39% delay rate in 2023–2024 (lift 1.86) and 39.42% in 2025 (lift 1.77). The more specific summer-evening WN rule had rates of 44.46% and 42.98% in the two periods. A within-month, within-airport and within-airline comparison of summer flights retained an evening risk difference of 15.90 percentage points in 2025 among eligible strata.

**Limitations.** The airport clusters are descriptive and sensitive to the minimum-volume threshold; the k=3 silhouette score is only slightly higher than alternatives. The association rules are observational, overlap substantially, and may reflect residual differences in routes, weather, traffic or operations. Year 2025 was excluded from rule ranking in this pipeline, but prior exploration informed some design choices, so its results should be viewed as a temporal robustness check rather than a blind external validation.
