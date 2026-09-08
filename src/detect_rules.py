#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
detect_rules.py
规则参考基线：基于 WARN 级别（HDFS "Got exception while serving block"）判断异常。
在无官方块级标注的小样本数据（HDFS_2k）上，本规则被用作「参考真值」参与评估，
同时为孤立森林检出的异常提供可读的判断依据。

说明：由于该规则本身是评估中的参考真值，报告会如实声明此局限——
即以 WARN 为真值时，二者共用同一信号源的交叉验证尺度需要谨慎解读。
"""
import argparse
import pandas as pd
from pathlib import Path


def build_reference(input_csv: str, output_csv: str):
    feats = pd.read_csv(input_csv)
    ref = pd.DataFrame({
        "win": feats["win"],
        "n_warn": feats["n_warn"],
        "y_ref": (feats["n_warn"] > 0).astype(int),  # 含 WARN => 视为异常窗口
    })
    Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
    ref.to_csv(output_csv, index=False, encoding="utf-8-sig")
    n = int(ref["y_ref"].sum())
    print(f"[规则] 参考异常窗口 {n}/{len(ref)} ({n/len(ref):.1%}) -> {output_csv}")
    return ref


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="reports/windows_features.csv")
    ap.add_argument("--output", default="reports/rule_reference.csv")
    args = ap.parse_args()
    build_reference(args.input, args.output)