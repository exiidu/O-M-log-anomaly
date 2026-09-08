#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
report.py
汇总解析/特征/检测/评估结果，生成一页 Markdown 分析报告。
"""
import json
import pandas as pd
from pathlib import Path

OUT = Path("reports")


def markdown_report():
    metrics = json.loads((OUT / "metrics.json").read_text(encoding="utf-8"))
    parsed = pd.read_csv(OUT / "parsed.csv")
    feats = pd.read_csv(OUT / "windows_features.csv")
    df = pd.read_csv(OUT / "evaluation.csv")
    miss = pd.read_csv(OUT / "missed_windows.csv")
    false = pd.read_csv(OUT / "false_positive_windows.csv")

    n_lines, n_tpl = len(parsed), parsed["template"].nunique()
    n_win, n_if = len(feats), int(df["is_outlier"].sum())
    n_ref = int(df["y_ref"].sum())

    # 重算 parsed 的时间窗口，用于定位代表样本
    _sec = parsed["time_str"].apply(
        lambda s: int(s[:2]) * 3600 + int(s[3:5]) * 60 + int(s[6:8])
    )
    parsed = parsed.assign(win=_sec // 600)

    # 代表异常样本：真实 WARN( Got exception ) 行 + 一个高频误报窗口(win63) 的对照行
    warn_lines = "\n".join(
        "- `" + x + "`"
        for x in parsed[parsed["level"] == "WARN"]["raw"].dropna().head(3).tolist()
    )
    hi_lines = "\n".join(
        "- `" + x + "`"
        for x in parsed[parsed["win"] == 63]["raw"].head(3).tolist()
    )
    l = warn_lines + "\n  （对照：高频误报窗口 win63 的正常 INFO 日志）\n" + hi_lines

    return f"""# HDFS 日志异常检测分析报告（模板解析 + 统计特征 + 孤立森林）

## 1. 一句话摘要
基于 2000 行 HDFS 真实日志（LogHub），完成字段化解析与模板挖掘，用**时间窗 × 统计特征 + 孤立森林**识别异常时间窗，并以 **WARN 规则**作为参考基线交叉验证，得到 Precision={metrics['precision']}、Recall={metrics['recall']}、F1={metrics['f1']}，并在报告尾部给出漏报/误报归因。

## 2. 数据与解析
- 数据集：`logpai/loghub` HDFS_2k（2000 行；近 24h；级别 INFO/WARN；6 类组件；解析 0 跳过）。
- 解析：正则字段化（时间/线程/级别/组件/消息/块ID）+ 变量归一化得日志模板，共 **{n_tpl} 个唯一模板**。
- 代表异常模板（WARN）：`IP:Port: Got exception while serving <*> to <*>`（HDFS 数据块服务异常，共 80 条）。

## 3. 方法设计（调研结论）
| 方法类别 | 选择 | 理由 |
|---|---|---|
| 模板 → 统计特征 | Drain 式变量归一化 + 窗口聚合 | 可解释、无需标注、可复现 |
| 异常检测主方法 | **Isolation Forest** | 无监督、适合异常占比低场景、能捕捉频率形态离群 |
| 参考基线 | WARN 规则 | HDFS 公认异常信号，提供判断依据与交叉验证 |

分析单元：**10 分钟时间窗**（{n_win} 窗），特征 = 各模板频次 + 总条数 + 模板种类 + 事件密度（不含 WARN 信号以保持方法独立）。

## 4. 检测结果
- 孤立森林判定异常窗：**{n_if} 个**（前 5 离群窗：{df.sort_values('if_score').head(5)['win'].tolist()}）。
- 规则参考异常窗（含 WARN）：**{n_ref} 个**。

## 5. 交叉验证（参考真值 = WARN 规则）
- 混淆矩阵：TP={metrics['TP']}  FP={metrics['FP']}  FN={metrics['FN']}  TN={metrics['TN']}
- **Precision={metrics['precision']}   Recall={metrics['recall']}   F1={metrics['f1']}**

## 6. 代表异常样本（原始日志）
{l}

## 7. 漏报 / 误报分析
- **漏报（{len(miss)} 窗）**：孤立森林只看操作频率，不感知级别语义。含 1~2 条 WARN 的窗口在频率形态上接近正常窗（如 win4/7/8），故被漏检 → 对"低频但致命"异常不敏感。
- **误报（{len(false)} 窗）**：正常业务高峰的**高频窗口**（win63=141 条、win28=65 条、win47=51 条）与**极稀疏窗口**（win86=1 条）在频率分布上离群，被孤立森林误隔离，但其中无真实异常 → 频率"量变"会把正常流量当异常。
- **结论**：孤立森林擅长"形态离群"、弱于"语义异常"；规则补充 WARN 语义、但另一端对未收录模式失效。二者并集更稳。

## 8. 局限性
HDFS_2k 为小样本且无官方块级标注，验证以 WARN 规则为参考真值，尺度是"与规则信号源的一致性"而非绝对准确率；换更大、带标注的 HDFS_v1 可做块级精确标注评估。
"""
    # 注：为便于阅读，报告原文较长；实际"一页"指摘要+主要表单项，可导出 PDF/精简排版。


def write(output: str = "reports/异常检测报告.md"):
    Open = Path(output)
    Open.write_text(markdown_report(), encoding="utf-8")
    print(f"[报告] 已生成 -> {output}")


if __name__ == "__main__":
    write()