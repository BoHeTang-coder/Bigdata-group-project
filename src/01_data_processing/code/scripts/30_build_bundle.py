# -*- coding: utf-8 -*-
"""
Build the single consolidated hand-off bundle:  交付包_成员1/

Collects every file the writing member needs into one numbered folder
(docs first, then figures, then data), writes a complete file manifest,
and produces a single ZIP at the project root.

Re-runnable: wipes and rebuilds the bundle folder each time.

Robustness notes
  * every source lives OUTSIDE the bundle folder, so wiping the bundle can
    never destroy an authored document (this bit us once)
  * the guide document is DISCOVERED by glob, not by a hard-coded filename,
    so a rename on disk can no longer break the build
  * after zipping, the archive is checked to hold exactly the same files,
    with exactly the same SHA-256, as the folder
"""
import glob
import hashlib
import os
import shutil
import sys
import time
import zipfile

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BUNDLE = os.path.join(ROOT, "交付包_成员1")
BTS = os.path.join(ROOT, "data", "bts")
FIG = os.path.join(ROOT, "figures")
ZIP_PATH = os.path.join(ROOT, "交付包_成员1.zip")

GUIDE_AS = "00_先读我_讲解文档.md"      # canonical name inside the bundle


def find_guide():
    """Locate the plain-language guide without hard-coding its filename."""
    hits = sorted(p for p in glob.glob(os.path.join(ROOT, "*讲解*.md"))
                  if os.path.isfile(p))
    if len(hits) != 1:
        raise SystemExit(
            f"expected exactly one '*讲解*.md' in {ROOT}, found {len(hits)}: {hits}")
    return hits[0]


# (source, destination-relative-to-bundle, one-line description)
# NOTE: every source lives OUTSIDE the bundle folder, so that wiping and
# rebuilding the bundle can never destroy an authored document again.
DOCS = [
    (find_guide(), GUIDE_AS,
     "★ 零基础导读：逐图讲解、概念解释、报告措辞、6 个雷区、FAQ"),
    (os.path.join(BTS, "clean", "DATA_DICTIONARY.md"), "02_数据字典.md",
     "114 个字段的中文含义、类型、实测缺失率、**是否被改过/怎么改**、官方英文定义"),
    (os.path.join(BTS, "clean", "DATA_DICTIONARY.csv"), "02_数据字典.csv",
     "同上，Excel/CSV 版，可按「改动」列筛选"),
    (os.path.join(FIG, "FIGURE_GUIDE.md"), "03_图表三件套.md",
     "★ 8 张图 = 300dpi PNG + 一句英文图注 + 这张图支撑的论点；含建议编号顺序"),
    (os.path.join(FIG, "CAPTIONS.md"), "04_英文图注.md",
     "纯英文图注 8 句，直接贴到图下方"),
    (os.path.join(ROOT, "素材包_成员1交付.md"), "01_素材包_六要素.md",
     "工作汇总：做了什么 / 为什么 / 关键结果 / 坑与解决 / 交付物清单 / 给写作岗三句话"),
    (os.path.join(BTS, "README.md"), "08_附_数据下载与口径说明.md",
     "数据来源、下载方式、9 条原始数据坑（技术成员才需要）"),
]
FIGURES = [
    ("fig1_delay_distribution.png", "延误分布直方图"),
    ("fig2_month_weekday_heatmap.png", "月份×星期延误率热力图"),
    ("fig3_hourly_pattern.png", "一天内各时段的延误率（三年对照）"),
    ("fig4_monthly_trend.png", "36 个月延误率 + 取消率趋势"),
    ("fig5_airline_ranking.png", "航司准点率排名"),
    ("fig6_worst_airports.png", "延误最严重的 15 个机场"),
    ("fig7_delay_causes.png", "★ 延误原因占比 + 三年稳定性"),
    ("fig8_airport_cause_profile.png", "12 大枢纽机场的延误原因构成"),
]
DATA = [
    ("otp_2023.parquet", "干净数据 2023 年（6,847,899 行 × 114 列）"),
    ("otp_2024.parquet", "干净数据 2024 年（7,079,061 行）"),
    ("otp_2025.parquet", "干净数据 2025 年（7,001,619 行）"),
    ("clean_summary.json", "清洗摘要（行数、体积）"),
]


