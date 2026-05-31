from __future__ import annotations

import math
import itertools
from fractions import Fraction
from typing import Any, Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import messagebox, ttk

from utils import fmt_num, fr, sense_to_standard
from models import ProblemData

def _halfspace_feasible(x: float, y: float, z: float,
                        planes: List[Tuple[float, float, float, float, str]],
                        tol: float = 1e-7) -> bool:
    
    for a, b, c, d, sense in planes:
        lhs = a * x + b * y + c * z
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
    det = (a1 * (b2 * c3 - b3 * c2)
           - b1 * (a2 * c3 - a3 * c2)
           + c1 * (a2 * b3 - a3 * b2))
    if abs(det) < 1e-12:
        return None
    x = ((d1 * (b2 * c3 - b3 * c2)
          - b1 * (d2 * c3 - d3 * c2)
          + c1 * (d2 * b3 - d3 * b2)) / det)
    y = ((a1 * (d2 * c3 - d3 * c2)
          - d1 * (a2 * c3 - a3 * c2)
          + c1 * (a2 * d3 - a3 * d2)) / det)
    z = ((a1 * (b2 * d3 - b3 * d2)
          - b1 * (a2 * d3 - a3 * d2)
          + d1 * (a2 * b3 - a3 * b2)) / det)
    return x, y, z


def _convex_hull_3d_simple(pts: List[Tuple[float, float, float]]):
    if len(pts) < 3:
        return []
    try:
        from scipy.spatial import ConvexHull
        import numpy as np
        arr = np.array(pts)
        hull = ConvexHull(arr)
        return [tuple(s) for s in hull.simplices]
    except Exception:
        pass

    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    cz = sum(p[2] for p in pts) / len(pts)
    center = (cx, cy, cz)
    n = len(pts)
    faces = []
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n))          
    pts_with_center = pts + [center]
    return faces, pts_with_center

