# -*- coding: utf-8 -*-
"""
生成论文第5章图表 - 日级模型版本
使用真实实验数据
"""
import json
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

# 设置输出目录
OUTPUT_DIR = Path(__file__).parent
OUTPUT_DIR.mkdir(exist_ok=True)

def load_metrics():
    """加载模型指标"""
    # 日级模型指标（当前使用）
    daily_metrics = {
        "model_name": "日级XGBoost",
        "test_mae": 85.41,
        "test_mape": 12.80,
        "test_r2": 0.722,
        "train_r2": 0.909,
        "n_samples": 257712,
        "n_features": 82
    }

    # 基线模型指标
    baseline = {
        "linear": {"mae": 57.77, "mape": 25.90, "r2": 0.438, "name": "线性Voting双支路"},
        "hist_gb": {"mae": 42.90, "mape": 18.03, "r2": 0.605, "name": "HistGradientBoosting"},
    }

    return daily_metrics, baseline

def generate_radar_chart():
    """
    生成图5-4: 模型性能雷达图
    对比日级XGBoost与基线模型
    """
    daily, baseline = load_metrics()

    # 数据准备 - 使用测试集指标
    models = ['线性Voting', 'HistGB', '日级XGBoost']

    # 指标（已归一化到0-1，1为最佳）
    # R²需要归一化（假设范围0-1）
    # MAE和MAPE需要反转（越小越好）
    r2_values = [0.438, 0.605, 0.722]  # 测试R²

    # 反转MAPE（假设最大30%为最差，0%为最佳）
    mape_max = 30
    mape_values = [25.90, 18.03, 12.80]
    mape_normalized = [(mape_max - v) / mape_max for v in mape_values]

    # 反转MAE（假设最大100为最差，0为最佳）
    mae_max = 100
    mae_values = [57.77, 42.90, 85.41]
    mae_normalized = [(mae_max - v) / mae_max for v in mae_values]

    # 样本量对数归一化
    n_samples = [1949, 1949, 257712]
    log_samples = np.log10(n_samples)
    samples_normalized = [(v - min(log_samples)) / (max(log_samples) - min(log_samples)) for v in log_samples]

    categories = ['R² Score', 'MAPE(反转)', 'MAE(反转)', '样本规模']
    N = len(categories)

    # 计算角度
    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    angles += angles[:1]  # 闭合

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(projection='polar'))

    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1']

    for idx, (model, color) in enumerate(zip(models, colors)):
        values = [
            r2_values[idx],
            mape_normalized[idx],
            mae_normalized[idx],
            samples_normalized[idx]
        ]
        values += values[:1]  # 闭合

        ax.plot(angles, values, 'o-', linewidth=2, label=model, color=color)
        ax.fill(angles, values, alpha=0.15, color=color)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=11)
    ax.set_ylim(0, 1)
    ax.set_title('图5-4 模型性能综合对比雷达图\n（测试集评估）', fontsize=14, fontweight='bold', pad=20)
    ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0))
    ax.grid(True)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'fig5-4_model_radar.png', dpi=300, bbox_inches='tight')
    print(f"已生成: {OUTPUT_DIR / 'fig5-4_model_radar.png'}")
    plt.close()

