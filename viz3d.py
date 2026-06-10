
from __future__ import annotations

import math
import itertools
from fractions import Fraction
from typing import Any, Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import messagebox, ttk

from utils import fmt_num, fr, sense_to_standard
from models import ProblemData, SolveReport, SolveTrace, Snapshot


# ══════════════════════════════════════════════════════════════════
#  Hàm tiện ích chung
# ══════════════════════════════════════════════════════════════════

def _halfspace_ok_2d(x: float, y: float,
                     halfplanes: List[Tuple], tol: float = 1e-7) -> bool:
    for a, b, c, sense, _ in halfplanes:
        lhs = float(a)*x + float(b)*y
        cc = float(c)
        if sense == "≤" and lhs > cc + tol:
            return False
        if sense == "≥" and lhs < cc - tol:
            return False
        if sense == "=" and abs(lhs - cc) > tol:
            return False
    return True


def _halfspace_feasible(x: float, y: float, z: float,
                        planes: List[Tuple], tol: float = 1e-7) -> bool:
    for a, b, c, d, sense in planes:
        lhs = a*x + b*y + c*z
        if sense == "≤" and lhs > d + tol:
            return False
        if sense == "≥" and lhs < d - tol:
            return False
        if sense == "=" and abs(lhs - d) > tol:
            return False
    return True


def _intersect_3planes(p1, p2, p3):
    (a1, b1, c1, d1, _) = p1
    (a2, b2, c2, d2, _) = p2
    (a3, b3, c3, d3, _) = p3
    det = (a1*(b2*c3 - b3*c2)
           - b1*(a2*c3 - a3*c2)
           + c1*(a2*b3 - a3*b2))
    if abs(det) < 1e-12:
        return None
    x = (d1*(b2*c3 - b3*c2) - b1*(d2*c3 - d3*c2) + c1*(d2*b3 - d3*b2)) / det
    y = (a1*(d2*c3 - d3*c2) - d1*(a2*c3 - a3*c2) + c1*(a2*d3 - a3*d2)) / det
    z = (a1*(b2*d3 - b3*d2) - b1*(a2*d3 - a3*d2) + d1*(a2*b3 - a3*b2)) / det
    return x, y, z


def _dedup3(pts, eps=1e-6):
    unique = []
    for p in pts:
        if not any(abs(p[0]-q[0]) < eps and abs(p[1]-q[1]) < eps
                   and abs(p[2]-q[2]) < eps for q in unique):
            unique.append(p)
    return unique


# ══════════════════════════════════════════════════════════════════
#  Trích xuất đường đi simplex từ SolveTrace
# ══════════════════════════════════════════════════════════════════

def _extract_simplex_path_2d(trace: SolveTrace, engine,
                              n_orig: int) -> List[Tuple[float, float]]:

    if trace is None:
        return []
    path: List[Tuple[float, float]] = []

    def _snap_to_xy(snap: Snapshot) -> Optional[Tuple[float, float]]:
        if snap is None:
            return None
        std_vals = {i: Fraction(0) for i in range(len(engine.std_names))}
        for i, b in enumerate(snap.basis):
            if b < len(engine.std_names):
                std_vals[b] = snap.rhs[i]
        orig_vals: Dict[int, Fraction] = {}
        for orig_idx, mapping in enumerate(engine.variable_mapping):
            val = Fraction(0)
            for k, coef in mapping:
                val += coef * std_vals.get(k, Fraction(0))
            orig_vals[orig_idx] = val
        if 0 in orig_vals and 1 in orig_vals:
            return (float(orig_vals[0]), float(orig_vals[1]))
        return None

    seen_pts: List[Tuple[float, float]] = []

    def add(pt):
        if pt is None:
            return
        # Bỏ trùng liền kề
        if seen_pts and abs(seen_pts[-1][0]-pt[0]) < 1e-9 and abs(seen_pts[-1][1]-pt[1]) < 1e-9:
            return
        seen_pts.append(pt)

    if trace.steps:
        add(_snap_to_xy(trace.steps[0].before))
        for step in trace.steps:
            if step.after is not None:
                add(_snap_to_xy(step.after))
    elif trace.final_snapshot is not None:
        add(_snap_to_xy(trace.final_snapshot))

    return seen_pts


def _extract_simplex_path_3d(trace: SolveTrace, engine) -> List[Tuple[float, float, float]]:

    if trace is None:
        return []

    def _snap_to_xyz(snap: Snapshot) -> Optional[Tuple[float, float, float]]:
        if snap is None:
            return None
        std_vals = {i: Fraction(0) for i in range(len(engine.std_names))}
        for i, b in enumerate(snap.basis):
            if b < len(engine.std_names):
                std_vals[b] = snap.rhs[i]
        orig_vals: Dict[int, Fraction] = {}
        for orig_idx, mapping in enumerate(engine.variable_mapping):
            val = Fraction(0)
            for k, coef in mapping:
                val += coef * std_vals.get(k, Fraction(0))
            orig_vals[orig_idx] = val
        if 0 in orig_vals and 1 in orig_vals and 2 in orig_vals:
            return (float(orig_vals[0]), float(orig_vals[1]), float(orig_vals[2]))
        return None

    seen: List[Tuple[float, float, float]] = []

    def add(pt):
        if pt is None:
            return
        if seen and all(abs(seen[-1][i]-pt[i]) < 1e-9 for i in range(3)):
            return
        seen.append(pt)

    if trace.steps:
        add(_snap_to_xyz(trace.steps[0].before))
        for step in trace.steps:
            if step.after is not None:
                add(_snap_to_xyz(step.after))
    elif trace.final_snapshot is not None:
        add(_snap_to_xyz(trace.final_snapshot))

    return seen


def _get_combined_trace(report: SolveReport,
                        report_bland=None):
    def combine(trace_a, trace_b):
        if trace_a is None:
            return trace_b
        if trace_b is None:
            return trace_a
        combined_steps = list(trace_a.steps) + list(trace_b.steps)
        return SolveTrace(
            status=trace_b.status,
            steps=combined_steps,
            final_snapshot=trace_b.final_snapshot,
            degenerate_steps=trace_a.degenerate_steps + trace_b.degenerate_steps,
            cycle_detected=trace_b.cycle_detected,
            infeasible=trace_b.infeasible,
            unbounded=trace_b.unbounded,
            multiple_optimal=trace_b.multiple_optimal,
        )

    def _is_phase1(trace) -> bool:
        if trace is None:
            return False
        return bool(trace.steps) and trace.steps[0].phase == 1

    # ── Trace Dantzig ────────────────────────────────────────────────────
    if report.phase2_dantzig is not None:
        # Dantzig cycle ở pha 2
        trace_d = combine(report.dantzig, report.phase2_dantzig)
    elif report.phase2_trace is not None and _is_phase1(report.dantzig):
        # Có pha 1 + pha 2, dùng Dantzig
        trace_d = combine(report.dantzig, report.phase2_trace)
    else:
        trace_d = report.dantzig

    # ── Trace Bland ──────────────────────────────────────────────────────
    # Ưu tiên 1: report_bland là engine riêng chạy Bland — nguồn chính xác nhất
    if report_bland is not None:
        rb = report_bland
        if rb.phase2_trace is not None and _is_phase1(rb.dantzig):
            trace_b = combine(rb.dantzig, rb.phase2_trace)
        elif rb.phase2_dantzig is not None:
            trace_b = combine(rb.dantzig, rb.phase2_dantzig)
        else:
            trace_b = rb.dantzig
        return trace_d, trace_b

    # Ưu tiên 2: report.bland (khi Dantzig cycle và Bland thay thế pha 2)
    if report.bland is not None:
        trace_b = report.bland
        if report.phase1_bland is not None:
            trace_b = combine(report.phase1_bland, trace_b)
        return trace_d, trace_b

    # Ưu tiên 3: used_method == "bland" → phase2_trace chính là Bland
    if report.used_method == "bland" and report.phase2_trace is not None:
        phase1_part = report.dantzig if _is_phase1(report.dantzig) else None
        trace_b = combine(phase1_part, report.phase2_trace)
        return trace_d, trace_b

    # Không tìm thấy trace Bland riêng
    return trace_d, None


