"""
html_exporter.py
~~~~~~~~~~~~~~~~
Xuất toàn bộ lời giải đơn hình thành file HTML độc lập với KaTeX render.
Không cần thư viện ngoài (chỉ dùng stdlib).

Cách dùng:
    from html_exporter import export_report_html
    path = export_report_html(report, engine, data_mode)
    webbrowser.open(f"file:///{path}")
"""

from __future__ import annotations

import os
import tempfile
from fractions import Fraction
from typing import Dict, List, Optional, Tuple

from models import PivotStep, Snapshot, SolveReport, SolveTrace
from utils import fmt_num

import html


# ---------------------------------------------------------------------------
# Helpers: chuyển Fraction → LaTeX
# ---------------------------------------------------------------------------

def _frac(x: Fraction, mode: str = "Phân số") -> str:
    """Chuyển Fraction thành chuỗi LaTeX: phân số → \\frac{a}{b}, số nguyên → a."""
    if not isinstance(x, Fraction):
        x = Fraction(x)
    if x == 0:
        return "0"
    if mode == "Số thập phân":
        return fmt_num(x, mode)
    if x.denominator == 1:
        return str(x.numerator)
    sign = "-" if x < 0 else ""
    return f"{sign}\\dfrac{{{abs(x.numerator)}}}{{{x.denominator}}}"


def _term(coeff: Fraction, var_name: str, mode: str) -> str:
    """Tạo hạng tử LaTeX: hệ số × tên biến (bỏ qua hệ số = 0)."""
    if coeff == 0:
        return ""
    abs_c = abs(coeff)
    sign = "+" if coeff > 0 else "-"
    if abs_c == 1:
        body = f"\\,{_tex_var(var_name)}"
    else:
        body = f"\\,{_frac(abs_c, mode)}{_tex_var(var_name)}"
    return f"{sign}{body}"


def _tex_var(name: str) -> str:
    """Biến x3 → x_{3},  w2 → w_{2},  z → z, v.v."""
    for prefix in ("x", "w", "y", "a", "b", "s", "δ"):
        if name.startswith(prefix) and name[len(prefix):].isdigit():
            return f"{prefix}_{{{name[len(prefix):]}}}"
    if name in ("z", "δ", "w", "z'"):
        return name
    return name


def _expr(coeffs_or_dict, names: List[str], mode: str,
          is_dict: bool = False) -> str:
    """
    Tạo biểu thức tuyến tính LaTeX.
    coeffs_or_dict: List[Fraction] | Dict[int,Fraction]
    """
    parts: List[str] = []
    if is_dict:
        items = [(j, coeffs_or_dict.get(j, Fraction(0))) for j in range(len(names))]
    else:
        items = list(enumerate(coeffs_or_dict))
    for j, c in items:
        if c == 0:
            continue
        t = _term(c, names[j], mode)
        parts.append(t)
    if not parts:
        return "0"
    s = " ".join(parts)
    # Xóa dấu "+" thừa đầu chuỗi
    return s.lstrip("+").strip()


def _rhs(val: Fraction, mode: str) -> str:
    return _frac(val, mode)


# ---------------------------------------------------------------------------
# Render bảng từ vựng (dictionary) → HTML table
# ---------------------------------------------------------------------------

def _snapshot_table(
    snapshot: Snapshot,
    mode: str,
    entering_name: Optional[str] = None,
    pivot_row: Optional[int] = None,
) -> str:
    """Tạo <table> HTML cho một snapshot (bảng từ vựng đơn hình).
    Chỉ hiển thị cột của biến phi cơ sở (biến cơ sở đã nằm ở cột nhãn, không cần cột riêng).
    """
    names = snapshot.all_names
    basis_set = set(snapshot.basis)

    # Chỉ lấy cột phi cơ sở (nonbasic columns)
    nonbasic_cols = [j for j in range(len(names)) if j not in basis_set]

    # Header
    header_cells = ["<th class='row-label'></th>", "<th class='rhs-col'>Hằng số</th>"]
    for j in nonbasic_cols:
        nm = names[j]
        css = "pivot-col-head" if nm == entering_name else ""
        header_cells.append(f"<th class='{css}'>${_tex_var(nm)}$</th>")
    thead = f"<thead><tr>{''.join(header_cells)}</tr></thead>"

    rows_html: List[str] = []

    # Hàng mục tiêu
    obj_label_tex = f"\\mathbf{{{_tex_var(snapshot.objective_label)}}}"
    obj_cells = [f"<td class='row-label'>${obj_label_tex}$</td>"]
    # Hằng số: ẩn nếu = 0 và có hạng tử khác (từ vựng xuất phát)
    obj_const_str = _frac(snapshot.obj_const, mode)
    has_obj_terms = any(snapshot.obj.get(j, Fraction(0)) != 0 for j in nonbasic_cols)
    if snapshot.obj_const == 0 and has_obj_terms:
        obj_cells.append(f"<td class='rhs-cell' style='color:#94A3B8'>$= 0$</td>")
    else:
        obj_cells.append(f"<td class='rhs-cell'>$= {obj_const_str}$</td>")
    for j in nonbasic_cols:
        nm = names[j]
        c = snapshot.obj.get(j, Fraction(0))
        css = "pivot-col" if nm == entering_name else ""
        cell_val = f"$+\\,{_frac(c, mode)}$" if c > 0 else (f"$-\\,{_frac(-c, mode)}$" if c < 0 else "$0$")
        obj_cells.append(f"<td class='{css}'>{cell_val}</td>")
    rows_html.append(f"<tr class='obj-row'>{''.join(obj_cells)}</tr>")

    # Hàng cơ sở
    for i, b in enumerate(snapshot.basis):
        b_name = names[b]
        is_pivot_row = (pivot_row is not None and i == pivot_row)
        row_css = "pivot-row" if is_pivot_row else ""
        cells = [f"<td class='row-label'>$\\mathbf{{{_tex_var(b_name)}}}$</td>"]
        cells.append(f"<td class='rhs-cell'>$= {_frac(snapshot.rhs[i], mode)}$</td>")
        for j in nonbasic_cols:
            nm = names[j]
            c = snapshot.rows[i].get(j, Fraction(0))
            cell_css = ""
            if nm == entering_name and is_pivot_row:
                cell_css = "pivot-cell"
            elif nm == entering_name:
                cell_css = "pivot-col"
            elif is_pivot_row:
                cell_css = "pivot-row"
            cell_val = f"$+\\,{_frac(c, mode)}$" if c > 0 else (f"$-\\,{_frac(-c, mode)}$" if c < 0 else "$0$")
            cells.append(f"<td class='{cell_css}'>{cell_val}</td>")
        rows_html.append(f"<tr class='{row_css}'>{''.join(cells)}</tr>")

    return f"""<div class="dict-table-wrap">
<table class="dict-table">
{thead}
<tbody>{''.join(rows_html)}</tbody>
</table>
</div>"""


# ---------------------------------------------------------------------------
# Render note cho từng bước xoay
# ---------------------------------------------------------------------------

