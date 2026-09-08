#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
report_html.py
生成一份自包含的 HTML 数据报告（可直接用浏览器打开）：
  一、概览        二、时间分布    三、级别分布
  四、来源(组件)   五、模板 Top    六、异常检测结果（IF vs 规则 + P/R/F1）
  七、漏报/误报    八、方法说明
统计「时间 / 级别 / 来源」等关键字段由归档后的 parsed 重新计算。
"""
import html
import json
import argparse
import pandas as pd
from pathlib import Path

OUT = Path("reports")


def _escap(x):
    return html.escape(str(x))


def bar(value, maxv, color="#4e8cff", label=None):
    pct = (value / maxv * 100) if maxv else 0
    lab = label if label is not None else str(value)
    return (f'<div class="barrow"><div class="barlab">{_escap(lab)}</div>'
            f'<div class="bar"><div class="barfill" style="width:{pct:.1f}%;background:{color}"></div></div></div>')


def build_html(input_csv="reports/parsed.csv", title="日志解析统计与异常检测报告", include_anomaly=False):
    parsed = pd.read_csv(input_csv)
    has_anom = include_anomaly and (OUT / "metrics.json").exists() and (OUT / "evaluation.csv").exists()
    metrics, ev = None, None
    if has_anom:
        metrics = json.loads((OUT / "metrics.json").read_text(encoding="utf-8"))
        ev = pd.read_csv(OUT / "evaluation.csv")

    n = len(parsed)
    dt = parsed["yyyymm"].astype(str) + " " + parsed["time_str"]
    sec = parsed["time_str"].apply(
        lambda s: int(s[:2]) * 3600 + int(s[3:5]) * 60 + int(s[6:8]))
    parsed = parsed.assign(hour=sec // 3600)

    # 时间
    hour_cnt = parsed["hour"].value_counts().sort_index()
    m_h = int(hour_cnt.max())
    hour_bars = "".join(
        f'<div class="tw"><div class="thour">{int(h)}时</div>{bar(int(c), m_h)}</div>'
        for h, c in hour_cnt.items())

    # 级别
    lv = parsed["level"].value_counts()
    ml = int(lv.max())
    lv_bars = "".join(
        bar(c, ml, "#e05555" if lvl == "WARN" else "#4e8cff",
            label=f"{lvl} ({c}, {c/n*100:.1f}%)")
        for lvl, c in lv.items()
    )

    # 来源
    comp = parsed["component"].value_counts().head(8)
    mc = int(comp.max())
    cross = parsed.pivot_table(index="component", columns="level", values="raw",
                               aggfunc="count", fill_value=0)
    cross_html = cross.to_html(classes="tbl", border=0)

    # 模板
    tpl = parsed["template"].value_counts().head(8)
    tpl_rows = "".join(
        f"<tr><td class='mono'>{_escap(t)}</td><td>{int(v)}</td></tr>"
        for t, v in tpl.items())

    # 异常报告板块（有异常数据才渲染检测结果，否则仅说明）
    anomaly_section = f"""<h2>五、异常检测</h2><div class="note">
      该日志数据未包含可用的异常检测结果（缺少窗口特征/评估文件，或日志本身无异常信号），
      本报告仅提供「解析与统计」板块；如需异常检测，请先运行特征构建与检测流程。</div>

  <h2>六、方法说明</h2>
  <ul>
    <li><b>解析</b>：格式自动识别（HDFS / 通用 `[时间][级别][来源] 消息`），变量归一化得日志模板。</li>
    <li><b>统计</b>：时间 / 级别 / 来源（组件）/ 模板四个维度，直接服务于「提炼关键字段」。</li>
  </ul>"""
    if has_anom:
        n_if = int(ev["is_outlier"].sum()); n_ref = int(ev["y_ref"].sum())
        fn_w = ev[(ev["y_ref"] == 1) & (ev["is_outlier"] == 0)]
        fp_w = ev[(ev["y_ref"] == 0) & (ev["is_outlier"] == 1)]
        warn_samples = parsed[parsed["level"] == "WARN"]["raw"].dropna().head(3)
        fp_detail = "".join(
            f"<tr><td>{int(r.win)}</td><td>{int(r.n_logs)}</td><td>{int(r.n_uniq)}</td><td>{r.density:.3f}</td></tr>"
            for r in fp_w.head(6).itertuples())
        n_warn_kpi = int((parsed["level"] == "WARN").sum())
        anomaly_section = f"""<h2>五、异常检测结果（10 分钟窗口，共 {len(ev)} 个）</h2>
  <div class="cf">
    <div class="box"><span>孤立森林异常窗</span><b>{n_if}</b></div>
    <div class="box red"><span>规则(WARN)异常窗</span><b>{n_ref}</b></div>
    <div class="box grn"><span>Precision</span><b>{metrics['precision']}</b></div>
    <div class="box grn"><span>Recall</span><b>{metrics['recall']}</b></div>
    <div class="box grn"><span>F1</span><b>{metrics['f1']}</b></div>
  </div>
  <div class="note">混淆矩阵：TP={metrics['TP']}　FP={metrics['FP']}　FN={metrics['FN']}　TN={metrics['TN']}（参考真值 = WARN 规则）。</div>

  <h2>六、代表性异常样本（WARN：Got exception while serving）</h2>
  <pre>{_escap(chr(10).join(warn_samples))}</pre>

  <h2>七、误报窗口示例（IF 检出但参考正常）</h2>
  <table class="tbl"><tr><th>窗口</th><th>日志数</th><th>模板数</th><th>密度</th></tr>{fp_detail}</table>

  <h2>八、方法说明与局限</h2>
  <ul>
    <li><b>方法</b>：Drain 式模板归一化 → 10 分钟窗 × 统计特征 → Isolation Forest（random_state=42）。</li>
    <li><b>漏报主因</b>：IF 无级别语义，低频 WARN 窗形态与正常窗相近。</li>
    <li><b>误报主因</b>：正常高频窗与极稀疏窗在分布上离群被误隔离。</li>
  </ul>"""

    return f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<title>{title}</title>
<style>
 :root{{ --c:#2b3a55; --sub:#7a8699; --line:#e6e9f0; }}
 *{{box-sizing:border-box;margin:0;padding:0}}
 body{{font-family:"Microsoft YaHei",system-ui,sans-serif;color:var(--c);background:#f4f6fb;padding:32px 16px;}}
 .wrap{{max-width:920px;margin:0 auto;background:#fff;border-radius:14px;box-shadow:0 8px 30px rgba(43,58,85,.08);padding:36px 44px;}}
 h1{{font-size:24px;margin-bottom:4px}} h2{{font-size:17px;margin:26px 0 12px;padding-left:10px;border-left:4px solid #4e8cff}}
 .sub{{color:var(--sub);font-size:13px;margin-bottom:22px}}
 .kpis{{display:flex;gap:14px;flex-wrap:wrap;margin-top:8px}}
 .kpi{{flex:1;min-width:130px;background:#f7f9fe;border:1px solid var(--line);border-radius:10px;padding:14px 16px}}
 .kpi b{{display:block;font-size:22px;color:#3559d6;margin-top:4px}} .kpi span{{font-size:12px;color:var(--sub)}}
 .barrow{{display:flex;align-items:center;margin:4px 0}} .barlab{{width:170px;font-size:12px;text-align:right;padding-right:8px}}
 .bar{{flex:1;background:#eef1f7;border-radius:6px;height:18px;overflow:hidden}}
 .barfill{{height:100%;border-radius:6px;transition:width .4s}}
 .tw{{display:flex;align-items:center;gap:8px;margin:3px 0}} .thour{{width:40px;font-size:12px;text-align:right;color:var(--sub)}}
 table.tbl{{border-collapse:collapse;width:100%;font-size:13px}} .tbl th,.tbl td{{border:1px solid var(--line);padding:6px 10px;text-align:center}}
 .tbl th{{background:#f2f5fc}} .mono{{font-family:Consolas,monospace;font-size:11px;text-align:left;color:#555}}
 .tag{{display:inline-block;padding:2px 10px;border-radius:12px;font-size:12px;font-weight:600}}
 .tag.g{{background:#e7f6ec;color:#1b8a4d}} .tag.r{{background:#fdecec;color:#c43d3d}} .tag.b{{background:#e8efff;color:#3559d6}}
 .cf{{display:flex;gap:14px;margin-top:8px}} .box{{flex:1;text-align:center;background:#f7f9fe;border:1px solid var(--line);border-radius:10px;padding:12px}}
 .box b{{font-size:20px}} .box span{{font-size:12px;color:var(--sub)}} .box.red{{background:#fff5f5;border-color:#f4c7c7}} .box.grn{{background:#f2fbf5;border-color:#c9ecd5}}
 .note{{font-size:12px;color:var(--sub);line-height:1.7;margin-top:6px}} ul{{padding-left:20px;font-size:13px;line-height:1.8}}
 pre{{background:#f6f8ff;border:1px solid var(--line);padding:8px 12px;border-radius:8px;font-size:12px;white-space:pre-wrap}}
</style></head><body><div class="wrap">
  <h1>{title}</h1>
  <div class="sub">模板解析 + 统计特征（可含 Isolation Forest 异常检测）</div>
  <div class="kpis">
    <div class="kpi"><span>日志总数</span><b>{n}</b></div>
    <div class="kpi"><span>唯一模板</span><b>{parsed['template'].nunique()}</b></div>
    <div class="kpi"><span>唯一块</span><b>{parsed['blockid'].nunique()}</b></div>
    <div class="kpi"><span>级别种类</span><b>{parsed['level'].nunique()}</b></div>
    <div class="kpi"><span>时间范围</span><b style="font-size:14px;margin-top:8px">{dt.min()}<br>{dt.max()}</b></div>
  </div>

  <h2>一、时间维度 — 按小时日志量</h2>{hour_bars}

  <h2>二、级别维度</h2>{lv_bars}

  <h2>三、来源（组件）维度</h2>{cross_html}

  <h2>四、模板 Top8</h2><table class="tbl"><tr><th>日志模板</th><th>条数</th></tr>{tpl_rows}</table>

  {anomaly_section}
</div></body></html>"""


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="reports/parsed.csv")
    ap.add_argument("--output", default="reports/日志解析统计与异常检测报告.html")
    ap.add_argument("--title", default="日志解析统计与异常检测报告")
    ap.add_argument("--with-anomaly", action="store_true",
                    help="包含异常检测板块（需 reports/metrics.json 与 evaluation.csv 存在且与输入匹配）")
    args = ap.parse_args()
    Path(args.output).write_text(build_html(args.input, args.title, args.with_anomaly), encoding="utf-8")
    print(f"[HTML报告] 已生成 -> {args.output}")