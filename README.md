# 智能运维：让日志开口说话

基于 LogHub HDFS 真实日志，完成 **日志解析 → 统计特征 → 孤立森林异常检测 → 规则交叉验证** 的最小实验，并输出异常检测分析报告。工具链同时支持对**任意格式日志**做解析与统计（桌面交互窗口一键出报告）。

- 解析：正则字段化 + Drain 式变量归一化 → 日志模板，**自动识别 HDFS 与通用 `[时间][级别][来源] 消息` 两种格式**
- 检测：10 分钟时间窗 × 统计特征 + **Isolation Forest**（无监督，可复现）
- 验证：以 **WARN 规则**（`Got exception while serving block`）为参考基线，输出 Precision / Recall / F1 与漏报误报归因
- 交互：`log_parser_gui.py` 桌面窗口 —— 选文件 → 一键解析统计 → 生成并打开 HTML 报告

## 环境要求

- Python ≥ 3.10
- 依赖见 `requirement.txt`（pandas / numpy / scikit-learn / matplotlib）
- 桌面窗口基于内置 Tkinter，无需额外安装

## 使用方式一：桌面窗口（推荐，免命令行）

```bash
# Windows：直接双击
run_gui.bat

# 或手动启动
.venv\Scripts\python log_parser_gui.py
```

窗口中依次：**1. 选择日志文件 → 2. 解析并生成 HTML 报告 → 3. 在浏览器打开报告**。
解析支持 HDFS 与通用 `[时间][级别][来源:行号] 消息` 格式；产物写入 `reports/`。

## 使用方式二：命令行 / 一键复现

```bash
# 1. 创建虚拟环境并安装依赖
python -m venv .venv
.venv/Scripts/pip install -r requirement.txt    # Windows
# .venv/bin/pip install -r requirement.txt      # macOS / Linux

# 2. 数据（来自 logpai/loghub:HDFS_2k，已放入 data/）

# 3. 一键复现 HDFS 完整流程（解析→特征→检测→评估→报告）
.venv/Scripts/python run_all.py                 # Windows
# .venv/bin/python run_all.py                   # macOS / Linux
```

### 解析你自己的日志（纯统计报告）

```bash
# ① 解析（自动识别格式），得到 parsed CSV
.venv/Scripts/python src/parse_drain.py   your.log   reports

# ② 生成 HTML 统计报告（无异常检测，适合单组件/无异常信号的日志）
.venv/Scripts/python src/report_html.py \
    --input reports/parsed.csv \
    --output reports/your_report.html \
    --title "我的日志解析统计报告"
```

`report_html.py` 参数：`--input`（解析结果）、`--output`（报告路径）、`--title`（标题）、`--with-anomaly`（追加异常检测板块，需 metrics/evaluation 与输入匹配时使用）。

## 分步运行（等价于 run_all.py）

```bash
.venv/Scripts/python src/parse_drain.py    data/HDFS_2k.log   reports   # 解析，→ REPORTS/parsed.csv
.venv/Scripts/python src/feature_build.py                            # 窗口特征 → windows_features.csv
.venv/Scripts/python src/detect_if.py                                # 孤立森林 → outliers_if.csv
.venv/Scripts/python src/detect_rules.py                             # 规则参考基线 → rule_reference.csv
.venv/Scripts/python src/evaluate.py                                 # P/R/F1 + 混淆矩阵
.venv/Scripts/python src/report.py                                   # 一页分析报告 → 异常检测报告.md
.venv/Scripts/python src/report_html.py --with-anomaly               # HTML 数据报告（统计+异常）
```

> HDFS 流程结束后，用浏览器打开 `reports/日志解析统计与异常检测报告.html`（带可视化图表：时间/级别/来源/模板/异常结果）。

## 目录结构

```
├── run_all.py           # 一键复现 HDFS 全流程
├── log_parser_gui.py    # 桌面交互窗口（解析任意日志 → HTML 报告）
├── run_gui.bat          # Windows 双击启动桌面窗口
├── requirement.txt
├── data/HDFS_2k.log     # 数据集（来源 logpai/loghub）
├── logs/                # 开发日志.md、日程.md
├── src/
│   ├── parse_drain.py   # 模板解析（HDFS + 通用格式自动识别）
│   ├── feature_build.py # 窗口统计特征
│   ├── detect_if.py     # Isolation Forest
│   ├── detect_rules.py  # WARN 规则参考基线
│   ├── evaluate.py      # P/R/F1、混淆矩阵、漏报/误报
│   ├── report.py        # 一页分析报告
│   └── report_html.py   # HTML 报告（可指定输入/标题，可含异常板块）
└── reports/             # 运行产物（parsed CSV + 报告，可随时重新生成）
```

## 数据集与来源

- 数据：`logpai/loghub` → `HDFS/HDFS_2k.log`（2000 行，2008-11 HDFS 数据块读写日志；级别 INFO/WARN）
- 协议：LogHub（引用请参见官方说明）；仅用于本赛题学习研究。

## 主要结论（详见 reports/异常检测报告.md）

- 识别出 16 个日志模板；WARN 全部为 `Got exception while serving block`（HDFS 数据块服务异常信号，80 条）。
- 孤立森林判定 25/124 个异常窗；规则参考 42/124 个。
- 交叉验证：Precision≈0.44、Recall≈0.26、F1≈0.33。
- 漏报主因：孤立森林无级别语义，含少量 WARN 的低频异常窗形态与正常窗相近；
  误报主因：正常高峰高频窗与极稀疏窗在分布上离群，被误隔离。

## 局限性

HDFS_2k 为小样本且无官方块级标注，验证以 WARN 规则为参考真值，尺度为与规则信号源的一致性而非绝对准确率。如需更强验证，可换带块级标注的 HDFS_v1（约 11M 行）并采用块级特征。