def _step_note_html(step: PivotStep, snapshot: Snapshot, mode: str) -> str:
    names = snapshot.all_names
    enter = _tex_var(names[step.entering]) if step.entering is not None else "?"
    leave = _tex_var(names[step.leaving_var]) if step.leaving_var is not None else "?"
    rule = "Dantzig" if step.method == "dantzig" else "Bland"
    lines: List[str] = []

    if step.status == "phase1_aux_pivot":
        lines.append(f"<p class='note-rule'>⚙️ <b>Quy tắc Dantzig — Pha 1 (biến phụ)</b></p>")
        lines.append(f"<p>Biến phụ $x_0$ đóng vai trò biến vào. "
                     f"Biến ra là hàng có $b_i$ âm nhỏ nhất.</p>")
        if step.ratios:
            lines.append("<ul>")
            for ri, bval, bi in step.ratios:
                lines.append(f"<li>${_tex_var(names[bi])}$: $b = {_frac(bval, mode)}$</li>")
            lines.append("</ul>")
        lines.append(f"<p>$\\Rightarrow$ Biến vào: ${enter}$ &nbsp;|&nbsp; Biến ra: ${leave}$</p>")
        if step.pivot_value is not None:
            lines.append(f"<p>Phần tử xoay: $a_{{{leave},{enter}}} = {_frac(step.pivot_value, mode)}$</p>")
        if step.degenerate:
            lines.append("<p class='warn'>⚠️ Bước suy biến ($\\theta = 0$).</p>")
        return "".join(lines)

    if step.status == "phase1_aux_degenerate_exit":
        lines.append(f"<p class='note-rule'>⚙️ <b>Xoay $x_0$ ra (degenerate pivot)</b></p>")
        lines.append(f"<p>$\\delta = 0$ nhưng $x_0$ vẫn trong cơ sở với $x_0 = 0$ "
                     f"→ cần xoay $x_0$ ra để chuẩn bị sang Pha 2.</p>")
        lines.append(f"<p>Chọn <b>${enter}$</b> vào thay $x_0$ ($\\theta = 0$, bước suy biến).</p>")
        lines.append(f"<p>$\\Rightarrow$ Biến vào: ${enter}$ &nbsp;|&nbsp; Biến ra: ${leave}$</p>")
        if step.pivot_value is not None:
            lines.append(f"<p>Phần tử xoay: $a_{{{leave},{enter}}} = {_frac(step.pivot_value, mode)}$</p>")
        return "".join(lines)

    lines.append(f"<p class='note-rule'>⚙️ <b>Quy tắc {rule}</b></p>")
    if step.entering is not None:
        coeff = snapshot.obj.get(step.entering, Fraction(0))
        if step.method == "dantzig":
            lines.append(f"<p>Chọn <b>${enter}$</b> vì có hệ số nhỏ nhất "
                         f"$= {_frac(coeff, mode)}$ trong hàm mục tiêu.</p>")
        else:
            lines.append(f"<p>Chọn biến có chỉ số bé nhất <b>${enter}$</b>.</p>")
        lines.append(f"<p>$\\Rightarrow$ Biến vào: ${enter}$</p>")

    if step.ratios:
        lines.append(f"<p>Bảng tỉ số $\\theta$ tại cột ${enter}$ có hệ số âm:</p>")
        lines.append("<table class='ratio-table'><tr><th>Hàng</th><th>$b_i$</th>"
                     "<th>$a_{{i,enter}}$</th><th>$\\theta = b_i / (-a_{{i,enter}})$</th></tr>")
        for ri, theta, bi in step.ratios:
            a_val = snapshot.rows[ri].get(step.entering, Fraction(0)) if step.entering is not None else Fraction(0)
            lines.append(f"<tr><td>${_tex_var(names[bi])}$</td>"
                         f"<td>${_frac(snapshot.rhs[ri], mode)}$</td>"
                         f"<td>${_frac(a_val, mode)}$</td>"
                         f"<td>${_frac(theta, mode)}$</td></tr>")
        lines.append("</table>")
        lines.append(f"<p>$\\Rightarrow$ Biến ra: ${leave}$</p>")

    if step.pivot_value is not None:
        lines.append(f"<p>Phần tử xoay: "
                     f"$a_{{{leave},{enter}}} = {_frac(step.pivot_value, mode)}$</p>")
    if step.degenerate:
        lines.append("<p class='warn'>⚠️ Bước suy biến ($\\theta = 0$).</p>")
    return "".join(lines)


# ---------------------------------------------------------------------------
# Render một trace (pha) hoàn chỉnh
# ---------------------------------------------------------------------------

def _render_trace_html(trace: SolveTrace, mode: str) -> str:
    parts: List[str] = []
    if not trace.steps:
        if trace.final_snapshot:
            parts.append("<p class='note'>Từ vựng xuất phát (không cần xoay):</p>")
            parts.append(_snapshot_table(trace.final_snapshot, mode))
        return "".join(parts)

    for step in trace.steps:
        title = "Từ vựng xuất phát" if step.iteration == 1 else f"Bước {step.iteration} — trước xoay"
        parts.append(f"<h4>{title}</h4>")

        # Bảng trước xoay (có highlight)
        entering_name = step.before.all_names[step.entering] if step.entering is not None else None
        parts.append(_snapshot_table(step.before, mode,
                                     entering_name=entering_name,
                                     pivot_row=step.leaving_row))

        # Giải thích bước
        parts.append(f"<div class='step-note'>")
        parts.append(_step_note_html(step, step.before, mode))
        parts.append("</div>")

        # Bảng sau xoay
        if step.after is not None:
            parts.append(f"<h4>Sau xoay — Bước {step.iteration}</h4>")
            parts.append(_snapshot_table(step.after, mode))

    # Trạng thái kết thúc
    if trace.status == "optimal":
        parts.append("<p class='success'>✅ Tất cả hệ số trên hàm mục tiêu đều ≥ 0 → từ vựng hiện tại là tối ưu.</p>")
    elif trace.status == "unbounded":
        last_entering = None
        if trace.steps:
            last_step = trace.steps[-1]
            if last_step.status == "unbounded" and last_step.entering is not None:
                last_entering = trace.steps[-1].before.all_names[last_step.entering]
        reason = f" (có biến vào ${_tex_var(last_entering)}$ nhưng không có biến ra)" if last_entering else ""
        parts.append(f"<p class='warn'>Bài toán không giới nội{reason}.</p>")
    elif trace.status == "cycle":
        rule = "Dantzig" if trace.steps and trace.steps[0].method == "dantzig" else "Bland"
        if rule == "Dantzig":
            parts.append("<p class='warn'>🔄 Dantzig phát hiện xoay vòng → chuyển sang Bland.</p>")
        else:
            parts.append("<p class='warn'>🔄 Bland phát hiện xoay vòng.</p>")

    return "".join(parts)


# ---------------------------------------------------------------------------
# Phần bài toán gốc + chuẩn hóa
# ---------------------------------------------------------------------------

