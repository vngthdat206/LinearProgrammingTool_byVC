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