# ══════════════════════════════════════════════════════════════════
#  Tìm đoạn tối ưu (vô số nghiệm) 2D
# ══════════════════════════════════════════════════════════════════

def _find_optimal_edge_2d(vertices_2d: List[Tuple[float, float, float]],
                           opt_val: float,
                           tol: float = 1e-6) -> List[Tuple[float, float]]:

    return [(x, y) for x, y, z in vertices_2d if abs(z - opt_val) < tol]


def _compute_optimal_face_3d(report: SolveReport,
                               engine,
                               vertices_3d: List[Tuple[float, float, float]],
                               c1: float, c2: float, c3: float,
                               maximize: bool
                               ) -> List[Tuple[float, float, float]]:
    import numpy as np

    TOL = 1e-6

    # ── Bước 1: Tính Z* ────────────────────────────────────────────────
    z_star = None
    if report and report.solution_orig:
        so = report.solution_orig
        z_star = (c1 * float(so.get(0, Fraction(0))) +
                  c2 * float(so.get(1, Fraction(0))) +
                  c3 * float(so.get(2, Fraction(0))))
    if z_star is None and vertices_3d:
        vals = [c1*x + c2*y + c3*z for x, y, z in vertices_3d]
        z_star = max(vals) if maximize else min(vals)
    if z_star is None:
        return []

    # ── Bước 2: Lấy đỉnh khả thi có Z ≈ Z* ───────────────────────────
    tol_z = max(TOL, 1e-4 * abs(z_star))
    opt_vertices = [(x, y, z) for x, y, z in vertices_3d
                    if abs(c1*x + c2*y + c3*z - z_star) <= tol_z]

    # ── Bước 3: Nếu không đủ đỉnh → grid sampling trên mặt phẳng Z=Z* ─
    if len(opt_vertices) < 2:
        try:
            # Xây halfplanes từ ràng buộc gốc + dấu biến
            halfplanes: List[Tuple[float, float, float, float, str]] = []
            for cons in engine.problem.constraints:
                coeffs = cons["coeffs"]
                a   = float(fr(coeffs[0])) if len(coeffs) > 0 else 0.0
                b   = float(fr(coeffs[1])) if len(coeffs) > 1 else 0.0
                c_c = float(fr(coeffs[2])) if len(coeffs) > 2 else 0.0
                d   = float(fr(cons["rhs"]))
                halfplanes.append((a, b, c_c, d, sense_to_standard(cons["sense"])))
            for i, sgn in enumerate(engine.problem.var_signs):
                row = [0., 0., 0.]
                row[i] = 1.
                if sgn == "≥0":   halfplanes.append((row[0], row[1], row[2], 0., "≥"))
                elif sgn == "≤0": halfplanes.append((row[0], row[1], row[2], 0., "≤"))

            def feasible_pt(x, y, z):
                for a, b, c_c, d, sense in halfplanes:
                    val = a*x + b*y + c_c*z
                    if sense == "≤" and val > d + TOL: return False
                    if sense == "≥" and val < d - TOL: return False
                    if sense == "=" and abs(val - d) > TOL: return False
                return True

            # Bounding box từ vertices_3d hoặc ước lượng từ nghiệm + RHS
            if vertices_3d:
                xs_r = [p[0] for p in vertices_3d]
                ys_r = [p[1] for p in vertices_3d]
                zs_r = [p[2] for p in vertices_3d]
                span = max(max(xs_r)-min(xs_r), max(ys_r)-min(ys_r),
                           max(zs_r)-min(zs_r), 2.0)
                cx_r = (max(xs_r)+min(xs_r))/2
                cy_r = (max(ys_r)+min(ys_r))/2
                cz_r = (max(zs_r)+min(zs_r))/2
            else:
                # vertices_3d rỗng = miền vô hạn (thường do ràng buộc "=")
                # Ước lượng bounding box từ:
                #   1) nghiệm engine (report.solution_orig) làm tâm
                #   2) max |RHS| của các ràng buộc làm span
                anchor = [0., 0., 0.]
                if report and report.solution_orig:
                    so = report.solution_orig
                    anchor = [float(so.get(0, Fraction(0))),
                              float(so.get(1, Fraction(0))),
                              float(so.get(2, Fraction(0)))]
                cx_r, cy_r, cz_r = anchor

                rhs_vals = [abs(float(fr(cons["rhs"])))
                            for cons in engine.problem.constraints
                            if cons["rhs"] != 0]
                base_span = max(rhs_vals) * 3 if rhs_vals else 10.0
                span = max(base_span, 2.0 * max(abs(cx_r), abs(cy_r), abs(cz_r), 1.0))
            pad = span * 1.2

            # Tìm 2 trục nằm trong mặt phẳng c1*x+c2*y+c3*z = z_star
            n0 = np.array([c1, c2, c3], dtype=float)
            n0_len = np.linalg.norm(n0)
            if n0_len < 1e-12:
                return []
            n0 /= n0_len

            # Trục u: chọn trục chuẩn ít song song với n0 nhất
            candidates = [np.array([1.,0.,0.]), np.array([0.,1.,0.]), np.array([0.,0.,1.])]
            best_u = min(candidates, key=lambda v: abs(float(np.dot(n0, v))))
            u_vec = best_u - float(np.dot(n0, best_u)) * n0
            u_vec /= (np.linalg.norm(u_vec) + 1e-12)
            w_vec = np.cross(n0, u_vec)
            w_vec /= (np.linalg.norm(w_vec) + 1e-12)

            origin = None
            for fix_dim in range(3):
                free_dims = [i for i in range(3) if i != fix_dim]
                coef_fix = [c1, c2, c3][fix_dim]
                if abs(coef_fix) < 1e-12:
                    continue
                fix_val = [cx_r, cy_r, cz_r][fix_dim]
                pt = [cx_r, cy_r, cz_r]
                pt[fix_dim] = (z_star - [c1, c2, c3][free_dims[0]]*pt[free_dims[0]]
                                       - [c1, c2, c3][free_dims[1]]*pt[free_dims[1]]) / coef_fix
                origin = np.array(pt, dtype=float)
                break
            if origin is None:
                return opt_vertices

            # Lưới tham số (s, t) → điểm 3D trên mặt phẳng
            N = 30
            ss = np.linspace(-pad, pad, N)
            tt = np.linspace(-pad, pad, N)
            S, T = np.meshgrid(ss, tt)
            S_flat = S.ravel()
            T_flat = T.ravel()

            sampled = []
            for s_val, t_val in zip(S_flat, T_flat):
                pt3 = origin + s_val * u_vec + t_val * w_vec
                x_p, y_p, z_p = float(pt3[0]), float(pt3[1]), float(pt3[2])
                if feasible_pt(x_p, y_p, z_p):
                    sampled.append((x_p, y_p, z_p))

            if len(sampled) >= 2:
                opt_vertices = sampled
        except Exception:
            pass

    if len(opt_vertices) < 2:
        return opt_vertices

    # ── Bước 4: Dedup ──────────────────────────────────────────────────
    deduped: List[Tuple[float, float, float]] = []
    for p in opt_vertices:
        if not any(abs(p[0]-q[0]) < 1e-5 and
                   abs(p[1]-q[1]) < 1e-5 and
                   abs(p[2]-q[2]) < 1e-5 for q in deduped):
            deduped.append(p)

    if len(deduped) < 2:
        return deduped

    # ── Bước 5: Phân loại đoạn thẳng vs mặt phẳng & sắp thứ tự ───────
    arr = np.array(deduped, dtype=float)

    if len(deduped) == 2:
        return deduped

    # Kiểm tra is_planar: có điểm nào không nằm trên đường thẳng nối 2 điểm xa nhất?
    max_dist = -1.0
    p0_idx, p1_idx = 0, 1
    n_pts = len(arr)
    for ii in range(n_pts):
        for jj in range(ii + 1, n_pts):
            dist = float(np.linalg.norm(arr[ii] - arr[jj]))
            if dist > max_dist:
                max_dist = dist
                p0_idx, p1_idx = ii, jj

    is_planar = False
    if max_dist > 1e-4:
        d0 = arr[p1_idx] - arr[p0_idx]
        d0_len = np.linalg.norm(d0)
        for ii in range(n_pts):
            if ii in (p0_idx, p1_idx):
                continue
            di = arr[ii] - arr[p0_idx]
            cp_len = float(np.linalg.norm(np.cross(d0, di))) / (d0_len + 1e-12)
            if cp_len > 1e-3:
                is_planar = True
                break

    if not is_planar:
        # Đoạn thẳng: chỉ cần 2 đầu mút xa nhất
        return [deduped[p0_idx], deduped[p1_idx]]

    # Mặt phẳng: sắp theo convex hull 2D trong mặt phẳng tối ưu
    center = arr.mean(axis=0)
    nv = np.array([c1, c2, c3], dtype=float)
    nv_len = np.linalg.norm(nv)
    if nv_len > 1e-10:
        nv /= nv_len
    u_v = arr[p1_idx] - arr[p0_idx]
    u_v /= (np.linalg.norm(u_v) + 1e-12)
    w_v = np.cross(nv, u_v)
    w_v /= (np.linalg.norm(w_v) + 1e-12)
    pts2d = np.array([
        (float(np.dot(p - center, u_v)),
         float(np.dot(p - center, w_v)))
        for p in arr
    ])
    try:
        from scipy.spatial import ConvexHull as _CH
        hull2 = _CH(pts2d)
        return [deduped[i] for i in hull2.vertices]
    except Exception:
        angles = [math.atan2(float(pts2d[i, 1]), float(pts2d[i, 0]))
                  for i in range(len(deduped))]
        return [deduped[i] for i in sorted(range(len(deduped)), key=lambda i: angles[i])]