def _problem_html(engine, mode: str) -> str:
    prob = engine.problem
    n = len(prob.obj_coeffs)

    def expr_orig(coeffs):
        parts = []
        for j, c in enumerate(coeffs):
            if c == 0:
                continue
            abs_c = abs(c)
            vname = f"x_{{{j+1}}}"
            sign = "+" if c > 0 else "-"
            if abs_c == 1:
                body = f"\\,{vname}"
            else:
                body = f"\\,{_frac(abs_c, mode)}{vname}"
            parts.append(f"{sign}{body}")
        if not parts:
            return "0"
        return " ".join(parts).lstrip("+").strip()

    sense_label = "\\max" if prob.objective_sense == "max" else "\\min"
    obj_expr = expr_orig(prob.obj_coeffs)

    con_lines = []
    for cons in prob.constraints:
        lhs = expr_orig(cons["coeffs"])
        s_tex = {"≤": "\\leq", "≥": "\\geq", "=": "="}.get(cons["sense"], cons["sense"])
        rhs = _frac(Fraction(cons["rhs"]), mode)
        con_lines.append(f"\\quad {lhs} {s_tex} {rhs}")

    for i, sg in enumerate(prob.var_signs):
        nm = f"x_{{{i+1}}}"
        if sg == "≥0":
            con_lines.append(f"\\quad {nm} \\geq 0")
        elif sg == "≤0":
            con_lines.append(f"\\quad {nm} \\leq 0")

    con_body = " \\\\\n".join(con_lines)

    return (
        f"$${sense_label}\\; Z = {obj_expr}$$\n"
        f"$$\\begin{{cases}}\n{con_body}\n\\end{{cases}}$$"
    )


