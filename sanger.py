from Bio import SeqIO
import matplotlib.pyplot as plt
import numpy as np

def plot_ab1_trace_aligned(filepath, start=None, end=None):
    # 读取 ab1 文件
    record = SeqIO.read(filepath, "abi")

    # 读取 trace 数据（4通道）
    trace = {
        'G': np.array(record.annotations['abif_raw']['DATA9'], dtype=np.int32),
        'A': np.array(record.annotations['abif_raw']['DATA10'], dtype=np.int32),
        'T': np.array(record.annotations['abif_raw']['DATA11'], dtype=np.int32),
        'C': np.array(record.annotations['abif_raw']['DATA12'], dtype=np.int32)
    }

    # 主叫碱基位置信息与序列
    peak_locations = record.annotations['abif_raw']['PLOC2']
    called_bases = str(record.seq)
    quality_scores = record.letter_annotations['phred_quality']

    total_bases = len(peak_locations)
    
    # 设置默认范围为全长
    if start is None:
        start = 0
    if end is None or end > total_bases:
        end = total_bases

    show_indices = list(range(start, end))
    show_peaks = peak_locations[start:end]
    show_bases = called_bases[start:end]
    show_quality = quality_scores[start:end]

    # 构建碱基编号为横坐标的对齐曲线（插值）
    base_x = np.arange(start, end)
    interp_x = np.linspace(base_x[0], base_x[-1], show_peaks[-1] - show_peaks[0])

    aligned_trace = {}
    for base, raw in trace.items():
        raw_segment = raw[show_peaks[0]:show_peaks[-1]]
        aligned_trace[base] = np.interp(interp_x, 
                                        np.linspace(base_x[0], base_x[-1], len(raw_segment)), 
                                        raw_segment)

    # 绘图
    plt.figure(figsize=(16, 6))
    base_colors = {'A': 'green', 'T': 'red', 'G': 'black', 'C': 'blue'}

    # 画 trace 曲线
    for base, trace_y in aligned_trace.items():
        plt.plot(interp_x, trace_y, color=base_colors[base], label=f'{base} trace', alpha=0.6)

    # 标注碱基
    for i, (x, base, qual) in enumerate(zip(base_x, show_bases, show_quality)):
        trace_vals_at_x = [aligned_trace[b][int((x - base_x[0]) / (base_x[-1] - base_x[0]) * len(interp_x))] for b in "ATGC"]
        max_y = max(trace_vals_at_x)
        plt.text(x, max_y + 150, base, ha='center', fontsize=9, color=base_colors.get(base, 'gray'))

    plt.xlim(base_x[0] - 1, base_x[-1] + 1)
    plt.ylim(0, max([max(v) for v in aligned_trace.values()]) + 300)
    plt.xlabel("Base Index")
    plt.ylabel("Fluorescent Intensity")
    plt.title("Sanger Sequencing Trace (Base-Aligned, Full Range)")
    plt.grid(True, linestyle="--", alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.show()