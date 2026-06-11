from __future__ import annotations

import concurrent.futures

import math
import os
import tkinter as tk
import webbrowser
from fractions import Fraction
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Any, Dict, List, Optional, Tuple

from models import ProblemData, SolveReport
from models import Snapshot, PivotStep, SolveTrace
from simplex_engine import SimplexEngine
from html_exporter import export_report_html
from utils import (VAR_SIGNS, SENSES, clean_number_text, fmt_num,
                   fr, parse_cell, row_expr, sense_to_standard, term_str)
from viz3d import Viz3DMixin
from animator import SimplexAnimator


class SimplexApp(Viz3DMixin, tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Ứng dụng Giải bài toán Quy hoạch tuyến tính (tổng quát)")
        self.geometry("1380x920")
        self.minsize(1100, 760)

        # Thiết lập các biến trạng thái mặc định
        self.objective_sense = tk.StringVar(value="min") # kiểu bài toán mặc định là min
        self.n_vars = tk.IntVar(value=2)
        self.n_constraints = tk.IntVar(value=3)
        self.data_mode = "Phân số"
        self.method_preference = tk.StringVar(value="Dantzig Simplex")
        self.demo_preset_var = tk.StringVar(value="Ví dụ duy nhất nghiệm (Dantzig / Bland)")
        self.need_aux_phase1 = False # cờ cho biết có cần biến phụ để giải pha 1 hay không
        self.phase1_aux_var_index: Optional[int] = None # chỉ số của biến phụ nếu cần thiết

        # Danh sách các widget nhập liệu sẽ được tạo động theo số biến và ràng buộc, lưu lại để dễ truy cập khi thu thập dữ liệu
        self.obj_entries: List[tk.Entry] = [] # hệ số x(j+1) của hàm mục tiêu
        self.var_signs: List[ttk.Combobox] = [] # dấu của x(j+1): ≥0 / ≤0 / tự do
        self.constraint_entries: List[List[tk.Entry]] = [] # hệ số x(j+1) của từng ràng buộc i
        self.constraint_senses: List[ttk.Combobox] = [] # dấu của ràng buộc i: ≤ / ≥ / =
        self.constraint_rhs: List[tk.Entry] = [] # vế phải của ràng buộc i

        # Biến lưu kết quả giải thuật gần nhất để có thể xuất file hoặc trực quan hóa nếu phù hợp
        self.last_report: Optional[SolveReport] = None
        self.last_report_d: Optional[SolveReport] = None   # report của engine Dantzig
        self.last_report_b: Optional[SolveReport] = None   # report của engine Bland
        self.last_problem: Optional[ProblemData] = None
        self.export_btn: Optional[tk.Button] = None
        self.html_btn: Optional[tk.Button] = None
        self.viz_btn: Optional[tk.Button] = None
        self.viz3d_btn: Optional[tk.Button] = None
        self.animate_btn: Optional[tk.Button] = None

        # Khởi động giao diện
        self._setup_style()
        self._build_ui()
        self._build_inputs()
        # Phím tắt đề chạy giải thuật: Ctrl + Alt + R (không phân biệt hoa thường)
        self.bind_all("<Control-Alt-r>", lambda e: self.run_solver())
        self.bind_all("<Control-Alt-R>", lambda e: self.run_solver())


    def _setup_style(self):
        # Palette màu cố định: "Nordic Frost"
        ME = {
            # Nền tổng thể: trắng tuyết nhạt, sạch và thoáng
            "bg":           "#FAFBFC",
            # Nền header (thanh tiêu đề trên cùng): xanh đêm Bắc Âu
            "header_bg":    "#1E3A5F",
            # Chữ tiêu đề trên header: trắng tinh
            "header_fg":    "#FFFFFF",
            # Chữ phụ trên header: xanh băng nhạt
            "subheader_fg": "#B5D4F4",
            # Chữ nội dung chính: xanh đen trung tính
            "fg":           "#334155",
            # Viền và tiêu đề labelframe: xanh dương đậm vừa
            "frame_fg":     "#185FA5",
            # Nút hành động chính (Chạy giải thuật): xanh dương Nordic
            "accent":       "#3B82F6",
            # Nút hành động chính khi hover / active: xanh dương đậm hơn
            "accent_hover": "#2563EB",
            # Nút hành động chính khi bị vô hiệu hóa: xám lạnh
            "accent_dis":   "#CBD5E1",
            # Chữ trên nút bị vô hiệu hóa: xám xanh
            "dis_fg":       "#94A3B8",
            # Nút cảnh báo (Điền ví dụ): hổ phách vàng ấm
            "warn":         "#F59E0B",
            # Nút cảnh báo khi hover: hổ phách đậm hơn
            "warn_hover":   "#D97706",
            # Nền vùng lời giải (output): trắng tinh
            "output_bg":    "#FFFFFF",
            # Chữ trong vùng lời giải: xanh đen đậm
            "output_fg":    "#1E293B",
            # Màu tag h1 (tên bài toán): xanh dương Nordic đậm
            "h1":           "#185FA5",
            # Màu tag h2 (tiêu đề bước): xanh đêm Bắc Âu
            "h2":           "#1E3A5F",
            # Màu tag note (ghi chú, kết luận): teal sage
            "note":         "#0F766E",
            # Màu tag warn (cảnh báo suy biến, không giới nội): hổ phách đậm
            "warn_tag":     "#B45309",
            # Nền ô cột xoay (pivotcol): vàng băng nhạt
            "pivot_col":    "#FEF9C3",
            # Nền hàng xoay (pivotrow): xanh băng nhạt
            "pivot_row":    "#E8F4FD",
            # Nền ô xoay giao nhau (pivotcell): xanh dương nhạt rõ
            "pivot_cell":   "#BFDBFE",
            # Nền kết luận cuối: xanh lá sage nhạt
            "conclusion":   "#F0FDF4",
        }
        self._me = ME  # lưu lại để các hàm khác có thể tham chiếu nếu cần

        # Áp dụng theme nền "clam" của ttk (nếu không có thì dùng theme mặc định)
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        # Nền mặc định cho tất cả TFrame: trắng tuyết "Nordic Frost"
        style.configure("TFrame", background=ME["bg"])

        # Header: nền xanh đêm Bắc Âu, chữ trắng nổi bật
        style.configure("Header.TFrame", background=ME["header_bg"])
        style.configure("Header.TLabel", background=ME["header_bg"],
                        foreground=ME["header_fg"], font=("Segoe UI", 12, "bold"))

        # Dòng phụ dưới tiêu đề: chữ xanh băng nhạt trên nền đêm
        style.configure("SubHeader.TLabel", background=ME["header_bg"],
                        foreground=ME["subheader_fg"], font=("Segoe UI", 10))

        # Nhãn nội dung thông thường: xanh đen trên nền trắng tuyết
        style.configure("TLabel", background=ME["bg"],
                        foreground=ME["fg"], font=("Segoe UI", 10))

        # Khung nhóm (LabelFrame): nền trắng tuyết, viền 1px
        style.configure("TLabelframe", background=ME["bg"], borderwidth=1)
        style.configure("TLabelframe.Label", background=ME["bg"],
                        foreground=ME["frame_fg"], font=("Segoe UI", 10, "bold"))

        # Nút chung: font đậm, padding thoáng
        style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=8)

        # Nút hành động chính (Accent): xanh dương "Nordic Frost"
        style.configure("Accent.TButton", background=ME["accent"], foreground=ME["header_fg"])
        style.map(
            "Accent.TButton",
            background=[("disabled", ME["accent_dis"]),
                        ("active",   ME["accent_hover"]),
                        ("!disabled", ME["accent"])],
            foreground=[("disabled", ME["dis_fg"]),
                        ("!disabled", ME["header_fg"])],
        )

        # Nút cảnh báo (Warn): hổ phách vàng, hover sang hổ phách đậm
        style.configure("Warn.TButton", background=ME["warn"], foreground=ME["header_fg"])
        style.map("Warn.TButton", background=[("active", ME["warn_hover"])])

        # Combobox và Treeview: padding/chiều cao hàng tiêu chuẩn
        style.configure("TCombobox", padding=4)
        style.configure("Treeview", rowheight=28)


    def _build_ui(self):
        # Dựng bố cục tổng thể của cửa sổ chính:
        #   row 0 → header (tiêu đề cố định, không co giãn)
        #   row 1 → vùng làm việc chính (co giãn theo cửa sổ)
        #   row 2 → thanh trạng thái (status bar, cố định)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # Thanh tiêu đề trên cùng: tên ứng dụng (h1) + hướng dẫn tóm tắt (h2)
        header = ttk.Frame(self, style="Header.TFrame", padding=(12, 5))
        header.grid(row=0, column=0, sticky="nsew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header,
                  text="🔢  Ứng dụng Giải Quy hoạch Tuyến tính (tổng quát)",
                  style="Header.TLabel").grid(row=0, column=0, sticky="w")

        # Khung chính: 2 cột
        # Cột 0 (left, cố định): bảng thiết lập + nhập liệu
        # Cột 1 (right, co giãn): vùng hiển thị lời giải
        main = ttk.Frame(self, padding=14)
        main.grid(row=1, column=0, sticky="nsew")
        main.columnconfigure(0, weight=0)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        # Cột trái: row 0 → Thiết lập (config), row 1 → Mẫu demo, row 3 → Nhập bài toán
        left = ttk.Frame(main)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.rowconfigure(3, weight=1)  # row nhập liệu co giãn theo chiều dọc

        # Nhóm "Thiết lập": kiểu dữ liệu, số biến, số ràng buộc, nút tạo lại
        config = ttk.Labelframe(left, text="Thiết lập", padding=12)
        config.grid(row=0, column=0, sticky="ew")
        config.columnconfigure(1, weight=1)

        setup_row = ttk.Frame(config)
        setup_row.grid(row=0, column=0, columnspan=2, sticky="ew", pady=3)
        
        ttk.Label(setup_row, text="Số biến (1-5):").pack(side="left", padx=(0, 4))
        ttk.Spinbox(setup_row, from_=1, to=5, textvariable=self.n_vars,
                    width=5, command=self._build_inputs).pack(side="left", padx=(0, 16))

        ttk.Label(setup_row, text="Số ràng buộc (1-10):").pack(side="left", padx=(0, 4))
        ttk.Spinbox(setup_row, from_=1, to=10, textvariable=self.n_constraints,
                    width=5, command=self._build_inputs).pack(side="left")


        # ── Hàng trên: Kết quả (4 nút) ───────────────────────────────────
        top_row = ttk.Frame(config)
        top_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 2))
        for c in range(4):
            top_row.columnconfigure(c, weight=1)

        self.export_btn = tk.Button(
            top_row, text="📄  Xuất .txt",
            font=("Segoe UI", 9, "bold"),
            bg="#CBD5E1", fg="white",
            activebackground="#94A3B8", activeforeground="white",
            relief="flat", bd=0, padx=6, pady=7,
            cursor="arrow", state=tk.DISABLED,
            command=self.export_solution_txt,
        )
        self.export_btn.grid(row=0, column=0, sticky="ew", padx=(0, 3))
        self.export_btn.bind("<Enter>", lambda e: self._on_button_enter(e, "#2563EB"))
        self.export_btn.bind("<Leave>", lambda e: self._on_button_leave(e, "#CBD5E1"))

        self.html_btn = tk.Button(
            top_row, text="🌐  Xem HTML",
            font=("Segoe UI", 9, "bold"),
            bg="#CBD5E1", fg="white",
            activebackground="#94A3B8", activeforeground="white",
            relief="flat", bd=0, padx=6, pady=7,
            cursor="arrow", state=tk.DISABLED,
            command=self.open_solution_html,
        )
        self.html_btn.grid(row=0, column=1, sticky="ew", padx=(0, 3))
        self.html_btn.bind("<Enter>", lambda e: self._on_button_enter(e, "#5B21B6"))
        self.html_btn.bind("<Leave>", lambda e: self._on_button_leave(e, "#CBD5E1"))

        self.animate_btn = tk.Button(
            top_row, text="▶  Hiện từ vựng",
            font=("Segoe UI", 9, "bold"),
            bg="#CBD5E1", fg="white",
            activebackground="#94A3B8", activeforeground="white",
            relief="flat", bd=0, padx=6, pady=7,
            cursor="arrow", state=tk.DISABLED,
            command=self._open_animator,
        )
        self.animate_btn.grid(row=0, column=2, sticky="ew", padx=(0, 3))
        self.animate_btn.bind("<Enter>", lambda e: self._on_button_enter(e, "#D97706"))
        self.animate_btn.bind("<Leave>", lambda e: self._on_button_leave(e, "#CBD5E1"))

        # Nút trực quan hóa – màu/nhãn cập nhật động qua _update_viz_btn_state()
        self.viz_btn = tk.Button(
            top_row, text="🔒  Trực quan hóa",
            font=("Segoe UI", 9, "bold"),
            bg="#CBD5E1", fg="white",
            activebackground="#94A3B8", activeforeground="white",
            relief="flat", bd=0, padx=6, pady=7,
            cursor="arrow", state=tk.DISABLED,
            command=self._viz_dispatch,
        )
        self.viz_btn.grid(row=0, column=3, sticky="ew")
        self.viz_btn.bind("<Enter>", lambda e: self._on_button_enter(e, None))
        self.viz_btn.bind("<Leave>", lambda e: self._on_button_leave(e, None))

        # ── Hàng dưới: Quản lý dữ liệu (4 nút) ──────────────────────────
        bot_row = ttk.Frame(config)
        bot_row.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(2, 0))
        for c in range(4):
            bot_row.columnconfigure(c, weight=1)

        self.clear_all_btn = tk.Button(
            bot_row, text="🗑  Xóa toàn bộ",
            font=("Segoe UI", 9, "bold"),
            bg="#EF4444", fg="white",
            activebackground="#DC2626", activeforeground="white",
            relief="flat", bd=0, padx=6, pady=6,
            cursor="hand2",
            command=self._clear_all,
        )
        self.clear_all_btn.grid(row=0, column=0, sticky="ew", padx=(0, 3))
        self.clear_all_btn.bind("<Enter>", lambda e: self._on_button_enter(e, "#DC2626"))
        self.clear_all_btn.bind("<Leave>", lambda e: self._on_button_leave(e, "#EF4444"))

        self.reset_btn = tk.Button(
            bot_row, text="↺  Xóa & nhập lại",
            font=("Segoe UI", 9, "bold"),
            bg="#94A3B8", fg="white",
            activebackground="#64748B", activeforeground="white",
            relief="flat", bd=0, padx=6, pady=6,
            cursor="hand2",
            command=self._build_inputs,
        )
        self.reset_btn.grid(row=0, column=1, sticky="ew", padx=(0, 3))
        self.reset_btn.bind("<Enter>", lambda e: self._on_button_enter(e, "#64748B"))
        self.reset_btn.bind("<Leave>", lambda e: self._on_button_leave(e, "#94A3B8"))

        self.import_csv_btn = tk.Button(
            bot_row, text="📥  Nhập CSV",
            font=("Segoe UI", 9, "bold"),
            bg="#0D9488", fg="white",
            activebackground="#0F766E", activeforeground="white",
            relief="flat", bd=0, padx=6, pady=6,
            cursor="hand2",
            command=self.import_from_csv,
        )
        self.import_csv_btn.grid(row=0, column=2, sticky="ew", padx=(0, 3))
        self.import_csv_btn.bind("<Enter>", lambda e: self._on_button_enter(e, "#0F766E"))
        self.import_csv_btn.bind("<Leave>", lambda e: self._on_button_leave(e, "#0D9488"))

        self.export_csv_btn = tk.Button(
            bot_row, text="📤  Xuất CSV",
            font=("Segoe UI", 9, "bold"),
            bg="#185FA5", fg="white",
            activebackground="#1E3A5F", activeforeground="white",
            relief="flat", bd=0, padx=6, pady=6,
            cursor="hand2",
            command=self.export_to_csv,
        )
        self.export_csv_btn.grid(row=0, column=3, sticky="ew")
        self.export_csv_btn.bind("<Enter>", lambda e: self._on_button_enter(e, "#1E3A5F"))
        self.export_csv_btn.bind("<Leave>", lambda e: self._on_button_leave(e, "#0891B2"))

        self.viz3d_btn = None

        # --- Dropdown chọn phương pháp giải ---
        

        ttk.Button(config, text="Chạy giải thuật  (Ctrl+Alt+R)",
                   style="Accent.TButton",
                   command=self.run_solver).grid(
            row=6, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        
        self.comparison_frame = ttk.Labelframe(left, text="Tham chiếu Phương pháp giải", padding=10)
        self.comparison_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self.comparison_frame.grid_remove()
        self.selected_method_view = tk.StringVar(value="")

        btns = ttk.Frame(left)
        btns.grid(row=1, column=0, sticky="ew", pady=(10, 10))
        btns.columnconfigure(1, weight=1)
        ttk.Label(btns, text="Mẫu:").grid(row=0, column=0, sticky="w",
                                           padx=(0, 6))
        demo_combo = ttk.Combobox(
            btns,
            textvariable=self.demo_preset_var,
            values=[
                "Ví dụ duy nhất nghiệm (Dantzig / Bland)",
                "Ví dụ duy nhất nghiệm (hai pha)",
                "Ví dụ không giới nội (Dantzig / Bland)",
                "Ví dụ không giới nội (hai pha)",
                "Ví dụ vô số nghiệm (Dantzig / Bland)",
                "Ví dụ vô số nghiệm (hai pha)",
                "Ví dụ vô nghiệm (hai pha)",
                "Ví dụ xoay vòng (Dantzig → Bland)",
                "Ví dụ xoay vòng (hai pha → Dantzig → Bland)",
            ],
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
        self.input_canvas = tk.Canvas(input_box, background="#FAFBFC",
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
        def _on_mousewheel(event):
            if event.num == 4 or event.delta > 0:
                self.input_canvas.yview_scroll(-1, "units")
            elif event.num == 5 or event.delta < 0:
                self.input_canvas.yview_scroll(1, "units")

        def _bind_mousewheel(event):
            self.input_canvas.bind_all("<MouseWheel>", _on_mousewheel)
            self.input_canvas.bind_all("<Button-4>", _on_mousewheel) 
            self.input_canvas.bind_all("<Button-5>", _on_mousewheel) 

        def _unbind_mousewheel(event):
            x, y = event.widget.winfo_pointerxy()
            widget_under_mouse = event.widget.winfo_containing(x, y)
            
            if widget_under_mouse and str(widget_under_mouse).startswith(str(input_box)):
                return
                
            self.input_canvas.unbind_all("<MouseWheel>")
            self.input_canvas.unbind_all("<Button-4>")
            self.input_canvas.unbind_all("<Button-5>")

        input_box.bind("<Enter>", _bind_mousewheel)
        input_box.bind("<Leave>", _unbind_mousewheel)

        # Cột phải (hiển thị lời giải): Dùng ScrolledText để cuộn cả dọc lẫn ngang; font monospace để canh cột bảng từ vựng
        right = ttk.Labelframe(main, text="Lời giải", padding=8)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)




        self.output = scrolledtext.ScrolledText(
            right, wrap="none", font=("Consolas", 12),
            bg="#FFFFFF", fg="#1E293B",
            insertbackground="#1E293B", relief="flat", padx=14, pady=10,
            state=tk.DISABLED
        )
        self.output.grid(row=0, column=0, sticky="nsew")

        h_scroll = ttk.Scrollbar(right, orient="horizontal", command=self.output.xview)
        h_scroll.grid(row=1, column=0, sticky="ew")
        self.output.configure(xscrollcommand=h_scroll.set)

        self.recom_frame = ttk.Frame(right, padding=10, style="TFrame")
        self.recom_frame.grid(row=2, column=0, sticky="ew")
        
        self.lbl_theory = ttk.Label(self.recom_frame, text="", font=("Segoe UI", 10, "bold"), foreground="#0F766E")
        self.lbl_theory.pack(anchor="w")
        
        self.lbl_optimal = ttk.Label(self.recom_frame, text="", font=("Segoe UI", 10, "bold"), foreground="#B45309")
        self.lbl_optimal.pack(anchor="w", pady=(4, 0))




        # Định nghĩa các "tag" màu sắc dùng trong vùng lời giải:
        #   h1        → tên bài toán (to, đậm, màu nâu đỏ)
        #   h2        → tiêu đề pha / bước (đậm, màu xanh than)
        #   note      → ghi chú, kết quả từng bước (xanh indigo đất)
        #   warn      → cảnh báo suy biến, vô nghiệm (vàng đất)
        #   mono      → dạng bảng từ vựng (Consolas, không trang trí thêm)
        #   pivotcol  → highlight cột biến vào (nền vàng nhạt)
        #   pivotrow  → highlight hàng biến ra (nền xanh lam nhạt)
        #   pivotcell → highlight ô phần tử xoay = giao pivotcol ∩ pivotrow (nền đỏ hồng nhạt)
        #   conclusion→ highlight khối kết luận cuối (nền cam kem)
        self.output.tag_configure("h1", font=("Segoe UI", 15, "bold"),
                                   foreground="#185FA5", spacing1=8, spacing3=10)
        self.output.tag_configure("h2", font=("Segoe UI", 12, "bold"),
                                   foreground="#1E3A5F", spacing1=8, spacing3=4)
        self.output.tag_configure("note", foreground="#0F766E")
        self.output.tag_configure("warn", foreground="#B45309")
        self.output.tag_configure("mono", font=("Consolas", 12))
        self.output.tag_configure("pivotcol", background="#FEF9C3")
        self.output.tag_configure("pivotrow", background="#E8F4FD")
        self.output.tag_configure("pivotcell", background="#BFDBFE")
        self.output.tag_configure("conclusion", background="#F0FDF4")

        self.status_var = tk.StringVar(value="Sẵn sàng.")
        ttk.Label(self, textvariable=self.status_var,
                  anchor="w", padding=(14, 6)).grid(row=2, column=0, sticky="ew")

        self.bind("<Configure>", self._on_resize)

    def _on_resize(self, event=None):
        # Khi cửa sổ thay đổi kích thước, đảm bảo vùng lời giải không tự xuống dòng
        # (wrap="none" giữ mỗi dòng bảng từ vựng thẳng hàng, cuộn ngang nếu cần)
        try:
            self.output.configure(wrap="none")
        except Exception:
            pass

    def _build_inputs(self):
        # Xây dựng lại toàn bộ bảng nhập liệu mỗi khi số biến / số ràng buộc thay đổi.
        # Bước 1: xóa sạch tất cả widget cũ bên trong input_inner
        # Bước 2: xóa các danh sách tham chiếu (entry, combobox) để tránh trỏ đến widget đã hủy
        for child in self.input_inner.winfo_children():
            child.destroy()
        self.obj_entries.clear()
        self.var_signs.clear()
        self.constraint_entries.clear()
        self.constraint_senses.clear()
        self.constraint_rhs.clear()

        n = int(self.n_vars.get())        # số biến quyết định x1..xn
        m = int(self.n_constraints.get()) # số ràng buộc

        # Hàm mục tiêu: combobox chọn max/min, hàng nhập hệ số cj, hàng chọn dấu xj
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
        # Tạo n ô entry cho hệ số c1..cn của hàm mục tiêu; sắp xếp ngang theo cột
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

        # Các ràng buộc: n ô hệ số, 1 combobox dấu (≤/≥/=), 1 ô vế phải
        cons_frame = ttk.Labelframe(self.input_inner,
                                     text="Ràng buộc", padding=10)
        cons_frame.grid(row=1, column=0, sticky="nsew")
        cons_frame.columnconfigure(0, weight=1)

        ttk.Label(cons_frame,
                  text="Nhập hệ số từng ràng buộc, chọn dấu rồi nhập vế phải."
                  ).grid(row=0, column=0, sticky="w", pady=(0, 6))
        table = ttk.Frame(cons_frame)

        table.grid(row=1, column=0, sticky="w") 

        ttk.Label(table, text="").grid(row=0, column=0, padx=2, pady=2)
        for j in range(n):
            ttk.Label(table, text=f"x{j+1}", anchor="center").grid(
                row=0, column=j+1, padx=2, pady=2, sticky="ew")
            
        ttk.Label(table, text="Dấu", anchor="center").grid(
            row=0, column=n+1, padx=2, pady=2, sticky="ew")
        ttk.Label(table, text="Hệ số tự do", anchor="center").grid(
            row=0, column=n+2, padx=2, pady=2, sticky="ew")

        for i in range(m):
            ttk.Label(table, text=f"(RB{i+1})", width=5, anchor="e").grid(
                row=i+1, column=0, padx=2, pady=2, sticky="e")
            
            row_entries = []
            for j in range(n):
                e = ttk.Entry(table, width=10)
                e.grid(row=i+1, column=j+1, padx=2, pady=2)
                row_entries.append(e)
                
            cb = ttk.Combobox(table, values=SENSES, state="readonly", width=6)
            cb.set("≤")
            cb.grid(row=i+1, column=n+1, padx=2, pady=2)
            
            rhs = ttk.Entry(table, width=10)
            rhs.grid(row=i+1, column=n+2, padx=2, pady=2)
            
            self.constraint_entries.append(row_entries)
            self.constraint_senses.append(cb)
            self.constraint_rhs.append(rhs)

        ttk.Label(
            self.input_inner,
            text="Bấm Tab để chuyển ô. Ctrl+Alt+R để giải.",
            foreground="#185FA5",
        ).grid(row=2, column=0, sticky="w", pady=(10, 0))

        self.input_inner.update_idletasks()
        self.input_canvas.configure(
            scrollregion=self.input_canvas.bbox("all"))
        self.last_problem = None
        self.last_report = None
        self.last_report_d = None
        self.last_report_b = None
        self._set_solution_available(False)
        self._update_viz_btn_state()

    def fill_demo(self):
        preset = self.demo_preset_var.get().strip()
        _map = {
            "Ví dụ duy nhất nghiệm (Dantzig / Bland)":     self._fill_demo_unique_dantzig,
            "Ví dụ duy nhất nghiệm (hai pha)":             self._fill_demo_unique_two_phase,
            "Ví dụ không giới nội (Dantzig / Bland)":      self._fill_demo_unbounded_dantzig,
            "Ví dụ không giới nội (hai pha)":              self._fill_demo_unbounded_two_phase,
            "Ví dụ vô số nghiệm (Dantzig / Bland)":        self._fill_demo_multiple_dantzig,
            "Ví dụ vô số nghiệm (hai pha)":                self._fill_demo_multiple_two_phase,
            "Ví dụ vô nghiệm (hai pha)":                   self._fill_demo_infeasible_two_phase,
            "Ví dụ xoay vòng (Dantzig → Bland)":           self._fill_demo_cycle,
            "Ví dụ xoay vòng (hai pha → Dantzig → Bland)": self._fill_demo_cycle_2,
        }
        handler = _map.get(preset)
        if handler:
            handler()
        else:
            self._fill_demo_unique_dantzig()

    # ──────────────────────────────────────────────────────────────────────────
    # Các hàm điền ví dụ mẫu (10 bài toán)
    # ──────────────────────────────────────────────────────────────────────────

    def _apply_demo(self, n_vars, n_cons, sense, obj, signs, constraints):
        """Hàm tiện ích: thiết lập kích thước, điền dữ liệu vào giao diện."""
        self.n_vars.set(n_vars); self.n_constraints.set(n_cons)
        self.objective_sense.set(sense); self._build_inputs()
        for i, v in enumerate(obj):
            self.obj_entries[i].delete(0, tk.END); self.obj_entries[i].insert(0, v)
        for i, sg in enumerate(signs):
            self.var_signs[i].set(sg)
        for i, (c, s, r) in enumerate(constraints):
            for j, e in enumerate(self.constraint_entries[i]):
                e.delete(0, tk.END); e.insert(0, c[j])
            self.constraint_senses[i].set(s)
            self.constraint_rhs[i].delete(0, tk.END)
            self.constraint_rhs[i].insert(0, r)

    def _fill_demo_unique_dantzig(self):
        self._apply_demo(
            n_vars=2, n_cons=8, sense="max",
            obj=["3", "2"], signs=["≥0", "≥0"],
            constraints=[
                (["-1", "2"], "≥", "-1"),
                (["1", "-1"], "≤", "2"),
                (["-2", "-1"], "≥", "-6"),
                (["1", ""], "≤", "5"),
                (["2", "1"], "≤", "16"),
                (["1", "1"], "≤", "12"),
                (["1", "2"], "≤", "21"),
                (["", "1"], "≤", "10"),
            ],
        )

    def _fill_demo_unique_two_phase(self):
        self._apply_demo(
            n_vars=2, n_cons=3, sense="min",
            obj=["5", "-7"], signs=["≥0", "≥0"],
            constraints=[
                (["-4",  "1"], "≤", "-2"),
                ([ "1",  "1"], "≤",  "5"),
                (["-1", "-1"], "≤", "-1"),
            ],
        )

    def _fill_demo_unbounded_dantzig(self):
        self._apply_demo(
            n_vars=2, n_cons=2, sense="max",
            obj=["1", "1"], signs=["≥0", "≥0"],
            constraints=[
                (["-1",  "1"], "≤", "1"),
                ([ "1", "-2"], "≤", "2"),
            ],
        )

    def _fill_demo_unbounded_two_phase(self):
        self._apply_demo(
            n_vars=2, n_cons=2, sense="min",
            obj=["-2", "-1"], signs=["≥0", "≥0"],
            constraints=[
                (["1", "-1"], "≥", "1"),
                (["1",  "1"], "≥", "2"),
            ],
        )

    def _fill_demo_multiple_dantzig(self):
        self._apply_demo(
            n_vars=2, n_cons=3, sense="max",
            obj=["2", "4"], signs=["≥0", "≥0"],
            constraints=[
                (["1", "2"], "≤", "6"),
                (["1", "0"], "≤", "4"),
                (["0", "1"], "≤", "3"),
            ],
        )

    def _fill_demo_multiple_two_phase(self):
        self._apply_demo(
            n_vars=2, n_cons=5, sense="max",
            obj=["1", "-1"], signs=["tự do", "tự do"],
            constraints=[
                (["3", "1"], "≥", "3"),
                (["1", "2"], "≥", "4"),
                (["1", "-1"], "≤", "1"),
                (["1", ""], "≤", "5"),
                (["", "1"], "≤", "5"),
            ],
        )

    def _fill_demo_infeasible_two_phase(self):
        self._apply_demo(
            n_vars=2, n_cons=3, sense="min",
            obj=["1", "1"], signs=["≥0", "≥0"],
            constraints=[
                (["1", "2"], "≥", "2"),
                (["3", "2"], "≤", "1"),
                (["1", "1"], "≥", "1"),
            ],
        )

    def _fill_demo_cycle(self):
        # Xoay vòng: ví dụ Beale (1955) — Dantzig lặp vô hạn, Bland thoát được
        self._apply_demo(
            n_vars=4, n_cons=3, sense="min",
            obj=["-10", "57", "9", "24"], signs=["≥0"] * 4,
            constraints=[
                (["1/2", "-11/2", "-5/2", "9"], "≤", "0"),
                (["1/2",  "-3/2", "-1/2", "1"], "≤", "0"),
                (["1",      "0",    "0",  "0"], "≤", "1"),
            ],
        )

    def _fill_demo_cycle_2(self):
        self._apply_demo(
            n_vars=5, n_cons=3, sense="max",
            obj=["3/4", "-20", "1/2", "-6", "0"], signs=["≥0"] * 5,
            constraints=[
                (["1/4", "-8", "-1", "9", "0"], "≤", "0"),
                (["1/2", "-12", "-1/2", "3", "0"], "≤", "0"),
                (["0", "0", "0", "0", "-1"], "≤", "-1"),
            ],
        )

    def _collect_problem(self) -> ProblemData:
        # Thu thập toàn bộ dữ liệu từ giao diện nhập liệu và đóng gói thành ProblemData.
        n = int(self.n_vars.get())
        m = int(self.n_constraints.get())
        obj_coeffs = [parse_cell(e.get(), self.data_mode)
                      for e in self.obj_entries[:n]]
        var_signs = [cb.get() or "≥0" for cb in self.var_signs[:n]]
        constraints = []
        for i in range(m):
            coeffs = [parse_cell(e.get(), self.data_mode)
                      for e in self.constraint_entries[i][:n]]
            sense = self.constraint_senses[i].get() or "≤"
            rhs = parse_cell(self.constraint_rhs[i].get(), self.data_mode)
            constraints.append({"coeffs": coeffs, "sense": sense, "rhs": rhs})
        return ProblemData(
            objective_sense=self.objective_sense.get(),
            obj_coeffs=obj_coeffs,
            constraints=constraints,
            var_signs=var_signs,
        )


    def _set_solution_available(self, available: bool) -> None:
        # Bật/tắt nút "Xuất file .txt" và "Xem HTML" tùy theo có kết quả giải hay chưa.
        for btn, hover_color, base_color in [
            (self.export_btn, "#2563EB", "#3B82F6"),
            (self.html_btn,   "#5B21B6", "#6D28D9"),
            (self.animate_btn, "#D97706", "#F59E0B"),
        ]:
            if btn is None:
                continue
            if available:
                btn._base_bg = base_color
                btn._hover_bg = hover_color
                btn.config(state=tk.NORMAL,
                           bg=base_color,
                           activebackground=hover_color,
                           cursor="hand2")
            else:
                btn._base_bg = "#CBD5E1"
                btn._hover_bg = "#94A3B8"
                btn.config(state=tk.DISABLED,
                           bg="#CBD5E1",
                           activebackground="#94A3B8",
                           cursor="arrow")

    # Bảng màu và nhãn nút trực quan hóa theo số biến:
    #   2 biến → nút xanh sage "Nordic Frost" "Trực quan hóa (2D)"
    #   3 biến → nút tím indigo "Trực quan hóa (3D)"
    #   >3 biến→ nút xám bị vô hiệu hóa (không hỗ trợ)
    _VIZ_STYLES = {
        2: dict(bg="#0E7490", hover="#0891B2", icon="📊",
                label="Trực quan hóa (2D)"),
        3: dict(bg="#1E3A5F", hover="#185FA5", icon="🧊",
                label="Trực quan hóa (3D)"),
    }
    _VIZ_DISABLED = dict(bg="#CBD5E1", hover="#94A3B8",
                         icon="🔒", label="Trực quan hóa (>3 biến)")

    def _update_viz_btn_state(self) -> None:
        # Cập nhật màu sắc, nhãn và trạng thái nút viz_btn theo số biến hiện tại.
        if self.viz_btn is None:
            return
        n = int(self.n_vars.get())

        if self.last_report is None:
            self.viz_btn.config(
                text="🔒  Trực quan hóa (Chưa giải)",
                state=tk.DISABLED,
                bg="#CBD5E1", cursor="arrow")
        elif n > 3:
            # Hơn 3 biến: không hỗ trợ trực quan, khóa nút lại
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
            # 2 hoặc 3 biến: kích hoạt nút với màu phù hợp
            s = self._VIZ_STYLES.get(n, self._VIZ_STYLES[2])
            self.viz_btn.config(
                text=f"{s['icon']}  {s['label']}",
                state=tk.NORMAL,
                bg=s["bg"], activebackground=s["hover"],
                cursor="hand2",
            )
            self.viz_btn._base_bg = s["bg"]
            self.viz_btn._hover_bg = s["hover"]

    def _clear_all(self):
        """Xóa toàn bộ: solution, output, comparison_frame, và reset inputs."""
        self._build_inputs()                          # xóa form nhập
        self.output.config(state=tk.NORMAL)
        self.output.delete("1.0", tk.END)
        self.output.config(state=tk.DISABLED)
        self.comparison_frame.grid_remove()           # ẩn "Tham chiếu Phương pháp giải"
        self.lbl_theory.config(text="")
        if hasattr(self, "lbl_optimal"):
            self.lbl_optimal.config(text="")
        self.last_report = None
        self.last_problem = None
        self.status_var.set("Đã xóa toàn bộ.")

    def _open_animator(self):
        """Mở cửa sổ hiện từ vựng các bước Simplex."""
        if self.last_report is None:
            return
        from animator import SimplexAnimator
        report = self.last_report
        sel  = self.selected_method_view.get()   # "dantzig" | "bland" | "haipha"
        mode = self.data_mode

        engine = report.engine
        is_two_phase = bool(engine.need_aux_phase1 or engine.artificial_vars)

        # Bài toán hai pha thật sự: có pha 1 bổ trợ (x0 hoặc biến nhân tạo)
        if is_two_phase:
            phase2 = getattr(report, "phase2_trace", None)
            phase1_trace = getattr(report, "dantzig", None)
            traces = []
            if phase1_trace is not None:
                traces.append(("Pha 1", phase1_trace))
            if phase2 is not None:
                traces.append(("Pha 2", phase2))
            if not traces:
                messagebox.showinfo("Hiện từ vựng", "Không có dữ liệu trace để hiện từ vựng.")
                return
            SimplexAnimator(self, traces=traces, data_mode=mode,
                            title="Hiện từ vựng – Hai Pha")
            return

        # Bài toán một pha: không hiển thị nhãn pha
        # phase2_trace ở đây chỉ là trace giải thẳng (engine gán vào phase2_trace
        # ngay cả khi không có pha 1 thật sự)
        phase2 = getattr(report, "phase2_trace", None)
        if sel == "bland":
            trace = getattr(report, "bland", None) or phase2 or getattr(report, "dantzig", None)
        else:
            trace = phase2 or getattr(report, "dantzig", None)

        if trace is None:
            messagebox.showinfo("Hiện từ vựng", "Không có dữ liệu trace để hiện từ vựng.")
            return
        SimplexAnimator(self, traces=[("", trace)], data_mode=mode)

    def _viz_dispatch(self) -> None:
        # Điều phối yêu cầu trực quan hóa theo số biến:
        #   2 biến → vẽ đồ thị 2D miền chấp nhận + đường đồng mức
        #   3 biến → vẽ mô hình 3D (Viz3DMixin)
        #   khác  → thông báo không hỗ trợ
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

    def _normalize_method_choice(self, choice: Optional[str]) -> str:
        """Chuẩn hóa lựa chọn từ dropdown thành khóa nội bộ của solver."""
        value = (choice or "").strip().lower()
        if value in {"dantzig simplex", "dantzig", "d"}:
            return "dantzig"
        if value in {"bland's rule", "bland", "blands rule", "bland rule"}:
            return "bland"
        # Fallback: dantzig (hành vi mặc định như v1)
        return "dantzig"

    def _on_button_enter(self, event, darker_color: Optional[str] = None) -> None:
        # Xử lý sự kiện hover vào nút: đổi sang màu hover (tối hơn).
        btn = event.widget
        if str(btn.cget("state")) == "disabled":
            return
        if darker_color is None:
            darker_color = getattr(btn, "_hover_bg", btn.cget("bg"))
        elif btn is self.export_btn:
            darker_color = getattr(btn, "_hover_bg", darker_color)
        btn.config(bg=darker_color)

    def _on_button_leave(self, event, original_color: Optional[str] = None) -> None:
        # Xử lý sự kiện hover rời nút: khôi phục màu nền gốc.
        btn = event.widget
        if str(btn.cget("state")) == "disabled":
            return
        if original_color is None or btn is self.export_btn:
            original_color = getattr(btn, "_base_bg", btn.cget("bg"))
        btn.config(bg=original_color)


    # ------------------------------------------------------------------
    # Import / Export CSV
    # ------------------------------------------------------------------
    # Định dạng CSV:
    #   Dòng 1:  sense,<max|min>
    #   Dòng 2:  obj,<c1>,<c2>,...,<cn>
    #   Dòng 3:  signs,<≥0|≤0|tự do>,...
    #   Dòng 4+: con,<a1>,...,<an>,<≤|≥|=>,<rhs>
    # Ví dụ:
    #   sense,max
    #   obj,2,4
    #   signs,≥0,≥0
    #   con,1,2,≤,6
    #   con,1,0,≤,4
    #   con,0,1,≤,3

    def import_from_csv(self) -> None:
        path = filedialog.askopenfilename(
            title="Chọn file CSV bài toán",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            import csv as _csv
            with open(path, newline="", encoding="utf-8-sig") as f:
                reader = _csv.reader(f)
                rows = [r for r in reader if r and not r[0].strip().startswith("#")]

            sense = "min"
            obj: List[str] = []
            signs: List[str] = []
            constraints: List[tuple] = []

            for row in rows:
                tag = row[0].strip().lower()
                if tag == "sense":
                    sense = row[1].strip().lower()
                elif tag == "obj":
                    obj = [v.strip() for v in row[1:] if v.strip() != ""]
                elif tag == "signs":
                    signs = [v.strip() for v in row[1:] if v.strip() != ""]
                elif tag == "con":
                    # format: con, a1, ..., an, sense_sign, rhs
                    vals = [v.strip() for v in row[1:] if v.strip() != ""]
                    # sense nằm ở vị trí áp cuối, rhs là phần tử cuối
                    # Tìm sense_sign: ≤, >=, =, <=, >=
                    sense_idx = None
                    for k, v in enumerate(vals):
                        if v in ("≤", "≥", "=", "<=", ">=", "le", "ge", "eq"):
                            sense_idx = k
                            break
                    if sense_idx is None:
                        raise ValueError(f"Không tìm thấy dấu ràng buộc trong: {row}")
                    coeffs = vals[:sense_idx]
                    s = vals[sense_idx]
                    rhs = vals[sense_idx + 1]
                    # chuẩn hóa dấu
                    s = {"<=": "≤", ">=": "≥", "le": "≤", "ge": "≥", "eq": "="}.get(s, s)
                    constraints.append((coeffs, s, rhs))

            if not obj:
                raise ValueError("Không tìm thấy dòng 'obj' trong CSV.")
            n_vars = len(obj)
            n_cons = len(constraints)
            if n_vars < 1 or n_vars > 5:
                raise ValueError(f"Số biến phải từ 1 đến 5, nhưng CSV có {n_vars}.")
            if n_cons < 1 or n_cons > 10:
                raise ValueError(f"Số ràng buộc phải từ 1 đến 10, nhưng CSV có {n_cons}.")
            if not signs:
                signs = ["≥0"] * n_vars
            if len(signs) < n_vars:
                signs += ["≥0"] * (n_vars - len(signs))
            # Kiểm tra mỗi ràng buộc đủ n_vars hệ số
            for i, (coeffs, s, rhs) in enumerate(constraints):
                if len(coeffs) < n_vars:
                    coeffs = coeffs + ["0"] * (n_vars - len(coeffs))
                    constraints[i] = (coeffs, s, rhs)

            self._apply_demo(
                n_vars=n_vars,
                n_cons=n_cons,
                sense=sense,
                obj=obj,
                signs=signs,
                constraints=constraints,
            )
            self.status_var.set(f"✅ Đã nhập từ {path.split('/')[-1]}  ({n_vars} biến, {n_cons} ràng buộc)")
        except Exception as ex:
            messagebox.showerror("Lỗi nhập CSV", str(ex))

    def export_to_csv(self) -> None:
        # Xuất bài toán hiện tại (hoặc template trống) ra CSV.
        try:
            n = int(self.n_vars.get())
            m = int(self.n_constraints.get())
            sense = self.objective_sense.get() or "min"
            obj = [e.get().strip() or "0" for e in self.obj_entries[:n]]
            signs = [cb.get() or "≥0" for cb in self.var_signs[:n]]
            constraints = []
            for i in range(m):
                coeffs = [e.get().strip() or "0" for e in self.constraint_entries[i][:n]]
                s = self.constraint_senses[i].get() or "≤"
                rhs = self.constraint_rhs[i].get().strip() or "0"
                constraints.append((coeffs, s, rhs))
        except Exception:
            n, m, sense, obj, signs, constraints = 2, 2, "min", ["1","1"], ["≥0","≥0"], [(["1","0"],"≤","4"),(["0","1"],"≤","6")]

        path = filedialog.asksaveasfilename(
            title="Lưu CSV bài toán",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile="bai_toan.csv",
        )
        if not path:
            return
        try:
            import csv as _csv
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = _csv.writer(f)
                w.writerow(["# Định dạng: sense | obj | signs | con (hệ số...,dấu,rhs)"])
                w.writerow(["sense", sense])
                w.writerow(["obj"] + obj)
                w.writerow(["signs"] + signs)
                for coeffs, s, rhs in constraints:
                    w.writerow(["con"] + coeffs + [s, rhs])
            self.status_var.set(f"✅ Đã xuất mẫu CSV → {path.split('/')[-1]}")
        except Exception as ex:
            messagebox.showerror("Lỗi xuất CSV", str(ex))

    def export_solution_txt(self) -> None:
        # Xuất nội dung vùng lời giải ra file .txt.
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

    def open_solution_html(self) -> None:
        """Xuất lời giải đầy đủ ra HTML+KaTeX và mở trong trình duyệt mặc định."""
        if self.last_report is None:
            messagebox.showinfo("Xem HTML", "Chưa có lời giải. Vui lòng chạy giải thuật trước.")
            return
        try:
            self.status_var.set("Đang tạo file HTML…")
            self.update_idletasks()
            path = export_report_html(self.last_report, self.data_mode)
            url = f"file:///{path.replace(os.sep, '/')}"
            webbrowser.open(url)
            self.status_var.set(f"Đã mở trình duyệt: {os.path.basename(path)}")
        except Exception as exc:
            messagebox.showerror("Lỗi xuất HTML", str(exc))
            self.status_var.set("Lỗi khi tạo file HTML.")


    def _boundary_text(self, coeffs, sense: str, rhs: Fraction) -> str:
        # Tạo chuỗi biểu diễn một ràng buộc dạng "a·x₁ + b·x₂ sense rhs" để hiển thị chú thích trên biểu đồ 2D.
        a, b = coeffs
        parts = []
        mode = self.data_mode
        if a != 0:
            parts.append(f"{fmt_num(a, mode)}x₁")
        if b != 0:
            sign = "+" if b > 0 and parts else ""
            parts.append(f"{sign}{fmt_num(b, mode)}x₂")
        lhs = " ".join(parts).replace("+ -", "- ") or "0"
        return f"{lhs} {sense} {fmt_num(rhs, mode)}"

    def _build_halfplanes(self, prob: ProblemData):
        # Chuyển danh sách ràng buộc + điều kiện dấu biến thành danh sách nửa mặt phẳng (a, b, rhs, sense, nhãn). Dùng để vẽ vùng chấp nhận được trên đồ thị 2D. Điều kiện dấu biến (≥0 / ≤0 / tự do) được thêm vào như các ràng buộc trục tọa độ.
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
        # Kiểm tra điểm (x, y) có thỏa tất cả nửa mặt phẳng không.
        for a, b, c, sense, _ in halfplanes:
            lhs = float(a)*x + float(b)*y
            cc = float(c)
            if sense == "≤" and lhs > cc+tol: return False
            if sense == "≥" and lhs < cc-tol: return False
            if sense == "=" and abs(lhs-cc) > tol: return False
        return True

    def _compute_feasible_vertices(self, halfplanes):
        # Tính tất cả đỉnh của miền chấp nhận được bằng cách giao từng cặp đường thẳng, sau đó lọc lại chỉ giữ các giao điểm thỏa toàn bộ ràng buộc còn lại.
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
        # Loại bỏ các điểm trùng lặp (trong phạm vi eps) để tránh vẽ đỉnh hai lần.
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
        EXPAND_LIMIT = 8.0
        for a, b, c, sense, _ in halfplanes:
            fa, fb, fc = float(a), float(b), float(c)
            cand_pts = []
            eps = 1e-12
            if abs(fb) > eps:
                cand_pts.append((xmin, (fc - fa*xmin)/fb))
                cand_pts.append((xmax, (fc - fa*xmax)/fb))
            if abs(fa) > eps: 
                cand_pts.append(((fc - fb*ymin)/fa, ymin))
                cand_pts.append(((fc - fb*ymax)/fa, ymax))
            for cx, cy in cand_pts:
                if not (math.isfinite(cx) and math.isfinite(cy)):
                    continue
                xr_cur = xmax - xmin; yr_cur = ymax - ymin
                if cx < xmin and cx >= xmin - EXPAND_LIMIT*xr_cur:
                    xmin = cx - 0.04*xr_cur
                if cx > xmax and cx <= xmax + EXPAND_LIMIT*xr_cur:
                    xmax = cx + 0.04*xr_cur
                if cy < ymin and cy >= ymin - EXPAND_LIMIT*yr_cur:
                    ymin = cy - 0.04*yr_cur
                if cy > ymax and cy <= ymax + EXPAND_LIMIT*yr_cur:
                    ymax = cy + 0.04*yr_cur
        xr, yr = xmax-xmin, ymax-ymin
        return xmin-0.10*xr, xmax+0.10*xr, ymin-0.10*yr, ymax+0.10*yr

    def _find_optimal_vertex(self, vertex_values, maximize):
        # Tìm đỉnh tối ưu trong danh sách (x, y, z): max z nếu maximize, min z nếu minimize.
        if not vertex_values: return None
        return max(vertex_values, key=lambda t: t[2]) if maximize \
               else min(vertex_values, key=lambda t: t[2])

    def _is_region_bounded(self, halfplanes):
        import math
        directions = [
            (1,0),(-1,0),(0,1),(0,-1),
            (1,1),(-1,1),(1,-1),(-1,-1),
        ]
        for dx, dy in directions:
            try:
                from scipy.optimize import linprog
                c_obj = [-dx, -dy]
                A_ub, b_ub, A_eq, b_eq = [], [], [], []
                for a, b, rhs, sense, _ in halfplanes:
                    fa, fb, fc = float(a), float(b), float(rhs)
                    if sense in ("<=", "≤"):
                        A_ub.append([fa, fb]); b_ub.append(fc)
                    elif sense in (">=", "≥"):
                        A_ub.append([-fa, -fb]); b_ub.append(-fc)
                    else:
                        A_eq.append([fa, fb]); b_eq.append(fc)
                res = linprog(
                    c_obj,
                    A_ub=A_ub or None, b_ub=b_ub or None,
                    A_eq=A_eq or None, b_eq=b_eq or None,
                    bounds=[(None,None),(None,None)],
                    method="highs",
                )
                if res.status == 3:
                    return False
            except Exception:
                far = 1e6
                px, py = dx*far, dy*far
                if self._is_feasible_point(px, py, halfplanes, tol=1.0):
                    return False
        return True

    def _request_canvas_redraw(self, canvas, delay_ms=14):
        # Đặt lịch vẽ lại canvas sau delay_ms mili-giây bằng widget.after().
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
        from viz3d import (
            _extract_simplex_path_2d, _get_combined_trace, _find_optimal_edge_2d
        )
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
        c1, c2 = float(prob.obj_coeffs[0]), float(prob.obj_coeffs[1])
        vertex_values = [(p[0], p[1], c1*p[0]+c2*p[1]) for p in vertices]
        maximize = prob.objective_sense == "max"

        report = self.last_report
        engine = report.engine if report else None
        status = report.status if report else ("infeasible" if not vertices else "optimal")

        # Xác định điểm tối ưu từ engine
        if report and engine and report.solution_orig and status not in ("infeasible", "unbounded"):
            so = report.solution_orig
            ox = float(so.get(0, Fraction(0)))
            oy = float(so.get(1, Fraction(0)))
            oz = c1*ox + c2*oy
            optimal_point = (ox, oy, oz)
        else:
            optimal_point = self._find_optimal_vertex(vertex_values, maximize)

        # Vô số nghiệm:
        multi_opt: List[Tuple[float, float]] = []
        _snap_check = self._get_final_snapshot(report)
        _is_multi = report and self._has_multiple_optimal(engine, _snap_check, report) and optimal_point
        # Phát hiện tập nghiệm là tia (không giới nội trên đường tối ưu):
        # Xảy ra khi có biến tự do "ab" (cả a_i, b_i phi cơ sở) → x_i không bị chặn
        _is_ray = False
        if _is_multi and engine and _snap_check:
            _all_fv, _sfp = self._expand_free_vars_with_splits(
                engine, _snap_check, report.multiple_optimal_vars or [])
            _is_ray = any(which == "ab" for _, ja, jb, which in _sfp)
        if _is_multi:
            opt_z = optimal_point[2]
            tol = max(1e-6, 1e-4 * abs(opt_z)) if abs(opt_z) > 1e-10 else 1e-6
            multi_opt = [(x, y) for x, y, z in vertex_values if abs(z - opt_z) < tol]

        # Đường đi simplex
        path_d: List[Tuple[float, float]] = []
        path_b: List[Tuple[float, float]] = []
        if engine and report:
            report_bland = self.last_report_b
            engine_b = report_bland.engine if report_bland else engine
            trace_d, trace_b = _get_combined_trace(report, report_bland)
            path_d = _extract_simplex_path_2d(trace_d, engine, 2)
            if trace_b:
                path_b = _extract_simplex_path_2d(trace_b, engine_b, 2)

        # ── Tính bounds cơ bản ──────────────────────────────────────────
        all_pts_for_bounds = list(vertices) + [p[:2] for p in path_d + path_b]
        xmin, xmax, ymin, ymax = self._compute_plot_bounds(
            all_pts_for_bounds if all_pts_for_bounds else vertices, halfplanes)

        # Không giới nội: tính vector mũi tên rồi mở rộng bounds TRƯỚC khi vẽ
        _unb_sx = _unb_sy = 0.0
        _unb_dx = _unb_dy = 0.0
        if status == "unbounded":
            norm_c = math.sqrt(c1**2 + c2**2)
            if norm_c > 1e-12:
                sign_u = 1 if maximize else -1
                if vertices:
                    _unb_sx = sum(p[0] for p in vertices) / len(vertices)
                    _unb_sy = sum(p[1] for p in vertices) / len(vertices)
                else:
                    _unb_sx, _unb_sy = (xmin+xmax)/2, (ymin+ymax)/2
                span = min(xmax-xmin, ymax-ymin) * 0.50
                _unb_dx = sign_u * c1 / norm_c * span
                _unb_dy = sign_u * c2 / norm_c * span
                # Mở rộng bounds để mũi tên không bị cắt
                tip_x = _unb_sx + _unb_dx * 1.65
                tip_y = _unb_sy + _unb_dy * 1.65
                extra = span * 0.3
                xmin = min(xmin, tip_x - extra)
                xmax = max(xmax, tip_x + extra)
                ymin = min(ymin, tip_y - extra)
                ymax = max(ymax, tip_y + extra)
              
        ray_origin: Optional[Tuple[float, float]] = None  # điểm đầu của tia (nếu là tia)
        if _is_multi and len(multi_opt) < 2 and abs(c1) + abs(c2) > 1e-12:
            opt_z  = optimal_point[2]
            tol    = max(1e-6, 1e-4 * abs(opt_z)) if abs(opt_z) > 1e-10 else 1e-6
            poly   = [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)]
            for a, b, c, sense, _ in halfplanes:
                poly = self._clip_polygon_by_halfplane(poly, a, b, c, sense)
                if not poly:
                    break
            if poly:
                poly_plus  = self._clip_polygon_by_halfplane(poly, c1, c2, opt_z, "≤")
                poly_minus = self._clip_polygon_by_halfplane(poly, c1, c2, opt_z, "≥")
                seg_pts: List[Tuple[float, float]] = []
                for px, py in (poly_plus or []) + (poly_minus or []):
                    if abs(c1*px + c2*py - opt_z) < tol * max(1, abs(opt_z)):
                        if not any(abs(px-qx) < 1e-7 and abs(py-qy) < 1e-7
                                   for qx, qy in seg_pts):
                            seg_pts.append((px, py))
                if len(seg_pts) >= 2:
                    multi_opt = seg_pts

        # Nếu là tia: xác định ray_origin = đỉnh tối ưu (đầu hữu hạn của tia)
        # multi_opt gồm các điểm trên đường tối ưu trong viewport;
        # với tia, một đầu là đỉnh góc hữu hạn, đầu kia chạm biên viewport
        if _is_ray and len(multi_opt) >= 2 and optimal_point:
            ox, oy = optimal_point[0], optimal_point[1]
            # Chọn điểm trong multi_opt gần nhất với optimal_point làm ray_origin
            ray_origin = min(multi_opt,
                             key=lambda p: (p[0]-ox)**2 + (p[1]-oy)**2)

        # ── Dựng cửa sổ ──────────────────────────────────────────────────
        win = self._create_visualization_window()
        outer = tk.Frame(win, bg="#0f172a")
        outer.grid(row=0, column=0, sticky="nsew")
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)

        canvas_host = tk.Frame(outer, bg="#0f172a")
        canvas_host.grid(row=0, column=0, sticky="nsew")
        canvas_host.rowconfigure(0, weight=1)
        canvas_host.columnconfigure(0, weight=1)

        region_bounded = status == "infeasible" or self._is_region_bounded(halfplanes)

        fig, ax = self._create_figure()
        self._plot_constraints(ax, halfplanes, xmin, xmax, ymin, ymax)
        self._plot_objective_contours(ax, c1, c2, vertex_values,
                                      xmin, xmax, ymin, ymax, maximize)
        if region_bounded:
            self._plot_vertices(ax, vertex_values, maximize)
        else:
            self._plot_unbounded_region(ax, halfplanes, xmin, xmax, ymin, ymax)

        # Vẽ đặc trưng theo trạng thái
        if status == "unbounded":
            self._plot_unbounded_arrow_2d(ax, _unb_sx, _unb_sy,
                                          _unb_dx, _unb_dy)
        if status != "infeasible" and status != "unbounded":
            if multi_opt and len(multi_opt) >= 2:
                if _is_ray and ray_origin is not None:
                    self._plot_optimal_ray_2d(ax, multi_opt, ray_origin, vertex_values)
                else:
                    self._plot_optimal_edge_2d(ax, multi_opt, vertex_values)
            elif optimal_point:
                self._plot_optimal_point(ax, optimal_point, maximize)

        if status == "infeasible":
            self._plot_infeasible_notice_2d(ax, xmin, xmax, ymin, ymax)

        # Đường đi simplex
        self._plot_simplex_paths_2d(ax, path_d, path_b,
                                    xmin, xmax, ymin, ymax, status)

        self._configure_axes(ax, xmin, xmax, ymin, ymax)
        self._add_status_subtitle_2d(ax, status, report)

        canvas = FigureCanvasTkAgg(fig, master=canvas_host)
        canvas.draw()
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.configure(bg="#0f172a", highlightthickness=0, bd=0)
        canvas_widget.grid(row=0, column=0, sticky="nsew")

        self._create_info_panel_v2(canvas_host, prob, vertices, vertex_values,
                                   optimal_point, maximize, status=status,
                                   multi_opt=multi_opt,
                                   is_ray=_is_ray,
                                   path_d=path_d, path_b=path_b)
        self._create_zoom_controls(outer, ax, canvas,
                                   (xmin, xmax), (ymin, ymax))
        self._enable_canvas_interactions(ax, canvas)
        win.focus_force()

    # ── Vẽ mũi tên không giới nội 2D ────────────────────────────────────
    def _clip_polygon_by_halfplane(self, poly, a, b, c, sense):
        if not poly:
            return []
        fa, fb, fc = float(a), float(b), float(c)
        def inside(p):
            v = fa*p[0] + fb*p[1]
            if sense == "≤": return v <= fc + 1e-9
            if sense == "≥": return v >= fc - 1e-9
            return abs(v - fc) <= 1e-7
        def intersect(p1, p2):
            dx, dy = p2[0]-p1[0], p2[1]-p1[1]
            denom = fa*dx + fb*dy
            if abs(denom) < 1e-12:
                return p1
            t = (fc - fa*p1[0] - fb*p1[1]) / denom
            return (p1[0] + t*dx, p1[1] + t*dy)
        result = []
        n = len(poly)
        for i in range(n):
            cur, nxt = poly[i], poly[(i+1) % n]
            ic, inxt = inside(cur), inside(nxt)
            if ic:
                result.append(cur)
            if ic != inxt:
                result.append(intersect(cur, nxt))
        return result

    def _plot_unbounded_region(self, ax, halfplanes, xmin, xmax, ymin, ymax):
        poly = [
            (xmin, ymin), (xmax, ymin),
            (xmax, ymax), (xmin, ymax),
        ]
        for a, b, c, sense, _ in halfplanes:
            poly = self._clip_polygon_by_halfplane(poly, a, b, c, sense)
            if not poly:
                break
        if len(poly) < 3:
            return
        from matplotlib.patches import Polygon as MplPolygon
        import numpy as np
        patch = MplPolygon(
            np.array(poly), closed=True,
            facecolor="#BBDEFB", alpha=0.42,
            edgecolor="#1565C0", linewidth=1.6,
            linestyle="-", zorder=1
        )
        ax.add_patch(patch)

    def _plot_unbounded_arrow_2d(self, ax, sx, sy, dx, dy):
        """Vẽ mũi tên chỉ hướng tối ưu hóa tiến tới vô cùng.
        sx,sy: gốc mũi tên.  dx,dy: vector hướng (đã tính sẵn, khớp với bounds).
        """
        # Mũi tên chính
        ax.annotate("", xy=(sx + dx, sy + dy), xytext=(sx, sy),
                    arrowprops=dict(arrowstyle="-|>", color="#C62828",
                                   lw=2.8, mutation_scale=22),
                    zorder=9)
        # Mũi tên phụ — tiếp tục từ 70% đến 130%
        ax.annotate("", xy=(sx + dx*1.50, sy + dy*1.50),
                    xytext=(sx + dx*0.85, sy + dy*0.85),
                    arrowprops=dict(arrowstyle="-|>", color="#E57373",
                                   lw=1.8, mutation_scale=16),
                    zorder=9)
        ax.text(sx + dx*1.55, sy + dy*1.55,
                "  → ∞\n(không giới nội)",
                color="#C62828", fontsize=10, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.3",
                          fc="#FFEBEE", ec="#C62828", alpha=0.95),
                zorder=10)

    # ── Vẽ tập nghiệm tối ưu vô số nghiệm 2D ───────────────────────────
    def _plot_optimal_edge_2d(self, ax,
                               multi_opt: List[Tuple[float, float]],
                               vertex_values: List[Tuple[float, float, float]] = None):
        """Highlight đoạn tối ưu (bounded). Vẽ đường vàng + ⭐ ở các đỉnh + Z*."""
        if len(multi_opt) < 2:
            return
        cx_m = sum(p[0] for p in multi_opt) / len(multi_opt)
        cy_m = sum(p[1] for p in multi_opt) / len(multi_opt)
        pts = sorted(multi_opt, key=lambda p: math.atan2(p[1]-cy_m, p[0]-cx_m))
        ax.plot([p[0] for p in pts], [p[1] for p in pts],
                color="#fbbf24", linewidth=7, alpha=0.70, zorder=6,
                solid_capstyle="round", label="Đoạn tối ưu (vô số nghiệm)")
        for px, py in pts:
            ax.scatter([px], [py], s=260, marker="*",
                       color="#f59e0b", edgecolors="#fde68a",
                       linewidths=1.2, zorder=8)
        px0, py0 = pts[0]
        opt_z_str = ""
        if vertex_values:
            for vx, vy, vz in vertex_values:
                if abs(vx - px0) < 1e-6 and abs(vy - py0) < 1e-6:
                    opt_z_str = f"\nZ* = {vz:.4g}"
                    break
        ax.annotate(
            f"Vô số nghiệm tối ưu\n(toàn bộ đoạn vàng đều tối ưu){opt_z_str}",
            xy=(px0, py0), xytext=(16, 20), textcoords="offset points",
            fontsize=9, fontweight="bold", color="#E65100",
            bbox=dict(boxstyle="round,pad=0.35", fc="#FFF8E1", ec="#F57F17", alpha=0.97),
            arrowprops=dict(arrowstyle="->", color="#E65100", lw=1.5),
            zorder=10)

    def _plot_optimal_ray_2d(self, ax,
                              multi_opt: List[Tuple[float, float]],
                              ray_origin: Tuple[float, float],
                              vertex_values: List[Tuple[float, float, float]] = None):
        """Highlight tia tối ưu (unbounded). Vẽ đường vàng + mũi tên → ∞, không ⭐."""
        if len(multi_opt) < 2:
            return
        ox, oy = ray_origin
        pts = sorted(multi_opt, key=lambda p: (p[0]-ox)**2 + (p[1]-oy)**2)
        ax.plot([p[0] for p in pts], [p[1] for p in pts],
                color="#fbbf24", linewidth=7, alpha=0.70, zorder=6,
                solid_capstyle="round", label="Tia/Đường tối ưu (vô số nghiệm)")
        tip_x, tip_y = pts[-1]
        prev_x, prev_y = pts[-2] if len(pts) > 2 else pts[0]
        ax.annotate("", xy=(tip_x, tip_y), xytext=(prev_x, prev_y),
                    arrowprops=dict(arrowstyle="-|>", color="#f59e0b",
                                   lw=2.5, mutation_scale=18),
                    zorder=9)
        opt_z_str = ""
        if vertex_values:
            for vx, vy, vz in vertex_values:
                if abs(vx - ox) < 1e-6 and abs(vy - oy) < 1e-6:
                    opt_z_str = f"\nZ* = {vz:.4g}"
                    break
        ax.annotate(
            f"Vô số nghiệm tối ưu{opt_z_str}",
            xy=(ox, oy), xytext=(16, 20), textcoords="offset points",
            fontsize=9, fontweight="bold", color="#E65100",
            bbox=dict(boxstyle="round,pad=0.35", fc="#FFF8E1", ec="#F57F17", alpha=0.97),
            arrowprops=dict(arrowstyle="->", color="#E65100", lw=1.5),
            zorder=10)

    # ── Vẽ thông báo vô nghiệm 2D ───────────────────────────────────────
    def _plot_infeasible_notice_2d(self, ax, xmin, xmax, ymin, ymax):
        cx = (xmin + xmax) / 2
        cy = (ymin + ymax) / 2
        ax.text(cx, cy, "Miền khả thi rỗng\nBài toán VÔ NGHIỆM",
                ha="center", va="center",
                fontsize=16, fontweight="bold", color="#C62828",
                bbox=dict(boxstyle="round,pad=0.6",
                          fc="#FFEBEE", ec="#C62828", alpha=0.95),
                zorder=15)

    # ── Vẽ đường đi simplex 2D ───────────────────────────────────────────
    def _plot_simplex_paths_2d(self, ax, path_d, path_b,
                                xmin, xmax, ymin, ymax, status):
        # Dantzig – cam đậm, đường liền
        if len(path_d) >= 2:
            xs_d = [p[0] for p in path_d]
            ys_d = [p[1] for p in path_d]
            ax.plot(xs_d, ys_d, color="#E65100", linewidth=2.4,
                    linestyle="-", alpha=0.92,
                    marker="o", markersize=7,
                    markerfacecolor="#E65100", markeredgecolor="white",
                    markeredgewidth=0.9, zorder=7,
                    label="Đường đi Dantzig")
            for k, (px, py) in enumerate(path_d):
                ax.annotate(f"D{k}", xy=(px, py),
                            xytext=(5, 5), textcoords="offset points",
                            fontsize=8, color="#BF360C",
                            bbox=dict(boxstyle="round,pad=0.15",
                                      fc="#FFF3E0", ec="#E65100", alpha=0.90),
                            zorder=8)

        # Bland – xanh cyan, nét đứt
        if len(path_b) >= 2:
            xs_b = [p[0] for p in path_b]
            ys_b = [p[1] for p in path_b]
            ax.plot(xs_b, ys_b, color="#00838F", linewidth=2.2,
                    linestyle="--", alpha=0.88,
                    marker="s", markersize=6,
                    markerfacecolor="#00838F", markeredgecolor="white",
                    markeredgewidth=0.8, zorder=7,
                    label="Đường đi Bland")
            for k, (px, py) in enumerate(path_b):
                ax.annotate(f"B{k}", xy=(px, py),
                            xytext=(-5, 8), textcoords="offset points",
                            fontsize=8, color="#006064",
                            bbox=dict(boxstyle="round,pad=0.15",
                                      fc="#E0F7FA", ec="#00838F", alpha=0.90),
                            zorder=8)

        # Nếu Dantzig xoay vòng mà Bland hội tụ: chú thích
        if status == "cycle" and len(path_d) >= 2 and len(path_b) >= 2:
            ax.text(xmin + (xmax-xmin)*0.02, ymax - (ymax-ymin)*0.04,
                    "⚠ Dantzig: xoay vòng (không hội tụ)\n"
                    "✓ Bland: hội tụ đến điểm tối ưu",
                    fontsize=8, color="#E65100", va="top",
                    bbox=dict(boxstyle="round,pad=0.3",
                              fc="#FFF8E1", ec="#E65100", alpha=0.92),
                    zorder=12)

    # ── Thêm subtitle 2D cho tiêu đề ────────────────────────────────────
    def _add_status_subtitle_2d(self, ax, status, report):
        status_map = {
            "optimal": "Nghiệm tối ưu duy nhất",
            "infeasible": "Bài toán VÔ NGHIỆM",
            "unbounded": "Bài toán KHÔNG GIỚI NỘI",
            "cycle": "Dantzig xoay vòng → dùng Bland",
        }
        _eng2d   = getattr(report, "engine", None)
        _snap2d  = self._get_final_snapshot(report)
        if report and status == "optimal" and self._has_multiple_optimal(_eng2d, _snap2d, report):
            txt = "VÔ SỐ NGHIỆM TỐI ƯU"
            color = "#1565C0"
        else:
            txt = status_map.get(status, f"Trạng thái: {status}")
            color = {"infeasible": "#C62828", "unbounded": "#E65100",
                     "cycle": "#F57F17"}.get(status, "#2E7D32")

        # Đặt tiêu đề kết hợp
        ax.set_title(
            f"Miền chấp nhận được và đường đồng mức hàm mục tiêu\n"
            f"[{txt}]",
            fontsize=13, fontweight="bold", pad=10,
            color="#263238")

    # ── Panel thông tin v2 (thay _create_info_panel) ────────────────────
    def _create_info_panel_v2(self, parent, prob, vertices, vv, optimal,
                               maximize, status="optimal", multi_opt=None,
                               is_ray=False, path_d=None, path_b=None):
        multi_opt = multi_opt or []
        path_d = path_d or []
        path_b = path_b or []

        info_frame = tk.Frame(parent, bg="#F0F4F8", bd=0,
                              highlightthickness=1, highlightbackground="#B0BEC5")
        info_frame.place(relx=0.987, rely=0.02, anchor="ne", width=320, height=280)

        canvas_i = tk.Canvas(info_frame, bg="#F0F4F8", highlightthickness=0)
        sb_i = ttk.Scrollbar(info_frame, orient="vertical", command=canvas_i.yview)
        canvas_i.configure(yscrollcommand=sb_i.set)
        sb_i.pack(side="right", fill="y")
        canvas_i.pack(side="left", fill="both", expand=True)
        inner_i = tk.Frame(canvas_i, bg="#F0F4F8")
        canvas_i.create_window((0, 0), window=inner_i, anchor="nw")
        inner_i.bind("<Configure>",
                     lambda e: canvas_i.configure(
                         scrollregion=canvas_i.bbox("all")))

        def lbl(text, fg="#37474F", font=("Segoe UI", 9)):
            tk.Label(inner_i, text=text, bg="#F0F4F8", fg=fg,
                     font=font, anchor="w", wraplength=295).pack(
                fill="x", padx=8, pady=1)

        def sep():
            tk.Frame(inner_i, bg="#CFD8DC", height=1).pack(
                fill="x", padx=6, pady=2)

        lbl("Tóm tắt", fg="#263238", font=("Segoe UI", 10, "bold"))
        sep()

        lbl(f"Kiểu: {'Bài toán Max' if prob.objective_sense == 'max' else 'Bài toán Min'}")
        lbl(f"Số ràng buộc: {len(prob.constraints)}")
        lbl(f"Số đỉnh khả thi: {len(vertices)}")

        # Trạng thái
        status_map = {
            "optimal": ("Nghiệm tối ưu", "#2E7D32"),
            "infeasible": ("VÔ NGHIỆM", "#C62828"),
            "unbounded": ("KHÔNG GIỚI NỘI", "#E65100"),
            "cycle": ("Xoay vòng Dantzig", "#F57F17"),
        }
        if multi_opt:
            st_text, st_col = "VÔ SỐ NGHIỆM TỐI ƯU", "#1565C0"
        else:
            st_text, st_col = status_map.get(status, (status, "#546E7A"))
        sep()
        lbl(f"Trạng thái: {st_text}", fg=st_col, font=("Segoe UI", 9, "bold"))

        if optimal and status not in ("infeasible", "unbounded"):
            sep()
            report = self.last_report
            if report and report.objective_orig is not None:
                z_val = float(report.objective_orig)
            else:
                z_val = optimal[2]
            z_label = "Z" if prob.objective_sense == "min" else "Z"
            z_str = f"{z_val:.4g}"
            if multi_opt:
                lbl("Nghiệm tối ưu:", fg="#1565C0",
                    font=("Segoe UI", 9, "bold"))
                if not is_ray:
                    # Đoạn: hiển thị tọa độ 2 đầu mút
                    cx_m = sum(p[0] for p in multi_opt) / len(multi_opt)
                    cy_m = sum(p[1] for p in multi_opt) / len(multi_opt)
                    multi_sorted = sorted(multi_opt,
                                          key=lambda p: math.atan2(p[1]-cy_m, p[0]-cx_m))
                    p0, p1 = multi_sorted[0], multi_sorted[-1]
                    lbl(f"  ({p0[0]:.4g}, {p0[1]:.4g}) — ({p1[0]:.4g}, {p1[1]:.4g})",
                        fg="#1565C0")
                lbl(f"Giá trị tối ưu: {z_label} = {z_str}",
                    fg="#1565C0", font=("Segoe UI", 9, "bold"))
            else:
                lbl(f"Điểm tối ưu: ({optimal[0]:.4g}, {optimal[1]:.4g})",
                    fg="#E65100")
                lbl(f"Giá trị tối ưu: {z_label} = {z_str}",
                    fg="#2E7D32", font=("Segoe UI", 9, "bold"))

        # Đường đi simplex
        if path_d or path_b:
            sep()
            lbl("Đường đi đơn hình:", fg="#546E7A",
                font=("Segoe UI", 8, "bold"))
            if path_d:
                lbl(f"Dantzig: {len(path_d)} bước", fg="#E65100",
                    font=("Segoe UI", 8))
                for k, (px, py) in enumerate(path_d):
                    lbl(f"  D{k}: ({px:.3g}, {py:.3g})",
                        fg="#BF360C", font=("Consolas", 8))
            if path_b:
                lbl(f"Bland: {len(path_b)} bước", fg="#00838F",
                    font=("Segoe UI", 8))
                for k, (px, py) in enumerate(path_b):
                    lbl(f"  B{k}: ({px:.3g}, {py:.3g})",
                        fg="#006064", font=("Consolas", 8))

        sep()
        lbl("Kéo chuột trái để pan", fg="#90A4AE")
        lbl("Lăn chuột để zoom", fg="#90A4AE")


    def _create_visualization_window(self):
        # Tạo cửa sổ Toplevel riêng biệt cho trực quan hóa với giao diện tối, đồng bộ 2D/3D.
        top = tk.Toplevel(self)
        top.title("Trực quan hóa bài toán 2 biến — 2D")
        top.geometry("1540x980")
        top.minsize(1100, 760)
        top.resizable(True, True)
        try:
            top.state("zoomed")
        except Exception:
            try:
                top.attributes("-zoomed", True)
            except Exception:
                pass
        top.configure(bg="#F0F4F8")
        top.columnconfigure(0, weight=1)
        top.rowconfigure(0, weight=1)
        top.protocol("WM_DELETE_WINDOW", top.destroy)
        return top

    def _create_figure(self):
        # Khởi tạo Figure và Axes matplotlib theo phong cách sáng, dễ nhìn.
        from matplotlib.figure import Figure
        fig = Figure(figsize=(15.6, 9.2), dpi=110)
        fig.patch.set_facecolor("#F8F9FA")
        fig.subplots_adjust(left=0.055, right=0.985, top=0.915, bottom=0.09)
        ax = fig.add_subplot(111)
        ax.set_facecolor("#FFFFFF")
        ax.set_axisbelow(True)
        ax.grid(True, linestyle="--", linewidth=0.7, alpha=0.45, color="#BBCDD8")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#90A4AE")
        ax.spines["bottom"].set_color("#90A4AE")
        ax.tick_params(colors="#37474F", labelsize=9)
        return fig, ax

    def _plot_constraints(self, ax, halfplanes, xmin, xmax, ymin, ymax):
        # Vẽ từng đường biên ràng buộc — màu xoay vòng Set3-inspired, đủ 12 màu phân biệt.
        # Không vẽ nhãn inline; nhãn hiển thị qua legend.
        palette = ["#4e9ac7","#e8604a","#5cb87a","#e8b820","#b07fbd","#e07a28",
                   "#d96b8a","#8ab550","#b08060","#7a7a7a","#d4a800","#5ba8c0"]
        seen = set()
        for idx, (a, b, c, sense, label) in enumerate(halfplanes):
            color = palette[idx % len(palette)]
            pts = self._line_box_intersections(a, b, c, xmin, xmax, ymin, ymax)
            if len(pts) < 2: continue
            pts = sorted(pts, key=lambda p: (p[0], p[1]))
            (x1,y1),(x2,y2) = pts[0], pts[-1]
            ax.plot([x1,x2],[y1,y2], color=color, linewidth=2.2,
                    alpha=0.92, solid_capstyle="round", zorder=2,
                    label=label if label not in seen else "_nolegend_")
            if label not in seen:
                seen.add(label)

    def _plot_objective_contours(self, ax, c1, c2, vv, xmin, xmax, ymin, ymax, maximize):
        # Vẽ đường đồng mức hàm mục tiêu — dark theme.
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
            ax.plot([x1,x2],[y1,y2], color="#1565C0",
                    linewidth=2.6 if is_best else 1.4,
                    linestyle="-" if is_best else "--",
                    alpha=0.85 if is_best else 0.30, zorder=1.5)
            if is_best:
                tx,ty = (x1+x2)/2,(y1+y2)/2
                ax.text(tx, ty,
                        f"  z = {fmt_num(Fraction(str(lv)), self.data_mode)}",
                        color="#0D47A1", fontsize=9, weight="bold",
                        bbox=dict(boxstyle="round,pad=0.25",
                                  fc="#E3F2FD", ec="#1565C0", alpha=0.95), zorder=4)

    def _convex_hull_order(self, coords_2d):

        import numpy as np
        n = len(coords_2d)
        if n < 2:
            return list(range(n))
        if n == 2:
            return [0, 1]

        # --- Thử scipy trước (nhanh, chính xác) ---
        try:
            from scipy.spatial import ConvexHull
            hull = ConvexHull(coords_2d, qhull_options="QJ")
            # hull.vertices là CCW; đảm bảo thứ tự bằng cách lấy theo simplices
            return list(hull.vertices)
        except Exception:
            pass

        # --- Fallback: Graham scan thuần Python ---
        pts = [(coords_2d[i][0], coords_2d[i][1], i) for i in range(n)]
        # Điểm khởi đầu: y nhỏ nhất, rồi x nhỏ nhất
        pivot = min(pts, key=lambda p: (p[1], p[0]))
        px, py = pivot[0], pivot[1]

        def cross(o, a, b):
            return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])

        rest = [p for p in pts if not (abs(p[0]-px)<1e-12 and abs(p[1]-py)<1e-12)]
        rest.sort(key=lambda p: (
            math.atan2(p[1]-py, p[0]-px),
            (p[0]-px)**2 + (p[1]-py)**2
        ))

        stack = [pivot, rest[0]] if rest else [pivot]
        for p in rest[1:]:
            while len(stack) >= 2 and cross(stack[-2], stack[-1], p) <= 0:
                stack.pop()
            stack.append(p)

        return [p[2] for p in stack]

    def _plot_vertices(self, ax, vv, maximize):
        if not vv: return
        import numpy as np
        from matplotlib.patches import Polygon as MplPolygon

        pts = list(vv)  # mỗi phần tử: (x, y, z)
        coords = np.array([(p[0], p[1]) for p in pts], dtype=float)

        # ── Trường hợp 1 đỉnh: chấm ──────────────────────────────────────
        if len(pts) == 1:
            ax.scatter([pts[0][0]], [pts[0][1]], s=42, color="#1976D2",
                       edgecolors="#FFFFFF", linewidths=1.2, zorder=5)
            ax.annotate("1", xy=(pts[0][0], pts[0][1]), xytext=(6,6),
                        textcoords="offset points", fontsize=9, color="#0D47A1",
                        bbox=dict(boxstyle="circle,pad=0.20",
                                  fc="#E3F2FD", ec="#1565C0", alpha=0.96), zorder=6)
            return

        # ── Trường hợp 2 đỉnh: đoạn thẳng ───────────────────────────────
        if len(pts) == 2:
            ax.plot([pts[0][0], pts[1][0]], [pts[0][1], pts[1][1]],
                    color="#1565C0", linewidth=2.2, alpha=0.75, zorder=2.5)
            for idx, (vx, vy, _) in enumerate(pts, start=1):
                ax.scatter([vx], [vy], s=42, color="#1976D2",
                           edgecolors="#FFFFFF", linewidths=1.2, zorder=5)
                ax.annotate(f"{idx}", xy=(vx, vy), xytext=(6,6),
                            textcoords="offset points", fontsize=9, color="#0D47A1",
                            bbox=dict(boxstyle="circle,pad=0.20",
                                      fc="#E3F2FD", ec="#1565C0", alpha=0.96), zorder=6)
            return

        # ── Trường hợp ≥3 đỉnh: vẽ polygon convex hull ───────────────────
        hull_idx = self._convex_hull_order(coords)
        hull_pts = [pts[i] for i in hull_idx]   # (x, y, z) theo CCW
        hull_xy  = np.array([(p[0], p[1]) for p in hull_pts])

        poly_patch = MplPolygon(
            hull_xy, closed=True,
            facecolor="#BBDEFB", alpha=0.42,
            edgecolor="#1565C0", linewidth=1.6,
            linestyle="-", zorder=1
        )
        ax.add_patch(poly_patch)

        hull_set = set(hull_idx)
        non_hull = [i for i in range(len(pts)) if i not in hull_set]
        ordered_for_label = list(hull_idx) + non_hull

        for label_num, orig_idx in enumerate(ordered_for_label, start=1):
            vx, vy, _ = pts[orig_idx]
            ax.scatter([vx], [vy], s=42, color="#1976D2",
                       edgecolors="#FFFFFF", linewidths=1.2, zorder=5)
            ax.annotate(f"{label_num}", xy=(vx, vy), xytext=(6, 6),
                        textcoords="offset points", fontsize=9, color="#0D47A1",
                        bbox=dict(boxstyle="circle,pad=0.20",
                                  fc="#E3F2FD", ec="#1565C0", alpha=0.96), zorder=6)

    def _plot_optimal_point(self, ax, optimal, maximize):
        # Đánh dấu điểm tối ưu bằng hình sao vàng lớn — light theme.
        if optimal is None: return
        bx,by,bz = optimal
        ax.scatter([bx],[by], s=240, marker="*", color="#E65100",
                   edgecolors="#FFFFFF", linewidths=1.2, zorder=7)
        ax.annotate(
            f"Điểm tối ưu\n({bx:.3g}, {by:.3g})",
            xy=(bx,by), xytext=(14,18), textcoords="offset points",
            fontsize=10, fontweight="bold", color="#BF360C",
            bbox=dict(boxstyle="round,pad=0.38",
                      fc="#FFF3E0", ec="#E65100", alpha=0.97),
            arrowprops=dict(arrowstyle="->", color="#E65100", lw=1.5), zorder=8)

    def _configure_axes(self, ax, xmin, xmax, ymin, ymax):
        # Thiết lập tiêu đề, nhãn trục, trục tọa độ, legend — light theme.
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)
        ax.set_aspect("auto", adjustable="box")
        ax.set_xlabel("x₁", fontsize=12, fontweight="bold", color="#37474F")
        ax.set_ylabel("x₂", fontsize=12, fontweight="bold", color="#37474F")
        ax.axhline(0, color="#90A4AE", linewidth=1.1, alpha=0.7, zorder=0.5)
        ax.axvline(0, color="#90A4AE", linewidth=1.1, alpha=0.7, zorder=0.5)
        hs, ls = ax.get_legend_handles_labels()
        if hs:
            ax.legend(hs, ls, loc="upper left", frameon=True, fontsize=9,
                    title="Ràng buộc", fancybox=True,
                    shadow=False, facecolor="#FFFFFF", edgecolor="#B0BEC5",
                    labelcolor="#37474F", title_fontproperties={"weight": "bold", "size": 10})

    def _create_control_button(self, parent, text, color, hover_color, command):
        # Tạo nút tkinter với hiệu ứng hover đơn giản (đổi màu nền khi rê chuột).
        btn = tk.Button(parent, text=text, font=("Segoe UI",10,"bold"),
                        bg=color, fg="white", activebackground=hover_color,
                        activeforeground="white", relief="flat", bd=0,
                        padx=10, pady=6, cursor="hand2", command=command)
        btn.pack(side="left", padx=4, pady=4)
        btn.bind("<Enter>", lambda e: btn.config(bg=hover_color))
        btn.bind("<Leave>", lambda e: btn.config(bg=color))
        return btn

    def _enable_canvas_interactions(self, ax, canvas):
        # Gắn các sự kiện chuột vào canvas matplotlib:
        #   - Kéo nút trái: pan (di chuyển khung nhìn)
        #   - Lăn chuột: zoom vào/ra quanh vị trí con trỏ
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
        # Tạo thanh điều khiển zoom ở góc dưới: nút "+" / "−" / "reset", light theme.
        ctrl = tk.Frame(parent, bg="#E8EEF2")
        ctrl.place(relx=0.0, rely=1.0, anchor="sw", relwidth=1.0)
        btn_frame = tk.Frame(ctrl, bg="#E8EEF2")
        btn_frame.pack(side="left", padx=8, pady=4)
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
        self._create_control_button(btn_frame,"+","#1976D2","#1565C0",zi)
        self._create_control_button(btn_frame,"−","#F57C00","#E65100",zo)
        self._create_control_button(btn_frame,"reset","#388E3C","#2E7D32",rst)
        tk.Label(ctrl, text="Kéo chuột trái để di chuyển · Lăn chuột để zoom",
                 bg="#E8EEF2", fg="#546E7A", font=("Segoe UI",9)).pack(
            side="left", padx=10, pady=6)

    def _create_info_panel(self, parent, prob, vertices, vv, optimal, maximize):
        # Bảng tóm tắt nhỏ ở góc trên phải đồ thị, light theme.
        info_frame = tk.Frame(parent, bg="#F0F4F8", bd=0,
                              highlightthickness=1, highlightbackground="#B0BEC5")
        info_frame.place(relx=0.987, rely=0.02, anchor="ne", width=320, height=182)
        title = tk.Label(info_frame, text="Tóm tắt", bg="#F0F4F8",
                         fg="#263238", font=("Segoe UI",11,"bold"))
        title.pack(anchor="w", padx=10, pady=(8,2))
        text = tk.Text(info_frame, wrap="word", bg="#F0F4F8", fg="#37474F",
                       bd=0, font=("Segoe UI",9), height=8, padx=10, pady=6,
                       insertbackground="#263238")
        text.pack(fill="both", expand=True)
        lines = [
            f"Kiểu: {'Bài toán Max' if prob.objective_sense=='max' else 'Bài toán Min'}",
            f"Số ràng buộc: {len(prob.constraints)}",
            f"Số đỉnh khả thi: {len(vertices)}",
        ]
        if optimal: lines += [f"Điểm tối ưu: ({optimal[0]:.3g}, {optimal[1]:.3g})"]
        else: lines.append("Chưa tìm được miền khả thi.")
        lines += ["Kéo chuột trái để pan.", "Dùng nút hoặc lăn chuột để zoom."]
        text.insert("1.0", "\n".join(lines))
        text.config(state="disabled")


    def _format_problem(self, engine):
        # Tạo chuỗi hiển thị bài toán gốc (trước chuẩn hóa):
        # Căn thẳng cột: cụm (hệ số·biến) của từng biến thẳng nhau, dấu ≤/≥/= thẳng, RHS thẳng.
        mode = self.data_mode
        prob = engine.problem
        n = len(prob.obj_coeffs)
        var_names = [f"x{i+1}" for i in range(n)]

        def fmt_coeff(c):
            return fmt_num(abs(c), mode)

        def build_terms(coeffs):
            terms = []
            for c, nm in zip(coeffs, var_names):
                if c == 0:
                    continue
                sign = "+" if c > 0 else "-"
                if abs(c) == 1:
                    body = nm
                else:
                    body = f"{fmt_coeff(c)}{nm}"
                terms.append((sign, body))
            return terms

        # ── Thu thập tất cả hàng để tính độ rộng cột ────────────────────
        # Mỗi hàng là list các (sign, body) theo thứ tự biến
        def row_cells(coeffs):
            cells = []
            for c, nm in zip(coeffs, var_names):
                if c == 0:
                    cells.append(("", ""))
                else:
                    sign = "+" if c > 0 else "-"
                    body = nm if abs(c) == 1 else f"{fmt_coeff(c)}{nm}"
                    cells.append((sign, body))
            return cells

        obj_cells   = row_cells(prob.obj_coeffs)
        cons_cells  = [row_cells(cons["coeffs"]) for cons in prob.constraints]
        all_cells   = [obj_cells] + cons_cells

        # Độ rộng mỗi cột (sign + body gộp lại, ví dụ "- 3/2x2")
        col_w = []
        for j in range(n):
            w = 0
            for row in all_cells:
                sign, body = row[j]
                cell_str = f"{sign} {body}" if sign else ""
                w = max(w, len(cell_str))
            col_w.append(max(w, len(var_names[j]) + 2))  # tối thiểu đủ chứa tên biến

        # Độ rộng RHS
        rhs_strs = [fmt_num(cons["rhs"], mode) for cons in prob.constraints]
        rhs_w = max((len(s) for s in rhs_strs), default=1)

        def render_row(cells):
            """Ghép một hàng đã căn phải theo col_w."""
            parts = []
            first_nonzero = True
            for j, (sign, body) in enumerate(cells):
                if not sign:  # hệ số = 0, điền khoảng trắng
                    parts.append(" " * col_w[j])
                else:
                    if first_nonzero and sign == "+":
                        cell_str = body          # hạng tử đầu bỏ dấu +
                    else:
                        cell_str = f"{sign} {body}"
                    parts.append(cell_str.rjust(col_w[j]))
                    first_nonzero = False
            return "  ".join(parts).rstrip()

        sense_label = "max" if prob.objective_sense == "max" else "min"
        obj_line = f"    {sense_label} Z = {render_row(obj_cells)}"

        # Căn dấu ràng buộc và RHS
        sense_w = 1  # "≤" / "≥" / "=" đều 1 ký tự
        con_lines = []
        for i, cons in enumerate(prob.constraints):
            lhs  = render_row(cons_cells[i])
            s    = cons["sense"]
            rhs  = rhs_strs[i].rjust(rhs_w)
            con_lines.append(f"      {lhs}  {s}  {rhs}")

        # Điều kiện dấu biến
        sign_parts = []
        for i, sg in enumerate(prob.var_signs):
            nm = f"x{i+1}"
            if sg == "≥0":     sign_parts.append(f"{nm} ≥ 0")
            elif sg == "≤0":   sign_parts.append(f"{nm} ≤ 0")
            else:              sign_parts.append(f"{nm} tự do")

        lines = [
            "Bài toán Quy Hoạch Tuyến Tính:",
            obj_line,
            "    s.t. {",
        ]
        lines += con_lines
        lines.append(f"      {',  '.join(sign_parts)}")
        lines.append("    }")
        return "\n".join(lines)

    def _format_standardization(self, engine):
        # Tạo chuỗi giải thích từng bước chuẩn hóa:
        #   - Biến tự do / âm được thay thế bằng biến phụ
        #   - Ràng buộc ≥ nhân (-1), ràng buộc = thêm biến bù
        #   - Bài toán max nhân (-1) để đưa về dạng min
        mode = self.data_mode
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
        lines=["──────────────────────────","| Chuẩn hóa bài toán gốc |","──────────────────────────","","+ Chuẩn hóa ràng buộc dấu:"]
        for idx,sign in enumerate(engine.problem.var_signs):
            nm=f"x{idx+1}"
            if sign=="≥0": lines.append(f"        {nm} ≥ 0: giữ nguyên {nm} ≥ 0")
            elif sign=="≤0": lines.append(f"        {nm} tự do âm: đặt {nm} = -y{idx+1}, với y{idx+1} ≥ 0")
            else: lines.append(f"        {nm} tự do: đặt {nm} = a{idx+1} - b{idx+1}, với a{idx+1}, b{idx+1} ≥ 0")
        lines+=["","+ Chuẩn hóa ràng buộc đẳng thức, bất đẳng thức:"]
        std_idx = 0
        for i,cons in enumerate(engine.problem.constraints):
            s=cons["sense"]
            if s=="≤":
                lines.append(f"    RB{i+1}: giữ nguyên (≤), thêm biến bù w{std_idx+1}")
                std_idx += 1
            elif s=="≥":
                lines.append(f"    RB{i+1}: nhân (-1) để đưa về ≤, thêm biến bù w{std_idx+1}")
                std_idx += 1
            else:
                # = tách thành 2 dòng: row_a và row_b
                wa = std_idx + 1; wb = std_idx + 2
                row_a = engine.std_constraints[std_idx]; rhs_a = engine.std_rhs[std_idx]
                row_b = engine.std_constraints[std_idx+1]; rhs_b = engine.std_rhs[std_idx+1]
                names_a = engine.std_names[:len(row_a)]
                lines.append(f"    RB{i+1}: đẳng thức → tách thành 2 ràng buộc ≤:")
                lines.append(f"    ---> RB{i+1}a: {expr(row_a, names_a)} ≤ {fmt_num(rhs_a, mode)}  (thêm biến bù w{wa})")
                lines.append(f"    ---> RB{i+1}b: {expr(row_b, names_a)} ≤ {fmt_num(rhs_b, mode)}  (thêm biến bù w{wb})")
                std_idx += 2
        lines+=["","+ Các biến sau chuẩn hóa:"]
        for idx,sign in enumerate(engine.problem.var_signs):
            if sign=="≥0": lines.append(f"        x{idx+1} = x{idx+1}")
            elif sign=="≤0": lines.append(f"        x{idx+1} = -y{idx+1}")
            else: lines.append(f"        x{idx+1} = a{idx+1} - b{idx+1}")
        for nm in extra_x: lines.append(f"        {nm} = {nm}")
        lines+=["","+ Chuẩn hóa hàm mục tiêu:"]
        obj_expr=expr(engine.std_obj_coeffs, engine.std_names)
        z_label = "Z'" if engine.problem.objective_sense == "max" else "Z"
        if engine.problem.objective_sense=="min": 
            lines.append("    Bài toán min, giữ nguyên:")
            lines.append(f"        min Z = {obj_expr}")
        else: 
            lines.append("    Bài toán max → đặt Z' = −Z, min Z' = −max Z:")
            lines.append(f"        min Z' = {obj_expr}")
        lines+=["","───────────────────────────",f"| Dạng chuẩn của bài toán |","───────────────────────────",f"    min {z_label} = {obj_expr}","    {"]
        for i,row in enumerate(engine.std_constraints):
            lines.append(f"      {expr(row,engine.std_names[:len(row)])} ≤ {fmt_num(engine.std_rhs[i],mode)}")
        slack_names=[nm for nm in engine.all_names if nm.startswith("w")]
        # Điều kiện dấu: chỉ liệt kê các biến chuẩn hóa thực sự >= 0
        # Biến gốc x_i tự do không >= 0; chỉ các biến thay thế (a_i, b_i, y_i) mới >= 0
        nonneg_vars = []
        for i, sign in enumerate(engine.problem.var_signs):
            if sign == "≥0":
                nonneg_vars.append(f"x{i+1}")
            elif sign == "≤0":
                nonneg_vars.append(f"y{i+1}")
            else:  # tự do: a_i, b_i >= 0 (không phải x_i)
                nonneg_vars.append(f"a{i+1}")
                nonneg_vars.append(f"b{i+1}")
        # Deduplicate giữ thứ tự
        seen_nonneg = set(); nonneg_unique = []
        for v in nonneg_vars:
            if v not in seen_nonneg: seen_nonneg.add(v); nonneg_unique.append(v)
        lines.append(f"      {', '.join(nonneg_unique)} ≥ 0")
        lines.append("    }")
        lines += [
            "",
            f"+ Các biến bù {', '.join(slack_names)}",
            f"  được thêm vào từng ràng buộc",
            f"  để tạo cơ sở ban đầu cho bảng từ vựng.",
        ]
        return "\n".join(lines)

    def _dict_lines(self, snapshot):
        # Tạo danh sách dòng cho bảng từ vựng.
        # Mỗi cột biến có độ rộng = max độ rộng hạng tử thực tế trên tất cả hàng.
        # Khoảng cách giữa các cột = GAP cố định (không phụ thuộc nội dung).
        # Bỏ separator │ để gọn hơn.
        GAP = 2          # số khoảng trắng giữa hai cột liền kề
        mode = self.data_mode
        names = snapshot.all_names

        all_rows = [(snapshot.objective_label, snapshot.obj_const, snapshot.obj)]
        for i, b in enumerate(snapshot.basis):
            all_rows.append((names[b], snapshot.rhs[i], snapshot.rows[i]))

        # Độ rộng cột nhãn và cột hằng số
        label_w = max(len(row[0]) for row in all_rows)
        const_strs = [fmt_num(row[1], mode) for row in all_rows]
        const_w = max(len(s) for s in const_strs)

        # Độ rộng mỗi cột biến: max độ rộng hạng tử (kể cả "0" nếu hệ số = 0 được bỏ → ô trống)
        # Hạng tử rỗng ("") vẫn cần giữ chỗ bằng đúng độ rộng cột → không dùng ljust mà dùng rjust
        col_w = []
        col_cells = []   # col_cells[row_idx][col_idx] = chuỗi hạng tử (có thể rỗng)
        for _ in all_rows:
            col_cells.append([])

        for j, name in enumerate(names):
            w = 0
            for ri, (_, _, coeffs) in enumerate(all_rows):
                s = term_str(coeffs.get(j, Fraction(0)), name, mode)
                col_cells[ri].append(s)
                w = max(w, len(s))
            col_w.append(w)   # độ rộng thực tế tối thiểu; có thể bằng 0 nếu cột toàn rỗng

        def line_for(ri, label, const_s):
            label_part = label.ljust(label_w)
            # Dòng objective (ri=0): nếu const=0 và có hạng tử thì bỏ "0" đi
            row_const, _, row_coeffs = all_rows[ri]
            has_terms = any(row_coeffs.get(j, Fraction(0)) != 0 for j in range(len(names)))
            if ri == 0 and row_const == 0 and has_terms:
                const_part = " " * const_w   # giữ chỗ nhưng không in "0"
            else:
                const_part = const_s.rjust(const_w)
            # Mỗi ô: ljust theo col_w[j] (giữ chỗ cho ô rỗng)
            term_parts = [col_cells[ri][j].ljust(col_w[j]) for j in range(len(names))]
            # Ghép bằng GAP khoảng trắng, sau đó rstrip để bỏ trailing spaces
            term_part = (" " * GAP).join(term_parts).rstrip()
            return f"{label_part} = {const_part}    {term_part}"

        lines = []
        for ri, ((label, const, coeffs), const_s) in enumerate(zip(all_rows, const_strs)):
            lines.append(line_for(ri, label, const_s))
        return lines

    def _insert_snapshot(self, snapshot, title, tags=None):
        # Chèn tiêu đề và bảng từ vựng vào output ScrolledText.
        # Nếu có tags (entering / pivot_row), áp dụng highlight màu:
        #   pivotcol  → tất cả ô cột biến vào
        #   pivotrow  → toàn bộ hàng biến ra
        #   pivotcell → ô giao (phần tử xoay)
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
        # In giải thích chi tiết một bước xoay: quy tắc chọn biến vào (Dantzig/Bland), bảng tỉ số θ để chọn biến ra, phần tử xoay, và cờ suy biến nếu θ = 0.
        mode=self.data_mode; names=snapshot.all_names
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
        if step.status=="phase1_aux_degenerate_exit":
            self.output.insert(tk.END,"Xoay x0 ra (degenerate pivot):\n","h2")
            self.output.insert(tk.END,f"— δ = 0 nhưng x0 vẫn trong cơ sở với x0 = 0 → cần xoay x0 ra.\n","note")
            self.output.insert(tk.END,f"— Chọn {enter} vào thay x0 (θ = 0, bước suy biến).\n","note")
            self.output.insert(tk.END,f"  ⟹ biến vào: {enter}\n  ⟹ biến ra: {leave}\n","note")
            if step.pivot_value is not None:
                self.output.insert(tk.END,f"— Phần tử xoay: a_{{{leave},{enter}}} = {fmt_num(step.pivot_value,mode)}.\n","note")
            return
        self.output.insert(tk.END,f"Theo quy tắc {rule}:\n","h2")
        if step.entering is not None:
            coeff=snapshot.obj.get(step.entering,Fraction(0))
            if step.method=="dantzig":
                self.output.insert(tk.END,f"— Chọn {enter} vì hệ số âm nhất {fmt_num(coeff,mode)} trong hàm mục tiêu.\n","note")
            else:
                self.output.insert(tk.END,f"— Chọn biến có chỉ số bé nhất {enter}.\n","note")
            self.output.insert(tk.END,f"  ⟹ biến vào: {enter}\n","note")
        if step.ratios:
            self.output.insert(tk.END,f"— Tỉ số θ tại cột {enter} với hệ số âm:\n","note")
            for ri,theta,bi in step.ratios:
                coeff=snapshot.rows[ri][step.entering] if step.entering is not None else Fraction(1)
                self.output.insert(tk.END,f"  • {names[bi]}: {fmt_num(snapshot.rhs[ri],mode)} / {fmt_num(-coeff,mode)} = {fmt_num(theta,mode)}\n","note")
            self.output.insert(tk.END,f"  ⟹ biến ra: {leave}\n","note")
        if step.pivot_value is not None:
            self.output.insert(tk.END,f"— Phần tử xoay: a_{{{leave},{enter}}} = {fmt_num(step.pivot_value,mode)}.\n","note")
        if step.degenerate: self.output.insert(tk.END,"— Bước suy biến (θ=0).\n","warn")

    def _linear_text(self, const, terms, mode):
        # Tạo chuỗi biểu diễn biểu thức tuyến tính: hằng số + tổng các hạng tử.
        # Bỏ qua hệ số = 0; xử lý dấu + / - giữa các hạng tử cho đúng ký pháp.
        parts=[]
        if const!=0 or not terms: parts.append(fmt_num(const,mode))
        for coef,name in terms:
            if coef==0: continue
            body=name if abs(coef)==1 else f"{fmt_num(abs(coef),mode)}{name}"
            if parts: parts.append(f"+ {body}" if coef>0 else f"- {body}")
            else: parts.append(body if coef>0 else f"- {body}")
        return " ".join(parts).strip() if parts else "0"

    def _get_final_snapshot(self, report):
        if report is None:
            return None
        if report.phase2_trace and report.phase2_trace.final_snapshot:
            return report.phase2_trace.final_snapshot
        if report.bland is not None and report.bland.final_snapshot:
            return report.bland.final_snapshot
        return report.dantzig.final_snapshot

    def _has_multiple_optimal(self, engine, snapshot, report):
        if report.multiple_optimal_vars:
            return True
        if snapshot is None:
            return False
        # Kiểm tra split pairs: chỉ tính là vô số nghiệm nếu x_i thực sự thay đổi
        basis_set = set(snapshot.basis)
        art_set   = set(engine.artificial_vars)
        aux_idx   = getattr(engine, "phase1_aux_var_index", None)
        aux_set   = {aux_idx} if aux_idx is not None else set()
        for mapping in engine.variable_mapping:
            if len(mapping) != 2:
                continue
            j_a, j_b = mapping[0][0], mapping[1][0]
            if j_a in art_set or j_b in art_set or j_a in aux_set or j_b in aux_set:
                continue
            j_a_free = (j_a not in basis_set and snapshot.obj.get(j_a, Fraction(0)) == 0)
            j_b_free = (j_b not in basis_set and snapshot.obj.get(j_b, Fraction(0)) == 0)
            if j_a_free and j_b in basis_set:
                ri_b = snapshot.basis.index(j_b)
                coef = snapshot.rows[ri_b].get(j_a, Fraction(0))
                if Fraction(1) - coef != 0:
                    return True
            elif j_b_free and j_a in basis_set:
                ri_a = snapshot.basis.index(j_a)
                coef = snapshot.rows[ri_a].get(j_b, Fraction(0))
                if coef - Fraction(1) != 0:
                    return True
            elif j_a_free and j_b_free:
                return True
        return False

    def _expand_free_vars_with_splits(self, engine, snapshot, base_free_vars):
        basis_set = set(snapshot.basis)
        art_set   = set(engine.artificial_vars)
        aux_idx   = getattr(engine, "phase1_aux_var_index", None)
        aux_set   = {aux_idx} if aux_idx is not None else set()
        base_set  = set(base_free_vars)

        extra: list[int] = []
        split_free_pairs = []
        for orig_idx, mapping in enumerate(engine.variable_mapping):
            if len(mapping) != 2:
                continue
            j_a, j_b = mapping[0][0], mapping[1][0]
            if j_a in art_set or j_b in art_set or j_a in aux_set or j_b in aux_set:
                continue

            a_nonbasic_zero = (j_a not in basis_set
                               and snapshot.obj.get(j_a, Fraction(0)) == 0)
            b_nonbasic_zero = (j_b not in basis_set
                               and snapshot.obj.get(j_b, Fraction(0)) == 0)

            if a_nonbasic_zero and b_nonbasic_zero:
                # Cả hai phi cơ sở, obj=0 → cặp tự do hoàn toàn (trường hợp 1)
                which = "ab"
                if j_a not in base_set:
                    extra.append(j_a)
                if j_b not in base_set:
                    extra.append(j_b)
                split_free_pairs.append((orig_idx, j_a, j_b, which))
            elif a_nonbasic_zero and j_b in basis_set:
                which = "a"
                if j_a not in base_set:
                    extra.append(j_a)
                split_free_pairs.append((orig_idx, j_a, j_b, which))
            elif b_nonbasic_zero and j_a in basis_set:
                which = "b"
                if j_b not in base_set:
                    extra.append(j_b)
                split_free_pairs.append((orig_idx, j_a, j_b, which))

        all_free_vars = list(base_free_vars) + extra
        return all_free_vars, split_free_pairs

    def _format_multiple_optimal_family(self, engine, snapshot, report):
        mode = self.data_mode
        base_free_vars = report.multiple_optimal_vars or []
        if not base_free_vars:
            return []

        all_free_vars, split_free_pairs = self._expand_free_vars_with_splits(
            engine, snapshot, base_free_vars)
        free_vars     = all_free_vars
        free_set_vars = set(free_vars)

        aux_idx   = getattr(engine, "phase1_aux_var_index", None)
        art_set   = set(engine.artificial_vars)
        basis_set = set(snapshot.basis)
        basis_list = list(snapshot.basis)

        # Map j → tên gốc xi (dùng để gộp a_i/b_i)
        std_to_xname: Dict[int, str] = {}
        for orig_idx, mapping in enumerate(engine.variable_mapping):
            xn = f"x{orig_idx+1}"
            for j, _ in mapping:
                std_to_xname[j] = xn

        # Map orig_idx → (j_a, j_b) cho biến tự do gốc
        split_map: Dict[int, tuple] = {}
        for oi, ja, jb, _ in split_free_pairs:
            split_map[oi] = (ja, jb)

        # Biến xi được tham số hóa bởi x_i = a_i - b_i
        # (orig_idx → set of xi names đã được "split")
        split_orig_idxs = {oi for oi, *_ in split_free_pairs}

        # Tên tham số tự do để in: gộp cặp (a_i, b_i) → x_i khi which == "ab"
        free_names_display = []
        seen_sfp_orig = set()
        free_set_vars_for_display = set(free_vars)
        for oi, ja, jb, which in split_free_pairs:
            if oi in seen_sfp_orig:
                continue
            seen_sfp_orig.add(oi)
            if which == "ab":
                free_names_display.append(f"x{oi+1}")
            elif which == "a":
                free_names_display.append(snapshot.all_names[ja])
            elif which == "b":
                free_names_display.append(snapshot.all_names[jb])
        # Thêm các biến tự do không phải split pair
        split_j_set = {ja for _, ja, jb, _ in split_free_pairs} | {jb for _, ja, jb, _ in split_free_pairs}
        for fv in free_vars:
            if fv not in split_j_set:
                free_names_display.append(snapshot.all_names[fv])

        # Biến phi cơ sở bị gán 0
        fixed_zero_names = [
            snapshot.all_names[j]
            for j in range(len(snapshot.all_names))
            if j not in basis_set
            and j not in free_set_vars
            and (aux_idx is None or j != aux_idx)
            and j not in art_set
        ]

        # ── Dòng mở đầu ─────────────────────────────────────────────────────
        names_str = ", ".join(free_names_display)
        fixed_str = (", ".join(fixed_zero_names) + " = 0") if fixed_zero_names else "(không có)"
        if len(free_names_display) == 1:
            lines = [
                f"  Do hệ số trước {free_names_display[0]} bằng 0. Bài toán có vô số nghiệm.",
                f"  Cho các biến không cơ sở (trừ {free_names_display[0]}) bằng 0: {fixed_str}",
            ]
        else:
            lines = [
                f"  Do hệ số trước {names_str} đều bằng 0. Bài toán có vô số nghiệm.",
                f"  Cho các biến không cơ sở (trừ {names_str}) bằng 0: {fixed_str}",
            ]

        # ── Helper: biểu diễn một biến std theo tham số tự do ───────────────
        def std_expr(jj, use_xi=True):
            if jj in basis_set:
                ri2 = basis_list.index(jj)
                c = snapshot.rhs[ri2]
                t = {fv: snapshot.rows[ri2].get(fv, Fraction(0)) for fv in free_vars}
            elif jj in free_set_vars:
                c = Fraction(0)
                t = {fv: (Fraction(1) if fv == jj else Fraction(0)) for fv in free_vars}
            else:
                c = Fraction(0)
                t = {fv: Fraction(0) for fv in free_vars}
            return c, t

        def xi_expr_calc(orig_idx, bl, snap, fvars, var_mapping, free_set):
            """Tính x_orig_idx = Σ mc * (biến std) theo tham số tự do."""
            c = Fraction(0)
            t: Dict[int, Fraction] = {fv: Fraction(0) for fv in fvars}
            mapping = var_mapping[orig_idx]
            for j, mc in mapping:
                if j in set(bl):
                    ri_j = bl.index(j)
                    c += mc * snap.rhs[ri_j]
                    for fv in fvars:
                        t[fv] = t.get(fv, Fraction(0)) + mc * snap.rows[ri_j].get(fv, Fraction(0))
                elif j in free_set:
                    t[j] = t.get(j, Fraction(0)) + mc
            return c, t

        # ── Tính biểu thức mỗi hàng basis theo tham số ──────────────────────
        # Với biến cơ sở là a_i: gộp với b_i (nếu b_i cơ sở) → x_i
        # Kết quả: xname → (const, {fv: coef})
        xname_expr: Dict[str, tuple] = {}
        printed_basis: set = set()
        for ri, b in enumerate(basis_list):
            if b in art_set or (aux_idx is not None and b == aux_idx):
                continue
            xn = std_to_xname.get(b, snapshot.all_names[b])
            if xn in printed_basis:
                continue
            printed_basis.add(xn)

            # Dấu: +1 cho a_i hoặc biến thường, -1 cho b_i
            sign = Fraction(1)
            for mapping in engine.variable_mapping:
                if len(mapping) == 2 and mapping[1][0] == b:
                    sign = Fraction(-1); break

            c0 = sign * snapshot.rhs[ri]
            t0 = {fv: sign * snapshot.rows[ri].get(fv, Fraction(0)) for fv in free_vars}

            # Nếu đây là a_i và b_i cũng trong basis → gộp
            for oi, (ja, jb) in split_map.items():
                if b == ja and jb in basis_set:
                    ri_b = basis_list.index(jb)
                    c0 += Fraction(-1) * snapshot.rhs[ri_b]
                    for fv in free_vars:
                        t0[fv] = t0.get(fv, Fraction(0)) + Fraction(-1) * snapshot.rows[ri_b].get(fv, Fraction(0))
                    break

            xname_expr[xn] = (c0, t0)

        # ── Gộp {fv:coef} → terms hiển thị, thay a_i/b_i bằng x_i khi có thể ──
        def to_xi_terms(t):
            """Với cặp (ja, jb): nếu t[jb] == -t[ja] thì gộp thành x_i với coef=t[ja].
            Nếu không gộp được thì giữ tên a_i, b_i riêng."""
            remaining: Dict[int, Fraction] = {fv: v for fv, v in t.items() if v != 0}
            result_terms: list = []
            for oi2, ja2, jb2, _ in split_free_pairs:
                ca = remaining.get(ja2, Fraction(0))
                cb = remaining.get(jb2, Fraction(0))
                if ca == 0 and cb == 0:
                    continue
                if cb == -ca:
                    # ca*a_i + (-ca)*b_i = ca*(a_i-b_i) = ca*x_i
                    if ca != 0:
                        result_terms.append((ca, f"x{oi2+1}"))
                    remaining.pop(ja2, None)
                    remaining.pop(jb2, None)
                else:
                    if ca != 0:
                        result_terms.append((ca, snapshot.all_names[ja2]))
                        remaining.pop(ja2, None)
                    if cb != 0:
                        result_terms.append((cb, snapshot.all_names[jb2]))
                        remaining.pop(jb2, None)
            for fv, coef in remaining.items():
                if coef != 0:
                    result_terms.append((coef, snapshot.all_names[fv]))
            return result_terms

        def linear_xi(c, t):
            return self._linear_text(c, to_xi_terms(t), mode)

        # ── Điều kiện khả thi ────────────────────────────────────────────────
        lines.append("  Để nghiệm khả thi (các biến cơ sở ≥ 0), cần:")

        # ai_set / bi_set: tập chỉ số a_i / b_i trong split_free_pairs
        ai_set_sfp = {ja for _, ja, jb, _ in split_free_pairs}
        bi_set_sfp = {jb for _, ja, jb, _ in split_free_pairs}

        seen_cond: set = set()
        # Tập các orig_idx đã suy ra x_i (để tránh in 2 lần)
        xi_derived: set = set()

        for ri, b in enumerate(basis_list):
            if b in art_set or (aux_idx is not None and b == aux_idx):
                continue
            xn = std_to_xname.get(b, snapshot.all_names[b])
            if xn in seen_cond:
                continue
            seen_cond.add(xn)
            if xn not in xname_expr:
                continue
            c0, t0 = xname_expr[xn]
            has_dep = any(v != 0 for v in t0.values())

            # Kiểm tra xem đây có phải hàng a_i hay b_i trong split_free_pairs không
            is_ai_row = b in ai_set_sfp
            is_bi_row = b in bi_set_sfp

            if is_ai_row or is_bi_row:
                # Tìm orig_idx của cặp split này
                the_oi = None
                the_ja = the_jb = None
                for oi2, ja2, jb2, _ in split_free_pairs:
                    if b == ja2 or b == jb2:
                        the_oi = oi2; the_ja = ja2; the_jb = jb2
                        break

                if the_oi is None:
                    continue

                # Tên của biến cơ sở (a_i hoặc b_i)
                b_name_std = snapshot.all_names[b]

                # Xây dựng biểu thức của biến cơ sở này (theo tham số tự do)
                # Sử dụng trực tiếp rhs[ri] và row[ri] thay vì xname_expr (đã gộp sign)
                sign_b = Fraction(1)
                for mapping in engine.variable_mapping:
                    if len(mapping) == 2 and mapping[1][0] == b:
                        sign_b = Fraction(-1); break
                # Nếu sign_b = -1 → đây là b_i → b_i = rhs[ri] + ...
                # xname_expr đã gộp cả hai a_i và b_i nếu cả hai trong basis
                # Nên ta dùng trực tiếp snapshot.rhs[ri] và snapshot.rows[ri] cho hàng này
                raw_c = snapshot.rhs[ri]
                raw_t = {fv: snapshot.rows[ri].get(fv, Fraction(0)) for fv in free_vars}
                raw_has_dep = any(v != 0 for v in raw_t.values())

                # Xây dựng chuỗi biểu thức (dạng a_i / b_i)
                raw_terms = [(v, snapshot.all_names[fv]) for fv, v in raw_t.items() if v != 0]
                expr_raw = self._linear_text(raw_c, raw_terms, mode)

                if not raw_has_dep and raw_c >= 0:
                    lines.append(f"    {b_name_std} = {fmt_num(raw_c, mode)} ≥ 0  ✓")
                else:
                    lines.append(f"    {b_name_std} = {expr_raw} ≥ 0")

                # Suy ra x_i = a_i - b_i (chỉ in 1 lần mỗi cặp)
                if the_oi not in xi_derived:
                    xi_derived.add(the_oi)
                    # Tính x_i = a_i - b_i đúng cách: duyệt mapping
                    mapping_oi = engine.variable_mapping[the_oi]
                    xi_c = Fraction(0)
                    xi_t: Dict[int, Fraction] = {fv: Fraction(0) for fv in free_vars}
                    for j_m, mc_m in mapping_oi:
                        if j_m in basis_set:
                            ri_m = basis_list.index(j_m)
                            xi_c += mc_m * snapshot.rhs[ri_m]
                            for fv in free_vars:
                                xi_t[fv] = xi_t.get(fv, Fraction(0)) + mc_m * snapshot.rows[ri_m].get(fv, Fraction(0))
                        elif j_m in free_set_vars:
                            xi_t[j_m] = xi_t.get(j_m, Fraction(0)) + mc_m
                    xi_terms_list = [(v, snapshot.all_names[fv]) for fv, v in xi_t.items() if v != 0]
                    xi_expr_str = self._linear_text(xi_c, xi_terms_list, mode)
                    lines.append(f"    → x{the_oi+1} = {xi_expr_str}")
            else:
                if not has_dep:
                    if c0 >= 0:
                        lines.append(f"    {xn} = {fmt_num(c0, mode)} ≥ 0  ✓")
                else:
                    expr_str = linear_xi(c0, t0)
                    lines.append(f"    {xn} = {expr_str} ≥ 0")

        # Điều kiện cho cặp (a_i, b_i) cả hai phi cơ sở (which == "ab")
        for oi2, ja2, jb2, which2 in split_free_pairs:
            if which2 != "ab":
                continue
            if oi2 in xi_derived:
                continue
            xi_derived.add(oi2)
            # a_i = 0 + a_i (tự do), b_i = 0 + b_i (tự do)
            # Biến cơ sở không phụ thuộc vào a_i, b_i → không có ràng buộc thêm
            # Chỉ cần nêu điều kiện: a_i, b_i ≥ 0 → x_i = a_i - b_i tự do
            a_name = snapshot.all_names[ja2]
            b_name = snapshot.all_names[jb2]
            lines.append(f"    {a_name} ≥ 0, {b_name} ≥ 0 (tự do)")
            lines.append(f"    → x{oi2+1} = {a_name} - {b_name} tự do")

        # Điều kiện các tham số phi cơ sở (không phải a_i/b_i)
        non_split_free = [fv for fv in free_vars
                          if not any(ja == fv or jb == fv
                                     for _, ja, jb, _ in split_free_pairs)]
        if non_split_free:
            for fv in non_split_free:
                lines.append(f"    {snapshot.all_names[fv]} ≥ 0")

        return lines

    def _format_multiple_optimal_conclusion(self, engine, snapshot, report):
        """Nghiệm tối ưu biểu diễn theo biến gốc x_i, với điều kiện theo x_i."""
        mode = self.data_mode
        base_free_vars = report.multiple_optimal_vars or []
        if not base_free_vars:
            return []

        all_free_vars, split_free_pairs = self._expand_free_vars_with_splits(
            engine, snapshot, base_free_vars)
        free_vars  = all_free_vars
        free_set   = set(free_vars)

        aux_idx    = getattr(engine, "phase1_aux_var_index", None)
        art_set    = set(engine.artificial_vars)
        basis_list = list(snapshot.basis)
        basis_set  = set(basis_list)
        n_orig     = len(engine.problem.var_signs)

        # Map orig_idx → (ja, jb) cho split
        split_map: Dict[int, tuple] = {oi: (ja, jb) for oi, ja, jb, _ in split_free_pairs}
        split_orig = set(split_map.keys())

        # ── Tính x_i theo tham số tự do (biểu diễn dạng xi) ─────────────────
        # Tham số tự do hiển thị: a_i/b_i → x_i, còn lại giữ tên gốc
        def param_display(fv):
            for oi2, ja2, jb2, _ in split_free_pairs:
                if fv == ja2 or fv == jb2:
                    return f"x{oi2+1}"
            return snapshot.all_names[fv]

        # xi_expr[orig_idx] = (const, {fv: coef}) theo free_vars
        xi_expr: Dict[int, tuple] = {}
        for orig_idx, mapping in enumerate(engine.variable_mapping):
            c = Fraction(0)
            t: Dict[int, Fraction] = {fv: Fraction(0) for fv in free_vars}
            for j, mc in mapping:
                if j in basis_set:
                    ri = basis_list.index(j)
                    c += mc * snapshot.rhs[ri]
                    for fv in free_vars:
                        t[fv] += mc * snapshot.rows[ri].get(fv, Fraction(0))
                elif j in free_set:
                    t[j] = t.get(j, Fraction(0)) + mc
            xi_expr[orig_idx] = (c, t)

        # Gộp coef của a_i/b_i → x_i: nếu t[jb] == -t[ja] thì coef_xi = t[ja]
        def to_xi_terms(orig_idx):
            c, t = xi_expr[orig_idx]
            remaining: Dict[int, Fraction] = {fv: v for fv, v in t.items() if v != 0}
            result_terms: list = []
            for oi2, ja2, jb2, _ in split_free_pairs:
                ca = remaining.get(ja2, Fraction(0))
                cb = remaining.get(jb2, Fraction(0))
                if ca == 0 and cb == 0:
                    continue
                if cb == -ca:
                    if ca != 0:
                        result_terms.append((ca, f"x{oi2+1}"))
                    remaining.pop(ja2, None)
                    remaining.pop(jb2, None)
                else:
                    if ca != 0:
                        result_terms.append((ca, snapshot.all_names[ja2]))
                        remaining.pop(ja2, None)
                    if cb != 0:
                        result_terms.append((cb, snapshot.all_names[jb2]))
                        remaining.pop(jb2, None)
            for fv, coef in remaining.items():
                if coef != 0:
                    result_terms.append((coef, snapshot.all_names[fv]))
            return c, result_terms

        # ── In nghiệm tối ưu ─────────────────────────────────────────────────
        # Tập orig_idx có which == "ab" (tham số tự do hoàn toàn)
        ab_free_orig = {oi for oi, ja, jb, which in split_free_pairs if which == "ab"}

        lines = ["  Nghiệm tối ưu là:"]
        for orig_idx in range(n_orig):
            if orig_idx in ab_free_orig:
                lines.append(f"  - x{orig_idx+1} = x{orig_idx+1}  (tự do, x{orig_idx+1} ∈ ℝ)")
            else:
                c, terms = to_xi_terms(orig_idx)
                lines.append(f"  - x{orig_idx+1} = {self._linear_text(c, terms, mode)}")

        cond_parts = []

        def row_to_xi_terms(t_row):
            """Gộp a_i/b_i → x_i trong hàng w_j."""
            remaining2 = {fv: v for fv, v in t_row.items() if v != 0}
            result2 = []
            for oi2, ja2, jb2, _ in split_free_pairs:
                ca = remaining2.get(ja2, Fraction(0))
                cb = remaining2.get(jb2, Fraction(0))
                if ca == 0 and cb == 0:
                    continue
                if cb == -ca:
                    if ca != 0:
                        result2.append((ca, f"x{oi2+1}"))
                    remaining2.pop(ja2, None)
                    remaining2.pop(jb2, None)
                else:
                    if ca != 0:
                        result2.append((ca, snapshot.all_names[ja2]))
                        remaining2.pop(ja2, None)
                    if cb != 0:
                        result2.append((cb, snapshot.all_names[jb2]))
                        remaining2.pop(jb2, None)
            for fv2, coef2 in remaining2.items():
                if coef2 != 0:
                    result2.append((coef2, snapshot.all_names[fv2]))
            return result2

        ai_set = {ja for _, ja, jb, _ in split_free_pairs}
        bi_set = {jb for _, ja, jb, _ in split_free_pairs}

        seen_rows: set = set()
        for ri, b in enumerate(basis_list):
            if b in art_set or (aux_idx is not None and b == aux_idx):
                continue
            if b in ai_set or b in bi_set or ri in seen_rows:
                continue  # Bỏ qua hàng a_i, b_i — điều kiện nội bộ
            seen_rows.add(ri)
            t_row = {fv: snapshot.rows[ri].get(fv, Fraction(0)) for fv in free_vars}
            has_dep = any(v != 0 for v in t_row.values())
            if not has_dep:
                continue
            terms2 = row_to_xi_terms(t_row)
            if terms2:
                cond_parts.append(f"{self._linear_text(snapshot.rhs[ri], terms2, mode)} ≥ 0")

        # Tham số phi cơ sở không phải a_i/b_i (ví dụ w_j tự do)
        non_split_free = [fv for fv in free_vars if fv not in ai_set and fv not in bi_set]
        for fv in non_split_free:
            cond_parts.append(f"{snapshot.all_names[fv]} ≥ 0")

        # ── Rút gọn điều kiện cho từng tham số xi (split "ab" hoặc non-split) ──
        # Tìm tất cả tham số thực sự (mỗi split-ab pair gộp thành 1 xi, non-split là 1 param)
        # Chỉ rút gọn khi đúng 1 tham số thực sự
        ab_pairs = [(oi, ja, jb) for oi, ja, jb, which in split_free_pairs if which == "ab"]
        n_real_params = len(ab_pairs) + len(non_split_free)

        if n_real_params == 1:
            cond_parts_rut = []
            if ab_pairs:
                # Tham số là x_i = a_i - b_i, tự do → chỉ bị giới hạn bởi biến cơ sở
                oi_p, ja_p, jb_p = ab_pairs[0]
                param_name = f"x{oi_p+1}"
                # Duyệt các hàng basis (không phải a/b của split)
                # Hàng có coef[ja_p] hoặc coef[jb_p] ≠ 0 tạo ra ràng buộc
                # Biến cơ sở w = rhs + coef_a*a + coef_b*b ≥ 0
                # a và b tự do, nhưng x = a - b. Nếu chỉ có cặp này:
                # w = rhs + coef_a*a + coef_b*b ≥ 0
                # Tốt nhất: với mỗi hàng, gộp coef_a*a + coef_b*b → c_x * x (nếu coef_b == -coef_a)
                lowers, uppers = [], []
                for ri, b in enumerate(basis_list):
                    if b in art_set or (aux_idx is not None and b == aux_idx):
                        continue
                    if b in ai_set or b in bi_set:
                        continue
                    ca = snapshot.rows[ri].get(ja_p, Fraction(0))
                    cb = snapshot.rows[ri].get(jb_p, Fraction(0))
                    if ca == 0 and cb == 0:
                        continue
                    # Nếu cb == -ca: hàng có dạng w = rhs + ca*(a-b) = rhs + ca*x → w ≥ 0
                    if cb == -ca and ca != 0:
                        rhs_v = snapshot.rhs[ri]
                        # ca*x ≥ -rhs_v → nếu ca > 0: x ≥ -rhs_v/ca; nếu ca < 0: x ≤ -rhs_v/ca
                        bound = -rhs_v / ca
                        if ca > 0:
                            lowers.append(bound)
                        else:
                            uppers.append(bound)
                    # Nếu không gộp được → giữ nguyên dạng raw (bỏ qua rút gọn)
                lower = max(lowers) if lowers else None
                upper = min(uppers) if uppers else None
                if lower is not None and upper is not None:
                    cond_parts_rut.append(
                        f"{fmt_num(lower, mode)} ≤ {param_name} ≤ {fmt_num(upper, mode)}")
                elif lower is not None:
                    if lower == 0:
                        cond_parts_rut.append(f"{param_name} ≥ 0")
                    else:
                        cond_parts_rut.append(f"{param_name} ≥ {fmt_num(lower, mode)}")
                elif upper is not None:
                    cond_parts_rut.append(f"{param_name} ≤ {fmt_num(upper, mode)}")
                # else: không có ràng buộc → x_i hoàn toàn tự do, không in gì
                cond_parts = cond_parts_rut
            else:
                # Tham số non-split đơn: logic cũ
                param_idx = non_split_free[0]
                param_name = snapshot.all_names[param_idx]
                lowers, uppers = [Fraction(0)], []
                for ri, b in enumerate(basis_list):
                    if b in art_set or b in ai_set or b in bi_set:
                        continue
                    if aux_idx is not None and b == aux_idx:
                        continue
                    coef = snapshot.rows[ri].get(param_idx, Fraction(0))
                    if coef == 0:
                        continue
                    bound = -snapshot.rhs[ri] / coef
                    if coef > 0:
                        lowers.append(bound)
                    else:
                        uppers.append(bound)
                lower = max(lowers)
                cond_parts_rut = []
                if uppers:
                    upper = min(uppers)
                    cond_parts_rut.append(
                        f"{fmt_num(lower, mode)} ≤ {param_name} ≤ {fmt_num(upper, mode)}")
                else:
                    cond_parts_rut.append(f"{param_name} ≥ {fmt_num(lower, mode)}")
                cond_parts = cond_parts_rut

        if cond_parts:
            lines.append(f"  với {'; '.join(cond_parts)}.")

        return lines


    def _render_trace(self, title, trace):
        # In toàn bộ quá trình lặp của một pha (Dantzig hoặc Bland):
        #   - Với mỗi bước: in bảng từ vựng trước xoay (có highlight) → ghi chú bước → bảng sau xoay
        #   - In trạng thái kết thúc: tối ưu / không giới nội / xoay vòng
        if not trace.steps:
            self.output.insert(tk.END,"Từ vựng xuất phát:\n","h2")
            if trace.final_snapshot: self._insert_snapshot(trace.final_snapshot,"")
            return
        for step in trace.steps:
            t="Từ vựng xuất phát:" if step.iteration==1 else f"Bước {step.iteration} trước xoay:"
            self._insert_snapshot(step.before,t,
                tags={"entering":step.before.all_names[step.entering] if step.entering is not None else None,"pivot_row":step.leaving_row} if step.entering is not None else None)
            self.output.insert(tk.END,"\n")
            self._insert_step_note(step,step.before)
            self.output.insert(tk.END,"\n")
            if step.after is not None:
                self._insert_snapshot(step.after,f"Sau xoay bước {step.iteration}:")
                self.output.insert(tk.END,"\n")
        if trace.status=="optimal": self.output.insert(tk.END,"  Tất cả hệ số trên hàm mục tiêu đều ≥ 0 → từ vựng hiện tại là tối ưu.\n","note")
        elif trace.status=="unbounded":
            # Tìm biến vào từ bước cuối để nêu lý do
            last_entering = None
            if trace.steps:
                last_step = trace.steps[-1]
                if last_step.status == "unbounded" and last_step.entering is not None:
                    last_entering = trace.steps[-1].before.all_names[last_step.entering]
            reason = f" (có biến vào {last_entering} nhưng không có biến ra)" if last_entering else ""
            self.output.insert(tk.END,f"  Bài toán không giới nội{reason}.\n","warn")
        elif trace.status=="cycle": self.output.insert(tk.END,"  Phát hiện xoay vòng → thuật toán không thể tiếp tục.\n","warn")

    def _render_result(self, report):
        self.output.delete("1.0",tk.END)
        engine=report.engine; mode=self.data_mode
        self.output.insert(tk.END,self._format_problem(engine)+"\n\n","h1")
        self.output.insert(tk.END,self._format_standardization(engine)+"\n","mono")

        is_max = engine.problem.objective_sense == "max"

        if self._has_aux_phase1(engine):
            # ── Pha 1: biến phụ x0 ──────────────────────────────────────
            self.output.insert(tk.END,
                "\n───────────────────────────────────\n"
                " Pha 1: Giải bài toán bổ trợ\n"
                "───────────────────────────────────\n","h2")
            self.output.insert(tk.END,
                "  Tồn tại b_i < 0 → tìm từ vựng xuất phát chấp nhận được\n"
                                 "                    bằng bài toán bổ trợ.\n\n","note")
            for line in self._format_aux_phase1_problem(engine):
                self.output.insert(tk.END, line + "\n", "note")
            self.output.insert(tk.END, "\n")
            self._render_trace("Pha 1",report.dantzig)
            # Nếu đang chọn giải Dantzig mà xoay vòng thì dừng luôn
            if report.dantzig.status == "cycle":
                self.output.insert(tk.END, "\nKẾT LUẬN\n", "h2")
                self.output.insert(tk.END, "  Bài toán không thể giải bằng Dantzig do xoay vòng.\n", "warn")
                self.output.insert(tk.END, "  Từ vựng đã quay lại trạng thái trước đó sau các bước, thuật toán lặp vô hạn.\n", "note")
                self.output.insert(tk.END, "  Hãy chuyển sang phương pháp Bland để giải quyết.\n", "warn")
                return
            self.output.insert(tk.END,"\n")
            if report.status=="infeasible":
                self.output.insert(tk.END,"  Tất cả hệ số trên hàm mục tiêu đều ≥ 0 → từ vựng hiện tại là tối ưu.\n","note")
                self.output.insert(tk.END,"\nKẾT LUẬN\n","h2")
                inf_msg = "z_max = −∞" if is_max else "z_min = +∞"
                self.output.insert(tk.END,
                    f"  Vô nghiệm: sau Pha 1, x0 vẫn còn trong cơ sở (x0 > 0)\n"
                    f"  → miền chấp nhận được rỗng → {inf_msg}.\n","warn")
                return
            if report.phase2_trace is not None:
                # In bước chuyển sang pha 2
                snap1 = report.dantzig.final_snapshot
                if snap1:
                    self.output.insert(tk.END,
"\n───────────────────────────────────\n"
                        " Chuyển sang Pha 2\n"
"───────────────────────────────────\n","h2")
                    for line in self._format_phase2_transition_aux(engine, snap1):
                        self.output.insert(tk.END, line + "\n", "note")
                    self.output.insert(tk.END, "\n")
                self.output.insert(tk.END,
"\n───────────────────────────────────\n"
                    " Pha 2: Giải bài toán gốc\n"
"───────────────────────────────────\n","h2")
                # Nếu Pha 2 Dantzig cycle và đã fallback sang Bland: phase1_bland chứa trace Dantzig (cycle)
                phase2_dantzig_cycle = (
                    report.phase1_bland is not None
                    and report.phase1_bland.cycle_detected
                    and report.used_method == "bland"
                )
                if phase2_dantzig_cycle:
                    self._render_trace("Pha 2 - Dantzig", report.phase1_bland)
                    self.output.insert(tk.END, "\n  ⚠️ Dantzig xoay vòng ở Pha 2 → chuyển sang Bland.\n", "warn")
                    self.output.insert(tk.END,
"\n───────────────────────────────────\n"
                        " Pha 2 (Bland): Giải bài toán gốc\n"
"───────────────────────────────────\n","h2")
                self._render_trace("Pha 2", report.phase2_trace)
                if report.phase2_trace.status == "cycle":
                    self.output.insert(tk.END, "\nKẾT LUẬN\n", "h2")
                    self.output.insert(tk.END, "  ⚠️ Bài toán không thể giải bằng Dantzig do xoay vòng ở Pha 2!\n", "warn")
                    self.output.insert(tk.END, "  Hàm mục tiêu rơi vào vòng lặp vô hạn giữa các từ vựng suy biến.\n", "note")
                    self.output.insert(tk.END, "  👉 Hãy chuyển sang phương pháp Bland hoặc Hai pha để giải quyết.\n", "warn")
                    return
            else:
                inf_msg = "z_max = −∞" if is_max else "z_min = +∞"
                self.output.insert(tk.END,f"\nKẾT LUẬN\n  Vô nghiệm → {inf_msg}.\n","warn"); return
        else:
            # ── Không cần Pha 1 ─────────────────────────────────────────
            self.output.insert(tk.END,
                "\n───────────────────────────────────\n"
                " Không cần Pha 1\n"
"───────────────────────────────────\n","h2")
            self.output.insert(tk.END,
                "  Tất cả b_i ≥ 0 → từ vựng xuất phát là chấp nhận được,\n"
                "                   không cần thực hiện Pha 1.\n\n")
            self.output.insert(tk.END,
                "───────────────────────────────────\n"
                " Giải bài toán\n"
"───────────────────────────────────\n","h2")
            self._render_trace("Giải bài toán",report.dantzig)
            if report.dantzig.status == "cycle":
                self.output.insert(tk.END, "\nKẾT LUẬN\n", "h2")
                self.output.insert(tk.END, "  ⚠️ Bài toán không thể giải bằng Dantzig do xoay vòng!\n", "warn")
                self.output.insert(tk.END, "  Từ vựng đã quay lại trạng thái trước đó sau các bước suy biến, thuật toán lặp vô hạn.\n", "note")
                self.output.insert(tk.END, "  👉 Hãy chuyển sang phương pháp Bland hoặc Hai pha để giải quyết.\n", "warn")
                return

        final=self._get_final_snapshot(report)

        # Không giới nội
        if report.status in ("unbounded",):
            self.output.insert(tk.END,"\nKẾT LUẬN\n","h2")
            if is_max:
                self.output.insert(tk.END,"  Bài toán không giới nội: z_max = +∞.\n","warn")
            else:
                self.output.insert(tk.END,"  Bài toán không giới nội: z_min = −∞.\n","warn")
            return
        if report.status=="cycle":
            self.output.insert(tk.END,"\nKẾT LUẬN\n  ⚠️ Bài toán không thể giải bằng phương pháp này do xoay vòng.\n","warn"); return

        obj_std=report.objective_std or Fraction(0)
        obj_orig=report.objective_orig or Fraction(0)

        if final and self._has_multiple_optimal(engine, final, report):
            for line in self._format_multiple_optimal_family(engine,final,report):
                self.output.insert(tk.END,line+"\n","warn" if "vô số" in line else "note")
            self.output.insert(tk.END,"\nKẾT LUẬN\n","h2")
            self.output.insert(tk.END,"  Bài toán có vô số nghiệm tối ưu.\n","note")
            for line in self._format_multiple_optimal_conclusion(engine,final,report):
                self.output.insert(tk.END,line+"\n","note")
            if is_max:
                self.output.insert(tk.END,
                    f"  Giá trị tối ưu là: z* = max Z = −(min Z') = −({fmt_num(obj_std,mode)}) = {fmt_num(obj_orig,mode)}\n","note")
            else:
                self.output.insert(tk.END,
                    f"  Giá trị tối ưu là: z* = {fmt_num(obj_orig,mode)}\n","note")
        else:
            self.output.insert(tk.END,"\nKẾT LUẬN\n","h2")
            method_lbl = "Dantzig" if report.used_method == "dantzig" else "Bland"
            if is_max:
                self.output.insert(tk.END,
                    f"  Tối ưu ({method_lbl}).\n"
                    f"  Giá trị tối ưu là: z* = max Z = −(min Z') = −({fmt_num(obj_std,mode)}) = {fmt_num(obj_orig,mode)}\n",
                    "note")
            else:
                self.output.insert(tk.END,
                    f"  Tối ưu ({method_lbl}).\n"
                    f"  Giá trị tối ưu là: z* = {fmt_num(obj_orig,mode)}\n",
                    "note")
            n_orig = len(engine.problem.var_signs)
            sol_strs = [fmt_num(report.solution_orig.get(i, Fraction(0)), mode) for i in range(n_orig)]
            val_w = max(len(s) for s in sol_strs)
            var_w = max(len(f"x{i+1}") for i in range(n_orig))
            self.output.insert(tk.END,"  Nghiệm tối ưu là:\n","note")
            for i, val_s in enumerate(sol_strs):
                nm = f"x{i+1}".ljust(var_w)
                val = val_s.rjust(val_w)
                self.output.insert(tk.END, f"    {nm} = {val}\n", "note")
        d=(report.dantzig.degenerate_steps or 0)
        if d: self.output.insert(tk.END,f"  Có {d} bước suy biến.\n","warn")

    def _has_aux_phase1(self, engine):
        # Trả về True nếu engine đã thực hiện pha 1 với biến phụ x0
        # (xảy ra khi có ít nhất một b_i âm sau khi đưa về dạng chuẩn).
        return bool(getattr(engine,"need_aux_phase1",False))

    def _format_aux_phase1_problem(self, engine):
        """In bài toán bổ trợ x0 theo dạng đề bài cụ thể."""
        mode = self.data_mode
        lines = []
        lines.append("  Bài toán bổ trợ:")
        lines.append("")
        lines.append("    min x0")
        lines.append("    {")
        # Từ initial_rows: w_k = rhs_k + Σ row_kj * x_j + x0
        # Ràng buộc gốc: Σ(-row_kj)*x_j - x0 ≤ rhs_k
        for i, (b, row) in enumerate(zip(engine.initial_rhs, engine.initial_rows)):
            lhs_parts = []
            for j in range(len(engine.std_names)):
                a = -row.get(j, Fraction(0))  # hệ số gốc
                if a == 0:
                    continue
                nm = engine.all_names[j]
                abs_a = abs(a)
                coef_str = fmt_num(abs_a, mode) if abs_a != 1 else ""
                sign = "+" if a > 0 else "-"
                lhs_parts.append(f"{sign} {coef_str}{nm}")
            lhs_str = " ".join(lhs_parts).lstrip("+ ").strip() or "0"
            rhs_str = fmt_num(b, mode)
            lines.append(f"      {lhs_str} - x0 ≤ {rhs_str}")
        # Ràng buộc không âm
        var_list = ["x0"] + list(engine.std_names)
        lines.append(f"      {', '.join(var_list)} ≥ 0")
        lines.append("    }")
        lines.append("")
        lines.append("  (Giải pha 1: đưa x0 vào cơ sở tại hàng có b_i âm nhất,")
        lines.append("   sau đó tối thiểu hóa x0 bằng đơn hình chuẩn)")
        return lines

    def _format_phase2_transition_aux(self, engine, snap1):
        """In chi tiết bước chuyển từ pha 1 bổ trợ sang pha 2."""
        mode = self.data_mode
        lines = []
        aux_idx = getattr(engine, "phase1_aux_var_index", None)

        lines.append("  Từ vựng hiện là tối ưu: cho x0 = 0, khi đó ta có:")
        lines.append("")

        # In từng ràng buộc mới (sau khi loại x0)
        for i, (b_val, bas_idx) in enumerate(zip(snap1.rhs, snap1.basis)):
            row = snap1.rows[i]
            b_name = snap1.all_names[bas_idx]
            terms_str = fmt_num(b_val, mode)
            extras = []
            for j, a in sorted(row.items()):
                if aux_idx is not None and j == aux_idx:
                    continue
                if a == 0 or j >= len(snap1.all_names):
                    continue
                nm = snap1.all_names[j]
                abs_c = abs(a)
                coef_str = fmt_num(abs_c, mode) if abs_c != 1 else ""
                sign = "+" if a > 0 else "-"
                extras.append(f"{sign} {coef_str}{nm}")
            expr = terms_str + (" " + " ".join(extras) if extras else "")
            lines.append(f"    {b_name} = {expr.lstrip('+ ')}")

        lines.append("")

        # Hàm mục tiêu gốc (trước thay)
        is_max = engine.problem.objective_sense == "max"
        obj_sense_str = "min Z'" if is_max else "min Z"

        obj_parts = []
        for j, c in enumerate(engine.std_obj_coeffs):
            if c == 0 or j >= len(engine.all_names):
                continue
            nm = engine.all_names[j]
            abs_c = abs(c)
            coef_str = fmt_num(abs_c, mode) if abs_c != 1 else ""
            sign = "+" if c > 0 else "-"
            obj_parts.append(f"{sign} {coef_str}{nm}")
        obj_expr_raw = " ".join(obj_parts).lstrip("+ ").strip() or "0"

        # Khai triển hàm mục tiêu: thay các biến cơ sở từ snap1 vào
        bp = {b: i for i, b in enumerate(snap1.basis)}
        expanded_const = Fraction(0)
        expanded_terms: Dict[int, Fraction] = {}
        for j, c in enumerate(engine.std_obj_coeffs):
            if c == 0:
                continue
            if j in bp:
                ri = bp[j]
                expanded_const += c * snap1.rhs[ri]
                for k, a in snap1.rows[ri].items():
                    if aux_idx is not None and k == aux_idx:
                        continue
                    expanded_terms[k] = expanded_terms.get(k, Fraction(0)) + c * a
            else:
                if aux_idx is not None and j == aux_idx:
                    continue
                expanded_terms[j] = expanded_terms.get(j, Fraction(0)) + c

        exp_parts = []
        if expanded_const != 0:
            exp_parts.append(fmt_num(expanded_const, mode))
        first_term = True
        for j in sorted(expanded_terms.keys()):
            c = expanded_terms.get(j, Fraction(0))
            if c == 0 or j >= len(snap1.all_names):
                continue
            if aux_idx is not None and j == aux_idx:
                continue
            nm = snap1.all_names[j]
            abs_c = abs(c)
            coef_str = fmt_num(abs_c, mode) if abs_c != 1 else ""
            if not exp_parts and first_term:
                prefix = "" if c > 0 else "-"
                exp_parts.append(f"{prefix}{coef_str}{nm}")
            else:
                sign = "+" if c > 0 else "-"
                exp_parts.append(f"{sign} {coef_str}{nm}")
            first_term = False
        expanded_expr = " ".join(exp_parts).strip() or "0"

        lines.append(f"  Hàm mục tiêu mới: {obj_sense_str} = {obj_expr_raw} = {expanded_expr}")
        return lines


    def run_solver(self):
        try:
            prob = self._collect_problem()
            
            engine_d = SimplexEngine(prob)
            engine_b = SimplexEngine(prob)

            rhs = engine_d.initial_rhs
            has_negative = any(b < 0 for b in rhs)
            has_zero = any(b == 0 for b in rhs)

            self.status_var.set("Đang chạy đa luồng giải bài toán...")
            self.update_idletasks()
            
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future_d = executor.submit(engine_d.solve_full, "dantzig")
                future_b = executor.submit(engine_b.solve_full, "bland")
                report_d = future_d.result()
                report_b = future_b.result()

            self.last_problem = prob
            self.last_report_d = report_d
            self.last_report_b = report_b

            if has_negative:
                priority = "haipha"
            elif has_zero:
                priority = "bland"
            else:
                priority = "dantzig"

            def format_label(base_name, key, is_disabled):
                if is_disabled:
                    return base_name
                if priority == key:
                    return f"{base_name} (đề xuất)"
                return base_name
            
            if has_negative:
                state_d, lbl_d = tk.DISABLED, format_label("Dantzig", "dantzig", True)
                state_b, lbl_b = tk.DISABLED, format_label("Bland", "bland", True)
                state_hp, lbl_hp = tk.NORMAL, format_label("Hai Pha", "haipha", False)
                reason_th = "Thuật toán đề xuất: Hai Pha (vì tồn tại b_i < 0, bắt buộc dùng bài toán bổ trợ)."
                default_view = "haipha"
                
            elif has_zero:
                state_d, lbl_d = tk.NORMAL, format_label("Dantzig", "dantzig", False)
                state_b, lbl_b = tk.NORMAL, format_label("Bland", "bland", False)
                state_hp, lbl_hp = tk.DISABLED, format_label("Hai Pha", "haipha", True)
                reason_th = "Thuật toán đề xuất: Bland (vì tồn tại b_i = 0, dễ bị xoay vòng)."
                default_view = "bland"
                
            else:
                state_d, lbl_d = tk.NORMAL, format_label("Dantzig", "dantzig", False)
                state_b, lbl_b = tk.NORMAL, format_label("Bland", "bland", False)
                state_hp, lbl_hp = tk.DISABLED, format_label("Hai Pha", "haipha", True)
                reason_th = "Thuật toán đề xuất: Dantzig (vì tất cả b_i > 0)."
                default_view = "dantzig"

            self.lbl_theory.config(text=reason_th)
            if hasattr(self, 'lbl_optimal'):
                self.lbl_optimal.config(text="")

            for widget in self.comparison_frame.winfo_children():
                widget.destroy()

            ttk.Radiobutton(self.comparison_frame, text=lbl_d, variable=self.selected_method_view, value="dantzig", state=state_d).pack(anchor="w", pady=2)
            ttk.Radiobutton(self.comparison_frame, text=lbl_b, variable=self.selected_method_view, value="bland", state=state_b).pack(anchor="w", pady=2)
            ttk.Radiobutton(self.comparison_frame, text=lbl_hp, variable=self.selected_method_view, value="haipha", state=state_hp).pack(anchor="w", pady=2)

            self.selected_method_view.set(default_view)

            btn_view = ttk.Button(self.comparison_frame, text="Hiển thị lời giải phương pháp đã chọn", style="Accent.TButton", 
                                  command=lambda: self._view_selected_solution(report_d, report_b))
            btn_view.pack(anchor="w", pady=(10, 0))

            self.comparison_frame.grid()

            self._view_selected_solution(report_d, report_b)
            self._set_solution_available(True)
            self._update_viz_btn_state()
            self.status_var.set("Đã giải xong (Đa luồng).")

        except Exception as exc:
            self.last_report = None
            self.last_report_d = None
            self.last_report_b = None
            self._set_solution_available(False)
            messagebox.showerror("Lỗi nhập liệu / giải thuật", str(exc))
            self.status_var.set("Có lỗi xảy ra. Kiểm tra lại dữ liệu nhập.")
            self.output.config(state=tk.NORMAL)
            self.output.delete("1.0", tk.END)
            self.output.config(state=tk.DISABLED)

    def _view_selected_solution(self, report_d, report_b):
        sel = self.selected_method_view.get()
        self.output.config(state=tk.NORMAL)
        
        if sel == "bland":
            self.last_report = report_b
            self._render_result(report_b)
        else:
            self.last_report = report_d
            self._render_result(report_d)
            
        self.output.config(state=tk.DISABLED)