def human(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {u}"
        n /= 1024
    return f"{n:.1f} TB"


def main():
    if os.path.exists(BUNDLE):
        shutil.rmtree(BUNDLE)
    os.makedirs(os.path.join(BUNDLE, "05_图片"))
    os.makedirs(os.path.join(BUNDLE, "06_数据"))
    print(f"building {BUNDLE}")

    manifest = []          # (bundle-relative path, description, bytes)

    for src, rel, desc in DOCS:
        if not os.path.exists(src):
            raise SystemExit(f"missing source: {src}")
        dst = os.path.join(BUNDLE, rel)
        shutil.copy2(src, dst)
        manifest.append((rel, desc, os.path.getsize(dst)))

    for name, desc in FIGURES:
        src = os.path.join(FIG, name)
        if not os.path.exists(src):
            raise SystemExit(f"missing figure: {src}")
        rel = f"05_图片/{name}"
        dst = os.path.join(BUNDLE, rel)
        shutil.copy2(src, dst)
        manifest.append((rel, desc, os.path.getsize(dst)))

    for name, desc in DATA:
        src = os.path.join(BTS, "clean", name)
        if not os.path.exists(src):
            raise SystemExit(f"missing data file: {src}")
        rel = f"06_数据/{name}"
        dst = os.path.join(BUNDLE, rel)
        shutil.copy2(src, dst)
        manifest.append((rel, desc, os.path.getsize(dst)))

    # ---- 07 manifest document
    L = ["# 文件总清单 — 交付包_成员1\n",
         f"> 生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
         "> 本包共 %d 个文件，合计 %s。\n" % (
             len(manifest), human(sum(m[2] for m in manifest))),
         "| # | 文件 | 大小 | 这是什么 |", "|---|---|---|---|"]
    for i, (rel, desc, size) in enumerate(manifest, 1):
        L.append(f"| {i} | `{rel}` | {human(size)} | {desc} |")
    L += ["",
          "## 你该用哪个文件",
          "",
          "| 你想做什么 | 打开哪个 |",
          "|---|---|",
          "| 第一次了解这个项目 | `00_先读我_讲解文档.md` |",
          "| 写报告、看图、配图注 | `03_图表三件套.md` + `05_图片/` |",
          "| 查某个字段是什么意思 | `02_数据字典.md` |",
          "| 汇报进度、写 Discussion | `01_素材包_六要素.md` |",
          "| 核对交付是否完整 | 本文件 |",
          "| 重新计算数据（需技术工具） | `06_数据/` |",
          ""]
    mf = os.path.join(BUNDLE, "07_文件总清单.md")
    with open(mf, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    manifest.append(("07_文件总清单.md", "本清单", os.path.getsize(mf)))

    # ---- ZIP (parquet/png are already compressed -> store them)
    print(f"writing {os.path.basename(ZIP_PATH)} ...")
    t0 = time.time()
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for dirpath, _dirs, files in os.walk(BUNDLE):
            for fn in sorted(files):
                full = os.path.join(dirpath, fn)
                arc = os.path.relpath(full, ROOT).replace("\\", "/")
                if fn.endswith((".parquet", ".png")):
                    zi = zipfile.ZipInfo.from_file(full, arc)
                    zi.compress_type = zipfile.ZIP_STORED
                    with open(full, "rb") as src, z.open(zi, "w") as out:
                        shutil.copyfileobj(src, out, 1 << 20)
                else:
                    z.write(full, arc)

    print(f"\nbundle : {BUNDLE}")
    print(f"zip    : {ZIP_PATH}  ({human(os.path.getsize(ZIP_PATH))}, "
          f"{time.time()-t0:.0f}s)")
    print(f"files  : {len(manifest)}")

    # ---- integrity: the archive must mirror the folder exactly -----------
    def sha(b):
        return hashlib.sha256(b).hexdigest()

    on_disk = {}
    for dp, _d, fs in os.walk(BUNDLE):
        for fn in fs:
            full = os.path.join(dp, fn)
            rel = os.path.relpath(full, BUNDLE).replace("\\", "/")
            on_disk[rel] = sha(open(full, "rb").read())

    with zipfile.ZipFile(ZIP_PATH) as z:
        in_zip = {n.split("交付包_成员1/", 1)[-1]: sha(z.read(n))
                  for n in z.namelist() if not n.endswith("/")}

    problems = []
    if set(on_disk) != set(in_zip):
        problems.append(f"file sets differ: only-on-disk={sorted(set(on_disk)-set(in_zip))} "
                        f"only-in-zip={sorted(set(in_zip)-set(on_disk))}")
    for k in sorted(set(on_disk) & set(in_zip)):
        if on_disk[k] != in_zip[k]:
            problems.append(f"content differs: {k}")
    if problems:
        for p in problems:
            print("  INTEGRITY FAIL:", p)
        raise SystemExit("bundle folder and ZIP do not match")

    print(f"integrity: ZIP matches the folder exactly "
          f"({len(on_disk)} files, all SHA-256 equal)")


if __name__ == "__main__":
    main()
