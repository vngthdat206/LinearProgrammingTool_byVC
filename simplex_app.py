from __future__ import annotations

import math
import tkinter as tk
from fractions import Fraction
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Any, Dict, List, Optional, Tuple

from models import ProblemData, SolveReport
from models import Snapshot, PivotStep, SolveTrace 
from simplex_engine import SimplexEngine
from utils import (VAR_SIGNS, SENSES, clean_number_text, fmt_num,
                   fr, parse_cell, row_expr, sense_to_standard, term_str)
from viz3d import Viz3DMixin


class SimplexApp(Viz3DMixin, tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Ứng dụng Quy hoạch tuyến tính — Đơn hình")
        self.geometry("1380x920")
        self.minsize(1100, 760)

        self.objective_sense = tk.StringVar(value="max")
        self.n_vars = tk.IntVar(value=3)
        self.n_constraints = tk.IntVar(value=3)
        self.data_mode = tk.StringVar(value="Phân số")
        self.method_preference = tk.StringVar(value="auto")
        self.demo_preset_var = tk.StringVar(value="Ví dụ giải bằng 2 pha")
        self.need_aux_phase1 = False
        self.phase1_aux_var_index: Optional[int] = None

        self.obj_entries: List[tk.Entry] = []
        self.var_signs: List[ttk.Combobox] = []
        self.constraint_entries: List[List[tk.Entry]] = []
        self.constraint_senses: List[ttk.Combobox] = []
        self.constraint_rhs: List[tk.Entry] = []

        self.last_report: Optional[SolveReport] = None
        self.last_problem: Optional[ProblemData] = None
        self.export_btn: Optional[tk.Button] = None
        self.viz_btn: Optional[tk.Button] = None
        self.viz3d_btn: Optional[tk.Button] = None

        self._setup_style()
        self._build_ui()
        self._build_inputs()
        self.bind_all("<Control-Alt-r>", lambda e: self.run_solver())
        self.bind_all("<Control-Alt-R>", lambda e: self.run_solver())


    def _setup_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TFrame", background="#f4f1eb")
        style.configure("Header.TFrame", background="#1f2937")
        style.configure("Header.TLabel", background="#1f2937",
                        foreground="#ffffff", font=("Segoe UI", 16, "bold"))
        style.configure("SubHeader.TLabel", background="#1f2937",
                        foreground="#dbeafe", font=("Segoe UI", 10))
        style.configure("TLabel", background="#f4f1eb",
                        foreground="#172033", font=("Segoe UI", 10))
        style.configure("TLabelframe", background="#f4f1eb", borderwidth=1)
        style.configure("TLabelframe.Label", background="#f4f1eb",
                        foreground="#111827", font=("Segoe UI", 10, "bold"))
        style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=8)
        style.configure("Accent.TButton", background="#2563eb", foreground="white")
        style.map(
            "Accent.TButton",
            background=[("disabled", "#d1d5db"), ("active", "#1d4ed8"),
                        ("!disabled", "#2563eb")],
            foreground=[("disabled", "#6b7280"), ("!disabled", "white")],
        )
        style.configure("Warn.TButton", background="#b45309", foreground="white")
        style.map("Warn.TButton", background=[("active", "#92400e")])
        style.configure("TCombobox", padding=4)
        style.configure("Treeview", rowheight=28)


    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self, style="Header.TFrame", padding=(16, 12))
        header.grid(row=0, column=0, sticky="nsew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header,
                  text="Ứng dụng Quy hoạch tuyến tính — Phương pháp Đơn hình",
                  style="Header.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="Tab để chuyển ô • Ctrl+Alt+R để giải • "
                 "Hỗ trợ max/min, ràng buộc ≤ ≥ =, biến tự do và biến dấu âm",
            style="SubHeader.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        main = ttk.Frame(self, padding=14)
        main.grid(row=1, column=0, sticky="nsew")
        main.columnconfigure(0, weight=0)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        left = ttk.Frame(main)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.rowconfigure(3, weight=1)

        config = ttk.Labelframe(left, text="Thiết lập", padding=12)
        config.grid(row=0, column=0, sticky="ew")
        config.columnconfigure(1, weight=1)

        ttk.Label(config, text="Kiểu dữ liệu:").grid(
            row=0, column=0, sticky="w", pady=3)
        ttk.Combobox(config, textvariable=self.data_mode,
                     values=["Phân số", "Số thập phân"],
                     state="readonly", width=12).grid(
            row=0, column=1, sticky="w", pady=3)

        ttk.Label(config, text="Số biến (1–5):").grid(
            row=1, column=0, sticky="w", pady=3)
        ttk.Spinbox(config, from_=1, to=5, textvariable=self.n_vars,
                    width=10, command=self._build_inputs).grid(
            row=1, column=1, sticky="w", pady=3)

        ttk.Label(config, text="Số ràng buộc (1–10):").grid(
            row=2, column=0, sticky="w", pady=3)
        ttk.Spinbox(config, from_=1, to=10, textvariable=self.n_constraints,
                    width=10, command=self._build_inputs).grid(
            row=2, column=1, sticky="w", pady=3)

        ttk.Button(config, text="Tạo lại bảng nhập",
                   command=self._build_inputs).grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        action_row = ttk.Frame(config)
        action_row.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        action_row.columnconfigure(0, weight=1)
        action_row.columnconfigure(1, weight=1)

        self.export_btn = tk.Button(
            action_row,
            text="📄  Xuất file .txt",
            font=("Segoe UI", 9, "bold"),
            bg="#9ca3af", fg="white",
            activebackground="#6b7280", activeforeground="white",
            relief="flat", bd=0, padx=6, pady=7,
            cursor="arrow", state=tk.DISABLED,
            command=self.export_solution_txt,
        )
        self.export_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.export_btn.bind("<Enter>",
                             lambda e: self._on_button_enter(e, "#0f766e"))
        self.export_btn.bind("<Leave>",
                             lambda e: self._on_button_leave(e, "#9ca3af"))

        self.viz_btn = tk.Button(
            action_row,
            text="📊  Trực quan hóa (2D)",
            font=("Segoe UI", 9, "bold"),
            bg="#0d9488", fg="white",
            activebackground="#0f766e", activeforeground="white",
            relief="flat", bd=0, padx=6, pady=7,
            cursor="hand2",
            command=self._viz_dispatch,
        )
        self.viz_btn.grid(row=0, column=1, sticky="ew")
        self.viz_btn.bind("<Enter>",
                          lambda e: self._on_button_enter(e, None))
        self.viz_btn.bind("<Leave>",
                          lambda e: self._on_button_leave(e, None))

        self.viz3d_btn = None

        ttk.Button(config, text="Chạy giải thuật  (Ctrl+Alt+R)",
                   style="Accent.TButton",
                   command=self.run_solver).grid(
            row=5, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        btns = ttk.Frame(left)
        btns.grid(row=1, column=0, sticky="ew", pady=(10, 10))
        btns.columnconfigure(1, weight=1)
        ttk.Label(btns, text="Mẫu:").grid(row=0, column=0, sticky="w",
                                           padx=(0, 6))
        demo_combo = ttk.Combobox(
            btns,
            textvariable=self.demo_preset_var,
            values=["Ví dụ giải bằng 2 pha",
                    "Ví dụ giải bài toán xoay vòng",
                    "Ví dụ giải bài toán vô số nghiệm",
                    "Ví dụ 3 biến (trực quan 3D)"],
            state="readonly", width=28,
        )
        demo_combo.grid(row=0, column=1, sticky="ew", padx=(0, 6))
        ttk.Button(btns, text="Điền ví dụ",
                   style="Warn.TButton",
                   command=self.fill_demo).grid(row=0, column=2, sticky="ew")

        input_box = ttk.Labelframe(left, text="Nhập bài toán", padding=14)
        input_box.grid(row=3, column=0, sticky="nsew")
        input_box.columnconfigure(0, weight=1)
        input_box.rowconfigure(0, weight=1)
        self.input_canvas = tk.Canvas(input_box, background="#f4f1eb",
                                      highlightthickness=0, width=580, height=650)
        self.input_canvas.grid(row=0, column=0, sticky="nsew")
        vsb = ttk.Scrollbar(input_box, orient="vertical",
                             command=self.input_canvas.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self.input_canvas.configure(yscrollcommand=vsb.set)
        self.input_inner = ttk.Frame(self.input_canvas)
        self.input_window = self.input_canvas.create_window(
            (0, 0), window=self.input_inner, anchor="nw")
        self.input_inner.bind(
            "<Configure>",
            lambda e: self.input_canvas.configure(
                scrollregion=self.input_canvas.bbox("all")))
        self.input_canvas.bind(
            "<Configure>",
            lambda e: self.input_canvas.itemconfigure(
                self.input_window, width=e.width))

        right = ttk.Labelframe(main, text="Lời giải", padding=8)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        self.output = scrolledtext.ScrolledText(
            right, wrap="none", font=("Consolas", 12),
            bg="#fbfaf6", fg="#1e1b1b",
            insertbackground="#1e1b1b", relief="flat", padx=14, pady=10,
        )
        self.output.grid(row=0, column=0, sticky="nsew")
        self.output.tag_configure("h1", font=("Segoe UI", 15, "bold"),
                                   foreground="#b45309", spacing1=8, spacing3=10)
        self.output.tag_configure("h2", font=("Segoe UI", 12, "bold"),
                                   foreground="#1f2937", spacing1=8, spacing3=4)
        self.output.tag_configure("note", foreground="#0f4c81")
        self.output.tag_configure("warn", foreground="#a16207")
        self.output.tag_configure("mono", font=("Consolas", 12))
        self.output.tag_configure("pivotcol", background="#fde68a")
        self.output.tag_configure("pivotrow", background="#dbeafe")
        self.output.tag_configure("pivotcell", background="#fca5a5")
        self.output.tag_configure("conclusion", background="#fff7ed")

        self.status_var = tk.StringVar(value="Sẵn sàng.")
        ttk.Label(self, textvariable=self.status_var,
                  anchor="w", padding=(14, 6)).grid(row=2, column=0, sticky="ew")

        self.bind("<Configure>", self._on_resize)

    def _on_resize(self, event=None):
        try:
            self.output.configure(wrap="none")
        except Exception:
            pass

    def _build_inputs(self):
        for child in self.input_inner.winfo_children():
            child.destroy()
        self.obj_entries.clear()
        self.var_signs.clear()
        self.constraint_entries.clear()
        self.constraint_senses.clear()
        self.constraint_rhs.clear()

        n = int(self.n_vars.get())
        m = int(self.n_constraints.get())

        obj_frame = ttk.Labelframe(self.input_inner,
                                    text="Hàm mục tiêu", padding=10)
        obj_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        obj_frame.columnconfigure(1, weight=1)

        ttk.Label(obj_frame, text="Kiểu bài toán:").grid(
            row=0, column=0, sticky="w")
        ttk.Combobox(obj_frame, textvariable=self.objective_sense,
                     values=["max", "min"], state="readonly", width=8).grid(
            row=0, column=1, sticky="w", pady=2)

        ttk.Label(obj_frame, text="Hệ số:").grid(
            row=1, column=0, sticky="w", pady=(8, 2))
        coef_row = ttk.Frame(obj_frame)
        coef_row.grid(row=1, column=1, sticky="ew", pady=(8, 2))
        for j in range(n):
            coef_row.columnconfigure(j, weight=1)
            cell = ttk.Frame(coef_row)
            cell.grid(row=0, column=j, padx=4, sticky="ew")
            ttk.Label(cell, text=f"x{j+1}").grid(row=0, column=0, sticky="w")
            e = ttk.Entry(cell, width=10)
            e.grid(row=1, column=0, sticky="ew")
            self.obj_entries.append(e)

        sign_frame = ttk.Frame(obj_frame)
        sign_frame.grid(row=2, column=0, columnspan=2,
                         sticky="ew", pady=(10, 0))
        for j in range(n):
            sc = ttk.Frame(sign_frame)
            sc.grid(row=0, column=j, padx=4, sticky="ew")
            ttk.Label(sc, text=f"x{j+1}").grid(row=0, column=0, sticky="w")
            cb = ttk.Combobox(sc, values=VAR_SIGNS, state="readonly", width=10)
            cb.set("≥0")
            cb.grid(row=1, column=0, sticky="ew")
            self.var_signs.append(cb)

        cons_frame = ttk.Labelframe(self.input_inner,
                                     text="Ràng buộc", padding=10)
        cons_frame.grid(row=1, column=0, sticky="nsew")
        cons_frame.columnconfigure(0, weight=1)

        ttk.Label(cons_frame,
                  text="Nhập hệ số từng ràng buộc, chọn dấu rồi nhập vế phải."
                  ).grid(row=0, column=0, sticky="w", pady=(0, 6))
        table = ttk.Frame(cons_frame)
        table.grid(row=1, column=0, sticky="ew")

        hdr = ttk.Frame(table)
        hdr.grid(row=0, column=0, columnspan=n+3, sticky="ew")
        ttk.Label(hdr, text="").grid(row=0, column=0, padx=2)
        for j in range(n):
            ttk.Label(hdr, text=f"x{j+1}", width=8,
                      anchor="center").grid(row=0, column=j+1, padx=2)
        ttk.Label(hdr, text="Dấu", width=8,
                  anchor="center").grid(row=0, column=n+1, padx=2)
        ttk.Label(hdr, text="Hệ số tự do", width=10,
                  anchor="center").grid(row=0, column=n+2, padx=2)

        for i in range(m):
            rf = ttk.Frame(table)
            rf.grid(row=i+1, column=0, columnspan=n+3, sticky="ew", pady=2)
            ttk.Label(rf, text=f"(RB{i+1})", width=5).grid(
                row=0, column=0, padx=2)
            row_entries = []
            for j in range(n):
                e = ttk.Entry(rf, width=10)
                e.grid(row=0, column=j+1, padx=2)
                row_entries.append(e)
            cb = ttk.Combobox(rf, values=SENSES, state="readonly", width=6)
            cb.set("≤")
            cb.grid(row=0, column=n+1, padx=2)
            rhs = ttk.Entry(rf, width=10)
            rhs.grid(row=0, column=n+2, padx=2)
            self.constraint_entries.append(row_entries)
            self.constraint_senses.append(cb)
            self.constraint_rhs.append(rhs)

        ttk.Label(
            self.input_inner,
            text="Bấm Tab để chuyển ô. Ctrl+Alt+R để giải.",
            foreground="#92400e",
        ).grid(row=2, column=0, sticky="w", pady=(10, 0))

        self.input_inner.update_idletasks()
        self.input_canvas.configure(
            scrollregion=self.input_canvas.bbox("all"))
        self.last_problem = None
        self.last_report = None
        self._set_solution_available(False)
        self._update_viz_btn_state()

    def fill_demo(self):
        preset = self.demo_preset_var.get().strip()
        if preset == "Ví dụ giải bài toán xoay vòng":
            self._fill_demo_cycle()
        elif preset == "Ví dụ giải bài toán vô số nghiệm":
            self._fill_demo_multiple_optimal()
        elif preset == "Ví dụ 3 biến (trực quan 3D)":
            self._fill_demo_3var()
        else:
            self._fill_demo_two_phase()

    def _fill_demo_two_phase(self):
        self.n_vars.set(2); self.n_constraints.set(3)
        self.objective_sense.set("min"); self._build_inputs()
        for i, v in enumerate(["5", "-7"]):
            self.obj_entries[i].delete(0, tk.END)
            self.obj_entries[i].insert(0, v)
        for cb in self.var_signs:
            cb.set("≥0")
        data = [(["-4","1"],"≤","-2"),(["1","1"],"≤","5"),(["−1","−1"],"≤","-1")]
        for i,(c,s,r) in enumerate(data):
            for j,e in enumerate(self.constraint_entries[i]):
                e.delete(0,tk.END); e.insert(0,c[j])
            self.constraint_senses[i].set(s)
            self.constraint_rhs[i].delete(0,tk.END)
            self.constraint_rhs[i].insert(0,r)

    def _fill_demo_cycle(self):
        self.n_vars.set(4); self.n_constraints.set(3)
        self.objective_sense.set("min"); self._build_inputs()
        for i,v in enumerate(["-10","57","9","24"]):
            self.obj_entries[i].delete(0,tk.END); self.obj_entries[i].insert(0,v)
        for cb in self.var_signs: cb.set("≥0")
        data=[
            (["0.5","-5.5","-2.5","9"],"≤","0"),
            (["0.5","-1.5","-0.5","1"],"≤","0"),
            (["1","0","0","0"],"≤","1"),
        ]
        for i,(c,s,r) in enumerate(data):
            for j,e in enumerate(self.constraint_entries[i]):
                e.delete(0,tk.END); e.insert(0,c[j])
            self.constraint_senses[i].set(s)
            self.constraint_rhs[i].delete(0,tk.END)
            self.constraint_rhs[i].insert(0,r)

    def _fill_demo_multiple_optimal(self):
        self.n_vars.set(3); self.n_constraints.set(4)
        self.objective_sense.set("max"); self._build_inputs()
        for i,v in enumerate(["-3","1","1"]):
            self.obj_entries[i].delete(0,tk.END); self.obj_entries[i].insert(0,v)
        for cb in self.var_signs: cb.set("≥0")
        data=[
            (["1","-1","0"],"≤","0"),
            (["-2","0","1"],"≤","1"),
            (["0","-2","1"],"≤","2"),
            (["1","1","-1"],"≤","6"),
        ]
        for i,(c,s,r) in enumerate(data):
            for j,e in enumerate(self.constraint_entries[i]):
                e.delete(0,tk.END); e.insert(0,c[j])
            self.constraint_senses[i].set(s)
            self.constraint_rhs[i].delete(0,tk.END)
            self.constraint_rhs[i].insert(0,r)

    def _fill_demo_3var(self):
        self.n_vars.set(3); self.n_constraints.set(3)
        self.objective_sense.set("max"); self._build_inputs()
        for i,v in enumerate(["5","4","3"]):
            self.obj_entries[i].delete(0,tk.END); self.obj_entries[i].insert(0,v)
        for cb in self.var_signs: cb.set("≥0")
        data=[
            (["6","4","2"],"≤","240"),
            (["3","5","5"],"≤","270"),
            (["5","3","6"],"≤","420"),
        ]
        for i,(c,s,r) in enumerate(data):
            for j,e in enumerate(self.constraint_entries[i]):
                e.delete(0,tk.END); e.insert(0,c[j])
            self.constraint_senses[i].set(s)
            self.constraint_rhs[i].delete(0,tk.END)
            self.constraint_rhs[i].insert(0,r)

    def _collect_problem(self) -> ProblemData:
        n = int(self.n_vars.get())
        m = int(self.n_constraints.get())
        obj_coeffs = [parse_cell(e.get(), self.data_mode.get())
                      for e in self.obj_entries[:n]]
        var_signs = [cb.get() or "≥0" for cb in self.var_signs[:n]]
        constraints = []
        for i in range(m):
            coeffs = [parse_cell(e.get(), self.data_mode.get())
                      for e in self.constraint_entries[i][:n]]
            sense = self.constraint_senses[i].get() or "≤"
            rhs = parse_cell(self.constraint_rhs[i].get(), self.data_mode.get())
            constraints.append({"coeffs": coeffs, "sense": sense, "rhs": rhs})
        return ProblemData(
            objective_sense=self.objective_sense.get(),
            obj_coeffs=obj_coeffs,
            constraints=constraints,
            var_signs=var_signs,
        )


    def _set_solution_available(self, available: bool) -> None:
        if self.export_btn is None:
            return
        if available:
            self.export_btn._base_bg = "#16a34a"
            self.export_btn._hover_bg = "#15803d"
            self.export_btn.config(state=tk.NORMAL,
                                   bg="#16a34a",
                                   activebackground="#15803d",
                                   cursor="hand2")
        else:
            self.export_btn._base_bg = "#9ca3af"
            self.export_btn._hover_bg = "#6b7280"
            self.export_btn.config(state=tk.DISABLED,
                                   bg="#9ca3af",
                                   activebackground="#6b7280",
                                   cursor="arrow")

    _VIZ_STYLES = {
        2: dict(bg="#0d9488", hover="#0f766e", icon="📊",
                label="Trực quan hóa (2D)"),
        3: dict(bg="#7c3aed", hover="#6d28d9", icon="🧊",
                label="Trực quan hóa (3D)"),
    }
    _VIZ_DISABLED = dict(bg="#9ca3af", hover="#6b7280",
                         icon="🔒", label="Trực quan hóa (>3 biến)")

    def _update_viz_btn_state(self) -> None:
        if self.viz_btn is None:
            return
        n = int(self.n_vars.get())
        if n > 3:
            s = self._VIZ_DISABLED
            self.viz_btn.config(
                text=f"{s['icon']}  {s['label']}",
                state=tk.DISABLED,
                bg=s["bg"], activebackground=s["hover"],
                cursor="arrow",
            )
            self.viz_btn._base_bg = s["bg"]
            self.viz_btn._hover_bg = s["hover"]
        else:
            s = self._VIZ_STYLES.get(n, self._VIZ_STYLES[2])
            self.viz_btn.config(
                text=f"{s['icon']}  {s['label']}",
                state=tk.NORMAL,
                bg=s["bg"], activebackground=s["hover"],
                cursor="hand2",
            )
            self.viz_btn._base_bg = s["bg"]
            self.viz_btn._hover_bg = s["hover"]

    def _viz_dispatch(self) -> None:
        n = int(self.n_vars.get())
        if n == 2:
            self.visualize_two_variable_problem()
        elif n == 3:
            self.visualize_three_variable_problem()
        else:
            messagebox.showinfo(
                "Trực quan hóa",
                "Tính năng trực quan chỉ hỗ trợ bài toán 2 hoặc 3 biến.\n"
                "Vui lòng giảm số biến xuống còn 2 hoặc 3.",
            )

    def _on_button_enter(self, event, darker_color: Optional[str] = None) -> None:
        btn = event.widget
        if str(btn.cget("state")) == "disabled":
            return
        if darker_color is None:
            darker_color = getattr(btn, "_hover_bg", btn.cget("bg"))
        elif btn is self.export_btn:
            darker_color = getattr(btn, "_hover_bg", darker_color)
        btn.config(bg=darker_color)

    def _on_button_leave(self, event, original_color: Optional[str] = None) -> None:
        btn = event.widget
        if str(btn.cget("state")) == "disabled":
            return
        if original_color is None or btn is self.export_btn:
            original_color = getattr(btn, "_base_bg", btn.cget("bg"))
        btn.config(bg=original_color)


    def export_solution_txt(self) -> None:
        content = self.output.get("1.0", "end-1c").strip()
        if not content:
            messagebox.showinfo("Xuất file .txt", "Chưa có lời giải để xuất.")
            return
        path = filedialog.asksaveasfilename(
            title="Lưu nội dung lời giải",
            defaultextension=".txt",
            filetypes=[("Text file", "*.txt"), ("All files", "*.*")],
            initialfile="loi_giai.txt",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content + "\n")
            self.status_var.set(f"Đã xuất file: {path}")
        except Exception as exc:
            messagebox.showerror("Lỗi xuất file", str(exc))


    def _boundary_text(self, coeffs, sense: str, rhs: Fraction) -> str:
        a, b = coeffs
        parts = []
        mode = self.data_mode.get()
        if a != 0:
            parts.append(f"{fmt_num(a, mode)}x₁")
        if b != 0:
            sign = "+" if b > 0 and parts else ""
            parts.append(f"{sign}{fmt_num(b, mode)}x₂")
        lhs = " ".join(parts).replace("+ -", "- ") or "0"
        return f"{lhs} {sense} {fmt_num(rhs, mode)}"

    def _build_halfplanes(self, prob: ProblemData):
        halfplanes = []
        for i, cons in enumerate(prob.constraints, start=1):
            a = fr(cons["coeffs"][0])
            b = fr(cons["coeffs"][1])
            rhs = fr(cons["rhs"])
            sense = sense_to_standard(cons["sense"])
            halfplanes.append((a, b, rhs, sense, f"RB{i}"))
        s0, s1 = prob.var_signs[0], prob.var_signs[1]
        if s0 == "≥0":
            halfplanes.append((Fraction(1), Fraction(0), Fraction(0), "≥", "x₁ ≥ 0"))
        elif s0 == "≤0":
            halfplanes.append((Fraction(1), Fraction(0), Fraction(0), "≤", "x₁ ≤ 0"))
        if s1 == "≥0":
            halfplanes.append((Fraction(0), Fraction(1), Fraction(0), "≥", "x₂ ≥ 0"))
        elif s1 == "≤0":
            halfplanes.append((Fraction(0), Fraction(1), Fraction(0), "≤", "x₂ ≤ 0"))
        return halfplanes

    def _is_feasible_point(self, x, y, halfplanes, tol=1e-8):
        for a, b, c, sense, _ in halfplanes:
            lhs = float(a)*x + float(b)*y
            cc = float(c)
            if sense == "≤" and lhs > cc+tol: return False
            if sense == "≥" and lhs < cc-tol: return False
            if sense == "=" and abs(lhs-cc) > tol: return False
        return True

    def _compute_feasible_vertices(self, halfplanes):
        import math
        lines = [(a, b, c, lbl) for a, b, c, _, lbl in halfplanes]
        vertices = []
        for i in range(len(lines)):
            a1, b1, c1, _ = lines[i]
            for j in range(i+1, len(lines)):
                a2, b2, c2, _ = lines[j]
                det = float(a1*b2 - a2*b1)
                if abs(det) < 1e-12: continue
                x = float((c1*b2 - c2*b1)/det)
                y = float((a1*c2 - a2*c1)/det)
                if math.isfinite(x) and math.isfinite(y) and \
                   self._is_feasible_point(x, y, halfplanes):
                    vertices.append((x, y))
        return vertices

    def _deduplicate_points(self, points, eps=1e-7):
        unique = []
        for p in points:
            if not any(abs(p[0]-q[0]) <= eps and abs(p[1]-q[1]) <= eps
                       for q in unique):
                unique.append(p)
        return unique

    def _compute_plot_bounds(self, vertices, halfplanes):
        if vertices:
            xs = [p[0] for p in vertices]; ys = [p[1] for p in vertices]
            sx = max(xs)-min(xs); sy = max(ys)-min(ys)
            px = max(0.9, sx*0.18) if len(xs) > 1 else max(1.4, abs(xs[0])*0.35+1)
            py = max(0.9, sy*0.18) if len(ys) > 1 else max(1.4, abs(ys[0])*0.35+1)
            xmin, xmax = min(xs)-px, max(xs)+px
            ymin, ymax = min(ys)-py, max(ys)+py
            xmin, ymin = min(xmin, 0.), min(ymin, 0.)
            xmax, ymax = max(xmax, 0.), max(ymax, 0.)
        else:
            xmin, xmax, ymin, ymax = -5., 5., -5., 5.
        xr, yr = xmax-xmin, ymax-ymin
        return xmin-0.22*xr, xmax+0.22*xr, ymin-0.22*yr, ymax+0.22*yr

    def _create_meshgrid(self, xmin, xmax, ymin, ymax):
        import numpy as np
        x = np.linspace(xmin, xmax, 220)
        y = np.linspace(ymin, ymax, 220)
        X, Y = np.meshgrid(x, y)
        return x, y, X, Y

    def _compute_feasible_region(self, halfplanes, X, Y):
        import numpy as np
        mask = np.ones_like(X, dtype=bool)
        for a, b, c, sense, _ in halfplanes:
            lhs = float(a)*X + float(b)*Y; cc = float(c)
            if sense == "≤": mask &= lhs <= cc+1e-9
            elif sense == "≥": mask &= lhs >= cc-1e-9
            else: mask &= np.abs(lhs-cc) <= 1e-2
        return mask

    def _find_optimal_vertex(self, vertex_values, maximize):
        if not vertex_values: return None
        return max(vertex_values, key=lambda t: t[2]) if maximize \
               else min(vertex_values, key=lambda t: t[2])

    def _request_canvas_redraw(self, canvas, delay_ms=14):
        widget = canvas.get_tk_widget()
        if getattr(widget, "_redraw_job", None) is not None:
            return
        def _do():
            widget._redraw_job = None
            try: canvas.draw_idle()
            except Exception: pass
        widget._redraw_job = widget.after(delay_ms, _do)

    def _line_box_intersections(self, a, b, c, xmin, xmax, ymin, ymax):
        eps = 1e-12; pts = []
        def add(pt):
            x, y = pt
            if math.isfinite(x) and math.isfinite(y) \
               and xmin-1e-9 <= x <= xmax+1e-9 \
               and ymin-1e-9 <= y <= ymax+1e-9:
                for qx, qy in pts:
                    if abs(qx-x) <= 1e-7 and abs(qy-y) <= 1e-7: return
                pts.append((x, y))
        fa, fb, fc = float(a), float(b), float(c)
        if abs(fb) > eps:
            add((xmin, (fc-fa*xmin)/fb)); add((xmax, (fc-fa*xmax)/fb))
        if abs(fa) > eps:
            add(((fc-fb*ymin)/fa, ymin)); add(((fc-fb*ymax)/fa, ymax))
        return pts

    def visualize_two_variable_problem(self) -> None:
        try:
            prob = self._collect_problem()
        except Exception as exc:
            messagebox.showerror("Trực quan hóa", str(exc)); return
        if len(prob.obj_coeffs) != 2:
            messagebox.showinfo("Trực quan hóa",
                "Tính năng này chỉ hỗ trợ đúng 2 biến x₁ và x₂."); return
        try:
            import numpy as np, matplotlib
            matplotlib.use("TkAgg", force=True)
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        except Exception as exc:
            messagebox.showerror("Trực quan hóa",
                f"Không khởi tạo được thư viện: {exc}"); return

        halfplanes = self._build_halfplanes(prob)
        vertices = self._deduplicate_points(
            self._compute_feasible_vertices(halfplanes))
        xmin, xmax, ymin, ymax = self._compute_plot_bounds(vertices, halfplanes)
        _, _, X, Y = self._create_meshgrid(xmin, xmax, ymin, ymax)
        feasible_mask = self._compute_feasible_region(halfplanes, X, Y)
        c1, c2 = float(prob.obj_coeffs[0]), float(prob.obj_coeffs[1])
        vertex_values = [(p[0], p[1], c1*p[0]+c2*p[1]) for p in vertices]
        maximize = prob.objective_sense == "max"
        optimal_point = self._find_optimal_vertex(vertex_values, maximize)

        win = self._create_visualization_window()
        pf = tk.Frame(win, bg="#f8fafc", bd=0, highlightthickness=0)
        pf.grid(row=0, column=0, sticky="nsew")
        pf.rowconfigure(0, weight=1); pf.columnconfigure(0, weight=1)

        fig, ax = self._create_figure()
        self._plot_feasible_region(ax, X, Y, feasible_mask)
        self._plot_constraints(ax, halfplanes, xmin, xmax, ymin, ymax)
        self._plot_objective_contours(ax, c1, c2, vertex_values,
                                      xmin, xmax, ymin, ymax, maximize)
        self._plot_vertices(ax, vertex_values, maximize)
        self._plot_optimal_point(ax, optimal_point, maximize)
        self._configure_axes(ax, xmin, xmax, ymin, ymax)

        canvas = FigureCanvasTkAgg(fig, master=pf)
        canvas.draw()
        canvas.get_tk_widget().configure(bd=0, highlightthickness=0,
                                         relief="flat")
        canvas.get_tk_widget().pack(fill="both", expand=True)
        self._create_info_panel(pf, prob, vertices, vertex_values,
                                 optimal_point, maximize)
        self._create_zoom_controls(pf, ax, canvas,
                                   (xmin, xmax), (ymin, ymax))
        self._enable_canvas_interactions(ax, canvas)
        win.focus_force()

    def _create_visualization_window(self):
        top = tk.Toplevel(self)
        top.title("Trực quan hóa bài toán 2 biến")
        top.geometry("1540x980"); top.minsize(1100, 760)
        top.resizable(True, True)
        try: top.state("zoomed")
        except Exception:
            try: top.attributes("-zoomed", True)
            except Exception: pass
        top.configure(bg="#f8fafc")
        top.columnconfigure(0, weight=1); top.rowconfigure(0, weight=1)
        top.protocol("WM_DELETE_WINDOW", top.destroy)
        return top

    def _create_figure(self):
        from matplotlib.figure import Figure
        fig = Figure(figsize=(16, 9.6), dpi=105)
        fig.patch.set_facecolor("#f8fafc")
        fig.subplots_adjust(left=0.045, right=0.992, top=0.94, bottom=0.085)
        ax = fig.add_subplot(111)
        ax.set_facecolor("#ffffff")
        ax.grid(True, linestyle="--", linewidth=0.7, alpha=0.16)
        ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#cbd5e1"); ax.spines["bottom"].set_color("#cbd5e1")
        return fig, ax

    def _plot_feasible_region(self, ax, X, Y, mask):
        ax.contourf(X, Y, mask.astype(float), levels=[0.5, 1.5],
                    alpha=0.16, colors=["#93c5fd"], zorder=0)

    def _plot_constraints(self, ax, halfplanes, xmin, xmax, ymin, ymax):
        palette = ["#1d4ed8","#7c3aed","#0f766e","#d97706","#be123c","#0891b2"]
        seen = set()
        for idx, (a, b, c, sense, label) in enumerate(halfplanes):
            color = palette[idx % len(palette)]
            pts = self._line_box_intersections(a, b, c, xmin, xmax, ymin, ymax)
            if len(pts) < 2: continue
            pts = sorted(pts, key=lambda p: (p[0], p[1]))
            (x1,y1),(x2,y2) = pts[0], pts[-1]
            ax.plot([x1,x2],[y1,y2], color=color, linewidth=2.4,
                    alpha=0.95, solid_capstyle="round", zorder=2)
            if label not in seen:
                seen.add(label)
                mx,my = (x1+x2)/2,(y1+y2)/2
                dx,dy = 0.012*(xmax-xmin), 0.012*(ymax-ymin)
                ax.text(mx+dx, my+dy, label, fontsize=9, color=color,
                        weight="bold",
                        bbox=dict(boxstyle="round,pad=0.2",
                                  fc="#ffffff", ec=color, alpha=0.88), zorder=3)

    def _plot_objective_contours(self, ax, c1, c2, vv, xmin, xmax, ymin, ymax, maximize):
        if not vv or abs(c1)+abs(c2) < 1e-12: return
        zvals = sorted(v[2] for v in vv)
        z_best = max(zvals) if maximize else min(zvals)
        span = max(1., abs(zvals[-1]-zvals[0]) if len(zvals)>1 else max(1., abs(z_best)))
        levels = [z_best-span, z_best-0.5*span, z_best,
                  z_best+0.5*span, z_best+span]
        for lv in levels:
            pts = self._line_box_intersections(
                Fraction(str(c1)), Fraction(str(c2)), Fraction(str(lv)),
                xmin, xmax, ymin, ymax)
            if len(pts) < 2: continue
            pts = sorted(pts, key=lambda p:(p[0],p[1]))
            (x1,y1),(x2,y2) = pts[0],pts[-1]
            is_best = abs(lv-z_best) < 1e-9
            ax.plot([x1,x2],[y1,y2], color="#ef4444",
                    linewidth=2.8 if is_best else 1.6,
                    linestyle="-" if is_best else "--",
                    alpha=0.72 if is_best else 0.28, zorder=1.5)
            if is_best:
                tx,ty = (x1+x2)/2,(y1+y2)/2
                ax.text(tx, ty,
                        f"  z = {fmt_num(Fraction(str(lv)), self.data_mode.get())}",
                        color="#b91c1c", fontsize=9, weight="bold",
                        bbox=dict(boxstyle="round,pad=0.2",
                                  fc="#fff1f2", ec="#fca5a5", alpha=0.95), zorder=4)

    def _plot_vertices(self, ax, vv, maximize):
        if not vv: return
        pts = list(vv)
        cx = sum(p[0] for p in pts)/len(pts)
        cy = sum(p[1] for p in pts)/len(pts)
        pts.sort(key=lambda t: math.atan2(t[1]-cy, t[0]-cx))
        ax.fill([p[0] for p in pts],[p[1] for p in pts],
                color="#dbeafe", alpha=0.10, zorder=1)
        ax.plot([p[0] for p in pts]+[pts[0][0]],
                [p[1] for p in pts]+[pts[0][1]],
                color="#0f172a", linewidth=1.2, linestyle=":", alpha=0.52, zorder=2.5)
        for idx,(vx,vy,val) in enumerate(pts,start=1):
            ax.scatter([vx],[vy], s=42, color="#2563eb",
                       edgecolors="white", linewidths=1.0, zorder=5)
            ax.annotate(f"{idx}", xy=(vx,vy), xytext=(6,6),
                        textcoords="offset points", fontsize=9, color="#0f172a",
                        bbox=dict(boxstyle="circle,pad=0.18",
                                  fc="#eff6ff", ec="#93c5fd", alpha=0.95), zorder=6)

    def _plot_optimal_point(self, ax, optimal, maximize):
        if optimal is None: return
        bx,by,bz = optimal
        ax.scatter([bx],[by], s=220, marker="*", color="#f59e0b",
                   edgecolors="#111827", linewidths=1.2, zorder=7)
        ax.annotate(
            f"Điểm tối ưu\n({bx:.3g}, {by:.3g})\nz = {bz:.3g}",
            xy=(bx,by), xytext=(14,18), textcoords="offset points",
            fontsize=10, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.35",
                      fc="#fff7ed", ec="#fb923c", alpha=0.98),
            arrowprops=dict(arrowstyle="->", color="#fb923c", lw=1.5), zorder=8)

    def _configure_axes(self, ax, xmin, xmax, ymin, ymax):
        ax.set_xlim(xmin,xmax); ax.set_ylim(ymin,ymax)
        ax.set_aspect("auto", adjustable="box")
        ax.set_xlabel("x₁", fontsize=12, fontweight="bold")
        ax.set_ylabel("x₂", fontsize=12, fontweight="bold")
        ax.set_title("Miền chấp nhận được và đường đồng mức hàm mục tiêu",
                     fontsize=14, fontweight="bold", pad=10, color="#0f172a")
        ax.axhline(0,color="#334155",linewidth=1.1,alpha=0.7,zorder=0.5)
        ax.axvline(0,color="#334155",linewidth=1.1,alpha=0.7,zorder=0.5)
        hs, ls = ax.get_legend_handles_labels()
        if hs:
            ax.legend(hs,ls,loc="upper left",frameon=True,fontsize=9,
                      title="Ràng buộc",title_fontsize=10,fancybox=True,
                      shadow=False,facecolor="#ffffff",edgecolor="#cbd5e1")

    def _create_control_button(self, parent, text, color, hover_color, command):
        btn = tk.Button(parent, text=text, font=("Segoe UI",10,"bold"),
                        bg=color, fg="white", activebackground=hover_color,
                        activeforeground="white", relief="flat", bd=0,
                        padx=10, pady=6, cursor="hand2", command=command)
        btn.pack(side="left", padx=4, pady=4)
        btn.bind("<Enter>", lambda e: btn.config(bg=hover_color))
        btn.bind("<Leave>", lambda e: btn.config(bg=color))
        return btn

    def _enable_canvas_interactions(self, ax, canvas):
        state = {"press": None}
        def clamp():
            xm,xx = ax.get_xlim(); ym,yx = ax.get_ylim()
            if xx-xm < 1e-6: ax.set_xlim(xm-1,xx+1)
            if yx-ym < 1e-6: ax.set_ylim(ym-1,yx+1)
        def on_press(ev):
            if ev.inaxes!=ax or ev.button!=1 or ev.xdata is None: return
            state["press"]=(ev.xdata,ev.ydata,ax.get_xlim(),ax.get_ylim())
        def on_release(ev): state["press"]=None
        def on_move(ev):
            if not state["press"] or ev.inaxes!=ax or ev.xdata is None: return
            x0,y0,xl,yl = state["press"]
            ax.set_xlim(xl[0]+x0-ev.xdata, xl[1]+x0-ev.xdata)
            ax.set_ylim(yl[0]+y0-ev.ydata, yl[1]+y0-ev.ydata)
            clamp(); self._request_canvas_redraw(canvas)
        def on_scroll(ev):
            if ev.inaxes!=ax or ev.xdata is None: return
            base=1.10 if getattr(ev,"button",None)=="down" else 1/1.10
            xl=ax.get_xlim(); yl=ax.get_ylim()
            xd,yd=ev.xdata,ev.ydata
            nw=(xl[1]-xl[0])*base; nh=(yl[1]-yl[0])*base
            rx=(xl[1]-xd)/(xl[1]-xl[0]); ry=(yl[1]-yd)/(yl[1]-yl[0])
            ax.set_xlim(xd-(1-rx)*nw, xd+rx*nw)
            ax.set_ylim(yd-(1-ry)*nh, yd+ry*nh)
            clamp(); self._request_canvas_redraw(canvas)
        canvas.mpl_connect("button_press_event",on_press)
        canvas.mpl_connect("button_release_event",on_release)
        canvas.mpl_connect("motion_notify_event",on_move)
        canvas.mpl_connect("scroll_event",on_scroll)

    def _create_zoom_controls(self, parent, ax, canvas, initial_xlim, initial_ylim):
        cf = tk.Frame(parent, bg="#0f172a",
                      highlightthickness=1, highlightbackground="#334155")
        cf.place(relx=0.015, rely=0.965, anchor="sw")
        def zi():
            x1,x2=ax.get_xlim(); y1,y2=ax.get_ylim()
            dx=(x2-x1)*0.14; dy=(y2-y1)*0.14
            ax.set_xlim(x1+dx,x2-dx); ax.set_ylim(y1+dy,y2-dy)
            self._request_canvas_redraw(canvas)
        def zo():
            x1,x2=ax.get_xlim(); y1,y2=ax.get_ylim()
            dx=(x2-x1)*0.14; dy=(y2-y1)*0.14
            ax.set_xlim(x1-dx,x2+dx); ax.set_ylim(y1-dy,y2+dy)
            self._request_canvas_redraw(canvas)
        def rst():
            ax.set_xlim(initial_xlim); ax.set_ylim(initial_ylim)
            self._request_canvas_redraw(canvas)
        self._create_control_button(cf,"+","#2563eb","#1d4ed8",zi)
        self._create_control_button(cf,"−","#f59e0b","#d97706",zo)
        self._create_control_button(cf,"return","#10b981","#059669",rst)
        tk.Label(cf, text="Kéo chuột trái để di chuyển -- Lăn chuột để zoom",
                 bg="#0f172a", fg="#e2e8f0", font=("Segoe UI",9)).pack(
            side="left", padx=10, pady=6)

    def _create_info_panel(self, parent, prob, vertices, vv, optimal, maximize):
        info_frame = tk.Frame(parent, bg="#ffffff", bd=0,
                              highlightthickness=1, highlightbackground="#cbd5e1")
        info_frame.place(relx=0.987, rely=0.02, anchor="ne", width=320, height=182)
        title = tk.Label(info_frame, text="Tóm tắt", bg="#ffffff",
                         fg="#0f172a", font=("Segoe UI",11,"bold"))
        title.pack(anchor="w", padx=10, pady=(8,2))
        text = tk.Text(info_frame, wrap="word", bg="#ffffff", fg="#0f172a",
                       bd=0, font=("Segoe UI",9), height=8, padx=10, pady=6)
        text.pack(fill="both", expand=True)
        lines = [
            f"Kiểu: {'Bài toán Max' if prob.objective_sense=='max' else 'Bài toán Min'}",
            f"Số ràng buộc: {len(prob.constraints)}",
            f"Số đỉnh khả thi: {len(vertices)}",
        ]
        if optimal: lines += [f"Điểm tối ưu: ({optimal[0]:.3g}, {optimal[1]:.3g})",
                               f"Giá trị mục tiêu: {optimal[2]:.3g}"]
        else: lines.append("Chưa tìm được miền khả thi.")
        lines += ["Kéo chuột trái để pan.", "Dùng nút hoặc lăn chuột để zoom."]
        text.insert("1.0", "\n".join(lines))
        text.config(state="disabled")


    def _format_problem(self, engine):
        mode = self.data_mode.get()
        def expr(coeffs, names):
            parts=[]
            for c,nm in zip(coeffs,names):
                if c==0: continue
                if c==1: parts.append(f"+ {nm}")
                elif c==-1: parts.append(f"- {nm}")
                elif c>0: parts.append(f"+ {fmt_num(c,mode)}{nm}")
                else: parts.append(f"- {fmt_num(-c,mode)}{nm}")
            if not parts: return "0"
            s=" ".join(parts)
            return s[2:] if s.startswith("+ ") else s
        lines=["Bài tập Quy Hoạch Tuyến Tính — Phương pháp Đơn hình","  Bài toán gốc:"]
        n=len(engine.problem.obj_coeffs)
        lines.append(f"    {engine.problem.objective_sense} Z = {expr(engine.problem.obj_coeffs,[f'x{i+1}' for i in range(n)])}")
        lines.append("    {")
        for cons in engine.problem.constraints:
            lines.append(f"      {expr(cons['coeffs'],[f'x{i+1}' for i in range(len(cons['coeffs']))])} {cons['sense']} {fmt_num(cons['rhs'],mode)}")
        lines.append(f"    {', '.join(f'x{i+1}' for i in range(len(engine.problem.var_signs)))} thuộc các điều kiện dấu đã chọn")
        lines.append("    }")
        return "\n".join(lines)

    def _format_standardization(self, engine):
        mode = self.data_mode.get()
        def expr(coeffs, names):
            parts=[]
            for c,nm in zip(coeffs,names):
                if c==0: continue
                if c==1: parts.append(f"+ {nm}")
                elif c==-1: parts.append(f"- {nm}")
                elif c>0: parts.append(f"+ {fmt_num(c,mode)}{nm}")
                else: parts.append(f"- {fmt_num(-c,mode)}{nm}")
            if not parts: return "0"
            s=" ".join(parts)
            return s[2:] if s.startswith("+ ") else s
        n_orig=len(engine.problem.var_signs)
        extra_x=[nm for nm in engine.std_names if nm.startswith("x") and nm not in {f"x{i+1}" for i in range(n_orig)}]
        lines=["========================","*Chuẩn hóa bài toán gốc:","========================","","_Chuẩn hóa ràng buộc dấu:"]
        for idx,sign in enumerate(engine.problem.var_signs):
            nm=f"x{idx+1}"
            if sign=="≥0": lines.append(f"        {nm} ≥ 0: giữ nguyên {nm} ≥ 0")
            elif sign=="≤0": lines.append(f"        {nm} tự do âm: đặt {nm} = -y{idx+1}, với y{idx+1} ≥ 0")
            else: lines.append(f"        {nm} tự do: đặt {nm} = a{idx+1} - b{idx+1}, với a{idx+1}, b{idx+1} ≥ 0")
        lines+=["","_Chuẩn hóa ràng buộc đẳng thức, bất đẳng thức:"]
        sc=n_orig+1
        for i,cons in enumerate(engine.problem.constraints):
            s=cons["sense"]
            if s=="≤": lines.append(f"    RB{i+1}: giữ nguyên")
            elif s=="≥": lines.append(f"    RB{i+1}: nhân (-1) để đưa về ≤")
            else:
                snm=f"x{sc}"; sc+=1
                lines.append(f"    RB{i+1}: trừ thêm biến bù {snm} ≥ 0")
                row=engine.std_constraints[i]; names=engine.std_names[:len(row)]
                lines.append(f"    ---> RB{i+1}:  {expr(row,names)} ≤ {fmt_num(engine.std_rhs[i],mode)}")
        lines+=["","_Các biến sau chuẩn hóa:"]
        for idx,sign in enumerate(engine.problem.var_signs):
            if sign=="≥0": lines.append(f"        x{idx+1} = x{idx+1}")
            elif sign=="≤0": lines.append(f"        x{idx+1} = -y{idx+1}")
            else: lines.append(f"        x{idx+1} = a{idx+1} - b{idx+1}")
        for nm in extra_x: lines.append(f"        {nm} = {nm}")
        lines+=["","_Chuẩn hóa hàm mục tiêu:"]
        if engine.problem.objective_sense=="min": lines.append("    Hàm min, giữ nguyên:")
        else: lines.append("    Hàm max → nhân (-1):")
        obj_expr=expr(engine.std_obj_coeffs, engine.std_names)
        lines.append(f"        min Z = {obj_expr}")
        lines+=["","=========================","*Dạng chuẩn của bài toán:","=========================",f"    min Z = {obj_expr}","    {"]
        for i,row in enumerate(engine.std_constraints):
            lines.append(f"      {expr(row,engine.std_names[:len(row)])} ≤ {fmt_num(engine.std_rhs[i],mode)}")
        slack_names=[nm for nm in engine.std_names if nm.startswith("x") and nm not in {f"x{i+1}" for i in range(n_orig)}]
        aux_names=[nm for nm in engine.std_names if not nm.startswith("x")]
        var_list=[f"x{i+1}" for i in range(n_orig)]+slack_names+aux_names
        lines.append(f"    {', '.join(var_list)} ≥ 0")
        lines.append("    }")
        return "\n".join(lines)

    def _dict_lines(self, snapshot):
        mode=self.data_mode.get(); names=snapshot.all_names
        widths=[]
        for j,name in enumerate(names):
            ml=len(name)
            for c in [snapshot.obj.get(j,Fraction(0))]+[r.get(j,Fraction(0)) for r in snapshot.rows]:
                ml=max(ml,len(term_str(c,name,mode)))
            widths.append(max(8,min(14,ml+2)))
        def line_for(label,const,coeffs):
            out=[f"{label} = {fmt_num(const,mode)}"]
            for j,name in enumerate(names):
                out.append(term_str(coeffs.get(j,Fraction(0)),name,mode).ljust(widths[j]))
            return " ".join(out).rstrip()
        lines=[line_for(snapshot.objective_label, snapshot.obj_const, snapshot.obj)]
        for i,b in enumerate(snapshot.basis):
            lines.append(line_for(names[b], snapshot.rhs[i], snapshot.rows[i]))
        return lines

    def _insert_snapshot(self, snapshot, title, tags=None):
        self.output.insert(tk.END, title+"\n","h2")
        start=self.output.index(tk.END)
        for line in self._dict_lines(snapshot):
            self.output.insert(tk.END, line+"\n","mono")
        if tags and snapshot.all_names:
            var_name=tags.get("entering"); pivot_row=tags.get("pivot_row")
            if var_name:
                end=self.output.index(tk.END); idx=start
                while True:
                    pos=self.output.search(var_name,idx,stopindex=end)
                    if not pos: break
                    self.output.tag_add("pivotcol",pos,f"{pos}+{len(var_name)}c")
                    idx=f"{pos}+{len(var_name)}c"
            if pivot_row is not None:
                rn=int(start.split(".")[0])+int(pivot_row)
                self.output.tag_add("pivotrow",f"{rn}.0",f"{rn}.end")
                if var_name:
                    lt=self.output.get(f"{rn}.0",f"{rn}.end"); p=lt.find(var_name)
                    if p!=-1: self.output.tag_add("pivotcell",f"{rn}.{p}",f"{rn}.{p+len(var_name)}")

    def _insert_step_note(self, step, snapshot):
        mode=self.data_mode.get(); names=snapshot.all_names
        enter=names[step.entering] if step.entering is not None else "?"
        leave=names[step.leaving_var] if step.leaving_var is not None else "?"
        rule="Dantzig" if step.method=="dantzig" else "Bland"
        if step.status=="phase1_aux_pivot":
            self.output.insert(tk.END,"Theo quy tắc Dantzig:\n","h2")
            self.output.insert(tk.END,"— Pha 1: x0 là biến vào, biến ra là hàng có b_i âm.\n","note")
            if step.ratios:
                self.output.insert(tk.END,"— Xét các b_i âm:\n","note")
                for ri,bval,bi in step.ratios:
                    self.output.insert(tk.END,f"  • {names[bi]}: {fmt_num(bval,mode)}\n","note")
            self.output.insert(tk.END,f"  ⟹ biến vào: {enter}\n  ⟹ biến ra: {leave}\n","note")
            if step.pivot_value is not None:
                self.output.insert(tk.END,f"— Phần tử xoay: a_{{{leave},{enter}}} = {fmt_num(step.pivot_value,mode)}.\n","note")
            if step.degenerate: self.output.insert(tk.END,"— Bước suy biến (θ=0).\n","warn")
            return
        self.output.insert(tk.END,f"Theo quy tắc {rule}:\n","h2")
        if step.entering is not None:
            coeff=snapshot.obj.get(step.entering,Fraction(0))
            if step.method=="dantzig":
                self.output.insert(tk.END,f"— Chọn {enter} vì hệ số nhỏ nhất {fmt_num(coeff,mode)}.\n","note")
            else:
                self.output.insert(tk.END,f"— Bland: chọn {enter}.\n","note")
            self.output.insert(tk.END,f"  ⟹ biến vào: {enter}\n","note")
        if step.ratios:
            self.output.insert(tk.END,f"— Tỉ số tại cột {enter}:\n","note")
            for ri,theta,bi in step.ratios:
                coeff=snapshot.rows[ri][step.entering] if step.entering is not None else Fraction(1)
                self.output.insert(tk.END,f"  • {names[bi]}: {fmt_num(snapshot.rhs[ri],mode)} / {fmt_num(-coeff,mode)} = {fmt_num(theta,mode)}\n","note")
            self.output.insert(tk.END,f"  ⟹ biến ra: {leave}\n","note")
        if step.pivot_value is not None:
            self.output.insert(tk.END,f"— Phần tử xoay: a_{{{leave},{enter}}} = {fmt_num(step.pivot_value,mode)}.\n","note")
        if step.degenerate: self.output.insert(tk.END,"— Bước suy biến (θ=0).\n","warn")

    def _linear_text(self, const, terms, mode):
        parts=[]
        if const!=0 or not terms: parts.append(fmt_num(const,mode))
        for coef,name in terms:
            if coef==0: continue
            body=name if abs(coef)==1 else f"{fmt_num(abs(coef),mode)}{name}"
            if parts: parts.append(f"+ {body}" if coef>0 else f"- {body}")
            else: parts.append(body if coef>0 else f"- {body}")
        return " ".join(parts).strip() if parts else "0"

    def _format_multiple_optimal_family(self, engine, snapshot, report):
        mode=self.data_mode.get(); free_vars=report.multiple_optimal_vars or []
        if not free_vars: return []
        param_name=snapshot.all_names[free_vars[0]]
        lines=[f"  Do hệ số trước {param_name} bằng 0. Bài toán có vô số nghiệm.\n  Cho các biến mục tiêu bằng 0:","",f"    z = {fmt_num(snapshot.obj_const,mode)}"]
        def row_expr(ri):
            terms=[(snapshot.rows[ri].get(fv,Fraction(0)),snapshot.all_names[fv]) for fv in free_vars if snapshot.rows[ri].get(fv,Fraction(0))!=0]
            return self._linear_text(snapshot.rhs[ri],terms,mode)
        for ri,b in enumerate(snapshot.basis): lines.append(f"    {snapshot.all_names[b]} = {row_expr(ri)}")
        return lines

    def _format_multiple_optimal_conclusion(self, engine, snapshot, report):
        mode=self.data_mode.get(); free_vars=report.multiple_optimal_vars or []
        if not free_vars: return []
        lines=["  Nghiệm tối ưu:","  {"]
        bp={b:i for i,b in enumerate(snapshot.basis)}
        def std_expr(idx):
            if idx in bp:
                r=bp[idx]; terms=[(snapshot.rows[r].get(fv,Fraction(0)),snapshot.all_names[fv]) for fv in free_vars if snapshot.rows[r].get(fv,Fraction(0))!=0]
                return snapshot.rhs[r],terms
            if idx in free_vars: return Fraction(0),[(Fraction(1),snapshot.all_names[idx])]
            return Fraction(0),[]
        for orig_idx,mapping in enumerate(engine.variable_mapping):
            if len(mapping)==1 and mapping[0][0] in free_vars and mapping[0][1]==Fraction(1):
                lines.append(f"    x{orig_idx+1} ≥ 0"); continue
            const=Fraction(0); terms=[]
            for si,mc in mapping:
                sc,st=std_expr(si); const+=mc*sc
                for coef,name in st: terms.append((mc*coef,name))
            lines.append(f"    x{orig_idx+1} = {self._linear_text(const,terms,mode)}")
        lines.append("  }"); return lines

    def _render_trace(self, title, trace):
        if not trace.steps:
            self.output.insert(tk.END,"Từ vựng ban đầu:\n","h2")
            if trace.final_snapshot: self._insert_snapshot(trace.final_snapshot,"")
            return
        for step in trace.steps:
            t="Từ vựng ban đầu:" if step.iteration==1 else f"Bước {step.iteration} trước xoay:"
            self._insert_snapshot(step.before,t,
                tags={"entering":step.before.all_names[step.entering] if step.entering is not None else None,"pivot_row":step.leaving_row} if step.entering is not None else None)
            self.output.insert(tk.END,"\n")
            self._insert_step_note(step,step.before)
            self.output.insert(tk.END,"\n")
            if step.after is not None:
                self._insert_snapshot(step.after,f"Sau xoay bước {step.iteration}:")
                self.output.insert(tk.END,"\n")
        if trace.status=="optimal": self.output.insert(tk.END,"  Các hệ số cải thiện không còn âm → tối ưu.\n","note")
        elif trace.status=="unbounded": self.output.insert(tk.END,"  Bài toán không giới nội.\n","warn")
        elif trace.status=="cycle": self.output.insert(tk.END,"  Dantzig lặp → chuyển sang Bland.\n","warn")

    def _render_result(self, report):
        self.output.delete("1.0",tk.END)
        engine=report.engine; mode=self.data_mode.get()
        self.output.insert(tk.END,self._format_problem(engine)+"\n\n","h1")
        self.output.insert(tk.END,self._format_standardization(engine)+"\n","mono")
        if self._has_aux_phase1(engine):
            self.output.insert(tk.END,"\n=============================\n*Pha 1: Giải bài toán bổ trợ\n=============================\n","h2")
            self.output.insert(tk.END,"_ Tồn tại b_i âm → giải pha 1 bằng biến phụ x0\n","note")
            self._render_trace("Pha 1",report.dantzig)
            if report.phase1_bland is not None and report.phase1_bland is not report.dantzig:
                self.output.insert(tk.END,"\n*Bland sau Dantzig lặp ở pha 1\n","h2")
                self._render_trace("Pha 1 - Bland",report.phase1_bland)
            self.output.insert(tk.END,"\n")
            if report.status=="infeasible":
                self.output.insert(tk.END,"\nKẾT LUẬN\n","h2")
                self.output.insert(tk.END,"  Vô nghiệm: x0 vẫn trong cơ sở.\n","warn"); return
            if report.phase2_trace is not None:
                self.output.insert(tk.END,"\n============================\n*Pha 2: Giải bài toán gốc\n============================\n","h2")
                self._render_trace("Pha 2",report.phase2_trace)
            else:
                self.output.insert(tk.END,"\nKẾT LUẬN\n  Vô nghiệm.\n","warn"); return
        else:
            self.output.insert(tk.END,"\n============================\n*Pha 1:\n============================\n_ b_i ≥ 0, không cần pha 1.\n\n============================\n*Pha 2: Giải bài toán gốc\n============================\n","h2")
            self._render_trace("Pha 2",report.dantzig)
            if report.bland is not None and report.bland is not report.dantzig:
                self.output.insert(tk.END,"\n*Bland sau Dantzig lặp ở pha 2\n","h2")
                self._render_trace("Pha 2 - Bland",report.bland)
        final=report.phase2_trace.final_snapshot if report.phase2_trace and report.phase2_trace.final_snapshot else (report.bland.final_snapshot if report.bland and report.bland.final_snapshot else report.dantzig.final_snapshot)
        if report.status in ("unbounded",) or (report.bland and report.bland.status=="unbounded"):
            self.output.insert(tk.END,"\nKẾT LUẬN\n  Không giới nội.\n","warn"); return
        if report.status=="cycle":
            self.output.insert(tk.END,"\nKẾT LUẬN\n  Dantzig và Bland đều lặp.\n","warn"); return
        obj_std=report.objective_std or Fraction(0)
        obj_orig=report.objective_orig or Fraction(0)
        if report.multiple_optimal and final and report.multiple_optimal_vars:
            for line in self._format_multiple_optimal_family(engine,final,report):
                self.output.insert(tk.END,line+"\n","warn" if "vô số" in line else "note")
            self.output.insert(tk.END,"\nKẾT LUẬN\n","h2")
            self.output.insert(tk.END,f"  Tối ưu ({report.used_method.upper()}), z* = {fmt_num(obj_std,mode)}, gốc: {fmt_num(obj_orig,mode)}\n","note")
            for line in self._format_multiple_optimal_conclusion(engine,final,report):
                self.output.insert(tk.END,line+"\n","note")
        else:
            self.output.insert(tk.END,"\nKẾT LUẬN\n","h2")
            self.output.insert(tk.END,f"  Tối ưu ({report.used_method.upper()}).\n  z* (bảng min) = {fmt_num(obj_std,mode)}\n  Giá trị gốc: {fmt_num(obj_orig,mode)}\n","note")
            orig_parts=[f"x{i+1} = {fmt_num(report.solution_orig.get(i,Fraction(0)),mode)}" for i in range(len(engine.problem.var_signs))]
            self.output.insert(tk.END,"  Nghiệm: "+"  ;  ".join(orig_parts)+"\n","note")
        d=(report.dantzig.degenerate_steps or 0)+((report.bland.degenerate_steps if report.bland else 0) or 0)
        if d: self.output.insert(tk.END,f"  Có {d} bước suy biến.\n","warn")

    def _has_aux_phase1(self, engine):
        return bool(getattr(engine,"need_aux_phase1",False))

    def run_solver(self):
        try:
            prob=self._collect_problem()
            engine=SimplexEngine(prob)
            report=engine.solve_full()
            self.last_problem=prob; self.last_report=report
            self._render_result(report)
            self._set_solution_available(report.status=="optimal")
            self.status_var.set(f"Đã giải xong: {report.status}.")
        except Exception as exc:
            self.last_report=None; self._set_solution_available(False)
            messagebox.showerror("Lỗi nhập liệu / giải thuật",str(exc))
            self.status_var.set("Có lỗi xảy ra.")