def _standardization_html(engine, mode: str) -> str:
    """Render các bước chuẩn hóa dưới dạng LaTeX đẹp theo thứ tự: Biến -> Ràng buộc -> Mục tiêu."""
    prob = engine.problem
    n = len(prob.obj_coeffs)
    parts = []

    # ── Bước 1: Thay thế biến không chuẩn ────────────────────────────────
    sub_notes = []
    for i, sg in enumerate(prob.var_signs):
        idx = f"{{{i+1}}}"
        nm  = f"x_{idx}"
        if sg == "≤0":
            y_nm = f"y_{idx}"
            sub_notes.append(f"$\\quad {nm} \\leq 0$: đặt ${y_nm} = -{nm} \\geq 0$")
        elif sg == "tự do":
            a_nm = f"a_{idx}"
            b_nm = f"b_{idx}"
            sub_notes.append(
                f"$\\quad {nm}$ tự do: đặt ${nm} = {a_nm} - {b_nm}$, "
                f"$\\;{a_nm},\\, {b_nm} \\geq 0$"
            )
            
    if sub_notes:
        parts.append("<p>📌 <b>Bước 1: Thay thế biến không chuẩn</b></p>")
        for note in sub_notes:
            parts.append(f"<p>{note}</p>")
    else:
        parts.append("<p>📌 <b>Bước 1: Biến số</b> — tất cả $x_i \\geq 0$, không cần thay đổi.</p>")

    # ── Bước 2: Chuẩn hóa ràng buộc ──────────────────────────────────────
    parts.append("<p>📌 <b>Bước 2: Chuẩn hóa ràng buộc</b></p>")

    std_names_list = getattr(engine, "std_names", None)
    all_names_list = getattr(engine, "all_names", None)

    def lhs_tex(row_coeffs_std):
        ps = []
        for j, c in enumerate(row_coeffs_std):
            if c == 0:
                continue
            abs_c = abs(c)
            sign = "+" if c > 0 else "-"
            nm_tex = _tex_var(std_names_list[j]) if std_names_list and j < len(std_names_list) else f"x_{{{j+1}}}"
            body = f"\\,{nm_tex}" if abs_c == 1 else f"\\,{_frac(abs_c, mode)}{nm_tex}"
            ps.append(f"{sign}{body}")
        return " ".join(ps).lstrip("+").strip() or "0"

    # Xây dựng bảng từ ràng buộc GỐC (prob.constraints), map sang std_constraints.
    # Ràng buộc "=" đã được tách thành 2 dòng ≤ trong engine, mỗi dòng có 1 biến bù.
    table_rows = []
    w_count = 0          # đếm biến bù (w1, w2, ...) theo thứ tự trong std_constraints
    std_row_idx = 0      # con trỏ vào engine.std_constraints

    for orig_i, cons in enumerate(prob.constraints):
        orig_sense = cons["sense"]
        # Tính lhs gốc (sau khi thay thế biến nếu có) từ std_constraints
        if orig_sense == "=":
            # Ràng buộc = → 2 dòng std liên tiếp: row_a (≤ b) và row_b (≤ -b)
            row_a  = engine.std_constraints[std_row_idx]
            rhs_a  = engine.std_rhs[std_row_idx]
            std_row_idx += 1
            row_b  = engine.std_constraints[std_row_idx]
            rhs_b  = engine.std_rhs[std_row_idx]
            std_row_idx += 1

            w_count += 1; slack_a = f"w_{{{w_count}}}"
            w_count += 1; slack_b = f"w_{{{w_count}}}"

            lhs_a = lhs_tex(row_a)
            lhs_b = lhs_tex(row_b)
            rhs_a_tex = _frac(rhs_a, mode)
            rhs_b_tex = _frac(rhs_b, mode)

            # Biểu diễn dạng gốc trước khi thay thế biến
            orig_lhs = lhs_tex([Fraction(c) for c in cons["coeffs"]] + [Fraction(0)] * (len(row_a) - len(cons["coeffs"])))
            orig_rhs = _frac(Fraction(cons["rhs"]), mode)

            sub_rows = (
                f"<tr>"
                f"<td style='white-space:nowrap' rowspan='2'><b>RB {orig_i+1}</b></td>"
                f"<td style='white-space:nowrap' rowspan='2'>${orig_lhs} = {orig_rhs}$</td>"
                f"<td style='white-space:nowrap;color:#0F766E'>${lhs_a} \\leq {rhs_a_tex}$</td>"
                f"<td style='white-space:nowrap;color:#0F766E'>${lhs_a} + {slack_a} = {rhs_a_tex}$</td>"
                f"</tr>"
                f"<tr>"
                f"<td style='white-space:nowrap;color:#0F766E'>${lhs_b} \\leq {rhs_b_tex}$  <span style=\"color:#64748B;font-size:0.85em\">(nhân $-1$)</span></td>"
                f"<td style='white-space:nowrap;color:#0F766E'>${lhs_b} + {slack_b} = {rhs_b_tex}$</td>"
                f"</tr>"
            )
            table_rows.append(sub_rows)
        else:
            std_row = engine.std_constraints[std_row_idx]
            rhs_val = engine.std_rhs[std_row_idx]
            std_row_idx += 1

            lhs_str = lhs_tex(std_row)
            rhs_tex = _frac(rhs_val, mode)
            orig_lhs = lhs_tex([Fraction(c) for c in cons["coeffs"]] + [Fraction(0)] * (len(std_row) - len(cons["coeffs"])))
            orig_rhs = _frac(Fraction(cons["rhs"]), mode)

            w_count += 1
            slack_nm = f"w_{{{w_count}}}"
            if orig_sense == '≤':
                orig_rb    = f'${orig_lhs} \\leq {orig_rhs}$'
                std_lean   = f'${lhs_str} \\leq {rhs_tex}$'
                slack_eq   = f'${lhs_str} + {slack_nm} = {rhs_tex}$'
            else:  # ≥
                orig_rb    = f'${orig_lhs} \\geq {orig_rhs}$'
                std_lean   = f'${lhs_str} \\leq {rhs_tex}$  <span style="color:#64748B;font-size:0.85em">(nhân $-1$)</span>'
                slack_eq   = f'${lhs_str} + {slack_nm} = {rhs_tex}$'

            table_rows.append(
                f"<tr>"
                f"<td style='white-space:nowrap'><b>RB {orig_i+1}</b></td>"
                f"<td style='white-space:nowrap'>{orig_rb}</td>"
                f"<td style='white-space:nowrap;color:#0F766E'>{std_lean}</td>"
                f"<td style='white-space:nowrap;color:#0F766E'>{slack_eq}</td>"
                f"</tr>"
            )

    parts.append(
        "<table style='border-collapse:collapse;width:100%;margin:8px 0 16px'>"
        "<thead><tr style='background:#EFF6FF'>"
        "<th style='padding:6px 12px;border:1px solid #CBD5E1;text-align:left'>RB</th>"
        "<th style='padding:6px 12px;border:1px solid #CBD5E1'>Dạng gốc</th>"
        "<th style='padding:6px 12px;border:1px solid #CBD5E1'>Dạng chuẩn ($\\leq$)</th>"
        "<th style='padding:6px 12px;border:1px solid #CBD5E1'>Thêm biến bù</th>"
        "</tr></thead>"
        f"<tbody>{''.join(table_rows)}</tbody>"
        "</table>"
    )

    # ── Bước 3: Hàm mục tiêu ─────────────────────────────────────────────
    parts.append("<p>📌 <b>Bước 3: Dạng mục tiêu</b></p>")

    def get_replaced_terms(coeffs, multiplier=1):
        """Tạo danh sách (hệ số, tên biến) sau khi tính toán cả phép thay thế a_i, b_i, y_i"""
        terms = []
        for i, c in enumerate(coeffs):
            if c == 0: continue
            c_mult = c * multiplier
            sg = prob.var_signs[i]
            idx = i + 1
            if sg == "≤0":
                terms.append((-c_mult, f"y_{{{idx}}}"))
            elif sg == "tự do":
                terms.append((c_mult, f"a_{{{idx}}}"))
                terms.append((-c_mult, f"b_{{{idx}}}"))
            else:
                terms.append((c_mult, f"x_{{{idx}}}"))
        return terms

    def format_terms(terms):
        """Chuyển đổi danh sách tuples (hệ số, tên biến) thành biểu thức LaTeX"""
        ps = []
        for c, nm in terms:
            if c == 0: continue
            abs_c = abs(c)
            sign = "+" if c > 0 else "-"
            tex_nm = _tex_var(nm)
            body = f"\\,{tex_nm}" if abs_c == 1 else f"\\,{_frac(abs_c, mode)}{tex_nm}"
            ps.append(f"{sign}{body}")
        return " ".join(ps).lstrip("+").strip() or "0"

    # Lấy biểu thức gốc ban đầu (tất cả là x)
    orig_terms = [(c, f"x_{{{i+1}}}") for i, c in enumerate(prob.obj_coeffs) if c != 0]
    orig_expr = format_terms(orig_terms)

    if prob.objective_sense == "max":
        parts.append(f"<p>Hàm mục tiêu gốc: $$\\max Z = {orig_expr}$$</p>")
        
        # Nếu có thay thế biến ở Bước 1, in ra hàm mục tiêu sau khi thế
        if sub_notes:
            replaced_expr = format_terms(get_replaced_terms(prob.obj_coeffs, 1))
            parts.append(f"<p>Thay thế biến vào hàm mục tiêu: $$\\max Z = {replaced_expr}$$</p>")
            
        # Biểu thức dạng chuẩn (min) - nhân hệ số với -1
        min_expr = format_terms(get_replaced_terms(prob.obj_coeffs, -1))
        parts.append(f"<p>Đặt $Z' = -Z$, chuyển về bài toán $\\min$:</p>")
        parts.append(f"<p>$$\\min Z' = -\\max Z = {min_expr}$$</p>")
    else:
        parts.append(f"<p>Hàm mục tiêu gốc: $$\\min Z = {orig_expr}$$</p>")
        
        # Nếu có thay thế biến ở Bước 1, in ra hàm mục tiêu sau khi thế
        if sub_notes:
            replaced_expr = format_terms(get_replaced_terms(prob.obj_coeffs, 1))
            parts.append(f"<p>Thay thế biến vào hàm mục tiêu: $$\\min Z = {replaced_expr}$$</p>")

    # ── Bảng biến chuẩn hóa cuối ──────────────────────────────────────────
    if std_names_list:
        std_tex = ",\\;".join(_tex_var(nm) for nm in std_names_list)
        parts.append(f"<p style='margin-top:20px'>Các biến trong bài toán chuẩn hóa: $\\quad {std_tex}$</p>")

    raw_lines = getattr(engine, "standardization_lines", [])
    if raw_lines:
        parts.append("<details style='margin-top:8px'>"
                     "<summary style='color:#64748B;font-size:0.87rem'>Xem log chi tiết (text thuần)</summary>")
        for ln in raw_lines:
            if not ln.strip():
                parts.append("<br>")
            else:
                safe = ln.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                parts.append(f"<p class='std-line'>{safe}</p>")
        parts.append("</details>")

    return "".join(parts)


# ---------------------------------------------------------------------------
# Kết luận cuối
# ---------------------------------------------------------------------------

