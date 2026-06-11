"""simplex_animator.py

Module cung cấp lớp `SimplexAnimator` – cửa sổ popup Tkinter dùng để phát lại
(animate) từng bước giải của thuật toán Simplex dựa trên đối tượng `SolveTrace`.

Sử dụng:
    from simplex_animator import SimplexAnimator
    animator = SimplexAnimator(parent, trace=solve_trace, data_mode="Phân số")
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import List, Optional, Tuple, NamedTuple
from fractions import Fraction

from models import SolveTrace, Snapshot, PivotStep
from utils import fmt_num


# ──────────────────────────────────────────────────────────────────────────────
# Màu sắc
# ──────────────────────────────────────────────────────────────────────────────
C_HEADER_BG      = "#1E3A5F"   # xanh dương đậm  – thanh tiêu đề
C_HEADER_FG      = "#FFFFFF"   # chữ trắng

C_TH_BG          = "#E2E8F0"   # xám nhạt        – header row / label col
C_TH_FG          = "#1E293B"
C_OBJ_BG         = "#F0FDF4"   # xanh lá nhạt    – hàng hàm mục tiêu
C_OBJ_FG         = "#166534"

C_PIVOT_COL_BG   = "#FEF9C3"   # vàng nhạt       – cột biến vào
C_PIVOT_ROW_BG   = "#E0F2FE"   # xanh lam nhạt   – hàng biến ra
C_PIVOT_CELL_BG  = "#BFDBFE"   # xanh lam đậm    – ô giao (phần tử xoay)
C_PIVOT_CELL_FG  = "#C2410C"   # cam đậm          – chữ ô pivot

C_CELL_BG        = "#FFFFFF"   # trắng            – ô bình thường
C_CELL_FG        = "#1E293B"

C_BTN_ACTIVE     = "#1E3A5F"
C_BTN_FG         = "#FFFFFF"
C_BTN_DISABLED   = "#94A3B8"

C_WIN_BG         = "#F8FAFC"   # nền cửa sổ


# ──────────────────────────────────────────────────────────────────────────────
# Frame data structure
# ──────────────────────────────────────────────────────────────────────────────
class AnimFrame(NamedTuple):
    """Một 'khung hình' trong chuỗi animation."""
    snapshot: Snapshot
    entering_col_name: Optional[str]   # tên biến vào (None nếu không có pivot)
    leaving_row_idx: Optional[int]     # chỉ số hàng biến ra  (None nếu không có pivot)
    description: str                   # câu mô tả hiển thị trên header


# ──────────────────────────────────────────────────────────────────────────────
# Helper: xây dựng danh sách frames từ SolveTrace
# ──────────────────────────────────────────────────────────────────────────────
def _build_frames_single(trace: SolveTrace, phase_label: str = "") -> List[AnimFrame]:
    """Build danh sách AnimFrame cho một trace.

    Parameters
    ----------
    phase_label : str
        Nhãn pha hiển thị trong description, vd ``"Pha 1"``, ``"Pha 2"``.
        Truyền ``""`` (mặc định) để không hiện nhãn pha (bài toán 1 pha).
    """
    frames: List[AnimFrame] = []

    steps: List[PivotStep] = trace.steps or []

    for step in steps:
        snapshot = step.before
        method_label = "Dantzig" if step.method == "dantzig" else "Bland"
        step_label   = f"Bước {step.iteration}"
        phase_part   = f" [{phase_label}]" if phase_label else ""

        if step.entering is not None and snapshot is not None:
            enter_name = (
                snapshot.all_names[step.entering]
                if step.entering < len(snapshot.all_names)
                else f"var{step.entering}"
            )
        else:
            enter_name = None

        if step.leaving_var is not None and snapshot is not None:
            leave_name = (
                snapshot.all_names[step.leaving_var]
                if step.leaving_var < len(snapshot.all_names)
                else f"var{step.leaving_var}"
            )
        else:
            leave_name = None

        leaving_row = step.leaving_row  # có thể None nếu unbounded

        if enter_name and leave_name:
            desc = (
                f"{step_label} ({method_label}){phase_part}"
                f": Biến vào [{enter_name}], Biến ra [{leave_name}]"
            )
        elif enter_name:
            desc = (
                f"{step_label} ({method_label}){phase_part}"
                f": Biến vào [{enter_name}] – Không giới nội (Unbounded)"
            )
        else:
            desc = f"{step_label} – Tối ưu"

        frames.append(AnimFrame(
            snapshot=snapshot,
            entering_col_name=enter_name,
            leaving_row_idx=leaving_row,
            description=desc,
        ))

    # Frame cuối: bảng từ vựng kết thúc pha
    if trace.final_snapshot is not None:
        status_map = {
            "optimal"    : "Tối ưu",
            "unbounded"  : "Không giới nội",
            "infeasible" : "Vô nghiệm",
            "cycle"      : "Phát hiện vòng lặp",
        }
        status_label = status_map.get(trace.status, trace.status)
        phase_suffix = f" ({phase_label})" if phase_label else ""
        final_desc = f"Kết quả{phase_suffix}: {status_label}"
        frames.append(AnimFrame(
            snapshot=trace.final_snapshot,
            entering_col_name=None,
            leaving_row_idx=None,
            description=final_desc,
        ))

    return frames


def _build_frames_multi(traces: List[Tuple[str, SolveTrace]]) -> List[AnimFrame]:
    """Ghép frames từ nhiều trace (nhiều pha) thành một danh sách duy nhất.

    Parameters
    ----------
    traces : list of (phase_label, SolveTrace)
        Danh sách các pha theo thứ tự. ``phase_label`` là nhãn hiển thị,
        vd ``"Pha 1"``, ``"Pha 2"``. Truyền ``""`` cho bài toán 1 pha.
    """
    all_frames: List[AnimFrame] = []
    for phase_label, trace in traces:
        all_frames.extend(_build_frames_single(trace, phase_label=phase_label))
    return all_frames


# ──────────────────────────────────────────────────────────────────────────────
# SimplexAnimator
# ──────────────────────────────────────────────────────────────────────────────
class SimplexAnimator(tk.Toplevel):
    """Cửa sổ popup phát lại từng bước giải Simplex.

    Parameters
    ----------
    master : tk.Widget
        Widget cha.
    trace : SolveTrace
        Đối tượng trace trả về từ SimplexEngine (một pha).
    data_mode : str
        "Phân số" hoặc "Số thập phân" – dùng để format số.
    title : str
        Tiêu đề cửa sổ (tuỳ chọn).
    """

    def __init__(
        self,
        master: tk.Widget,
        traces: List[Tuple[str, SolveTrace]],
        data_mode: str = "Phân số",
        title: str = "Phát lại từ vựng các bước",
    ):
        """
        Parameters
        ----------
        traces : list of (phase_label, SolveTrace)
            Mỗi phần tử là một pha. Truyền ``[("", trace)]`` cho bài toán 1 pha.
            Truyền ``[("Pha 1", t1), ("Pha 2", t2)]`` cho bài toán 2 pha.
        """
        super().__init__(master)
        self.title(title)
        self.data_mode = data_mode
        self.resizable(True, True)
        self.minsize(640, 420)
        self.configure(bg=C_WIN_BG)

        # ── State ────────────────────────────────────────────────────────────
        self.frames: List[AnimFrame] = _build_frames_multi(traces)
        self.current_idx: int = 0

        if not self.frames:
            tk.Label(
                self, text="Không có bước nào để hiển thị.",
                bg=C_WIN_BG, fg="#64748B", font=("Segoe UI", 13)
            ).pack(expand=True)
            return

        # ── Layout ───────────────────────────────────────────────────────────
        self._build_ui()
        self._render_frame()

        # Căn giữa cửa sổ
        self.update_idletasks()
        self._center_window()
        self.grab_set()

    # ─────────────────────────────────────────────────────────────────────────
    # UI construction
    # ─────────────────────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        """Tạo 3 khu vực: header / matrix / controls."""

        # 1. Header label ─────────────────────────────────────────────────────
        self._header_var = tk.StringVar()
        self._header_lbl = tk.Label(
            self,
            textvariable=self._header_var,
            bg=C_HEADER_BG,
            fg=C_HEADER_FG,
            font=("Segoe UI", 12, "bold"),
            anchor="w",
            padx=16,
            pady=10,
            wraplength=900,
            justify="left",
        )
        self._header_lbl.pack(side="top", fill="x")

        # 2. Matrix frame (scrollable) ────────────────────────────────────────
        matrix_outer = tk.Frame(self, bg=C_WIN_BG)
        matrix_outer.pack(side="top", fill="both", expand=True, padx=12, pady=(10, 4))

        # Canvas + scrollbars để hỗ trợ bảng lớn
        self._canvas = tk.Canvas(matrix_outer, bg=C_WIN_BG, highlightthickness=0)
        v_scroll = ttk.Scrollbar(matrix_outer, orient="vertical",   command=self._canvas.yview)
        h_scroll = ttk.Scrollbar(matrix_outer, orient="horizontal", command=self._canvas.xview)
        self._canvas.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        h_scroll.pack(side="bottom", fill="x")
        v_scroll.pack(side="right",  fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        # Frame bên trong canvas – đây là nơi vẽ lưới Label
        self._matrix_frame = tk.Frame(self._canvas, bg=C_WIN_BG)
        self._canvas_window = self._canvas.create_window(
            (0, 0), window=self._matrix_frame, anchor="nw"
        )
        self._matrix_frame.bind("<Configure>", self._on_matrix_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        # Mouse-wheel scroll (bind to canvas widget, not globally)
        self._canvas.bind("<MouseWheel>",       self._on_mousewheel)
        self._canvas.bind("<Shift-MouseWheel>", self._on_h_mousewheel)
        # Also bind to the inner frame so scrolling works anywhere inside
        self._matrix_frame.bind("<MouseWheel>",       self._on_mousewheel)
        self._matrix_frame.bind("<Shift-MouseWheel>", self._on_h_mousewheel)
        self.bind("<MouseWheel>",       self._on_mousewheel)
        self.bind("<Shift-MouseWheel>", self._on_h_mousewheel)

        # 3. Media controls ───────────────────────────────────────────────────
        ctrl_frame = tk.Frame(self, bg=C_WIN_BG)
        ctrl_frame.pack(side="bottom", fill="x", padx=12, pady=8)

        btn_cfg = dict(
            font=("Segoe UI", 13),
            relief="flat",
            cursor="hand2",
            padx=14, pady=6,
            bd=0,
        )

        self._btn_first = tk.Button(
            ctrl_frame, text="⏮  Về đầu",
            command=self._go_first, **btn_cfg
        )
        self._btn_prev = tk.Button(
            ctrl_frame, text="◀  Lùi lại",
            command=self._go_prev, **btn_cfg
        )
        self._btn_next = tk.Button(
            ctrl_frame, text="Tiến lên  ▶",
            command=self._go_next, **btn_cfg
        )
        self._btn_last = tk.Button(
            ctrl_frame, text="Đến cuối  ⏭",
            command=self._go_last, **btn_cfg
        )

        # Đặt các nút cân đối ở giữa
        ctrl_frame.columnconfigure((0, 1, 2, 3, 4, 5), weight=1)
        self._btn_first.grid(row=0, column=1, padx=4)
        self._btn_prev.grid (row=0, column=2, padx=4)
        self._btn_next.grid (row=0, column=3, padx=4)
        self._btn_last.grid (row=0, column=4, padx=4)

        # Nút đóng cửa sổ
        tk.Button(
            ctrl_frame, text="✕  Đóng",
            command=self.destroy,
            font=("Segoe UI", 11), relief="flat", cursor="hand2",
            bg="#EF4444", fg="white", padx=12, pady=6, bd=0,
        ).grid(row=0, column=5, padx=(20, 4), sticky="e")

    # ─────────────────────────────────────────────────────────────────────────
    # Scrollbar / canvas helpers
    # ─────────────────────────────────────────────────────────────────────────
    def _on_matrix_configure(self, event: tk.Event) -> None:
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event) -> None:
        # Không ép chiều rộng nếu bảng rộng hơn canvas
        canvas_w = event.width
        frame_w  = self._matrix_frame.winfo_reqwidth()
        self._canvas.itemconfigure(
            self._canvas_window,
            width=max(canvas_w, frame_w)
        )

    def _on_mousewheel(self, event: tk.Event) -> None:
        try:
            if self._canvas.winfo_exists():
                self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass

    def _on_h_mousewheel(self, event: tk.Event) -> None:
        try:
            if self._canvas.winfo_exists():
                self._canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────────────
    # Navigation
    # ─────────────────────────────────────────────────────────────────────────
    def _go_first(self) -> None:
        self.current_idx = 0
        self._render_frame()

    def _go_prev(self) -> None:
        if self.current_idx > 0:
            self.current_idx -= 1
            self._render_frame()

    def _go_next(self) -> None:
        if self.current_idx < len(self.frames) - 1:
            self.current_idx += 1
            self._render_frame()

    def _go_last(self) -> None:
        self.current_idx = len(self.frames) - 1
        self._render_frame()

    # ─────────────────────────────────────────────────────────────────────────
    # Core render
    # ─────────────────────────────────────────────────────────────────────────
    def _render_frame(self) -> None:
        """Xóa và vẽ lại toàn bộ lưới Label cho khung hiện tại."""
        frame = self.frames[self.current_idx]
        n = len(self.frames)
        idx = self.current_idx

        # ── Header text ───────────────────────────────────────────────────────
        self._header_var.set(f"  {idx + 1}/{n}:  {frame.description}")

        # ── Cập nhật trạng thái nút ──────────────────────────────────────────
        self._update_buttons(idx, n)

        # ── Xóa lưới cũ ──────────────────────────────────────────────────────
        for widget in self._matrix_frame.winfo_children():
            widget.destroy()

        # ── Vẽ bảng mới ──────────────────────────────────────────────────────
        snapshot = frame.snapshot
        if snapshot is None:
            tk.Label(
                self._matrix_frame,
                text="(Không có dữ liệu bảng từ vựng)",
                bg=C_WIN_BG, fg="#94A3B8", font=("Segoe UI", 11, "italic"),
                padx=10, pady=10,
            ).grid(row=0, column=0)
            return

        self._draw_snapshot(snapshot, frame.entering_col_name, frame.leaving_row_idx)

    def _update_buttons(self, idx: int, n: int) -> None:
        """Enable/disable các nút điều hướng theo vị trí hiện tại."""
        at_start = (idx == 0)
        at_end   = (idx == n - 1)

        def _apply(btn: tk.Button, disabled: bool) -> None:
            if disabled:
                btn.configure(
                    state="disabled",
                    bg="#E2E8F0",
                    fg=C_BTN_DISABLED,
                    activebackground="#E2E8F0",
                )
            else:
                btn.configure(
                    state="normal",
                    bg=C_BTN_ACTIVE,
                    fg=C_BTN_FG,
                    activebackground="#2D5A9B",
                    activeforeground="white",
                )

        _apply(self._btn_first, at_start)
        _apply(self._btn_prev,  at_start)
        _apply(self._btn_next,  at_end)
        _apply(self._btn_last,  at_end)

    # ─────────────────────────────────────────────────────────────────────────
    # Vẽ Snapshot thành lưới Label
    # ─────────────────────────────────────────────────────────────────────────
    def _draw_snapshot(
        self,
        snap: Snapshot,
        entering_col_name: Optional[str],
        leaving_row_idx: Optional[int],
    ) -> None:
        """Vẽ bảng từ vựng Simplex dưới dạng lưới tk.Label.

        Cấu trúc bảng:
            col 0       : Nhãn hàng cơ sở (Cơ sở)
            col 1       : RHS của hàng đó
            col 2+      : Hệ số các biến phi cơ sở (all_names theo thứ tự)
            Hàng 0      : Header – tên các cột
            Hàng 1..m   : Các hàng ràng buộc (biến cơ sở)
            Hàng m+1    : Hàng hàm mục tiêu (z / w / δ)
        """
        all_names: List[str] = snap.all_names
        basis:     List[int] = snap.basis
        m = len(basis)

        # Xác định cột nào là "biến vào" (để tô vàng)
        entering_col_idx: Optional[int] = None
        if entering_col_name is not None:
            try:
                entering_col_idx = all_names.index(entering_col_name)
            except ValueError:
                entering_col_idx = None

        # Xác định tập biến phi cơ sở xuất hiện trong bảng
        basis_set = set(basis)

        # Tập chỉ số cần ẩn khỏi cột:
        #   - Biến cơ sở: luôn ẩn (cột chỉ toàn 0/1 theo identity, không mang thông tin)
        #   - x0: ẩn ở pha 2 (đã loại sau pha 1); engine đặt tên "x0" nhất quán
        hide_set: set = set(basis_set)
        if snap.phase == 2 and "x0" in all_names:
            hide_set.add(all_names.index("x0"))

        # Cột hiển thị: chỉ biến phi cơ sở, không có x0 ở pha 2
        display_col_indices: List[int] = [
            j for j in range(len(all_names)) if j not in hide_set
        ]

        # Helper: lấy hệ số hàng i tại cột j
        def row_coeff(row_i: int, col_j: int) -> Fraction:
            if col_j in basis_set:
                # Biến cơ sở: hệ số 1 nếu đúng hàng, 0 nếu hàng khác
                return Fraction(1) if basis[row_i] == col_j else Fraction(0)
            return snap.rows[row_i].get(col_j, Fraction(0))

        def obj_coeff(col_j: int) -> Fraction:
            if col_j in basis_set:
                return Fraction(0)
            return snap.obj.get(col_j, Fraction(0))

        def fmt(v: Fraction) -> str:
            return fmt_num(v, self.data_mode)

        cell_font        = ("Consolas", 10)
        header_font      = ("Segoe UI", 10, "bold")
        basis_label_font = ("Segoe UI", 10, "bold")

        PAD_X, PAD_Y = 10, 5

        # ── Hàng 0: Header ───────────────────────────────────────────────────
        # col 0 = "Cơ sở", col 1 = "hệ số tự do", col 2+ = tên biến
        headers = ["Cơ sở", "hệ số tự do"] + [all_names[j] for j in display_col_indices]
        for gc, text in enumerate(headers):
            is_pivot_col = (
                gc >= 2
                and display_col_indices[gc - 2] == entering_col_idx
            )
            bg = C_PIVOT_COL_BG if is_pivot_col else C_TH_BG
            fg = C_TH_FG
            lbl = tk.Label(
                self._matrix_frame,
                text=text,
                bg=bg, fg=fg,
                font=header_font,
                relief="flat",
                borderwidth=1,
                padx=PAD_X, pady=PAD_Y,
                anchor="center",
            )
            lbl.grid(row=0, column=gc, sticky="nsew", padx=1, pady=1)

        # ── Hàng 1: Hàm mục tiêu (đặt trên cùng, trước các ràng buộc) ────────
        obj_label = snap.objective_label if snap.objective_label else "z"

        # col 0: nhãn hàm mục tiêu
        tk.Label(
            self._matrix_frame,
            text=obj_label,
            bg=C_OBJ_BG, fg=C_OBJ_FG,
            font=basis_label_font,
            relief="flat",
            padx=PAD_X, pady=PAD_Y,
            anchor="center",
        ).grid(row=1, column=0, sticky="nsew", padx=1, pady=1)

        # col 1: hằng số hàm mục tiêu (obj_const)
        tk.Label(
            self._matrix_frame,
            text=fmt(snap.obj_const),
            bg=C_OBJ_BG, fg=C_OBJ_FG,
            font=cell_font,
            relief="flat",
            padx=PAD_X, pady=PAD_Y,
            anchor="e",
        ).grid(row=1, column=1, sticky="nsew", padx=1, pady=1)

        # col 2+: hệ số mục tiêu
        for gc_off, cj in enumerate(display_col_indices):
            gc = gc_off + 2
            coeff = obj_coeff(cj)
            is_pivot_col_cell = (entering_col_idx is not None and cj == entering_col_idx)

            bg = C_PIVOT_COL_BG if is_pivot_col_cell else C_OBJ_BG
            fg = C_OBJ_FG
            font = cell_font

            tk.Label(
                self._matrix_frame,
                text=fmt(coeff),
                bg=bg, fg=fg,
                font=font,
                relief="flat",
                padx=PAD_X, pady=PAD_Y,
                anchor="e",
            ).grid(row=1, column=gc, sticky="nsew", padx=1, pady=1)

        # ── Hàng 2..m+1: Ràng buộc ───────────────────────────────────────────
        for ri in range(m):
            is_pivot_row = (leaving_row_idx is not None and ri == leaving_row_idx)
            basis_var_idx = basis[ri]
            basis_name    = (
                all_names[basis_var_idx]
                if basis_var_idx < len(all_names)
                else f"var{basis_var_idx}"
            )

            gr = ri + 2  # grid row: 0=header, 1=objective, 2..m+1=constraints

            # col 0: nhãn biến cơ sở
            row_bg = C_PIVOT_ROW_BG if is_pivot_row else C_CELL_BG
            tk.Label(
                self._matrix_frame,
                text=basis_name,
                bg=C_PIVOT_ROW_BG if is_pivot_row else C_TH_BG,
                fg=C_TH_FG,
                font=basis_label_font,
                relief="flat",
                padx=PAD_X, pady=PAD_Y,
                anchor="center",
            ).grid(row=gr, column=0, sticky="nsew", padx=1, pady=1)

            # col 1: RHS
            rhs_val = snap.rhs[ri]
            is_pivot_cell_rhs = False  # RHS không phải pivot cell
            tk.Label(
                self._matrix_frame,
                text=fmt(rhs_val),
                bg=C_PIVOT_ROW_BG if is_pivot_row else C_CELL_BG,
                fg=C_CELL_FG,
                font=cell_font,
                relief="flat",
                padx=PAD_X, pady=PAD_Y,
                anchor="e",
            ).grid(row=gr, column=1, sticky="nsew", padx=1, pady=1)

            # col 2+: hệ số
            for gc_off, cj in enumerate(display_col_indices):
                gc = gc_off + 2
                coeff = row_coeff(ri, cj)
                is_pivot_col_cell = (entering_col_idx is not None and cj == entering_col_idx)
                is_pivot_cell     = is_pivot_row and is_pivot_col_cell

                if is_pivot_cell:
                    bg = C_PIVOT_CELL_BG
                    fg = C_PIVOT_CELL_FG
                    font = (cell_font[0], cell_font[1], "bold")
                elif is_pivot_row:
                    bg = C_PIVOT_ROW_BG
                    fg = C_CELL_FG
                    font = cell_font
                elif is_pivot_col_cell:
                    bg = C_PIVOT_COL_BG
                    fg = C_CELL_FG
                    font = cell_font
                else:
                    bg = C_CELL_BG
                    fg = C_CELL_FG
                    font = cell_font

                tk.Label(
                    self._matrix_frame,
                    text=fmt(coeff),
                    bg=bg, fg=fg,
                    font=font,
                    relief="flat",
                    padx=PAD_X, pady=PAD_Y,
                    anchor="e",
                ).grid(row=gr, column=gc, sticky="nsew", padx=1, pady=1)

        # Cho phép các cột co giãn đều
        total_cols = 2 + len(display_col_indices)
        for c in range(total_cols):
            self._matrix_frame.columnconfigure(c, weight=1)

    # ─────────────────────────────────────────────────────────────────────────
    # Tiện ích
    # ─────────────────────────────────────────────────────────────────────────
    def _center_window(self) -> None:
        """Đặt cửa sổ vào giữa màn hình."""
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")