def generate_metrics_bar_chart():
    """
    生成模型指标对比柱状图（补充图）
    """
    daily, baseline = load_metrics()

    models = ['线性Voting\n双支路', 'HistGradient\nBoosting', '日级\nXGBoost']
    mae_values = [57.77, 42.90, 85.41]
    mape_values = [25.90, 18.03, 12.80]
    r2_values = [0.438, 0.605, 0.722]

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1']

    # MAE
    axes[0].bar(models, mae_values, color=colors, alpha=0.8, edgecolor='black')
    axes[0].set_ylabel('MAE (元)', fontsize=12)
    axes[0].set_title('平均绝对误差 (MAE)', fontsize=12, fontweight='bold')
    axes[0].set_ylim(0, max(mae_values) * 1.2)
    for i, v in enumerate(mae_values):
        axes[0].text(i, v + 2, f'{v:.1f}', ha='center', fontsize=10)

    # MAPE
    axes[1].bar(models, mape_values, color=colors, alpha=0.8, edgecolor='black')
    axes[1].set_ylabel('MAPE (%)', fontsize=12)
    axes[1].set_title('平均绝对百分比误差 (MAPE)', fontsize=12, fontweight='bold')
    axes[1].set_ylim(0, max(mape_values) * 1.2)
    for i, v in enumerate(mape_values):
        axes[1].text(i, v + 0.5, f'{v:.1f}%', ha='center', fontsize=10)

    # R²
    axes[2].bar(models, r2_values, color=colors, alpha=0.8, edgecolor='black')
    axes[2].set_ylabel('R² Score', fontsize=12)
    axes[2].set_title('决定系数 (R²)', fontsize=12, fontweight='bold')
    axes[2].set_ylim(0, 1)
    for i, v in enumerate(r2_values):
        axes[2].text(i, v + 0.02, f'{v:.3f}', ha='center', fontsize=10)

    plt.suptitle('图5-X 基线模型与日级XGBoost性能对比', fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'fig5-x_metrics_comparison.png', dpi=300, bbox_inches='tight')
    print(f"已生成: {OUTPUT_DIR / 'fig5-x_metrics_comparison.png'}")
    plt.close()

def generate_sample_distribution():
    """
    生成样本分布图 - 展示日级模型的数据规模优势
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    models = ['基线模型\n(房源级)', '日级XGBoost\n(房源×日历日)']
    samples = [1949, 257712]
    colors = ['#FF6B6B', '#45B7D1']

    bars = ax.bar(models, samples, color=colors, alpha=0.8, edgecolor='black', width=0.5)

    # 添加数值标签
    for bar, val in zip(bars, samples):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{val:,}',
                ha='center', va='bottom', fontsize=14, fontweight='bold')

    ax.set_ylabel('训练样本数', fontsize=12)
    ax.set_title('图5-X 训练样本规模对比', fontsize=14, fontweight='bold')
    ax.set_yscale('log')  # 使用对数刻度
    ax.set_ylim(1000, 500000)

    # 添加注释
    ax.annotate('提升132倍', xy=(1, 257712), xytext=(0.5, 100000),
                arrowprops=dict(arrowstyle='->', color='red', lw=2),
                fontsize=12, color='red', fontweight='bold')

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'fig5-x_sample_distribution.png', dpi=300, bbox_inches='tight')
    print(f"已生成: {OUTPUT_DIR / 'fig5-x_sample_distribution.png'}")
    plt.close()

def print_model_summary():
    """打印模型指标摘要（供论文使用）"""
    print("\n" + "="*60)
    print("论文模型指标摘要（已更新为日级模型）")
    print("="*60)

    print("\n【日级XGBoost模型 - 项目实际使用】")
    print("- 测试MAE: 85.41元")
    print("- 测试MAPE: 12.80%")
    print("- 测试R2: 0.722")
    print("- 训练样本: 257,712行（房源×日历日）")
    print("- 特征维度: 82维（含14维日期特征）")

    print("\n【基线模型对比】")
    print("- 线性Voting双支路: MAE=57.77, MAPE=25.90%, R2=0.438")
    print("- HistGradientBoosting: MAE=42.90, MAPE=18.03%, R2=0.605")

    print("\n【论文需更新的描述】")
    print("1. 表5-4: 使用日级XGBoost指标（MAE=85.41, MAPE=12.80%, R2=0.722）")
    print("2. 表5-6: 对比表更新为'线性Voting vs HistGB vs 日级XGBoost'")
    print("3. 图5-4: 雷达图已更新（使用上述真实数据）")
    print("4. 摘要: 更新模型指标和样本量描述")
    print("5. 第5章正文: 删除'房源级'描述，统一为'日级模型'")
    print("="*60)

if __name__ == "__main__":
    print("开始生成论文图表...")
    print(f"输出目录: {OUTPUT_DIR}")
    print()

    # 生成图表
    generate_radar_chart()
    generate_metrics_bar_chart()
    generate_sample_distribution()

    # 打印摘要
    print_model_summary()

    print("\n所有图表生成完成！")