def _conclusion_html(report: SolveReport, engine, mode: str) -> str:
    parts: List[str] = []
    status = report.status
    is_max = engine.problem.objective_sense == "max"

    if status == "infeasible":
        has_aux = bool(getattr(engine, "need_aux_phase1", False))
        z_val = "$z_{\\max} = -\\infty$" if is_max else "$z_{\\min} = +\\infty$"
        if has_aux:
            reason = f"Biến phụ $x_0$ vẫn còn trong cơ sở sau Pha 1 (giá trị $x_0 > 0$) → miền chấp nhận được rỗng ({z_val})."
        else:
            art_names = [engine.all_names[a] for a in engine.artificial_vars] if engine.artificial_vars else []
            art_str = ", ".join(f"${nm}$" for nm in art_names) if art_names else "biến độ nhiễu"
            reason = f"Pha 1 kết thúc với hàm bổ trợ $> 0$ — {art_str} không thể đưa ra khỏi cơ sở → bài toán vô nghiệm ({z_val})."
        parts.append(f"<div class='conclusion warn-box'><h3>KẾT LUẬN: Vô nghiệm</h3>"
                     f"<p>{reason}</p></div>")
        return "".join(parts)
    if status == "unbounded":
        z_val = "$z_{\\max} = +\\infty$" if is_max else "$z_{\\min} = -\\infty$"
        parts.append(f"<div class='conclusion warn-box'><h3>KẾT LUẬN: Không giới nội</h3>"
                     f"<p>Có biến vào nhưng không có biến ra tương ứng → {z_val}.</p></div>")
        return "".join(parts)
    if status == "cycle":
        rule = "Dantzig" if report.dantzig.steps and report.dantzig.steps[0].method == "dantzig" else "Bland"
        if rule == "Dantzig" and report.bland is not None and report.bland.status == "cycle":
            parts.append("<div class='conclusion warn-box'><h3>KẾT LUẬN: Xoay vòng</h3>"
                         "<p>Cả Dantzig và Bland đều phát hiện xoay vòng.</p></div>")
        elif rule == "Dantzig":
            parts.append("<div class='conclusion warn-box'><h3>KẾT LUẬN: Xoay vòng</h3>"
                         "<p>Dantzig phát hiện xoay vòng — hãy thử Bland.</p></div>")
        else:
            parts.append("<div class='conclusion warn-box'><h3>KẾT LUẬN: Xoay vòng</h3>"
                         "<p>Bland phát hiện xoay vòng.</p></div>")
        return "".join(parts)

    # Optimal
    obj_std  = report.objective_std  or Fraction(0)
    obj_orig = report.objective_orig or Fraction(0)
    method_label = "Dantzig" if report.used_method == "dantzig" else "Bland"

    parts.append(f"<div class='conclusion success-box'>")
    parts.append(f"<h3>KẾT LUẬN: Tối ưu ({method_label})</h3>")

    # Giá trị mục tiêu
    if is_max:
        parts.append(
            f"<p>Giá trị tối ưu là: $z^* = \\max Z = -(\\min Z') = -({_frac(obj_std, mode)}) = {_frac(obj_orig, mode)}$</p>"
        )
    else:
        parts.append(f"Giá trị tối ưu là: <p>$z^* = \\min Z = {_frac(obj_orig, mode)}$</p>")

    # Nghiệm
    if report.multiple_optimal and report.multiple_optimal_vars:
        parts.append("<p class='warn'>Bài toán có <b>vô số nghiệm tối ưu</b>.</p>")
        snap = (report.phase2_trace.final_snapshot
                if report.phase2_trace and report.phase2_trace.final_snapshot
                else report.dantzig.final_snapshot)
        if snap:
            base_free_vars: List[int] = report.multiple_optimal_vars
            aux_idx = getattr(engine, "phase1_aux_var_index", None)
            art_set = set(engine.artificial_vars)
            basis_list = list(snap.basis)
            basis_set  = set(basis_list)
            n_orig = len(engine.problem.var_signs)

            # ── Expand split pairs (biến tự do x_i = a_i - b_i) ─────────────
            # Replicate logic from simplex_app._expand_free_vars_with_splits
            split_free_pairs: List[Tuple] = []  # (orig_idx, ja, jb, which)
            base_set = set(base_free_vars)
            extra: List[int] = []
            for orig_idx, mapping in enumerate(engine.variable_mapping):
                if len(mapping) != 2:
                    continue
                ja, mc_a = mapping[0]
                jb, mc_b = mapping[1]
                # Check if both are phi-co-so
                ja_nonbasic = (ja not in basis_set)
                jb_nonbasic = (jb not in basis_set)
                if ja in base_set and jb_nonbasic:
                    split_free_pairs.append((orig_idx, ja, jb, "a"))
                elif jb in base_set and ja_nonbasic:
                    split_free_pairs.append((orig_idx, ja, jb, "b"))
                elif ja in base_set and jb in base_set:
                    split_free_pairs.append((orig_idx, ja, jb, "ab"))
                elif ja_nonbasic and jb_nonbasic and (ja in base_set or jb in base_set):
                    which = "a" if ja in base_set else "b"
                    split_free_pairs.append((orig_idx, ja, jb, which))

            ai_set = {ja for _, ja, jb, _ in split_free_pairs}
            bi_set = {jb for _, ja, jb, _ in split_free_pairs}

            # free_vars = base_free_vars + any extra (partner of split not already there)
            extra_set: set = set()
            for _, ja, jb, which in split_free_pairs:
                if ja not in base_set and ja not in extra_set:
                    extra_set.add(ja); extra.append(ja)
                if jb not in base_set and jb not in extra_set:
                    extra_set.add(jb); extra.append(jb)
            free_vars = list(base_free_vars) + extra
            free_set  = set(free_vars)

            ab_free_orig = {oi for oi, ja, jb, which in split_free_pairs if which == "ab"}

            # ── xi_expr[orig_idx] = (const, {fv: coef}) ──────────────────────
            xi_expr: dict = {}
            for orig_idx, mapping in enumerate(engine.variable_mapping):
                const_v = Fraction(0)
                fv_coefs: Dict[int, Fraction] = {fv: Fraction(0) for fv in free_vars}
                for j, mc in mapping:
                    if j in basis_set:
                        ri = basis_list.index(j)
                        const_v += mc * snap.rhs[ri]
                        for fv in free_vars:
                            fv_coefs[fv] = fv_coefs.get(fv, Fraction(0)) + mc * snap.rows[ri].get(fv, Fraction(0))
                    elif j in free_set:
                        fv_coefs[j] = fv_coefs.get(j, Fraction(0)) + mc
                xi_expr[orig_idx] = (const_v, fv_coefs)

            # ── Helper: gộp a_i/b_i → x_i trong danh sách term ──────────────
            def to_xi_terms_html(orig_idx2: int):
                c2, t2 = xi_expr[orig_idx2]
                remaining: Dict[int, Fraction] = {fv: v for fv, v in t2.items() if v != 0}
                result_terms: list = []
                for oi2, ja2, jb2, _ in split_free_pairs:
                    ca = remaining.get(ja2, Fraction(0))
                    cb = remaining.get(jb2, Fraction(0))
                    if ca == 0 and cb == 0:
                        continue
                    if cb == -ca:
                        if ca != 0:
                            result_terms.append((ca, f"x_{{{oi2+1}}}"))
                        remaining.pop(ja2, None); remaining.pop(jb2, None)
                    else:
                        if ca != 0:
                            result_terms.append((ca, _tex_var(snap.all_names[ja2])))
                            remaining.pop(ja2, None)
                        if cb != 0:
                            result_terms.append((cb, _tex_var(snap.all_names[jb2])))
                            remaining.pop(jb2, None)
                for fv2, coef2 in remaining.items():
                    if coef2 != 0:
                        result_terms.append((coef2, _tex_var(snap.all_names[fv2])))
                return c2, result_terms

            def fmt_xi_expr(orig_idx2: int) -> str:
                c2, terms = to_xi_terms_html(orig_idx2)
                ps = []
                if c2 != 0 or not terms:
                    ps.append(_frac(c2, mode))
                for coef2, var_tex in terms:
                    abs_c = abs(coef2)
                    sign = "+" if coef2 > 0 else "-"
                    body = f"\\,{var_tex}" if abs_c == 1 else f"\\,{_frac(abs_c, mode)}{var_tex}"
                    ps.append(f"{sign}{body}")
                s = " ".join(ps).lstrip("+").strip()
                return s or "0"

            # ── Nghiệm tối ưu ────────────────────────────────────────────────
            parts.append("<p><b>Nghiệm tối ưu là:</b></p><ul>")
            for orig_idx in range(n_orig):
                if orig_idx in ab_free_orig:
                    xi_tex = f"x_{{{orig_idx+1}}}"
                    parts.append(f"<li>${xi_tex} = {xi_tex}$ &nbsp; (tự do, $x_{{{orig_idx+1}}} \\in \\mathbb{{R}}$)</li>")
                else:
                    expr_str = fmt_xi_expr(orig_idx)
                    parts.append(f"<li>$x_{{{orig_idx+1}}} = {expr_str}$</li>")
            parts.append("</ul>")

            # ── Điều kiện ────────────────────────────────────────────────────
            # n_real_params: số tham số thực sự (mỗi split-ab pair = 1; non-split free = 1)
            non_split_free = [fv for fv in free_vars if fv not in ai_set and fv not in bi_set]
            ab_pairs = [(oi, ja, jb) for oi, ja, jb, which in split_free_pairs if which == "ab"]
            n_real_params = len(ab_pairs) + len(non_split_free)

            if n_real_params == 1:
                if ab_pairs:
                    oi_p, ja_p, jb_p = ab_pairs[0]
                    param_tex = f"x_{{{oi_p+1}}}"
                    lowers2: list = []
                    uppers2: list = []
                    for ri, b in enumerate(basis_list):
                        if b in art_set or (aux_idx is not None and b == aux_idx):
                            continue
                        if b in ai_set or b in bi_set:
                            continue
                        ca = snap.rows[ri].get(ja_p, Fraction(0))
                        cb = snap.rows[ri].get(jb_p, Fraction(0))
                        if ca == 0 and cb == 0:
                            continue
                        if cb == -ca and ca != 0:
                            bound = -snap.rhs[ri] / ca
                            if ca > 0:
                                lowers2.append(bound)
                            else:
                                uppers2.append(bound)
                    lower2 = max(lowers2) if lowers2 else None
                    upper2 = min(uppers2) if uppers2 else None
                    if lower2 is not None and upper2 is not None:
                        cond_tex = f"${_frac(lower2, mode)} \\leq {param_tex} \\leq {_frac(upper2, mode)}$"
                        parts.append(f"<p>với {cond_tex}.</p>")
                    elif lower2 is not None:
                        if lower2 == 0:
                            parts.append(f"<p>với ${param_tex} \\geq 0$.</p>")
                        else:
                            parts.append(f"<p>với ${param_tex} \\geq {_frac(lower2, mode)}$.</p>")
                    elif upper2 is not None:
                        parts.append(f"<p>với ${param_tex} \\leq {_frac(upper2, mode)}$.</p>")
                    # else: hoàn toàn tự do, không in điều kiện
                else:
                    param_idx2 = non_split_free[0]
                    param_tex2 = _tex_var(snap.all_names[param_idx2])
                    lowers3: list = [Fraction(0)]
                    uppers3: list = []
                    for ri, b in enumerate(basis_list):
                        if b in art_set or b in ai_set or b in bi_set:
                            continue
                        if aux_idx is not None and b == aux_idx:
                            continue
                        coef = snap.rows[ri].get(param_idx2, Fraction(0))
                        if coef == 0:
                            continue
                        bound = -snap.rhs[ri] / coef
                        if coef > 0:
                            lowers3.append(bound)
                        else:
                            uppers3.append(bound)
                    lower3 = max(lowers3)
                    if uppers3:
                        upper3 = min(uppers3)
                        cond_tex3 = f"${_frac(lower3, mode)} \\leq {param_tex2} \\leq {_frac(upper3, mode)}$"
                    else:
                        cond_tex3 = f"${param_tex2} \\geq {_frac(lower3, mode)}$"
                    parts.append(f"<p>với {cond_tex3}.</p>")
            else:
                # Nhiều tham số: liệt kê điều kiện cho từng hàng và từng free var
                cond_parts_tex = []
                seen_rows: set = set()

                # Helper gộp a/b → x_i cho hàng ràng buộc
                def row_to_xi_terms_html(t_row: dict):
                    remaining2 = {fv: v for fv, v in t_row.items() if v != 0}
                    result2: list = []
                    for oi2, ja2, jb2, _ in split_free_pairs:
                        ca = remaining2.get(ja2, Fraction(0))
                        cb = remaining2.get(jb2, Fraction(0))
                        if ca == 0 and cb == 0:
                            continue
                        if cb == -ca:
                            if ca != 0:
                                result2.append((ca, f"x_{{{oi2+1}}}"))
                            remaining2.pop(ja2, None); remaining2.pop(jb2, None)
                        else:
                            if ca != 0:
                                result2.append((ca, _tex_var(snap.all_names[ja2])))
                                remaining2.pop(ja2, None)
                            if cb != 0:
                                result2.append((cb, _tex_var(snap.all_names[jb2])))
                                remaining2.pop(jb2, None)
                    for fv2, coef2 in remaining2.items():
                        if coef2 != 0:
                            result2.append((coef2, _tex_var(snap.all_names[fv2])))
                    return result2

                for ri, b in enumerate(basis_list):
                    if b in art_set or (aux_idx is not None and b == aux_idx):
                        continue
                    if b in ai_set or b in bi_set or ri in seen_rows:
                        continue
                    seen_rows.add(ri)
                    t_row = {fv: snap.rows[ri].get(fv, Fraction(0)) for fv in free_vars}
                    if not any(v != 0 for v in t_row.values()):
                        continue
                    terms2 = row_to_xi_terms_html(t_row)
                    if terms2:
                        ps2 = []
                        rhs_v = snap.rhs[ri]
                        if rhs_v != 0:
                            ps2.append(_frac(rhs_v, mode))
                        for coef2, var_tex in terms2:
                            abs_c = abs(coef2)
                            sign = "+" if coef2 > 0 else "-"
                            body = f"\\,{var_tex}" if abs_c == 1 else f"\\,{_frac(abs_c, mode)}{var_tex}"
                            ps2.append(f"{sign}{body}")
                        expr2 = " ".join(ps2).lstrip("+").strip() or "0"
                        cond_parts_tex.append(f"${expr2} \\geq 0$")

                for fv in non_split_free:
                    cond_parts_tex.append(f"${_tex_var(snap.all_names[fv])} \\geq 0$")

                if cond_parts_tex:
                    parts.append(f"<p>với {'; '.join(cond_parts_tex)}.</p>")
    else:
        parts.append("<p><b>Nghiệm tối ưu là:</b></p><ul>")
        for i in range(len(engine.problem.var_signs)):
            val = report.solution_orig.get(i, Fraction(0))
            parts.append(f"<li>$x_{{{i+1}}} = {_frac(val, mode)}$</li>")
        parts.append("</ul>")

    # Suy biến
    d = (report.dantzig.degenerate_steps or 0) + \
        ((report.bland.degenerate_steps if report.bland else 0) or 0)
    if d:
        parts.append(f"<p class='warn'>ℹ️ Có {d} bước suy biến ($\\theta = 0$).</p>")

    parts.append("</div>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# CSS + HTML template
# ---------------------------------------------------------------------------

_CSS = """
body {
    font-family: 'Segoe UI', 'Arial', sans-serif;
    background: #F8FAFC;
    color: #1E293B;
    margin: 0;
    padding: 0;
}
.page-header {
    background: #1E3A5F;
    color: #fff;
    padding: 24px 40px 18px;
}
.page-header h1 { margin: 0 0 4px; font-size: 1.45rem; }
.page-header p  { margin: 0; color: #B5D4F4; font-size: 0.9rem; }

.container { max-width: 1100px; margin: 0 auto; padding: 28px 32px 60px; }

h2 { color: #1E3A5F; border-bottom: 2px solid #BFDBFE; padding-bottom: 6px; margin-top: 36px; }
h3 { color: #185FA5; margin-top: 24px; }
h4 { color: #334155; margin: 20px 0 6px; font-size: 1rem; }

/* Bảng từ vựng */
.dict-table-wrap { overflow-x: auto; margin: 8px 0 16px; }
.dict-table {
    border-collapse: collapse;
    font-size: 0.95rem;
    min-width: 360px;
}
.dict-table th, .dict-table td {
    border: 1px solid #CBD5E1;
    padding: 7px 14px;
    text-align: center;
    white-space: nowrap;
}
.dict-table th { background: #EFF6FF; font-weight: 600; color: #1E3A5F; }
.dict-table .row-label { background: #F1F5F9; font-weight: 600; text-align: left; }
.dict-table .rhs-cell  { background: #F8FAFC; border-right: 2px solid #94A3B8; }
.dict-table .rhs-col   { background: #EFF6FF; border-right: 2px solid #94A3B8; }
.dict-table .obj-row td { background: #EEF2FF; }

/* Highlight xoay */
.dict-table .pivot-col      { background: #FEF9C3 !important; }
.dict-table .pivot-col-head { background: #FDE68A !important; }
.dict-table .pivot-row      { background: #E0F2FE !important; }
.dict-table .pivot-cell     { background: #BFDBFE !important; font-weight: 700; }

/* Step note */
.step-note {
    background: #F0FDF4;
    border-left: 4px solid #22C55E;
    padding: 10px 18px;
    margin: 8px 0 18px;
    border-radius: 0 6px 6px 0;
    font-size: 0.93rem;
}
.step-note p  { margin: 4px 0; }
.step-note ul { margin: 4px 0 4px 18px; }
.note-rule    { font-size: 1rem; margin-bottom: 6px !important; color: #185FA5; }

/* Ratio table */
.ratio-table {
    border-collapse: collapse;
    margin: 8px 0;
    font-size: 0.88rem;
}
.ratio-table th, .ratio-table td {
    border: 1px solid #CBD5E1;
    padding: 5px 12px;
    text-align: center;
}
.ratio-table th { background: #F1F5F9; }

/* Status */
.note    { color: #0F766E; }
.warn    { color: #B45309; font-weight: 600; }
.success { color: #15803D; font-weight: 600; }

/* Conclusion boxes */
.conclusion { border-radius: 8px; padding: 20px 28px; margin-top: 32px; }
.success-box { background: #F0FDF4; border: 1.5px solid #86EFAC; }
.warn-box    { background: #FFFBEB; border: 1.5px solid #FCD34D; }
.conclusion h3 { margin-top: 0; }
.conclusion ul { margin: 8px 0 8px 20px; line-height: 1.9; }

/* Std lines */
.std-line { margin: 2px 0; font-family: 'Consolas', monospace; font-size: 0.88rem; color: #334155; }

/* Section divider */
.phase-section {
    border: 1.5px solid #BFDBFE;
    border-radius: 8px;
    padding: 18px 24px;
    margin: 24px 0;
    background: #fff;
}
.phase-section h2 { margin-top: 0; }

/* Collapsible */
details { margin: 12px 0; }
summary {
    cursor: pointer;
    font-weight: 600;
    color: #185FA5;
    padding: 8px 0;
    user-select: none;
}
summary:hover { color: #1E3A5F; }

/* Print */
@media print {
    .page-header { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    details { display: block; }
    details[open] summary ~ * { display: block !important; }
}
"""

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lời giải Quy hoạch tuyến tính</title>
<link rel="stylesheet"
      href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
<script defer
        src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
<script defer
        src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"
        onload="renderMathInElement(document.body, {{
          delimiters: [
            {{left:'$$', right:'$$', display:true}},
            {{left:'$',  right:'$',  display:false}}
          ]
        }});"></script>
