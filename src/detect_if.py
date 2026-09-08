#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
detect_if.py
孤立森林（Isolation Forest）异常检测。

设计说明：
- 输入特征仅使用「操作频率类」特征（日志条数 / 模板种类 / 事件密度 / 各模板频次），
  故意不包含 n_warn/warn_ratio，以保持与规则方法（WARN 信号源）相互独立，
  从而能检验两种方法能否发现彼此遗漏的异常窗口。
- 对特征做标准化后送入 IsolationForest。
- 固定 random_state 保证结果可复现。
"""
import argparse
import pandas as pd
from pathlib import Path
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest


def detect(input_csv: str, output_csv: str, contamination: float = 0.2):
    feats = pd.read_csv(input_csv)
    # 排除非特征列与 WARN 相关列，保持方法独立性
    drop_cols = [c for c in ["win", "n_warn", "warn_ratio"] if c in feats.columns]
    X = feats.drop(columns=drop_cols)
    X = X.loc[:, X.nunique() > 1]  # 剔除常数列

    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)

    model = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        random_state=42,
        n_jobs=-1,
    )
    pred = model.fit_predict(Xs)          # 1=正常, -1=异常
    score = model.score_samples(Xs)       # 越大越正常
    model.feature_names_in_ = list(X.columns)

    out = pd.DataFrame({
        "win": feats["win"],
        "if_score": score,
        "if_pred": pred,                  # -1 => 异常
        "is_outlier": (pred == -1).astype(int),
    })
    out["is_outlier_rank"] = out["if_score"].rank(ascending=True, method="min").astype(int)
    Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_csv, index=False, encoding="utf-8-sig")

    n_out = int(out["is_outlier"].sum())
    print(f"[IF] 窗口数 {len(out)}，判定异常窗口 {n_out} ({n_out/len(out):.1%})")
    print("[IF] top5 离群窗口:", out.sort_values("is_outlier_rank").head(5)["win"].tolist())
    return out, model


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="reports/windows_features.csv")
    ap.add_argument("--output", default="reports/outliers_if.csv")
    ap.add_argument("--contamination", type=float, default=0.2)
    args = ap.parse_args()
    detect(args.input, args.output, args.contamination)