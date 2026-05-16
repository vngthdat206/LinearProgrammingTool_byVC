from __future__ import annotations

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from fractions import Fraction
from typing import List, Optional, Dict

if __package__ in (None, ""):
    from models import ProblemData, Snapshot, SolveReport, PivotStep, SENSES, VAR_SIGNS
    from simplex_engine import SimplexEngine
    from utils import parse_cell, fmt_num, term_str
else:
    from .models import ProblemData, Snapshot, SolveReport, PivotStep, SENSES, VAR_SIGNS
    from .simplex_engine import SimplexEngine
    from .utils import parse_cell, fmt_num, term_str


# =========================
# GUI App
# =========================

class SimplexApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Ứng dụng Quy hoạch tuyến tính — Đơn hình")
        self.geometry("1380x920")
        self.minsize(1100, 760)

        self.objective_sense = tk.StringVar(value="max")
        self.n_vars = tk.IntVar(value=3)
        self.n_constraints = tk.IntVar(value=3)
        self.data_mode = tk.StringVar(value="fraction")
        self.method_preference = tk.StringVar(value="auto")
        self.need_aux_phase1 = False
        self.phase1_aux_var_index: Optional[int] = None

        self.obj_entries: List[tk.Entry] = []
        self.var_signs: List[ttk.Combobox] = []
        self.constraint_entries: List[List[tk.Entry]] = []
        self.constraint_senses: List[ttk.Combobox] = []
        self.constraint_rhs: List[tk.Entry] = []

        self.need_aux_phase1 = False
        self.phase1_aux_var_index: Optional[int] = None
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
        style.configure("Header.TLabel", background="#1f2937", foreground="#ffffff", font=("Segoe UI", 16, "bold"))
        style.configure("SubHeader.TLabel", background="#1f2937", foreground="#dbeafe", font=("Segoe UI", 10))
        style.configure("TLabel", background="#f4f1eb", foreground="#172033", font=("Segoe UI", 10))
        style.configure("TLabelframe", background="#f4f1eb", borderwidth=1)
        style.configure("TLabelframe.Label", background="#f4f1eb", foreground="#111827", font=("Segoe UI", 10, "bold"))
        style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=8)
        style.configure("Accent.TButton", background="#2563eb", foreground="white")
        style.map("Accent.TButton", background=[("active", "#1d4ed8")])
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
        ttk.Label(header, text="Ứng dụng Quy hoạch tuyến tính — Phương pháp Đơn hình", style="Header.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            header,
            text="Tab để chuyển ô • Ctrl+Alt+R để giải • Hỗ trợ max/min, ràng buộc ≤ ≥ =, biến tự do và biến dấu âm",
            style="SubHeader.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        main = ttk.Frame(self, padding=14)
        main.grid(row=1, column=0, sticky="nsew")
        main.columnconfigure(0, weight=0)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        left = ttk.Frame(main)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.rowconfigure(2, weight=0)
        left.rowconfigure(3, weight=1)

        config = ttk.Labelframe(left, text="Thiết lập", padding=12)
        config.grid(row=0, column=0, sticky="ew")
        config.columnconfigure(1, weight=1)

        ttk.Label(config, text="Kiểu dữ liệu:").grid(row=0, column=0, sticky="w", pady=3)
        mode = ttk.Combobox(config, textvariable=self.data_mode, values=["fraction", "decimal"], state="readonly", width=12)
        mode.grid(row=0, column=1, sticky="w", pady=3)

        ttk.Label(config, text="Số biến (1–5):").grid(row=1, column=0, sticky="w", pady=3)
        nvars = ttk.Spinbox(config, from_=1, to=5, textvariable=self.n_vars, width=10, command=self._build_inputs)
        nvars.grid(row=1, column=1, sticky="w", pady=3)

        ttk.Label(config, text="Số ràng buộc (1–10):").grid(row=2, column=0, sticky="w", pady=3)
        ncons = ttk.Spinbox(config, from_=1, to=10, textvariable=self.n_constraints, width=10, command=self._build_inputs)
        ncons.grid(row=2, column=1, sticky="w", pady=3)

        btns = ttk.Frame(left)
        btns.grid(row=1, column=0, sticky="ew", pady=(10, 10))
        btns.columnconfigure((0, 1), weight=1)
        ttk.Button(btns, text="Tạo lại bảng nhập", command=self._build_inputs).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(btns, text="Điền ví dụ", style="Warn.TButton", command=self.fill_demo).grid(row=0, column=1, sticky="ew", padx=(6, 0))
        ttk.Button(left, text="Chạy giải thuật  (Ctrl+Alt+R)", style="Accent.TButton", command=self.run_solver).grid(
            row=2, column=0, sticky="ew"
        )

        input_box = ttk.Labelframe(left, text="Nhập bài toán", padding=14)
        input_box.grid(row=3, column=0, sticky="nsew")
        input_box.columnconfigure(0, weight=1)
        input_box.rowconfigure(0, weight=1)
        self.input_canvas = tk.Canvas(input_box, background="#f4f1eb", highlightthickness=0, width=580, height=650)
        self.input_canvas.grid(row=0, column=0, sticky="nsew")
        vsb = ttk.Scrollbar(input_box, orient="vertical", command=self.input_canvas.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self.input_canvas.configure(yscrollcommand=vsb.set)
        self.input_inner = ttk.Frame(self.input_canvas)
        self.input_window = self.input_canvas.create_window((0, 0), window=self.input_inner, anchor="nw")
        self.input_inner.bind("<Configure>", lambda e: self.input_canvas.configure(scrollregion=self.input_canvas.bbox("all")))
        self.input_canvas.bind("<Configure>", lambda e: self.input_canvas.itemconfigure(self.input_window, width=e.width))

        right = ttk.Labelframe(main, text="Lời giải", padding=8)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        self.output = scrolledtext.ScrolledText(
            right,
            wrap="none",
            font=("Consolas", 12),
            bg="#fbfaf6",
            fg="#1e1b1b",
            insertbackground="#1e1b1b",
            relief="flat",
            padx=14,
            pady=10,
        )
        self.output.grid(row=0, column=0, sticky="nsew")
        self.output.tag_configure("h1", font=("Segoe UI", 15, "bold"), foreground="#b45309", spacing1=8, spacing3=10)
        self.output.tag_configure("h2", font=("Segoe UI", 12, "bold"), foreground="#1f2937", spacing1=8, spacing3=4)
        self.output.tag_configure("note", foreground="#0f4c81")
        self.output.tag_configure("warn", foreground="#a16207")
        self.output.tag_configure("mono", font=("Consolas", 12))
        self.output.tag_configure("pivotcol", background="#fde68a")
        self.output.tag_configure("pivotrow", background="#dbeafe")
        self.output.tag_configure("pivotcell", background="#fca5a5")
        self.output.tag_configure("conclusion", background="#fff7ed")

        self.status_var = tk.StringVar(value="Sẵn sàng.")
        status = ttk.Label(self, textvariable=self.status_var, anchor="w", padding=(14, 6))
        status.grid(row=2, column=0, sticky="ew")

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

        # Objective block
        obj_frame = ttk.Labelframe(self.input_inner, text="Hàm mục tiêu", padding=10)
        obj_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        obj_frame.columnconfigure(1, weight=1)

        ttk.Label(obj_frame, text="Kiểu bài toán:").grid(row=0, column=0, sticky="w")
        ttk.Combobox(obj_frame, textvariable=self.objective_sense, values=["max", "min"], state="readonly", width=8).grid(
            row=0, column=1, sticky="w", pady=2
        )
        ttk.Label(obj_frame, text="Hệ số:").grid(row=1, column=0, sticky="w", pady=(8, 2))
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
        sign_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        for j in range(n):
            sign_cell = ttk.Frame(sign_frame)
            sign_cell.grid(row=0, column=j, padx=4, sticky="ew")
            ttk.Label(sign_cell, text=f"x{j+1}").grid(row=0, column=0, sticky="w")
            cb = ttk.Combobox(sign_cell, values=VAR_SIGNS, state="readonly", width=10)
            cb.set(">=0")
            cb.grid(row=1, column=0, sticky="ew")
            self.var_signs.append(cb)

        # Constraints block
        cons_frame = ttk.Labelframe(self.input_inner, text="Ràng buộc", padding=10)
        cons_frame.grid(row=1, column=0, sticky="nsew")
        cons_frame.columnconfigure(0, weight=1)

        ttk.Label(cons_frame, text="Nhập hệ số từng ràng buộc, chọn dấu rồi nhập vế phải.").grid(row=0, column=0, sticky="w", pady=(0, 6))
        table = ttk.Frame(cons_frame)
        table.grid(row=1, column=0, sticky="ew")
        for j in range(n):
            table.columnconfigure(j, weight=1)
        table.columnconfigure(n, weight=0)
        table.columnconfigure(n+1, weight=0)
        table.columnconfigure(n+2, weight=0)

        header = ttk.Frame(table)
        header.grid(row=0, column=0, columnspan=n+3, sticky="ew")
        ttk.Label(header, text="").grid(row=0, column=0, padx=2)
        for j in range(n):
            ttk.Label(header, text=f"x{j+1}", width=8, anchor="center").grid(row=0, column=j+1, padx=2)
        ttk.Label(header, text="Dấu", width=8, anchor="center").grid(row=0, column=n+1, padx=2)
        ttk.Label(header, text="Bên phải", width=10, anchor="center").grid(row=0, column=n+2, padx=2)

        for i in range(m):
            row_frame = ttk.Frame(table)
            row_frame.grid(row=i+1, column=0, columnspan=n+3, sticky="ew", pady=2)
            ttk.Label(row_frame, text=f"(RB{i+1})", width=5).grid(row=0, column=0, padx=2)
            row_entries = []
            for j in range(n):
                e = ttk.Entry(row_frame, width=10)
                e.grid(row=0, column=j+1, padx=2)
                row_entries.append(e)
            cb = ttk.Combobox(row_frame, values=SENSES, state="readonly", width=6)
            cb.set("<=")
            cb.grid(row=0, column=n+1, padx=2)
            rhs = ttk.Entry(row_frame, width=10)
            rhs.grid(row=0, column=n+2, padx=2)
            self.constraint_entries.append(row_entries)
            self.constraint_senses.append(cb)
            self.constraint_rhs.append(rhs)

        hint = ttk.Label(
            self.input_inner,
            text="Muốn chuyển con trỏ nhập liệu sang ô khác bấm phím Tab. Dùng Ctrl+Alt+R để chạy quá trình giải thuật.",
            foreground="#92400e",
        )
        hint.grid(row=2, column=0, sticky="w", pady=(10, 0))

        self.input_inner.update_idletasks()
        self.input_canvas.configure(scrollregion=self.input_canvas.bbox("all"))

    def fill_demo(self):
        # Demo theo bài mẫu pha 1 người dùng cung cấp
        self.n_vars.set(2)
        self.n_constraints.set(3)
        self.objective_sense.set("min")
        self._build_inputs()

        demo_obj = ["5", "-7"]
        for i, e in enumerate(self.obj_entries):
            e.delete(0, tk.END)
            if i < len(demo_obj):
                e.insert(0, demo_obj[i])

        for i, cb in enumerate(self.var_signs):
            cb.set(">=0")

        data = [
            (["-4", "1"], "<=", "-2"),
            (["1", "1"], "<=", "5"),
            (["-1", "-1"], "<=", "-1"),
        ]
        for i in range(3):
            coeffs, sense, rhs = data[i]
            for j, e in enumerate(self.constraint_entries[i]):
                e.delete(0, tk.END)
                if j < len(coeffs):
                    e.insert(0, coeffs[j])
            self.constraint_senses[i].set(sense)
            self.constraint_rhs[i].delete(0, tk.END)
            self.constraint_rhs[i].insert(0, rhs)

    def _collect_problem(self) -> ProblemData:
        n = int(self.n_vars.get())
        m = int(self.n_constraints.get())
        obj_coeffs = [parse_cell(e.get(), self.data_mode.get()) for e in self.obj_entries[:n]]
        var_signs = [cb.get() or ">=0" for cb in self.var_signs[:n]]
        constraints = []
        for i in range(m):
            coeffs = [parse_cell(e.get(), self.data_mode.get()) for e in self.constraint_entries[i][:n]]
            sense = self.constraint_senses[i].get() or "<="
            rhs = parse_cell(self.constraint_rhs[i].get(), self.data_mode.get())
            constraints.append({"coeffs": coeffs, "sense": sense, "rhs": rhs})
        return ProblemData(
            objective_sense=self.objective_sense.get(),
            obj_coeffs=obj_coeffs,
            constraints=constraints,
            var_signs=var_signs,
        )

    # ---------- formatting ----------
    def _format_problem(self, engine: SimplexEngine) -> str:
        mode = self.data_mode.get()
        lines = []
        lines.append("Bài tập Quy Hoạch Tuyến Tính — Phương pháp Đơn hình")
        lines.append("")
        lines.append("a)")
        lines.append("")
        lines.append("  Bài toán gốc:")
        obj_terms = []
        for i, c in enumerate(engine.problem.obj_coeffs):
            name = f"x{i+1}"
            if c == 0:
                continue
            sign = "+" if c > 0 else "-"
            abs_c = abs(c)
            if abs_c == 1:
                obj_terms.append(f"{sign} {name}")
            else:
                obj_terms.append(f"{sign} {fmt_num(abs_c, mode)}{name}")
        obj_text = " ".join(obj_terms).lstrip("+").strip() or "0"
        lines.append(f"  {engine.problem.objective_sense} Z = {obj_text}")
        lines.append("  {")
        for cons in engine.problem.constraints:
            row_terms = []
            for j, a in enumerate(cons["coeffs"]):
                if a == 0:
                    continue
                name = f"x{j+1}"
                sign = "+" if a > 0 else "-"
                abs_a = abs(a)
                if abs_a == 1:
                    row_terms.append(f"{sign} {name}")
                else:
                    row_terms.append(f"{sign} {fmt_num(abs_a, mode)}{name}")
            row_text = " ".join(row_terms).lstrip("+").strip() or "0"
            lines.append(f"    {row_text} {cons['sense']} {fmt_num(cons['rhs'], mode)}")
        lines.append("    " + ", ".join([f"x{i+1}" for i in range(len(engine.problem.var_signs))]) + " thuộc các điều kiện dấu đã chọn")
        lines.append("  }")
        lines.append("")
        return "\n".join(lines)

    def _format_standardization(self, engine: SimplexEngine) -> str:
        lines = []
        lines.append("  Đưa về dạng chuẩn:")
        obj_terms = []
        for i, c in enumerate(engine.std_obj_coeffs):
            if c == 0:
                continue
            name = engine.std_names[i]
            sign = "+" if c > 0 else "-"
            abs_c = abs(c)
            if abs_c == 1:
                obj_terms.append(f"{sign} {name}")
            else:
                obj_terms.append(f"{sign} {fmt_num(abs_c, self.data_mode.get())}{name}")
        obj_text = " ".join(obj_terms).lstrip("+").strip() or "0"
        lines.append(f"  min Z = {obj_text}")
        lines.append("  {")
        lines.append("    Quy ước đổi biến:")
        for line in engine.standardization_lines:
            lines.append(f"      {line}")
        for line in engine.strict_notes:
            lines.append(f"      {line}")
        lines.append("  }")
        lines.append("")
        return "\n".join(lines)

    def _dict_lines(self, snapshot: Snapshot) -> List[str]:
        mode = self.data_mode.get()
        names = snapshot.all_names
        # Width per variable column.
        widths = []
        for j, name in enumerate(names):
            max_len = len(name)
            # objective + rows
            candidates = [snapshot.obj.get(j, Fraction(0))]
            for r in snapshot.rows:
                candidates.append(r.get(j, Fraction(0)))
            for c in candidates:
                s = term_str(c, name, mode)
                max_len = max(max_len, len(s))
            widths.append(max(8, min(14, max_len + 2)))

        def line_for(label: str, const: Fraction, coeffs: Dict[int, Fraction]) -> str:
            out = [f"{label} = {fmt_num(const, mode)}"]
            for j, name in enumerate(names):
                cell = term_str(coeffs.get(j, Fraction(0)), name, mode)
                out.append(cell.ljust(widths[j]))
            return " ".join(out).rstrip()

        lines = [line_for(snapshot.objective_label, snapshot.obj_const, snapshot.obj)]
        for i, b in enumerate(snapshot.basis):
            lines.append(line_for(names[b], snapshot.rhs[i], snapshot.rows[i]))
        return lines

    def _insert_snapshot(self, snapshot: Snapshot, title: str, tags: Optional[Dict[str, str]] = None):
        self.output.insert(tk.END, title + "\n", "h2")
        start = self.output.index(tk.END)
        lines = self._dict_lines(snapshot)
        for line in lines:
            self.output.insert(tk.END, line + "\n", "mono")
        # tags
        if tags and snapshot.all_names:
            var_name = tags.get("entering")
            pivot_row = tags.get("pivot_row")
            if var_name:
                block_end = self.output.index(tk.END)
                idx = start
                while True:
                    pos = self.output.search(var_name, idx, stopindex=block_end)
                    if not pos:
                        break
                    self.output.tag_add("pivotcol", pos, f"{pos}+{len(var_name)}c")
                    idx = f"{pos}+{len(var_name)}c"
            if pivot_row is not None:
                row_no = int(start.split(".")[0]) + int(pivot_row)
                row_start = f"{row_no}.0"
                row_end = f"{row_no}.end"
                self.output.tag_add("pivotrow", row_start, row_end)
                if var_name:
                    line_text = self.output.get(row_start, row_end)
                    pos = line_text.find(var_name)
                    if pos != -1:
                        self.output.tag_add("pivotcell", f"{row_no}.{pos}", f"{row_no}.{pos+len(var_name)}")



    def _insert_step_note(self, step: PivotStep, snapshot: Snapshot):
        mode = self.data_mode.get()
        names = snapshot.all_names
        enter = names[step.entering] if step.entering is not None else "?"
        leave = names[step.leaving_var] if step.leaving_var is not None else "?"
        rule = "Dantzig" if step.method == "dantzig" else "Bland"

        if step.status == "phase1_aux_pivot":
            self.output.insert(tk.END, "Theo quy tắc Dantzig:\n", "h2")
            self.output.insert(tk.END, "— Pha 1: xét các b_i âm, chọn hàng có b_i âm nhất để đưa x0 vào cơ sở.\n", "note")
            if step.ratios:
                self.output.insert(tk.END, "— Xét các b_i âm:\n", "note")
                for row_idx, bval, basis_idx in step.ratios:
                    row_name = names[basis_idx]
                    self.output.insert(tk.END, f"  • {row_name}: {fmt_num(bval, mode)}\n", "note")
            self.output.insert(tk.END, f"  ⟹ biến vào: {enter}\n", "note")
            self.output.insert(tk.END, f"  ⟹ biến ra: {leave}\n", "note")
            if step.pivot_value is not None:
                self.output.insert(tk.END, f"— Phần tử xoay: a_{{{leave},{enter}}} = {fmt_num(step.pivot_value, mode)}.\n", "note")
            if step.degenerate:
                self.output.insert(tk.END, "— Bước này là suy biến vì θ = 0.\n", "warn")
            return

        self.output.insert(tk.END, f"Theo quy tắc {rule}:\n", "h2")
        if step.phase == 1:
            self.output.insert(tk.END, "— Pha 1 dùng biến giả để tìm cơ sở khả thi trước khi sang pha 2.\n", "note")
        if step.entering is not None:
            coeff = snapshot.obj.get(step.entering, Fraction(0))
            if step.method == "dantzig":
                self.output.insert(tk.END, f"— Trong các biến có hệ số âm trên hàm mục tiêu, chọn {enter} vì có hệ số nhỏ nhất {fmt_num(coeff, mode)}.\n", "note")
            else:
                self.output.insert(tk.END, f"— Bland: ưu tiên nhóm biến x trước rồi mới tới nhóm w; trong nhóm có hệ số âm, chọn {enter}.\n", "note")
            self.output.insert(tk.END, f"  ⟹ biến vào: {enter}\n", "note")
        if step.ratios:
            self.output.insert(tk.END, f"— Xét tỉ số tại cột {enter} (chỉ lấy hàng có hệ số âm):\n", "note")
            for row_idx, theta, basis_idx in step.ratios:
                row_name = names[basis_idx]
                coeff = snapshot.rows[row_idx][step.entering] if step.entering is not None else Fraction(1)
                self.output.insert(tk.END, f"  • {row_name}: {fmt_num(snapshot.rhs[row_idx], mode)} / {fmt_num(-coeff, mode)} = {fmt_num(theta, mode)}\n", "note")
            self.output.insert(tk.END, f"  ⟹ biến ra: {leave}\n", "note")
        if step.pivot_value is not None:
            self.output.insert(tk.END, f"— Phần tử xoay: a_{{{leave},{enter}}} = {fmt_num(step.pivot_value, mode)}.\n", "note")
        if step.degenerate:
            self.output.insert(tk.END, "— Bước này là suy biến vì θ = 0.\n", "warn")


    def _render_trace(self, title: str, trace: SolveTrace):
        header = f"* {title}:" if title.startswith("Pha ") else f"* Quy tắc {title}:"
        self.output.insert(tk.END, header + "\n", "h2")
        if not trace.steps:
            self.output.insert(tk.END, "— Từ vựng ban đầu\n", "note")
            if trace.final_snapshot:
                self._insert_snapshot(trace.final_snapshot, "", None)
            return
        current_phase = None
        for step in trace.steps:
            if current_phase != step.phase:
                current_phase = step.phase
                self.output.insert(tk.END, f"  * Pha {current_phase}\n", "h2")
            title_text = "  — Từ vựng ban đầu" if step.iteration == 1 else f"  — Bước {step.iteration} trước xoay"
            self._insert_snapshot(step.before, title_text, tags={"entering": step.before.all_names[step.entering] if step.entering is not None else None, "pivot_row": step.leaving_row} if step.entering is not None else None)
            self.output.insert(tk.END, "\n")
            self._insert_step_note(step, step.before)
            self.output.insert(tk.END, "\n")
            if step.after is not None:
                self._insert_snapshot(step.after, f"  — Sau xoay bước {step.iteration}")
                self.output.insert(tk.END, "\n")

        if trace.status == "optimal":
            self.output.insert(tk.END, "  Các hệ số cải thiện trên hàm mục tiêu đã không còn âm nên đạt tối ưu.\n", "note")
        elif trace.status == "unbounded":
            self.output.insert(tk.END, "  Bài toán không bị chặn: đã chọn được biến vào nhưng không còn hàng cho phép xoay.\n", "warn")
        elif trace.status == "cycle":
            self.output.insert(tk.END, "  Dantzig đã lặp cơ sở sau hữu hạn bước nên sẽ giải lại từ đầu bằng Bland.\n", "warn")


    def _render_result(self, report: SolveReport):
        self.output.delete("1.0", tk.END)
        engine = report.engine
        self.output.insert(tk.END, self._format_problem(engine), "h1")
        self.output.insert(tk.END, self._format_standardization(engine), "mono")

        if self._has_aux_phase1(engine):
            self.output.insert(tk.END, "  * Pha 1\n", "h2")
            self.output.insert(tk.END, "  Bài toán bổ trợ, (x0 ≥ 0), ta có\n\n", "note")
        elif self._has_artificial(engine):
            self.output.insert(tk.END, "  * Pha 1\n", "h2")
            self.output.insert(tk.END, "  Pha 1 dùng biến giả để tìm cơ sở khả thi trước khi sang pha 2.\n\n", "note")

        # Trace đầu tiên luôn là pha 1 / Dantzig ban đầu.
        self._render_trace("Dantzig", report.dantzig)
        self.output.insert(tk.END, "\n")

        if report.bland is not None:
            if self._has_aux_phase1(engine) and report.dantzig.status != "cycle":
                # report.bland là pha 2
                self.output.insert(tk.END, "  * Pha 2\n", "h2")
                self._render_trace("Pha 2", report.bland)
                self.output.insert(tk.END, "\n")
            else:
                if report.dantzig.status == "cycle":
                    self.output.insert(tk.END, "Dantzig lặp cơ sở nên chuyển sang Bland để giải lại từ đầu.\n\n", "warn")
                self._render_trace("Bland", report.bland)
                self.output.insert(tk.END, "\n")

        # Conclusion
        self.output.insert(tk.END, "KẾT LUẬN\n", "h2")
        if report.status == "infeasible":
            if self._has_aux_phase1(engine) and engine.phase1_aux_var_index is not None:
                self.output.insert(
                    tk.END,
                    "  Trạng thái: vô nghiệm. Pha 1 tối ưu nhưng x0 vẫn nằm trong cơ sở nên miền chấp nhận được là rỗng.\n",
                    "warn",
                )
            else:
                self.output.insert(tk.END, "  Trạng thái: vô nghiệm.\n", "warn")
            return
        if report.status == "unbounded":
            self.output.insert(tk.END, "  Trạng thái: không bị chặn.\n", "warn")
            return
        if report.status == "cycle":
            self.output.insert(tk.END, "  Trạng thái: Dantzig lặp và Bland cũng chưa kết thúc trong giới hạn lặp.\n", "warn")
            return

        obj_std = report.objective_std if report.objective_std is not None else Fraction(0)
        obj_orig = report.objective_orig if report.objective_orig is not None else Fraction(0)
        self.output.insert(tk.END, f"  Trạng thái: tối ưu đạt được bằng {report.used_method.upper()}.\n", "note")
        self.output.insert(tk.END, f"  Trong bảng min: z* = {fmt_num(obj_std, self.data_mode.get())}\n", "note")
        if engine.problem.objective_sense == "max":
            self.output.insert(tk.END, f"  Giá trị tối ưu của bài toán gốc: {fmt_num(obj_orig, self.data_mode.get())}\n", "note")
        else:
            self.output.insert(tk.END, f"  Giá trị tối ưu của bài toán gốc: {fmt_num(obj_orig, self.data_mode.get())}\n", "note")
        self.output.insert(tk.END, "  Nghiệm tối ưu: ", "note")
        orig_parts = []
        for i in range(len(engine.problem.var_signs)):
            orig_parts.append(f"x{i+1} = {fmt_num(report.solution_orig.get(i, Fraction(0)), self.data_mode.get())}")
        self.output.insert(tk.END, "; ".join(orig_parts) + "\n", "note")
        if report.multiple_optimal:
            self.output.insert(tk.END, "  Có dấu hiệu đa nghiệm vì còn biến không cơ sở với chi phí giảm bằng 0.\n", "warn")
        if report.dantzig.degenerate_steps or (report.bland and report.bland.degenerate_steps):
            d = report.dantzig.degenerate_steps + (report.bland.degenerate_steps if report.bland else 0)
            self.output.insert(tk.END, f"  Có {d} bước suy biến trong quá trình xoay.\n", "warn")

    def _has_artificial(self, engine: SimplexEngine) -> bool:
        return bool(engine.artificial_vars)

    def _has_aux_phase1(self, engine: SimplexEngine) -> bool:
        return bool(getattr(engine, "need_aux_phase1", False))

    def run_solver(self):
        try:
            prob = self._collect_problem()
            engine = SimplexEngine(prob)
            report = engine.solve_full()
            self._render_result(report)
            self.status_var.set(f"Đã giải xong: {report.status}.")
        except Exception as exc:
            messagebox.showerror("Lỗi nhập liệu / giải thuật", str(exc))
            self.status_var.set("Có lỗi xảy ra. Kiểm tra lại dữ liệu nhập.")