<style>
{css}
</style>
</head>
<body>
<div class="page-header">
  <h1>Giải Bài toán Quy hoạch tuyến tính (tổng quát) </h1>
  <p>Xuất từ ứng dụng &nbsp;·&nbsp; Hiển thị LaTeX với KaTeX</p>
</div>
<div class="container">
{body}
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Helpers for aux phase 1 problem description and phase1→phase2 transition
# ---------------------------------------------------------------------------

def _aux_phase1_problem_html(engine, mode: str) -> str:
    """Tạo HTML mô tả bài toán bổ trợ x0 dạng đề bài cụ thể."""
    parts: List[str] = []
    parts.append("<div style='background:#F0FDF4;border-left:4px solid #22C55E;padding:12px 18px;margin:8px 0;border-radius:0 6px 6px 0'>")
    parts.append("<p><b>Bài toán bổ trợ:</b></p>")
    parts.append("<p style='margin:4px 0 2px'>$$\\min\\; x_0$$</p>")
    # Build constraint lines
    con_lines: List[str] = []
    for i, (b_val, row) in enumerate(zip(engine.initial_rhs, engine.initial_rows)):
        lhs_parts: List[str] = []
        for j in range(len(engine.std_names)):
            a = -row.get(j, Fraction(0))
            if a == 0:
                continue
            t = _term(a, engine.all_names[j], mode)
            if t:
                lhs_parts.append(t)
        lhs_str = " ".join(lhs_parts).lstrip("+").strip() or "0"
        rhs_str = _frac(b_val, mode)
        con_lines.append(f"\\quad {lhs_str} - x_0 \\leq {rhs_str}")
    # Non-negativity
    var_tex = ",\\;".join(["x_0"] + [_tex_var(nm) for nm in engine.std_names])
    con_lines.append(f"\\quad {var_tex} \\geq 0")
    con_body = " \\\\\n".join(con_lines)
    parts.append(f"$$\\begin{{cases}}\n{con_body}\n\\end{{cases}}$$")
    parts.append("<p class='note' style='margin-top:6px;font-size:0.9rem'>Đưa $x_0$ vào cơ sở tại hàng có $b_i$ âm nhất, "
                 "sau đó tối thiểu hóa $x_0$ bằng đơn hình chuẩn.</p>")
    parts.append("</div>")
    return "".join(parts)


