#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
log_parser_gui.py
日志解析与统计报告生成器 —— 桌面交互窗口（Tkinter，零额外依赖，现代扁平风格）。

流程：选择日志文件 → 一键解析并生成 HTML 报告 → 在浏览器打开。
复用 src/parse_drain.py（解析）与 src/report_html.py（报告）。
运行：.venv\\Scripts\\python log_parser_gui.py （或双击 run_gui.bat）
"""
import sys
import webbrowser
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, scrolledtext, messagebox

_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT / "src"))
import parse_drain  # noqa: E402
import report_html  # noqa: E402

OUT = _ROOT / "reports"
OUT.mkdir(exist_ok=True)

# ---------- 配色 ----------
BG = "#F4F6FB"          # 主背景
CARD = "#FFFFFF"        # 卡片背景
PRIMARY = "#3559D6"     # 主色
PRIMARY_DARK = "#2742A8"
PRIMARY_HOVER = "#2A47B5"
ACCENT = "#21A179"      # 成功绿
TEXT = "#1F2933"
MUTED = "#8A94A6"
BORDER = "#E3E8F0"
LOG_BG = "#0F172A"
LOG_FG = "#D3DCE6"
LOG_ACCENT = "#7C9CFF"
FONT_FAM = "Microsoft YaHei UI"


class RoundedButton(tk.Button):
    """扁平主按钮：悬停加深、按下变暗、禁用自动变灰。"""

    def __init__(self, master, text="", command=None, kind="primary", **kw):
        self.kind = kind
        if kind == "primary":
            self._base, self._hover, self._pressed = PRIMARY, PRIMARY_HOVER, PRIMARY_DARK
            fg = "#FFFFFF"
        elif kind == "ghost":
            self._base, self._hover, self._pressed = CARD, "#EEF2FB", BORDER
            fg = PRIMARY
        else:  # success
            self._base, self._hover, self._pressed = ACCENT, "#1B8A67", "#15704F"
            fg = "#FFFFFF"
        super().__init__(master, text=text, command=command, relief="flat",
                         bg=self._base, fg=fg, activebackground=self._pressed,
                         activeforeground=fg, bd=0, cursor="hand2",
                         font=(FONT_FAM, 10, "bold"),
                         highlightthickness=0, **kw)
        self.bind("<Enter>", lambda _e: self._set(self._hover))
        self.bind("<Leave>", lambda _e: self._set(self._base))

    def _set(self, color):
        if self.cget("state") != "disabled":
            self.config(bg=color)


class LogParserGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("日志解析与统计报告生成器")
        root.geometry("800x640")
        root.minsize(680, 520)
        root.configure(bg=BG)
        self.input_path: Path | None = None
        self.report_path: Path | None = None
        self.busy = False
        self._build()

    def _build(self):
        # ------- 顶部标题 -------
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=28, pady=(24, 12))
        tk.Label(header, text="日志解析与统计报告生成器", bg=BG, fg=TEXT,
                 font=(FONT_FAM, 18, "bold")).pack(anchor="w")
        tk.Label(header, text="选择日志 → 一键解析统计 → 生成并打开 HTML 报告",
                 bg=BG, fg=MUTED, font=(FONT_FAM, 9)).pack(anchor="w", pady=(2, 0))

        # ------- 主卡片 -------
        card = tk.Frame(self.root, bg=CARD, highlightbackground=BORDER,
                        highlightthickness=1, bd=0)
        card.pack(fill="x", padx=28, pady=4)

        # 步骤 1：选择文件
        r1 = tk.Frame(card, bg=CARD, padx=22, pady=14)
        r1.pack(fill="x")
        self.step_badge = tk.Frame(r1, bg=PRIMARY, width=26, height=26)
        self.step_badge.pack(side="left", padx=(0, 12))
        self.step_badge.pack_propagate(False)
        tk.Label(self.step_badge, text="1", bg=PRIMARY, fg="white",
                 font=(FONT_FAM, 10, "bold")).pack(expand=True)
        self.lbl_file = tk.Label(r1, text="尚未选择日志文件", bg=CARD, fg=MUTED,
                                 font=(FONT_FAM, 10), anchor="w")
        self.lbl_file.pack(side="left", fill="x", expand=True)
        RoundedButton(r1, text="选择文件", command=self.open_file,
                      kind="ghost", width=12).pack(side="right")

        # 分隔线
        tk.Frame(card, bg=BORDER, height=1).pack(fill="x")

        # 步骤 2/3：执行
        r2 = tk.Frame(card, bg=CARD, padx=22, pady=16)
        r2.pack(fill="x")
        self.btn_run = RoundedButton(r2, text="解析并生成 HTML 报告",
                                     command=self.run, kind="primary",
                                     padx=24, pady=8)
        self.btn_run.pack(side="left")
        self.btn_open = RoundedButton(r2, text="在浏览器打开报告",
                                      command=self.open_report, kind="ghost",
                                      padx=20, pady=8, state="disabled")
        self.btn_open.pack(side="left", padx=12)

        # ------- 运行日志 -------
        log_head = tk.Frame(self.root, bg=BG)
        log_head.pack(fill="x", padx=28, pady=(16, 6))
        tk.Label(log_head, text="运行日志", bg=BG, fg=TEXT,
                 font=(FONT_FAM, 11, "bold")).pack(side="left")
        tk.Button(log_head, text="清空", command=self._clear_log, relief="flat",
                  bg=BG, fg=MUTED, activebackground=BG, activeforeground=PRIMARY,
                  cursor="hand2", bd=0, font=(FONT_FAM, 9)).pack(side="right")

        self.txt = scrolledtext.ScrolledText(self.root, bg=LOG_BG, fg=LOG_FG,
                                             insertbackground="#FFFFFF",
                                             relief="flat", height=12,
                                             font=("Consolas", 10), padx=14, pady=10)
        self.txt.pack(fill="both", expand=True, padx=28, pady=(0, 10))

        # ------- 底部状态栏 -------
        bar = tk.Frame(self.root, bg=CARD, highlightbackground=BORDER,
                       highlightthickness=1, bd=0)
        bar.pack(fill="x", side="bottom")
        self.status = tk.StringVar(value="就绪 · 请选择日志文件开始")
        tk.Label(bar, textvariable=self.status, bg=CARD, fg=MUTED,
                 font=(FONT_FAM, 9), padx=16, pady=6).pack(side="left")

        self.log("欢迎使用！点击「选择文件」开始解析日志。")

    # ---------- 工具 ----------
    def log(self, s: str, color=LOG_FG):
        self.txt.configure(state="normal")
        self.txt.insert("end", s + "\n")
        self.txt.configure(state="disabled")
        self.txt.see("end")

    def _set_busy(self, v: bool):
        self.busy = v
        self.btn_run.config(state="disabled" if v else "normal")

    def _clear_log(self):
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.configure(state="disabled")
        self.log("运行日志已清空")

    # ---------- 1. 选文件 ----------
    def open_file(self):
        p = filedialog.askopenfilename(
            title="选择日志文件",
            filetypes=[("日志文件", "*.log *.txt *.out *.json"), ("所有文件", "*.*")])
        if p:
            self.input_path = Path(p)
            self.lbl_file.config(text=str(self.input_path), fg=TEXT)
            self.status.set(f"已选择 · {self.input_path.name}")
            self.log(f"[OK] 已选择：{self.input_path}")

    # ---------- 2. 解析 + 报告 ----------
    def run(self):
        if self.busy:
            return
        if not self.input_path:
            self.status.set("请先选择日志文件")
            self.log("[提醒] 请先点击「选择文件」。")
            return
        base = self.input_path.stem
        self._set_busy(True)
        try:
            self.status.set("解析中…")
            self.log(f"[INFO] 正在解析 {self.input_path.name} …")
            df, skipped = parse_drain.parse_file(self.input_path)
            if df.empty:
                self.log("[ERROR] 未解析到有效日志行（格式可能不匹配）。")
                self.status.set("解析失败：无有效行")
                return
            parsed_csv = OUT / f"{base}_parsed.csv"
            df.to_csv(parsed_csv, index=False, encoding="utf-8-sig")
            self.log(f"[OK] 解析完成：{len(df)} 行，跳过 {skipped} 行")
            levels = "、".join(f"{k}={v}" for k, v in df["level"].value_counts().items())
            sources = "、".join(map(str, df["component"].value_counts().index))
            self.log(f"[信息] 级别分布：{levels}")
            self.log(f"[信息] 来源(组件)：{sources}")
            self.log(f"[信息] 唯一模板：{df['template'].nunique()}")

            self.log("[INFO] 生成 HTML 报告 …")
            html = report_html.build_html(str(parsed_csv), title=f"{base} 日志解析统计报告")
            self.report_path = OUT / f"{base}_report.html"
            self.report_path.write_text(html, encoding="utf-8")
            self.log(f"[OK] 报告已生成：{self.report_path}")
            self.btn_open.config(state="normal")
            self.status.set("完成 ✅ · 报告已生成")
            messagebox.showinfo("完成", f"解析与报告已生成！\n{self.report_path}")
        except Exception as e:  # noqa: BLE001
            self.log(f"[ERROR] {e}")
            self.status.set("出错，详见运行日志")
            messagebox.showerror("错误", str(e))
        finally:
            self._set_busy(False)

    # ---------- 3. 打开报告 ----------
    def open_report(self):
        if self.report_path and self.report_path.exists():
            webbrowser.open(self.report_path.resolve().as_uri())


if __name__ == "__main__":
    root = tk.Tk()
    LogParserGUI(root)
    root.mainloop()