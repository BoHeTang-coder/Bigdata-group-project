import pandas as pd
import numpy as np
import time
import os
import pyarrow.parquet as pq
from multiprocessing import Pool
import matplotlib.pyplot as plt

# ================= 配置区 =================
# 这里填写你三个文件的具体路径
FILES = [
    r'otp_2023.parquet',
    r'otp_2024.parquet',
    r'otp_2025.parquet'
]

PROCESS_LIST = [1, 2, 4, 8]  # 要测试的进程数
REPEAT = 3                   # 每组重复次数
CHUNK_SIZE = 150000          # 分块大小（行数），防止内存溢出

# 基准（自动校验）
EXPECTED_DELAYED = 4371303
EXPECTED_TOTAL = 20588134

# ================= 核心计算函数 =================
def process_chunk(args):
    df_chunk, chunk_id = args

    # 1. 分母条件（未取消、未备降、ArrDel15非空）
    valid_mask = (df_chunk['Cancelled'] == 0) & (df_chunk['Diverted'] == 0) & (df_chunk['ArrDel15'].notna())
    valid_df = df_chunk[valid_mask].copy()

    if len(valid_df) == 0:
        return None

    # 2. 模拟计算密集型负载
    valid_df['delay_calc'] = valid_df['ArrDelayMinutes'].apply(
        lambda x: sum((x * i) % 100 for i in range(100)) if pd.notna(x) else 0
    )

    # 3. 局部聚合
    delayed_count = int((valid_df['ArrDel15'] == 1).sum())
    total_count = len(valid_df)

    airport_partial = valid_df.groupby('Origin').agg(
        delayed=('ArrDel15', lambda x: (x == 1).sum()),
        total=('ArrDel15', 'count')
    )

    return {
        'delayed_count': delayed_count,
        'total_count': total_count,
        'airport_partial': airport_partial
    }

def read_and_chunk(file_path, chunk_size):
    """按 row group 读取 Parquet 并切块"""
    pf = pq.ParquetFile(file_path)
    chunks = []
    for i in range(pf.num_row_groups):
        df = pf.read_row_group(i).to_pandas()
        for j in range(0, len(df), chunk_size):
            chunks.append((df.iloc[j:j+chunk_size], f"{os.path.basename(file_path)}_{i}_{j}"))
    return chunks

def run_parallel(chunks, workers):
    """运行并行逻辑，返回耗时和统计结果"""
    t0 = time.perf_counter()
    with Pool(processes=workers) as pool:
        results = pool.map(process_chunk, chunks)

    total_delayed = 0
    total_valid = 0
    airport_tables = []

    for r in results:
        if r is not None:
            total_delayed += r['delayed_count']
            total_valid += r['total_count']
            airport_tables.append(r['airport_partial'])

    final_airport = pd.concat(airport_tables).groupby(level=0).sum()
    elapsed = time.perf_counter() - t0
    return elapsed, total_delayed, total_valid, final_airport

def main():
    print("正在读取并分块3年的全量数据（约 570MB）...")
    all_chunks = []
    for f in FILES:
        if not os.path.exists(f):
            print(f"找不到文件: {f}，请检查路径！")
            return
        all_chunks.extend(read_and_chunk(f, CHUNK_SIZE))
    print(f"总共切分为 {len(all_chunks)} 个数据块。开始实验...\n")

    results = []

    # 预热
    print("正在进行预热（防止冷启动干扰）...")
    run_parallel(all_chunks[:3], 2)

    # 循环测试 1, 2, 4, 8 进程
    for p in PROCESS_LIST:
        print(f"\n--- 测试 {p} 进程 (跑 {REPEAT} 次取平均) ---")
        p_times = []
        for i in range(REPEAT):
            elapsed, delayed, total, airport_df = run_parallel(all_chunks, p)
            p_times.append(elapsed)
            print(f"第 {i+1} 次耗时: {elapsed:.2f} 秒")

        avg_time = np.mean(p_times)
        speedup = 1.0 if p == 1 else results[0]['time'] / avg_time
        efficiency = speedup / p

        results.append({
            'workers': p,
            'time': avg_time,
            'speedup': speedup,
            'efficiency': efficiency,
            'delayed': delayed,
            'total': total,
            'rate': delayed / total * 100
        })

        print(f"【{p} 进程平均耗时】: {avg_time:.2f} 秒 | 加速比: {speedup:.2f}x | 效率: {efficiency:.1%}")
        print(f"【结果核对】 分子: {delayed} | 分母: {total} | 延误率: {delayed/total*100:.4f}%")

        # 自动校验全量总数
        if p == 1:
            print("\n--- 对齐基准校验 ---")
            if delayed == EXPECTED_DELAYED and total == EXPECTED_TOTAL:
                print("一致")
            else:
                print("不一致，请检查数据口径或文件是否齐全。")

    # 保存结果到 CSV
    df_res = pd.DataFrame(results)
    df_res.to_csv("speedup_results.csv", index=False)
    print("\n实验结果已保存至 speedup_results.csv")

    # 画图
    plt.figure(figsize=(8, 6))
    plt.plot(df_res['workers'], df_res['speedup'], marker='o', linewidth=2, label='Experimental Speedup')
    plt.plot(df_res['workers'], df_res['workers'], linestyle='--', color='gray', label='Ideal Linear Speedup')
    plt.title('Flight Data Processing Speedup (Parallel For Loop)')
    plt.xlabel('Number of Processes')
    plt.ylabel('Speedup (T_1 / T_p)')
    plt.xticks(PROCESS_LIST)
    plt.grid(True, linestyle=':', alpha=0.7)
    plt.legend()
    plt.savefig("speedup_curve.png", dpi=150, bbox_inches='tight')
    print("加速比曲线图已保存至 speedup_curve.png")

if __name__ == '__main__':
    main()