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
    if name in ("z", "δ", "w"):
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
    """Tạo <table> HTML cho một snapshot (bảng từ vựng đơn hình)."""
    names = snapshot.all_names
    n = len(names)

    # Header: tên biến phi cơ sở (hiển thị tên biến thay vì chỉ số)
    header_cells = ["<th class='row-label'></th>", "<th class='rhs-col'>Hằng số</th>"]
    for j, nm in enumerate(names):
        css = "pivot-col-head" if nm == entering_name else ""
        header_cells.append(f"<th class='{css}'>${_tex_var(nm)}$</th>")
    thead = f"<thead><tr>{''.join(header_cells)}</tr></thead>"

    rows_html: List[str] = []

    # Hàng mục tiêu
    obj_cells = [f"<td class='row-label'>$\\mathbf{{{_tex_var(snapshot.objective_label)}}}$</td>"]
    obj_cells.append(f"<td class='rhs-cell'>$= {_frac(snapshot.obj_const, mode)}$</td>")
    for j, nm in enumerate(names):
        c = snapshot.obj.get(j, Fraction(0))
        css = "pivot-col" if nm == entering_name else ""
        obj_cells.append(f"<td class='{css}'>${_frac(c, mode)}$</td>" if c != 0
                         else f"<td class='{css}'>$0$</td>")
    rows_html.append(f"<tr class='obj-row'>{''.join(obj_cells)}</tr>")

    # Hàng cơ sở
    for i, b in enumerate(snapshot.basis):
        b_name = names[b]
        is_pivot_row = (pivot_row is not None and i == pivot_row)
        row_css = "pivot-row" if is_pivot_row else ""
        cells = [f"<td class='row-label'>$\\mathbf{{{_tex_var(b_name)}}}$</td>"]
        cells.append(f"<td class='rhs-cell'>$= {_frac(snapshot.rhs[i], mode)}$</td>")
        for j, nm in enumerate(names):
            c = snapshot.rows[i].get(j, Fraction(0))
            cell_css = ""
            if nm == entering_name and is_pivot_row:
                cell_css = "pivot-cell"
            elif nm == entering_name:
                cell_css = "pivot-col"
            elif is_pivot_row:
                cell_css = "pivot-row"
            cells.append(f"<td class='{cell_css}'>${_frac(c, mode)}$</td>" if c != 0
                         else f"<td class='{cell_css}'>$0$</td>")
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

    lines.append(f"<p class='note-rule'>⚙️ <b>Quy tắc {rule}</b></p>")
    if step.entering is not None:
        coeff = snapshot.obj.get(step.entering, Fraction(0))
        if step.method == "dantzig":
            lines.append(f"<p>Chọn <b>${enter}$</b> vì có hệ số nhỏ nhất "
                         f"$= {_frac(coeff, mode)}$ trong hàng mục tiêu.</p>")
        else:
            lines.append(f"<p>Bland: chọn <b>${enter}$</b> (chỉ số nhỏ nhất trong các biến cải thiện).</p>")
        lines.append(f"<p>$\\Rightarrow$ Biến vào: ${enter}$</p>")

    if step.ratios:
        lines.append(f"<p>Bảng tỉ số $\\theta$ tại cột ${enter}$:</p>")
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
            parts.append("<p class='note'>Từ vựng ban đầu (không cần xoay):</p>")
            parts.append(_snapshot_table(trace.final_snapshot, mode))
        return "".join(parts)

    for step in trace.steps:
        title = "Từ vựng ban đầu" if step.iteration == 1 else f"Bước {step.iteration} — trước xoay"
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
        parts.append("<p class='success'>✅ Tất cả hệ số cải thiện ≥ 0 → Tối ưu.</p>")
    elif trace.status == "unbounded":
        parts.append("<p class='warn'>⚠️ Bài toán không giới nội (unbounded).</p>")
    elif trace.status == "cycle":
        parts.append("<p class='warn'>🔄 Phát hiện xoay vòng (cycling) → chuyển sang Bland.</p>")

    return "".join(parts)


# ---------------------------------------------------------------------------
# Phần bài toán gốc + chuẩn hóa
# ---------------------------------------------------------------------------

def _problem_html(engine, mode: str) -> str:
    prob = engine.problem
    n = len(prob.obj_coeffs)
    names_orig = [f"x_{{{i+1}}}" for i in range(n)]

    def expr_orig(coeffs):
        parts = []
        for c, nm in zip(coeffs, names_orig):
            if c == 0:
                continue
            t = _term(c, f"x{nm[2:-1]}", mode)   # strip the braces for _term then re-tex
            parts.append(t)
        if not parts:
            return "0"
        return " ".join(parts).lstrip("+").strip()

    # Hàm mục tiêu
    obj_expr = expr_orig(prob.obj_coeffs)
    sense_label = "\\max" if prob.objective_sense == "max" else "\\min"
    lines = [f"$${sense_label}\\; Z = {obj_expr}$$"]

    # Ràng buộc
    con_lines = []
    for i, cons in enumerate(prob.constraints):
        lhs = expr_orig(cons["coeffs"])
        s = cons["sense"]
        rhs = _frac(Fraction(cons["rhs"]), mode)
        s_tex = {"≤": "\\leq", "≥": "\\geq", "=": "="}.get(s, s)
        con_lines.append(f"\\quad {lhs} {s_tex} {rhs}")

    # Điều kiện dấu: thêm vào cuối cases (bỏ biến tự do vì không cần ghi)
    for i, sg in enumerate(prob.var_signs):
        nm = f"x_{{{i+1}}}"
        if sg == "≥0":
            con_lines.append(f"\\quad {nm} \\geq 0")
        elif sg == "≤0":
            con_lines.append(f"\\quad {nm} \\leq 0")
        # tự do: không ghi gì

    con_block = " \\\\\\\\\\n".join(con_lines)
    constraint_tex = f"$$\\\\begin{{cases}}\\n{con_block}\\n\\\\end{{cases}}$$"

    return "".join(lines) + constraint_tex


