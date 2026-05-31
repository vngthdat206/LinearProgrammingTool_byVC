from __future__ import annotations
import math
import itertools


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
