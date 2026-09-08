#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
feature_build.py
将解析后的日志构建为「时间窗口」粒度的统计特征矩阵。

分析单元：10 分钟时间窗（window_sec=600）。
每个窗口聚合特征：
  - n_logs       日志总条数
  - n_uniq       不同模板种类数
  - n_warn       WARN 级别条数（HDFS "Got exception" 异常信号）
  - density      事件密度（条数 / 窗口活跃跨度秒）
  - t_<eventid>  各日志模板在窗口内的出现频次（事件分布向量）
"""
import argparse
import pandas as pd
from pathlib import Path

WINDOW_SEC = 600


def build(input_csv: str, output_csv: str, window_sec: int = WINDOW_SEC) -> pd.DataFrame:
    df = pd.read_csv(input_csv)
    sec = df["time_str"].apply(
        lambda s: int(s[:2]) * 3600 + int(s[3:5]) * 60 + int(s[6:8])
    )
    df = df.assign(sec=sec, win=(sec // window_sec), is_warn=(df["level"] == "WARN").astype(int))

    rows = []
    for win, g in df.groupby("win"):
        # 窗口内各模板频次
        tcnt = g["eventid"].value_counts().to_dict()
        n = len(g)
        n_uniq = len(tcnt)
        n_warn = int(g["is_warn"].sum())
        active = int(g["sec"].max() - g["sec"].min()) + 1
        rows.append({
            "win": int(win),
            "n_logs": n,
            "n_uniq": n_uniq,
            "n_warn": n_warn,
            "warn_ratio": round(n_warn / n, 4) if n else 0.0,
            "density": round(n / active, 4) if active else 0.0,
            **{f"t_{k}": v for k, v in tcnt.items()},
        })
    feats = pd.DataFrame(rows).sort_values("win").reset_index(drop=True)
    feats = feats.fillna(0)
    Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
    feats.to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"[特征] 窗口数 {len(feats)} -> {output_csv}")
    return feats


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="reports/parsed.csv")
    ap.add_argument("--output", default="reports/windows_features.csv")
    ap.add_argument("--window", type=int, default=WINDOW_SEC)
    args = ap.parse_args()
    build(args.input, args.output, args.window)