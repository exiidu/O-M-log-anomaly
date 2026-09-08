#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
parse_drain.py
HDFS 日志解析模块（Drain 式模板解析）。
- 对原始日志行进行字段化（时间戳 / 线程 ID / 级别 / 组件 / 消息 / 块 ID）
- 对消息做变量归一化，聚合出日志模板（eventid -> template）

以命令行为入口时，输出解析结果 CSV 并打印基础统计。
"""
import re
import hashlib
import pandas as pd
from pathlib import Path

# HDFS 日志行格式示例：
#  081109 203615 148 INFO dfs.DataNode$PacketResponder: PacketResponder 1 for block blk_38865049064139660 terminating
_LINE_RE = re.compile(
    r"^(?P<yyyymm>\d{6})\s+(?P<time>\d{6})\s+(?P<tid>\d+)\s+"
    r"(?P<level>\w+)\s+(?P<component>[^:]+):\s*(?P<message>.*)$"
)
_BLK_RE = re.compile(r"blk_(-?\d+)")

# 通用日志行格式：
#  [2026-09-07 13:40:41.856] [off] [taskbarattributeworker.cpp:1296] message
_GEN_RE = re.compile(
    r"^\[\s*(?P<ts>[\d\-\s:.]+)\s*\]\s*"
    r"\[\s*(?P<level>[^\]]+?)\s*\]\s*"
    r"\[\s*(?P<source>[^\]:]+)(?::\s*(?P<sline>\d+))?\s*\]\s*"
    r"(?P<message>.*)$"
)

# 变量 token 归一化模式（以顺序优先级匹配），命中即替换为 <*>
_VAR_RE = re.compile(
    r"\b(?:blk_)?-?\d+\b"          # 数值 / blk_id
    r"|\d+\.\d+\.\d+\.\d+(?::\d+)?"  # IP / IP:端口
    r"|0x[0-9a-fA-F]+"
    r"|(?:[A-Za-z]:)?[\\/][\w\\/.-]+"  # 路径
)


def _tm(x):
    """数值时间戳 -> HH:MM:SS 字符串，便于排序。"""
    x = str(x).zfill(6)
    return f"{x[0:2]}:{x[2:4]}:{x[4:6]}"


def _fetch_time(time_str: str) -> str:
    """从通用时间串（可含日期）提取 HH:MM:SS(.mmm)；无时间则回退 00:00:00。"""
    m = re.search(r"(\d{2}):(\d{2}):(\d{2})", time_str or "")
    return f"{m.group(1)}:{m.group(2)}:{m.group(3)}" if m else "00:00:00"


def parse_line(line: str) -> dict | None:
    """解析单行日志，返回字段字典；非标准行返回 None。

    先尝试 HDFS 格式，再尝试通用 `[time][level][source] message` 格式。
    """
    line = line.rstrip("\n")
    m = _LINE_RE.match(line)
    if m:
        msg = m.group("message")
        blk = _BLK_RE.search(line)
        return {
            "yyyymm": m.group("yyyymm"),
            "time_str": _tm(m.group("time")),
            "tid": int(m.group("tid")),
            "level": m.group("level"),
            "component": m.group("component"),
            "message": msg,
            "raw": line,
            "blockid": f"blk_{blk.group(1)}" if blk else None,
        }
    g = _GEN_RE.match(line)
    if g:
        src = g.group("source")
        sline = g.group("sline")
        component = re.sub(r"[\\/]+$", "", src)  # 去除尾部路径分隔符
        return {
            "yyyymm": re.sub(r"-", "", (g.group("ts") or "00000000")[:10]),
            "time_str": _fetch_time(g.group("ts")),
            "tid": int(sline) if sline else None,
            "level": g.group("level").strip(),
            "component": component.strip(),
            "message": g.group("message").strip(),
            "raw": line,
            "blockid": None,
        }
    return None


def normalize_template(message: str) -> str:
    """将消息中的变量（数字、IP、路径等）替换为 <*>，得到模板串。"""
    return _VAR_RE.sub("<*>", message)


def event_id(template: str) -> int:
    return int(hashlib.md5(template.encode("utf-8")).hexdigest()[:8], 16)


def parse_file(path: str | Path) -> pd.DataFrame:
    """解析整个日志文件，返回 (row 记录 + eventid + template) 的 DataFrame。"""
    rows, skipped = [], 0
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for ln in f:
            rec = parse_line(ln)
            if rec is None:
                skipped += 1
                continue
            rec["template"] = normalize_template(rec["message"])
            rec["eventid"] = event_id(rec["template"])
            rows.append(rec)
    df = pd.DataFrame(rows)
    return df, skipped


def run(input_path, output_dir):
    df, skipped = parse_file(input_path)
    print(f"[解析] 共解析 {len(df)} 行，跳过非标准行 {skipped}")
    if df.empty:
        raise SystemExit("无有效日志行")
    print("\n== 级别分布 ==")
    print(df["level"].value_counts())
    print("\n== 组件 Top10 ==")
    print(df["component"].value_counts().head(10))
    print(f"\n== 模板数 ==")
    print(f"唯一模板: {df['template'].nunique()}  唯一块: {df['blockid'].nunique()}")
    out = Path(output_dir) / "parsed.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\n[输出] 解析结果 -> {out}")
    return df


if __name__ == "__main__":
    import sys
    run(sys.argv[1] if len(sys.argv) > 1 else "data/HDFS_2k.log", "reports")