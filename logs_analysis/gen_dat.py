from __future__ import annotations

import csv
from pathlib import Path

from common import (
    BBM_INSTANCE_IDS,
    FASP_INSTANCE_IDS,
    PSEUDO_RANDOM_INSTANCE_IDS,
    RESULTS_DIRNAME,
    SELECTED_INSTANCE_IDS,
)

RESULTS_DIR = Path(RESULTS_DIRNAME)

SOLVERS = {
    "fASP_conj",      # fASP-c
    "fASP_src",       # fASP-s
    "Hybrid_BMSA",    # H.E.
    "PFVS",           # PFVS
}

INVALID = {"", "TIMEOUT", "OUT_OF_MEMORY", "ERROR", "-"}


def is_solved(val: str) -> bool:
    return val not in INVALID


def read_cpu_csv(path: Path):
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        solvers = [c for c in reader.fieldnames if c in SOLVERS]
    return rows, solvers


# ------------------------------------------------------------
# BBM cactus
# ------------------------------------------------------------
rows, solvers = read_cpu_csv(RESULTS_DIR / "cpu.csv")

with open(RESULTS_DIR / "time_for_cactus.dat", "w") as f:
    for r in rows:
        if r["Instance"] not in BBM_INSTANCE_IDS:
            continue

        for s in solvers:
            if is_solved(r[s]):
                f.write(f"{s},{float(r[s])}\n")


# ------------------------------------------------------------
# fASP cactus (Random + Selected)
# ------------------------------------------------------------
rows, solvers = read_cpu_csv(RESULTS_DIR / "cpu_fasp.csv")

with open(RESULTS_DIR / "time_fasp_for_cactus.dat", "w") as f:
    for r in rows:
        if r["Instance"] not in FASP_INSTANCE_IDS:
            continue

        for s in solvers:
            if is_solved(r[s]):
                f.write(f"{s},{float(r[s])}\n")


# ------------------------------------------------------------
# pseudo-random only
# ------------------------------------------------------------
with open(RESULTS_DIR / "time_pseudo_random_for_cactus.dat", "w") as f:
    for r in rows:
        if r["Instance"] not in PSEUDO_RANDOM_INSTANCE_IDS:
            continue

        for s in solvers:
            if is_solved(r[s]):
                f.write(f"{s},{float(r[s])}\n")

# ------------------------------------------------------------
# Selected-only cactus
# ------------------------------------------------------------
rows, solvers = read_cpu_csv(RESULTS_DIR / "cpu_fasp.csv")

with open(RESULTS_DIR / "time_selected_for_cactus.dat", "w") as f:
    for r in rows:
        if r["Instance"] not in SELECTED_INSTANCE_IDS:
            continue

        for s in solvers:
            if is_solved(r[s]):
                f.write(f"{s},{float(r[s])}\n")