# ══════════════════════════════════════════════════════════════════
#  Mixin 3D (gắn vào SimplexApp qua đa kế thừa)
# ══════════════════════════════════════════════════════════════════

class Viz3DMixin:

    # ------------------------------------------------------------------ #
    #  PUBLIC: Trực quan hóa 3 biến                                       #
    # ------------------------------------------------------------------ #
    def visualize_three_variable_problem(self) -> None:
        try:
            prob = self._collect_problem()
        except Exception as exc:
            messagebox.showerror("Trực quan hóa 3D", str(exc))
            return

        if len(prob.obj_coeffs) != 3:
            messagebox.showinfo(
                "Trực quan hóa 3D",
                "Tính năng này chỉ hỗ trợ đúng 3 biến x₁, x₂, x₃."
            )
            return

        try:
            import numpy as np
            import matplotlib
            matplotlib.use("TkAgg", force=True)
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from mpl_toolkits.mplot3d import Axes3D          # noqa: F401
            from mpl_toolkits.mplot3d.art3d import Poly3DCollection
        except Exception as exc:
            messagebox.showerror(
                "Trực quan hóa 3D",
                f"Không khởi tạo được thư viện:\n{exc}\n\nHãy cài: pip install matplotlib numpy"
            )
            return

        # ── Lấy kết quả từ engine (nếu có) ──────────────────────────────
        report: Optional[SolveReport] = self.last_report
        engine = report.engine if report else None
        status = report.status if report else "unknown"

        planes = self._build_planes_3d(prob)

        # ── Thêm bounding box nếu miền không có đỉnh cô lập ─────────────
        planes_draw, bbox_M, bbox_artificial = self._add_bounding_box(
            planes, prob, report)
        vertices = _dedup3(self._feasible_vertices_3d(planes_draw))

        c1 = float(prob.obj_coeffs[0])
        c2 = float(prob.obj_coeffs[1])
        c3 = float(prob.obj_coeffs[2])
        maximize = prob.objective_sense == "max"
        vv = [(x, y, z, c1*x + c2*y + c3*z) for x, y, z in vertices]

        # ── Xác định trạng thái từ engine ────────────────────────────────
        if status == "infeasible":
            optimal = None
            multi_pts: List[Tuple] = []
        elif status == "unbounded":
            optimal = None
            multi_pts = []
        elif status in ("optimal", "cycle") and vv:
            # Dùng kết quả engine nếu có
            if engine and report and report.solution_orig:
                so = report.solution_orig
                ox = float(so.get(0, Fraction(0)))
                oy = float(so.get(1, Fraction(0)))
                oz = float(so.get(2, Fraction(0)))
                opt_val = c1*ox + c2*oy + c3*oz
                optimal = (ox, oy, oz, opt_val)
            else:
                optimal = (max(vv, key=lambda t: t[3]) if maximize
                           else min(vv, key=lambda t: t[3]))
            # Vô số nghiệm: tính mặt/cạnh tối ưu
            # Dùng vertices bbox (đã có đủ đỉnh đại diện miền)
            if report and report.multiple_optimal and engine:
                multi_pts = _compute_optimal_face_3d(
                    report, engine, vertices, c1, c2, c3, maximize)
            else:
                multi_pts = []
        else:
            optimal = (max(vv, key=lambda t: t[3]) if maximize
                       else min(vv, key=lambda t: t[3])) if vv else None
            multi_pts = []

        # ── Trích xuất đường đi simplex ──────────────────────────────────
        path_d: List[Tuple[float, float, float]] = []
        path_b: List[Tuple[float, float, float]] = []
        if engine and report:
            report_bland = getattr(self, 'last_report_b', None)
            trace_d, trace_b = _get_combined_trace(report, report_bland)
            path_d = _extract_simplex_path_3d(trace_d, engine)
            path_b = _extract_simplex_path_3d(trace_b, report_bland.engine if (trace_b and report_bland) else engine) if trace_b else []

        # ── Dựng cửa sổ ──────────────────────────────────────────────────
        win = tk.Toplevel(self)
        win.title("Trực quan hóa bài toán 3 biến — 3D")
        win.geometry("1400x900")
        win.minsize(900, 600)
        try:
            win.state("zoomed")
        except Exception:
            try:
                win.attributes("-zoomed", True)
            except Exception:
                pass
        win.configure(bg="#0f172a")
        win.columnconfigure(0, weight=1)
        win.rowconfigure(0, weight=1)
        win.protocol("WM_DELETE_WINDOW", win.destroy)

        outer = tk.Frame(win, bg="#0f172a")
        outer.grid(row=0, column=0, sticky="nsew")
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)
        outer.columnconfigure(1, weight=0)

        from matplotlib.figure import Figure
        fig = Figure(figsize=(14, 9), dpi=100)
        fig.patch.set_facecolor("#0f172a")
        ax = fig.add_subplot(111, projection="3d")
        ax.set_facecolor("#0f172a")
        for pane in [ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane]:
            pane.fill = False
            pane.set_edgecolor("#334155")
        ax.tick_params(colors="#94a3b8", labelsize=8)
        ax.xaxis.label.set_color("#94a3b8")
        ax.yaxis.label.set_color("#94a3b8")
        ax.zaxis.label.set_color("#94a3b8")
        ax.set_xlabel("x₁", fontsize=11, labelpad=8)
        ax.set_ylabel("x₂", fontsize=11, labelpad=8)
        ax.set_zlabel("x₃", fontsize=11, labelpad=8)

        title_txt = self._3d_title(status, report)
        ax.set_title(title_txt, fontsize=12, fontweight="bold",
                     color="#e2e8f0", pad=12)

        self._draw_3d_scene(ax, planes_draw, vertices, vv, optimal, maximize, prob,
                            status=status, multi_pts=multi_pts,
                            path_d=path_d, path_b=path_b, report=report,
                            bbox_artificial=bbox_artificial, bbox_M=bbox_M)

        canvas = FigureCanvasTkAgg(fig, master=outer)
        canvas.draw()
        w = canvas.get_tk_widget()
        w.configure(bg="#0f172a", highlightthickness=0)
        w.grid(row=0, column=0, sticky="nsew")

        self._build_info_panel_3d(outer, prob, vertices, vv, optimal, maximize,
                                  status=status, multi_pts=multi_pts,
                                  path_d=path_d, path_b=path_b)

        ctrl = tk.Frame(win, bg="#1e293b")
        ctrl.grid(row=1, column=0, sticky="ew")
        self._build_3d_controls(ctrl, ax, canvas, fig)

        win.focus_force()

    # ------------------------------------------------------------------ #
    #  Tiêu đề cửa sổ 3D theo trạng thái                                 #
    # ------------------------------------------------------------------ #
    def _3d_title(self, status: str, report) -> str:
        if status == "infeasible":
            return "Miền chấp nhận được rỗng — Bài toán VÔ NGHIỆM"
        if status == "unbounded":
            return "Bài toán KHÔNG GIỚI NỘI — hàm mục tiêu tiến tới ±∞"
        if report and report.multiple_optimal:
            return "Miền chấp nhận được (3D) — VÔ SỐ NGHIỆM TỐI ƯU"
        return "Miền chấp nhận được (3D) & điểm tối ưu"

    # ------------------------------------------------------------------ #
    #  Build planes / feasible vertices 3D                                #
    # ------------------------------------------------------------------ #
    def _build_planes_3d(self, prob: ProblemData):
        planes = []
        for i, cons in enumerate(prob.constraints, start=1):
            a = float(fr(cons["coeffs"][0]))
            b = float(fr(cons["coeffs"][1]))
            c = float(fr(cons["coeffs"][2]))
            d = float(fr(cons["rhs"]))
            sense = sense_to_standard(cons["sense"])
            planes.append((a, b, c, d, sense, f"RB{i}"))

        signs = prob.var_signs
        if signs[0] == "≥0":
            planes.append((1, 0, 0, 0, "≥", "x₁ ≥ 0"))
        elif signs[0] == "≤0":
            planes.append((1, 0, 0, 0, "≤", "x₁ ≤ 0"))
        if signs[1] == "≥0":
            planes.append((0, 1, 0, 0, "≥", "x₂ ≥ 0"))
        elif signs[1] == "≤0":
            planes.append((0, 1, 0, 0, "≤", "x₂ ≤ 0"))
        if len(signs) > 2:
            if signs[2] == "≥0":
                planes.append((0, 0, 1, 0, "≥", "x₃ ≥ 0"))
            elif signs[2] == "≤0":
                planes.append((0, 0, 1, 0, "≤", "x₃ ≤ 0"))
        return planes

    def _feasible_vertices_3d(self, planes):
        hp = [(p[0], p[1], p[2], p[3], p[4]) for p in planes]
        vertices = []
        for i, j, k in itertools.combinations(range(len(hp)), 3):
            pt = _intersect_3planes(hp[i], hp[j], hp[k])
            if pt is None:
                continue
            x, y, z = pt
            if not all(math.isfinite(v) for v in (x, y, z)):
                continue
            if _halfspace_feasible(x, y, z, hp):
                vertices.append((x, y, z))
        return vertices

    def _add_bounding_box(self, planes: list, prob: ProblemData,
                          report) -> tuple:
        has_equality = any(p[4] == "=" for p in planes)
        if not has_equality:
            return planes, 0.0, False

        rhs_vals = [abs(float(fr(cons["rhs"])))
                    for cons in prob.constraints if cons["rhs"] != 0]
        sol_vals = []
        if report and report.solution_orig:
            so = report.solution_orig
            sol_vals = [abs(float(so.get(i, Fraction(0)))) for i in range(3)]
        base = max(rhs_vals + sol_vals + [1.0])
        M = max(base * 6, 20.0)

        planes_bounded = list(planes)
        signs = prob.var_signs

        axes = [
            ((1, 0, 0), "x₁"),
            ((0, 1, 0), "x₂"),
            ((0, 0, 1), "x₃"),
        ]
        for (ax_vec, name), sign in zip(axes, signs):
            a, b, c = ax_vec
            if sign == "≥0":
                planes_bounded.append((a, b, c,  M, "≤", f"{name}≤{M:.4g}"))
            elif sign == "≤0":
                planes_bounded.append((a, b, c, -M, "≥", f"{name}≥{-M:.4g}"))
            else:  # tự do
                planes_bounded.append((a, b, c,  M, "≤", f"{name}≤{M:.4g}"))
                planes_bounded.append((a, b, c, -M, "≥", f"{name}≥{-M:.4g}"))

        return planes_bounded, M, True

    # ------------------------------------------------------------------ #
    #  Vẽ cảnh 3D                                                         #
    # ------------------------------------------------------------------ #
    def _draw_3d_scene(self, ax, planes, vertices, vv, optimal, maximize, prob,
                       status="optimal", multi_pts=None, path_d=None, path_b=None,
                       report=None, bbox_artificial=False, bbox_M=0.0):
        import numpy as np
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection

        multi_pts = multi_pts or []
        path_d = path_d or []
        path_b = path_b or []
        mode = self.data_mode.get() if hasattr(self.data_mode, 'get') else self.data_mode
        c1f = float(prob.obj_coeffs[0])
        c2f = float(prob.obj_coeffs[1])
        c3f = float(prob.obj_coeffs[2])

        # ── Tính giới hạn trục ──────────────────────────────────────────
        all_pts = list(vertices)
        for p in path_d + path_b:
            all_pts.append(p)
        if multi_pts:
            for p in multi_pts:
                all_pts.append(p)
        if optimal:
            all_pts.append(optimal[:3])

        if all_pts:
            xs = [p[0] for p in all_pts]
            ys = [p[1] for p in all_pts]
            zs = [p[2] for p in all_pts]
        else:
            xs = ys = zs = [-3, 3]

        pad = max(1.0, (max(xs)-min(xs)+max(ys)-min(ys)+max(zs)-min(zs)) * 0.22)

        # Không giới nội: tính hướng mũi tên trước để mở rộng trục đúng
        _unb_dx = _unb_dy = _unb_dz = 0.0
        if status == "unbounded":
            _c1 = float(prob.obj_coeffs[0])
            _c2 = float(prob.obj_coeffs[1])
            _c3 = float(prob.obj_coeffs[2])
            _sign = 1 if maximize else -1
            _norm_c = math.sqrt(_c1**2 + _c2**2 + _c3**2)
            if _norm_c > 1e-10:
                _arrow_len = pad * 2.2
                _unb_dx = _sign * _c1 / _norm_c * _arrow_len
                _unb_dy = _sign * _c2 / _norm_c * _arrow_len
                _unb_dz = _sign * _c3 / _norm_c * _arrow_len

        # Gốc mũi tên
        if vertices:
            _cx = sum(p[0] for p in vertices) / len(vertices)
            _cy = sum(p[1] for p in vertices) / len(vertices)
            _cz = sum(p[2] for p in vertices) / len(vertices)
        else:
            _cx = _cy = _cz = 0.0

        xlo = min(xs) - pad
        xhi = max(xs) + pad
        ylo = min(ys) - pad
        yhi = max(ys) + pad
        zlo = min(zs) - pad
        zhi = max(zs) + pad

        if status == "unbounded" and _norm_c > 1e-10:
            # Đảm bảo đuôi mũi tên nằm trong bounds
            extra = pad * 0.5
            if _unb_dx > 0: xhi = max(xhi, _cx + _unb_dx * 1.15 + extra)
            elif _unb_dx < 0: xlo = min(xlo, _cx + _unb_dx * 1.15 - extra)
            if _unb_dy > 0: yhi = max(yhi, _cy + _unb_dy * 1.15 + extra)
            elif _unb_dy < 0: ylo = min(ylo, _cy + _unb_dy * 1.15 - extra)
            if _unb_dz > 0: zhi = max(zhi, _cz + _unb_dz * 1.15 + extra)
            elif _unb_dz < 0: zlo = min(zlo, _cz + _unb_dz * 1.15 - extra)

        ax.set_xlim(xlo, xhi)
        ax.set_ylim(ylo, yhi)
        ax.set_zlim(zlo, zhi)

        palette = ["#3b82f6", "#a855f7", "#10b981",
                   "#f59e0b", "#ef4444", "#06b6d4",
                   "#ec4899", "#84cc16"]
        hp = [(p[0], p[1], p[2], p[3], p[4]) for p in planes]

        # ── Vẽ convex hull miền khả thi ──────────────────────────────────
        if vertices and len(vertices) >= 4:
            try:
                from scipy.spatial import ConvexHull
                arr = np.array(vertices)
                hull = ConvexHull(arr)
                faces = [arr[s] for s in hull.simplices]
                poly = Poly3DCollection(
                    faces, alpha=0.15, linewidth=0.6,
                    facecolor="#93c5fd", edgecolor="#3b82f6"
                )
                ax.add_collection3d(poly)
            except Exception:
                pass

        # ── Vẽ các mặt phẳng ràng buộc ──────────────────────────────────
        for idx, (a, b, c, d, sense, label) in enumerate(planes):
            color = palette[idx % len(palette)]
            self._draw_plane_patch(ax, a, b, c, d, color,
                                   xlo, xhi, ylo, yhi, zlo, zhi, label, idx)

        # ── Vẽ các đỉnh khả thi ─────────────────────────────────────────
        if vertices:
            xs_v = [p[0] for p in vertices]
            ys_v = [p[1] for p in vertices]
            zs_v = [p[2] for p in vertices]
            ax.scatter(xs_v, ys_v, zs_v,
                       s=48, c="#60a5fa", edgecolors="white",
                       linewidths=0.8, zorder=5, depthshade=True,
                       label="Đỉnh khả thi")
            for idx2, (x, y, z, val) in enumerate(vv, start=1):
                ax.text(x, y, z,
                        f" {idx2}", fontsize=7, color="#94a3b8",
                        bbox=dict(boxstyle="round,pad=0.12",
                                  fc="#1e3a5f", ec="#3b82f6", alpha=0.75))


        # ── Cảnh báo bounding box nhân tạo ──────────────────────────────
        if bbox_artificial and status not in ("infeasible", "unbounded"):
            ax.text2D(0.02, 0.97,
                      f"⚠ Miền khả thi không bị chặn\n"
                      f"(đang hiển thị trong bounding box M={bbox_M:.4g})",
                      transform=ax.transAxes, fontsize=9,
                      ha="left", va="top", color="#fbbf24",
                      bbox=dict(boxstyle="round,pad=0.4",
                                fc="#1c1917", ec="#f59e0b", alpha=0.90))

        # ── Trường hợp đặc biệt ─────────────────────────────────────────

        # Không giới nội: mũi tên hướng tối ưu (dùng lại biến đã tính ở trên)
        if status == "unbounded":
            if _norm_c > 1e-10:
                # Vẽ 2 quiver liên tiếp để tạo hiệu ứng "tiến tới vô cùng"
                ax.quiver(_cx, _cy, _cz,
                          _unb_dx, _unb_dy, _unb_dz,
                          color="#f87171", linewidth=2.8,
                          arrow_length_ratio=0.18,
                          label="Hướng → ±∞ (không giới nội)")
                ax.quiver(_cx + _unb_dx * 0.7,
                          _cy + _unb_dy * 0.7,
                          _cz + _unb_dz * 0.7,
                          _unb_dx * 0.4, _unb_dy * 0.4, _unb_dz * 0.4,
                          color="#fca5a5", linewidth=1.8,
                          arrow_length_ratio=0.22)
                ax.text(_cx + _unb_dx * 1.05,
                        _cy + _unb_dy * 1.05,
                        _cz + _unb_dz * 1.05,
                        "  → ∞\n(không giới nội)",
                        fontsize=10, color="#f87171", fontweight="bold",
                        bbox=dict(boxstyle="round,pad=0.25",
                                  fc="#1c1917", ec="#f87171", alpha=0.92))

        # Vô số nghiệm: vẽ đoạn / mặt tối ưu
        elif multi_pts and len(multi_pts) >= 2:
            mxs = [p[0] for p in multi_pts]
            mys = [p[1] for p in multi_pts]
            mzs = [p[2] for p in multi_pts]
            is_planar = False
            ordered_pts = list(multi_pts)

            arr_m = np.array(multi_pts, dtype=float)
            d0 = arr_m[-1] - arr_m[0]
            d0_len = np.linalg.norm(d0)

            if len(multi_pts) >= 3:
                try:
                    max_dist = -1.0
                    best_pair = (0, 1)
                    n_pts = len(arr_m)
                    for ii in range(n_pts):
                        for jj in range(ii + 1, n_pts):
                            dist = np.linalg.norm(arr_m[ii] - arr_m[jj])
                            if dist > max_dist:
                                max_dist = dist
                                best_pair = (ii, jj)
                    if max_dist > 1e-4:
                        p0_idx, p1_idx = best_pair
                        d0 = arr_m[p1_idx] - arr_m[p0_idx]
                        d0_len = max_dist
                        for ii in range(n_pts):
                            if ii == p0_idx or ii == p1_idx:
                                continue
                            di = arr_m[ii] - arr_m[p0_idx]
                            cp = np.cross(d0, di)
                            cp_len = np.linalg.norm(cp)
                            perp_dist = cp_len / d0_len 
                            if perp_dist > 1e-3:
                                is_planar = True
                                break

                    if is_planar:
                        center_m = arr_m.mean(axis=0)
                        norm_v = np.array([c1f, c2f, c3f], dtype=float)
                        nlen_v = np.linalg.norm(norm_v)
                        if nlen_v > 1e-10:
                            norm_v /= nlen_v
                        u_v = d0 / d0_len
                        w_v = np.cross(norm_v, u_v)
                        w_v /= (np.linalg.norm(w_v) + 1e-12)
                        pts2d = np.array([
                            (float(np.dot(p - center_m, u_v)),
                             float(np.dot(p - center_m, w_v)))
                            for p in arr_m
                        ])
                        try:
                            from scipy.spatial import ConvexHull as _CH
                            hull2 = _CH(pts2d)
                            ordered_pts = [multi_pts[i] for i in hull2.vertices]
                        except Exception:
                            angles = [math.atan2(float(pts2d[i, 1]),
                                                 float(pts2d[i, 0]))
                                      for i in range(len(multi_pts))]
                            ordered_pts = [multi_pts[i] for i in
                                           sorted(range(len(multi_pts)),
                                                  key=lambda i: angles[i])]
                except Exception:
                    is_planar = False

            if is_planar:
                ox_list = [p[0] for p in ordered_pts]
                oy_list = [p[1] for p in ordered_pts]
                oz_list = [p[2] for p in ordered_pts]

                poly_opt = Poly3DCollection(
                    [list(zip(ox_list, oy_list, oz_list))],
                    alpha=0.60, linewidth=0,
                    facecolor="#fbbf24")
                ax.add_collection3d(poly_opt)
                ox_loop = ox_list + [ox_list[0]]
                oy_loop = oy_list + [oy_list[0]]
                oz_loop = oz_list + [oz_list[0]]
                ax.plot(ox_loop, oy_loop, oz_loop,
                        color="#f59e0b", linewidth=2.5, alpha=0.95,
                        zorder=9, label="Mặt tối ưu (vô số nghiệm)")

 
                ax.scatter(mxs, mys, mzs,
                           s=160, marker="*", c="#fbbf24",
                           edgecolors="#f59e0b", linewidths=1,
                           zorder=10, depthshade=False,
                           label="Đỉnh biên miền tối ưu")

                bx, by, bz = ordered_pts[0]
                opt_z_val = c1f*bx + c2f*by + c3f*bz
                ax.text(bx, by, bz,
                        f"  ★ Mặt tối ưu\n  Vô số nghiệm\n  Z* = {opt_z_val:.4g}",
                        fontsize=9, fontweight="bold", color="#fbbf24",
                        bbox=dict(boxstyle="round,pad=0.3",
                                  fc="#1c1917", ec="#f59e0b", alpha=0.96))

            else:
                try:
                    if d0_len > 1e-4:
                        projs = [float(np.dot(p, d0)) for p in arr_m]
                        sorted_pts = [multi_pts[i] for i in
                                      sorted(range(len(multi_pts)),
                                             key=lambda i: projs[i])]
                    else:
                        sorted_pts = multi_pts
                except Exception:
                    sorted_pts = multi_pts

                lxs = [p[0] for p in sorted_pts]
                lys = [p[1] for p in sorted_pts]
                lzs = [p[2] for p in sorted_pts]
                ax.plot(lxs, lys, lzs,
                        color="#fbbf24", linewidth=7, alpha=0.92,
                        solid_capstyle="round", zorder=9,
                        label="Đoạn tối ưu (vô số nghiệm)")

                ax.scatter([lxs[0], lxs[-1]], [lys[0], lys[-1]], [lzs[0], lzs[-1]],
                           s=200, marker="*", c="#fbbf24",
                           edgecolors="#f59e0b", linewidths=1,
                           zorder=10, depthshade=False,
                           label="Đầu mút đoạn tối ưu")

                bx, by, bz = sorted_pts[0]
                opt_z_val = c1f*bx + c2f*by + c3f*bz
                ax.text(bx, by, bz,
                        f"  ★ Đoạn tối ưu\n  Vô số nghiệm\n  Z* = {opt_z_val:.4g}",
                        fontsize=9, fontweight="bold", color="#fbbf24",
                        bbox=dict(boxstyle="round,pad=0.3",
                                  fc="#1c1917", ec="#f59e0b", alpha=0.96))

        # Nghiệm tối ưu duy nhất
        elif optimal is not None and status not in ("infeasible", "unbounded"):
            bx, by, bz, bval = optimal
            ax.scatter([bx], [by], [bz],
                       s=260, marker="*", c="#f59e0b",
                       edgecolors="#fbbf24", linewidths=1.2,
                       zorder=10, depthshade=False, label="Điểm tối ưu")
            ax.text(bx, by, bz,
                    f"  ★ tối ưu\n  ({bx:.3g}, {by:.3g}, {bz:.3g})\n  z={bval:.3g}",
                    fontsize=9, fontweight="bold", color="#fbbf24",
                    bbox=dict(boxstyle="round,pad=0.3",
                              fc="#1c1917", ec="#f59e0b", alpha=0.96))

        if status == "infeasible":
            ax.text2D(0.5, 0.5,
                      "Miền khả thi rỗng\nBài toán VÔ NGHIỆM",
                      transform=ax.transAxes, fontsize=16,
                      ha="center", va="center", color="#f87171",
                      fontweight="bold",
                      bbox=dict(boxstyle="round,pad=0.5",
                                fc="#1c1917", ec="#f87171", alpha=0.92))

        # ── Vẽ đường đi simplex ─────────────────────────────────────────
        # Dantzig
        if len(path_d) >= 2:
            xs_d = [p[0] for p in path_d]
            ys_d = [p[1] for p in path_d]
            zs_d = [p[2] for p in path_d]
            ax.plot(xs_d, ys_d, zs_d,
                    color="#f97316", linewidth=2.2, alpha=0.90,
                    marker="o", markersize=6, markerfacecolor="#f97316",
                    markeredgecolor="white", markeredgewidth=0.8,
                    zorder=8, label="Đường đi Dantzig")
            for k, (px, py, pz) in enumerate(path_d):
                ax.text(px, py, pz,
                        f" D{k}", fontsize=7, color="#f97316",
                        bbox=dict(boxstyle="round,pad=0.1",
                                  fc="#1c1917", ec="#f97316", alpha=0.82))

        # Bland
        if len(path_b) >= 2:
            xs_b = [p[0] for p in path_b]
            ys_b = [p[1] for p in path_b]
            zs_b = [p[2] for p in path_b]
            ax.plot(xs_b, ys_b, zs_b,
                    color="#22d3ee", linewidth=2.2, alpha=0.90,
                    marker="s", markersize=6, markerfacecolor="#22d3ee",
                    markeredgecolor="white", markeredgewidth=0.8,
                    zorder=8, linestyle="--",
                    label="Đường đi Bland")
            for k, (px, py, pz) in enumerate(path_b):
                ax.text(px, py, pz,
                        f" B{k}", fontsize=7, color="#22d3ee",
                        bbox=dict(boxstyle="round,pad=0.1",
                                  fc="#1c1917", ec="#22d3ee", alpha=0.82))

        # ── Hướng tối ưu (mũi tên) ──────────────────────────────────────
        if status not in ("unbounded", "infeasible") and vertices:
            c1f = float(prob.obj_coeffs[0])
            c2f = float(prob.obj_coeffs[1])
            c3f = float(prob.obj_coeffs[2])
            norm_c = math.sqrt(c1f**2 + c2f**2 + c3f**2)
            if norm_c > 1e-10:
                cx = sum(p[0] for p in vertices) / len(vertices)
                cy = sum(p[1] for p in vertices) / len(vertices)
                cz = sum(p[2] for p in vertices) / len(vertices)
                sign = 1 if maximize else -1
                scale = pad * 0.6 / norm_c
                dx, dy, dz = sign*c1f*scale, sign*c2f*scale, sign*c3f*scale
                ax.quiver(cx, cy, cz, dx, dy, dz,
                          color="#f87171", linewidth=1.8,
                          arrow_length_ratio=0.25,
                          label="Hướng tối ưu hóa", alpha=0.75)

        handles, labels = ax.get_legend_handles_labels()
        if handles:
            ax.legend(handles, labels, loc="upper left", fontsize=7,
                      facecolor="#1e293b", edgecolor="#334155",
                      labelcolor="#e2e8f0", framealpha=0.85)

    # ------------------------------------------------------------------ #
    #  Vẽ mặt phẳng ràng buộc 3D                                         #
    # ------------------------------------------------------------------ #
    def _draw_plane_patch(self, ax, a, b, c, d, color,
                          xlo, xhi, ylo, yhi, zlo, zhi, label, idx):
        import numpy as np
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection

        norm = math.sqrt(a**2 + b**2 + c**2)
        if norm < 1e-12:
            return
        try:
            res = 8
            if abs(c) > max(abs(a), abs(b)) * 0.5:
                xs = np.linspace(xlo, xhi, res)
                ys = np.linspace(ylo, yhi, res)
                X, Y = np.meshgrid(xs, ys)
                Z = (d - a*X - b*Y) / c
                mask = (Z >= zlo - 0.01) & (Z <= zhi + 0.01)
                if not mask.any():
                    return
                Z = np.clip(Z, zlo, zhi)
            elif abs(b) > abs(a) * 0.5:
                xs = np.linspace(xlo, xhi, res)
                zs = np.linspace(zlo, zhi, res)
                X, Z = np.meshgrid(xs, zs)
                Y = (d - a*X - c*Z) / b
                mask = (Y >= ylo - 0.01) & (Y <= yhi + 0.01)
                if not mask.any():
                    return
                Y = np.clip(Y, ylo, yhi)
            else:
                zs = np.linspace(zlo, zhi, res)
                ys = np.linspace(ylo, yhi, res)
                Y, Z = np.meshgrid(ys, zs)
                X = (d - b*Y - c*Z) / a
                mask = (X >= xlo - 0.01) & (X <= xhi + 0.01)
                if not mask.any():
                    return
                X = np.clip(X, xlo, xhi)

            ax.plot_surface(X, Y, Z, alpha=0.08, color=color,
                            linewidth=0, antialiased=True, zorder=1)

            if abs(c) > max(abs(a), abs(b)) * 0.5:
                for xi in [xlo, xhi]:
                    ys2 = np.linspace(ylo, yhi, 30)
                    zs2 = np.clip((d - a*xi - b*ys2) / c, zlo, zhi)
                    ax.plot([xi]*30, ys2, zs2, color=color,
                            linewidth=1.4, alpha=0.75)

            xm = (xlo + xhi) / 2
            ym = (ylo + yhi) / 2
            if abs(c) > 1e-10:
                zm = (d - a*xm - b*ym) / c
                zm = max(zlo, min(zhi, zm))
            elif abs(b) > 1e-10:
                zm = (zlo + zhi) / 2
                ym = (d - a*xm - c*zm) / b
                ym = max(ylo, min(yhi, ym))
            else:
                zm = (zlo + zhi) / 2
                xm = (d - b*ym - c*zm) / a
                xm = max(xlo, min(xhi, xm))

            if idx < 6:
                ax.text(xm, ym, zm, label, fontsize=8, color=color,
                        bbox=dict(boxstyle="round,pad=0.18",
                                  fc="#0f172a", ec=color, alpha=0.88))
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    #  Panel thông tin 3D                                                  #
    # ------------------------------------------------------------------ #
    def _build_info_panel_3d(self, parent, prob, vertices, vv, optimal, maximize,
                              status="optimal", multi_pts=None, path_d=None, path_b=None):
        mode = self.data_mode.get() if hasattr(self.data_mode, 'get') else self.data_mode

        panel = tk.Frame(parent, bg="#1e293b", width=290,
                         highlightthickness=1, highlightbackground="#334155")
        panel.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        panel.grid_propagate(False)
        panel.columnconfigure(0, weight=1)

        canvas_p = tk.Canvas(panel, bg="#1e293b", highlightthickness=0)
        sb = ttk.Scrollbar(panel, orient="vertical", command=canvas_p.yview)
        canvas_p.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas_p.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(canvas_p, bg="#1e293b")
        canvas_p.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda e: canvas_p.configure(
                       scrollregion=canvas_p.bbox("all")))

        def lbl(text, fg="#e2e8f0", font=("Segoe UI", 9), **kw):
            tk.Label(inner, text=text, bg="#1e293b", fg=fg,
                     font=font, anchor="w", wraplength=265, **kw).pack(
                fill="x", padx=8, pady=1)

        def sep():
            tk.Frame(inner, bg="#334155", height=1).pack(fill="x", padx=6, pady=3)

        lbl("Tóm tắt bài toán 3D", fg="#f8fafc", font=("Segoe UI", 11, "bold"))
        sep()

        sense_txt = "MAX" if prob.objective_sense == "max" else "MIN"
        c1, c2, c3 = prob.obj_coeffs

        def cs(c):
            return fmt_num(fr(c), mode)

        obj_txt = (f"{sense_txt} Z = {cs(c1)}x₁"
                   f" {'+ ' if c2 >= 0 else '- '}{cs(abs(fr(c2)))}x₂"
                   f" {'+ ' if c3 >= 0 else '- '}{cs(abs(fr(c3)))}x₃")
        lbl("Hàm mục tiêu:", fg="#94a3b8", font=("Segoe UI", 8))
        lbl(obj_txt, fg="#7dd3fc", font=("Consolas", 9))
        sep()

        # Trạng thái bài toán
        status_map = {
            "optimal": ("Nghiệm tối ưu duy nhất", "#4ade80"),
            "infeasible": ("VÔ NGHIỆM", "#f87171"),
            "unbounded": ("KHÔNG GIỚI NỘI", "#fb923c"),
            "cycle": ("Xoay vòng (Dantzig) → dùng Bland", "#fbbf24"),
        }
        if multi_pts:
            st_text, st_color = "VÔ SỐ NGHIỆM TỐI ƯU", "#fbbf24"
        else:
            st_text, st_color = status_map.get(status, (f"Trạng thái: {status}", "#94a3b8"))
        lbl(f"Trạng thái: {st_text}", fg=st_color, font=("Segoe UI", 9, "bold"))
        sep()

        lbl(f"Số ràng buộc: {len(prob.constraints)}", fg="#94a3b8")
        lbl(f"Số đỉnh khả thi: {len(vertices)}", fg="#94a3b8")
        sep()

        lbl("Ràng buộc:", fg="#94a3b8", font=("Segoe UI", 8))
        for i, cons in enumerate(prob.constraints, start=1):
            a, b, c_v = cons["coeffs"]
            d = cons["rhs"]
            s = sense_to_standard(cons["sense"])
            txt = f"RB{i}: {cs(a)}x₁+{cs(b)}x₂+{cs(c_v)}x₃ {s} {cs(d)}"
            lbl(txt, fg="#e2e8f0", font=("Consolas", 8))

        if vv and status not in ("infeasible",):
            sep()
            lbl("Đỉnh khả thi (Z):", fg="#94a3b8", font=("Segoe UI", 8))
            ordered = sorted(vv, key=lambda t: t[3], reverse=maximize)
            for idx, (x, y, z, val) in enumerate(ordered[:10], start=1):
                lbl(f"  {idx}. ({x:.3g},{y:.3g},{z:.3g}) z={val:.3g}",
                    fg="#e2e8f0", font=("Consolas", 8))

        if status == "unbounded":
            sep()
            lbl("Hàm mục tiêu không bị giới hạn.", fg="#fb923c")
            lbl("Có thể tăng/giảm tới ±∞.", fg="#fb923c")

        elif multi_pts:
            sep()
            lbl("Vô số nghiệm tối ưu!", fg="#fbbf24", font=("Segoe UI", 9, "bold"))
            lbl(f"Số đỉnh tối ưu: {len(multi_pts)}", fg="#fbbf24")
            if multi_pts:
                bx, by, bz = multi_pts[0]
                opt_z = float(prob.obj_coeffs[0])*bx + float(prob.obj_coeffs[1])*by + float(prob.obj_coeffs[2])*bz
                lbl(f"Z* = {opt_z:.4g}", fg="#fbbf24", font=("Consolas", 9))

        elif optimal is not None and status not in ("infeasible", "unbounded"):
            sep()
            bx, by, bz, bv = optimal
            lbl("Điểm tối ưu duy nhất:", fg="#fbbf24", font=("Segoe UI", 9, "bold"))
            lbl(f"  ({bx:.4g}, {by:.4g}, {bz:.4g})", fg="#fbbf24", font=("Consolas", 9))
            lbl(f"  Z = {bv:.4g}", fg="#fbbf24", font=("Consolas", 9))

        # Đường đi simplex
        if path_d or path_b:
            sep()
            lbl("Đường đi thuật toán đơn hình:", fg="#94a3b8", font=("Segoe UI", 8, "bold"))
            if path_d:
                lbl(f"Dantzig ({len(path_d)} điểm):", fg="#f97316", font=("Segoe UI", 8))
                for k, (px, py, pz) in enumerate(path_d):
                    lbl(f"  D{k}: ({px:.3g},{py:.3g},{pz:.3g})",
                        fg="#fed7aa", font=("Consolas", 8))
            if path_b:
                lbl(f"Bland ({len(path_b)} điểm):", fg="#22d3ee", font=("Segoe UI", 8))
                for k, (px, py, pz) in enumerate(path_b):
                    lbl(f"  B{k}: ({px:.3g},{py:.3g},{pz:.3g})",
                        fg="#a5f3fc", font=("Consolas", 8))

        sep()
        lbl("Xoay: kéo chuột trái\nZoom: lăn chuột\nPan: kéo chuột phải",
            fg="#64748b", font=("Segoe UI", 8))

    # ------------------------------------------------------------------ #
    #  Thanh điều khiển 3D                                                #
    # ------------------------------------------------------------------ #
    def _build_3d_controls(self, ctrl, ax, canvas, fig):
        ctrl.columnconfigure(0, weight=1)
        btn_frame = tk.Frame(ctrl, bg="#1e293b")
        btn_frame.pack(side="left", padx=12, pady=6)

        def mk_btn(text, color, hover, cmd):
            b = tk.Button(btn_frame, text=text,
                          font=("Segoe UI", 9, "bold"),
                          bg=color, fg="white",
                          activebackground=hover, activeforeground="white",
                          relief="flat", bd=0, padx=10, pady=5,
                          cursor="hand2", command=cmd)
            b.pack(side="left", padx=4)
            b.bind("<Enter>", lambda e, hv=hover: b.config(bg=hv))
            b.bind("<Leave>", lambda e, cv=color: b.config(bg=cv))

        mk_btn("Mặc định", "#334155", "#475569",
               lambda: (ax.view_init(elev=22, azim=-55), canvas.draw_idle()))
        mk_btn("Mặt XY",  "#1d4ed8", "#1e40af",
               lambda: (ax.view_init(elev=90, azim=-90), canvas.draw_idle()))
        mk_btn("Mặt XZ",  "#0f766e", "#0d9488",
               lambda: (ax.view_init(elev=0, azim=-90), canvas.draw_idle()))
        mk_btn("Mặt YZ",  "#7c3aed", "#6d28d9",
               lambda: (ax.view_init(elev=0, azim=0), canvas.draw_idle()))
        mk_btn("Lưới",    "#64748b", "#475569",
               lambda: (ax.grid(not ax.get_xgridlines()[0].get_visible()),
                        canvas.draw_idle()))

        tk.Label(ctrl,
                 text="Kéo chuột trái để xoay 3D -- Lăn chuột để zoom -- Kéo chuột phải để pan",
                 bg="#1e293b", fg="#64748b",
                 font=("Segoe UI", 9)).pack(side="right", padx=16)
