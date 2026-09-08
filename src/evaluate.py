#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
evaluate.py
以「规则基线（WARN→异常）」为参考真值，评估孤立森林检测结果，
输出精确率 / 召回率 / F1、混淆矩阵，以及漏报与误报窗口明细。

局限声明：HDFS_2k 无官方块级标注，此处以 WARN 规则作为参考真值，
因此评估尺度是「IF 与规则信号源的一致性」而非绝对准确率。
"""
import argparse
import pandas as pd
from pathlib import Path
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support


def evaluate(if_csv: str, ref_csv: str, feats_csv: str, out_dir: str = "reports"):
    pred = pd.read_csv(if_csv)[["win", "is_outlier", "if_score"]]
    ref = pd.read_csv(ref_csv)[["win", "y_ref"]]
    df = pred.merge(ref, on="win").merge(pd.read_csv(feats_csv), on="win")

    y_true = df["y_ref"].values
    y_pred = df["is_outlier"].values
    p, r, f1, _ = precision_recall_fscore_support(y_true, y_pred, average="binary")
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()

    metrics = {
        "TP": int(tp), "FP": int(fp), "FN": int(fn), "TN": int(tn),
        "precision": round(float(p), 3),
        "recall": round(float(r), 3),
        "f1": round(float(f1), 3),
    }
    print("[评估] 参考真值=WARN规则")
    print(f"  混淆矩阵: TP={tp} FP={fp} FN={fn} TN={tn}")
    print(f"  Precision={metrics['precision']} Recall={metrics['recall']} F1={metrics['f1']}")

    # 漏报：参考为异常但 IF 未检出
    miss = df[(df.y_ref == 1) & (df.is_outlier == 0)]
    # 误报：IF 检出但参考为正常
    false = df[(df.y_ref == 0) & (df.is_outlier == 1)]

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    df.to_csv(Path(out_dir) / "evaluation.csv", index=False, encoding="utf-8-sig")
    miss.to_csv(Path(out_dir) / "missed_windows.csv", index=False, encoding="utf-8-sig")
    false.to_csv(Path(out_dir) / "false_positive_windows.csv", index=False, encoding="utf-8-sig")

    print(f"\n[漏报] 参考异常未被 IF 检出: {len(miss)} 个窗口")
    if len(miss):
        print(miss[["win", "n_warn", "n_logs", "n_uniq", "if_score"]].head(8).to_string(index=False))
    print(f"\n[误报] IF 检出但参考正常: {len(false)} 个窗口")
    if len(false):
        print(false[["win", "n_logs", "n_uniq", "density", "if_score"]].head(8).to_string(index=False))

    # 保存指标
    pd.Series(metrics).to_json(Path(out_dir) / "metrics.json")
    return metrics, df


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--if_out", default="reports/outliers_if.csv")
    ap.add_argument("--ref", default="reports/rule_reference.csv")
    ap.add_argument("--feats", default="reports/windows_features.csv")
    args = ap.parse_args()
    evaluate(args.if_out, args.ref, args.feats)