def _standardization_html(engine, mode: str) -> str:
    lines = engine.standardization_lines
    # Mỗi dòng là text thuần, chỉ cần wrap vào <pre> hoặc escape rồi show
    items = []
    for ln in lines:
        if not ln.strip():
            items.append("<br>")
        else:
            # Escape HTML nhưng giữ ký tự toán
            safe = ln.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            items.append(f"<p class='std-line'>{safe}</p>")
    return "".join(items)


# ---------------------------------------------------------------------------
# Kết luận cuối
# ---------------------------------------------------------------------------

def _conclusion_html(report: SolveReport, engine, mode: str) -> str:
    from utils import fmt_num
    parts: List[str] = []

    status = report.status
    if status == "infeasible":
        parts.append("<div class='conclusion warn-box'><h3>KẾT LUẬN: Vô nghiệm</h3>"
                     "<p>Biến phụ $x_0$ còn trong cơ sở sau Pha 1 → Bài toán vô nghiệm.</p></div>")
        return "".join(parts)

    if status in ("unbounded",):
        parts.append("<div class='conclusion warn-box'><h3>KẾT LUẬN: Không giới nội</h3>"
                     "<p>Không tìm được nghiệm hữu hạn tối ưu.</p></div>")
        return "".join(parts)

    if status == "cycle":
        parts.append("<div class='conclusion warn-box'><h3>KẾT LUẬN: Xoay vòng</h3>"
                     "<p>Cả Dantzig và Bland đều phát hiện xoay vòng.</p></div>")
        return "".join(parts)

    # Optimal
    obj_std = report.objective_std or Fraction(0)
    obj_orig = report.objective_orig or Fraction(0)
    method_label = report.used_method.upper()

    parts.append(f"<div class='conclusion success-box'>")
    parts.append(f"<h3>KẾT LUẬN: Tối ưu ({method_label})</h3>")

    if report.multiple_optimal and report.multiple_optimal_vars:
        parts.append("<p class='warn'>⚠️ Bài toán có <b>vô số nghiệm tối ưu</b>.</p>")
        free_idx = report.multiple_optimal_vars[0]
        snap = (report.phase2_trace.final_snapshot if report.phase2_trace and report.phase2_trace.final_snapshot
                else report.dantzig.final_snapshot)
        if snap:
            param = _tex_var(snap.all_names[free_idx])
            parts.append(f"<p>Tham số tự do: ${param} \\geq 0$</p>")
            parts.append(f"<p>$z^* = {_frac(snap.obj_const, mode)}$</p>")
            parts.append("<p>Nghiệm tổng quát:</p><ul>")
            bp = {b: i for i, b in enumerate(snap.basis)}
            for orig_idx, mapping in enumerate(engine.variable_mapping):
                const = Fraction(0)
                terms = []
                for si, mc in mapping:
                    if si in bp:
                        r = bp[si]
                        const += mc * snap.rhs[r]
                        coef_fv = snap.rows[r].get(free_idx, Fraction(0))
                        if coef_fv != 0:
                            terms.append((mc * coef_fv, snap.all_names[free_idx]))
                    elif si == free_idx:
                        terms.append((mc, snap.all_names[free_idx]))
                rhs_parts = [_frac(const, mode)] if const != 0 or not terms else []
                for cf, nm in terms:
                    t = _term(cf, nm, mode)
                    rhs_parts.append(t)
                rhs_str = " ".join(rhs_parts).lstrip("+").strip() or "0"
                parts.append(f"<li>$x_{{{orig_idx+1}}} = {rhs_str}$</li>")
            parts.append("</ul>")
    else:
        parts.append(f"<p>$z^*$ (dạng chuẩn min) $= {_frac(obj_std, mode)}$</p>")
        parts.append(f"<p>Giá trị mục tiêu gốc $= {_frac(obj_orig, mode)}$</p>")
        parts.append("<p><b>Nghiệm tối ưu:</b></p><ul>")
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
  <h1>Bài toán Quy hoạch tuyến tính — Phương pháp Đơn hình</h1>
  <p>Xuất từ ứng dụng SimplexApp &nbsp;·&nbsp; Hiển thị LaTeX với KaTeX</p>
</div>
<div class="container">
{body}
</div>
</body>
</html>"""


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
            body_parts.append("<p class='note'>Tồn tại $b_i &lt; 0$ → Giải pha 1 bằng biến phụ $x_0$.</p>")
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
            body_parts.append("<h2>🎯 Pha 2</h2>")
            body_parts.append(_render_trace_html(report.phase2_trace, mode))
            body_parts.append("</div>")
    else:
        body_parts.append("<div class='phase-section'>")
        body_parts.append("<h2>🎯 Pha 2 (Giải trực tiếp)</h2>")
        body_parts.append("<p class='note'>$b_i \\geq 0$ với mọi $i$ → không cần Pha 1.</p>")
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