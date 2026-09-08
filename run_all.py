#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
run_all.py
一键复现完整流程：解析 -> 特征 -> 孤立森林检测 -> 规则参考基线 -> 评估 -> 报告。
"""
import subprocess
import sys
from pathlib import Path

PY = Path(".venv/Scripts/python.exe" if Path(".venv").exists() else sys.executable)
STEPS = [
    ("解析日志 (Drain 式模板解析)", ["src/parse_drain.py", "data/HDFS_2k.log", "reports"]),
    ("构建窗口统计特征", ["src/feature_build.py", "--input", "reports/parsed.csv", "--output", "reports/windows_features.csv"]),
    ("孤立森林异常检测", ["src/detect_if.py", "--input", "reports/windows_features.csv", "--output", "reports/outliers_if.csv"]),
    ("规则参考基线", ["src/detect_rules.py", "--input", "reports/windows_features.csv", "--output", "reports/rule_reference.csv"]),
    ("交叉验证与评估 (P/R/F1)", ["src/evaluate.py", "--if_out", "reports/outliers_if.csv", "--ref", "reports/rule_reference.csv", "--feats", "reports/windows_features.csv"]),
    ("生成分析报告", ["src/report.py"]),
    ("生成 HTML 数据报告", ["src/report_html.py", "--input", "reports/parsed.csv", "--output", "reports/日志解析统计与异常检测报告.html", "--with-anomaly"]),
]

if __name__ == "__main__":
    for name, args in STEPS:
        print(f"\n===== {name} =====")
        r = subprocess.run([str(PY), *args], cwd=Path(__file__).parent)
        if r.returncode != 0:
            sys.exit(f"[失败] {name}")
    print("\n[完成] 全部流程执行成功。报告见 reports/异常检测报告.md，可视化见 reports/日志解析统计与异常检测报告.html")