def _phase2_transition_aux_html(engine, snap1: Snapshot, mode: str) -> str:
    """Tạo HTML bước chuyển pha 1 bổ trợ → pha 2 với khai triển hàm mục tiêu."""
    parts: List[str] = []
    aux_idx = getattr(engine, "phase1_aux_var_index", None)
    parts.append("<div style='background:#EFF6FF;border-left:4px solid #3B82F6;padding:12px 18px;margin:8px 0;border-radius:0 6px 6px 0'>")
    parts.append("<p><b>Từ vựng hiện là tối ưu:</b> cho $x_0 = 0$, khi đó ta có:</p>")
    parts.append("<ul>")
    for i, (b_val, bas_idx) in enumerate(zip(snap1.rhs, snap1.basis)):
        row = snap1.rows[i]
        b_name = _tex_var(snap1.all_names[bas_idx])
        rhs_str = _frac(b_val, mode)
        extras: List[str] = []
        for j, a in sorted(row.items()):
            if aux_idx is not None and j == aux_idx:
                continue
            if a == 0 or j >= len(snap1.all_names):
                continue
            t = _term(a, snap1.all_names[j], mode)
            if t:
                extras.append(t)
        expr = rhs_str + (" " + " ".join(extras) if extras else "")
        parts.append(f"<li>${b_name} = {expr.lstrip('+').strip()}$</li>")
    parts.append("</ul>")

    # Hàm mục tiêu gốc (chưa thay)
    is_max = engine.problem.objective_sense == "max"
    obj_sense_str = "\\min Z'" if is_max else "\\min Z"
    obj_parts: List[str] = []
    for j, c in enumerate(engine.std_obj_coeffs):
        if c == 0 or j >= len(engine.all_names):
            continue
        t = _term(c, engine.all_names[j], mode)
        if t:
            obj_parts.append(t)
    obj_expr_raw = " ".join(obj_parts).lstrip("+").strip() or "0"

    # Canonicalize: thay biến cơ sở của snap1 vào hàm mục tiêu
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
            expanded_terms[j] = expanded_terms.get(j, Fraction(0)) + c

    exp_parts: List[str] = []
    if expanded_const != 0:
        exp_parts.append(_frac(expanded_const, mode))
    for j in sorted(expanded_terms.keys()):
        c2 = expanded_terms.get(j, Fraction(0))
        if c2 == 0 or j >= len(snap1.all_names):
            continue
        if aux_idx is not None and j == aux_idx:
            continue
        t = _term(c2, snap1.all_names[j], mode)
        if t:
            exp_parts.append(t)
    expanded_expr = " ".join(exp_parts).lstrip("+").strip() or "0"

    parts.append(f"<p><b>Hàm mục tiêu mới:</b> "
                 f"$${obj_sense_str} = {obj_expr_raw} = {expanded_expr}$$</p>")
    parts.append("</div>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Hàm chính
# ---------------------------------------------------------------------------

def export_report_html(report: SolveReport, mode: str = "Phân số") -> str:
    """
    Tạo file HTML đầy đủ cho lời giải và trả về đường dẫn file tạm.
    Gọi webbrowser.open(f"file:///{path}") để mở trong trình duyệt.
    """
    engine = report.engine
    body_parts: List[str] = []

    # 1. Bài toán gốc
    body_parts.append("<h2>📋 Bài toán gốc</h2>")
    body_parts.append(_problem_html(engine, mode))

    # 2. Chuẩn hóa (collapsible)
    body_parts.append("<details><summary>⚙️ Chi tiết chuẩn hóa bài toán</summary>")
    body_parts.append(_standardization_html(engine, mode))
    body_parts.append("</details>")

    # 3. Pha 1 (nếu có)
    has_aux = bool(getattr(engine, "need_aux_phase1", False))
    has_art = bool(engine.artificial_vars)

    if has_aux or has_art:
        body_parts.append("<div class='phase-section'>")
        body_parts.append("<h2>🔧 Pha 1</h2>")
        if has_aux:
            body_parts.append(
                "<p class='note'>Tồn tại $b_i &lt; 0$ → tìm từ vựng xuất phát chấp nhận được bằng bài toán bổ trợ.</p>"
            )
            body_parts.append(_aux_phase1_problem_html(engine, mode))
        elif has_art:
            art_names = [engine.all_names[a] for a in engine.artificial_vars]
            art_str = ", ".join(f"${nm}$" for nm in art_names)
            body_parts.append(
                f"<p class='note'>Ràng buộc đẳng thức → thêm biến độ nhiễu: {art_str}. "
                f"Bài toán bổ trợ:</p>"
            )
        body_parts.append(_render_trace_html(report.dantzig, mode))
        if report.phase1_bland is not None and report.phase1_bland is not report.dantzig:
            body_parts.append("<h3>🔄 Bland (sau Dantzig xoay vòng ở Pha 1)</h3>")
            body_parts.append(_render_trace_html(report.phase1_bland, mode))
        body_parts.append("</div>")

        if report.status == "infeasible":
            body_parts.append(_conclusion_html(report, engine, mode))
            return _write_html(body_parts)

        if report.phase2_trace:
            body_parts.append("<div class='phase-section'>")
            body_parts.append("<h2>🎯 Pha 2 — Giải bài toán gốc</h2>")
            if has_aux:
                snap1 = report.dantzig.final_snapshot
                if snap1:
                    body_parts.append(_phase2_transition_aux_html(engine, snap1, mode))
            elif has_art:
                body_parts.append(
                    "<p class='note'>$\\min$ bổ trợ $= 0$, các biến độ nhiễu $= 0$ → loại khỏi từ vựng, "
                    "thay hàm mục tiêu gốc vào từ vựng hiện tại.</p>"
                )
            body_parts.append(_render_trace_html(report.phase2_trace, mode))
            body_parts.append("</div>")
    else:
        body_parts.append("<div class='phase-section'>")
        body_parts.append("<h2>🎯 Giải bài toán</h2>")
        body_parts.append(
            "<p class='note'>Tất cả $b_i \\geq 0$ → từ vựng xuất phát là chấp nhận được, không cần thực hiện Pha 1.</p>"
        )
        body_parts.append(_render_trace_html(report.dantzig, mode))
        if report.bland is not None and report.bland is not report.dantzig:
            body_parts.append("<h3>🔄 Bland (sau Dantzig xoay vòng)</h3>")
            body_parts.append(_render_trace_html(report.bland, mode))
        body_parts.append("</div>")

    # 4. Kết luận
    body_parts.append(_conclusion_html(report, engine, mode))

    return _write_html(body_parts)


def _write_html(body_parts: List[str]) -> str:
    """Ghép body, điền vào template, ghi ra file tạm, trả về path."""
    body = "\n".join(body_parts)
    html = _HTML_TEMPLATE.format(css=_CSS, body=body)
    fd, path = tempfile.mkstemp(suffix=".html", prefix="simplex_solution_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(html)
    return path