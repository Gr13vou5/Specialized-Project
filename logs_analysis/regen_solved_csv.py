from __future__ import annotations

import csv
from pathlib import Path

from common import (
    BBM_INSTANCE_IDS,
    PSEUDO_RANDOM_INSTANCE_IDS,
    SELECTED_INSTANCE_IDS,
    RESULTS_DIRNAME,
)

RESULTS_DIR = Path(RESULTS_DIRNAME)

NUM_FIXED_POINTS_THRESHOLD = (10**10, 1000, 0)
NUM_VARS_THRESHOLD = (2000, 1000, 100, 0)

INVALID = {"", "TIMEOUT", "OUT_OF_MEMORY", "ERROR", "-"}

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def is_solved(val: str) -> bool:
    return val not in INVALID


def read_csv(path: Path):
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        solvers = [c for c in reader.fieldnames if c != "Instance"]
    return rows, solvers


# ------------------------------------------------------------
# Fixed points: ground truth from CSVs
# ------------------------------------------------------------
def load_num_fixed_points():
    """
    Ground-truth FP counts from fixed_points CSVs.

    For instances without known FP counts (e.g., Random),
    assign a large sentinel value (10^30), matching the paper's
    handling via d4-anytime.
    """
    fps = {}

    def read_fp_csv(path: Path):
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                inst = row["Instance"]
                for k, v in row.items():
                    if k == "Instance":
                        continue
                    if v:
                        fps[inst] = int(v.rstrip("*"))
                        break

    read_fp_csv(RESULTS_DIR / "fixed_points.csv")
    read_fp_csv(RESULTS_DIR / "fixed_points_fasp.csv")

    # --------------------------------------------------------
    # Assign large FP count to instances without ground truth
    # (Random instances)
    # --------------------------------------------------------
    ALL_INSTANCES = (
        set(BBM_INSTANCE_IDS)
        | set(PSEUDO_RANDOM_INSTANCE_IDS)
        | set(SELECTED_INSTANCE_IDS)
    )

    for inst in ALL_INSTANCES:
        if inst not in fps:
            fps[inst] = 10**30

    return fps


# ------------------------------------------------------------
# Variables: count lines in .bnet (minus header)
# ------------------------------------------------------------
def count_vars_bnet(path: Path) -> int:
    with open(path) as f:
        lines = [
            ln for ln in f
            if ln.strip() and not ln.strip().startswith("#")
        ]
    # subtract header: "targets,factors"
    return len(lines) - 1


def count_vars_bnet(path: Path) -> int:
    with open(path) as f:
        lines = [
            ln for ln in f
            if ln.strip() and not ln.strip().startswith("#")
        ]
    # subtract header: "targets,factors"
    return len(lines) - 1


def load_num_vars():
    num_vars = {}

    base = Path(__file__).resolve().parent.parent / "benchmarks" / "fASP" / "dataset"

    # --------------------------------------------------------
    # BBM: model_001.bnet → "001"
    # --------------------------------------------------------
    bbm_dir = base / "BBM"
    for p in bbm_dir.glob("model_*.bnet"):
        inst = p.stem.replace("model_", "")
        num_vars[inst] = count_vars_bnet(p)

    # --------------------------------------------------------
    # Random: filename stem is the instance id
    # --------------------------------------------------------
    random_dir = base / "Random"
    for p in random_dir.glob("*.bnet"):
        inst = p.stem
        num_vars[inst] = count_vars_bnet(p)

    # --------------------------------------------------------
    # Selected: filename stem is the instance id
    # --------------------------------------------------------
    selected_dir = base / "Selected"
    for p in selected_dir.glob("*.bnet"):
        inst = p.stem
        num_vars[inst] = count_vars_bnet(p)

    return num_vars


# ------------------------------------------------------------
# Load data
# ------------------------------------------------------------
num_vars = load_num_vars()
num_fixed_points = load_num_fixed_points()

cpu_bbm, solvers = read_csv(RESULTS_DIR / "cpu.csv")
cpu_fasp, _ = read_csv(RESULTS_DIR / "cpu_fasp.csv")
cpu_sel, _ = read_csv(RESULTS_DIR / "cpu_selected.csv")

cpu_rows = {r["Instance"]: r for r in cpu_bbm + cpu_fasp + cpu_sel}

BENCHMARK_SETS = [
    ("BBM", BBM_INSTANCE_IDS),
    ("Random", PSEUDO_RANDOM_INSTANCE_IDS),
    ("Selected", SELECTED_INSTANCE_IDS),
]

# ------------------------------------------------------------
# Counters
# ------------------------------------------------------------
count_fps = [{s: [0] * len(NUM_FIXED_POINTS_THRESHOLD) for s in solvers} for _ in BENCHMARK_SETS]
count_vars = [{s: [0] * len(NUM_VARS_THRESHOLD) for s in solvers} for _ in BENCHMARK_SETS]

total_fps = [[0] * len(NUM_FIXED_POINTS_THRESHOLD) for _ in BENCHMARK_SETS]
total_vars = [[0] * len(NUM_VARS_THRESHOLD) for _ in BENCHMARK_SETS]

for i, (_, ids) in enumerate(BENCHMARK_SETS):
    for inst in ids:
        fp = num_fixed_points[inst]
        v = num_vars[inst]

        for j, lb in reversed(list(enumerate(sorted(NUM_FIXED_POINTS_THRESHOLD)))):
            if fp >= lb:
                total_fps[i][j] += 1
                break

        for j, lb in reversed(list(enumerate(sorted(NUM_VARS_THRESHOLD)))):
            if v >= lb:
                total_vars[i][j] += 1
                break

        row = cpu_rows.get(inst)
        if not row:
            continue

        for s in solvers:
            if not is_solved(row[s]):
                continue

            for j, lb in reversed(list(enumerate(sorted(NUM_FIXED_POINTS_THRESHOLD)))):
                if fp >= lb:
                    count_fps[i][s][j] += 1
                    break

            for j, lb in reversed(list(enumerate(sorted(NUM_VARS_THRESHOLD)))):
                if v >= lb:
                    count_vars[i][s][j] += 1
                    break

# ------------------------------------------------------------
# solved_per_set.csv
# ------------------------------------------------------------
with open(RESULTS_DIR / "solved_per_set.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, ["Set", "#Instance"] + solvers)
    writer.writeheader()

    for i, (name, _) in enumerate(BENCHMARK_SETS):
        r = {"Set": name, "#Instance": str(sum(total_fps[i]))}
        for s in solvers:
            r[s] = str(sum(count_vars[i][s]))
        writer.writerow(r)

# ------------------------------------------------------------
# solved_per_fps_range.csv
# ------------------------------------------------------------
with open(RESULTS_DIR / "solved_per_fps_range.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, ["Range", "#Instance"] + solvers)
    writer.writeheader()

    for j, lb in enumerate(reversed(NUM_FIXED_POINTS_THRESHOLD)):
        r = {
            "Range": f"{lb}<=",
            "#Instance": str(sum(total_fps[i][j] for i in range(len(BENCHMARK_SETS)))),
        }
        for s in solvers:
            r[s] = str(sum(count_fps[i][s][j] for i in range(len(BENCHMARK_SETS))))
        writer.writerow(r)

# ------------------------------------------------------------
# solved_per_vars_range.csv
# ------------------------------------------------------------
with open(RESULTS_DIR / "solved_per_vars_range.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, ["Range", "#Instance"] + solvers)
    writer.writeheader()

    for j, lb in enumerate(reversed(NUM_VARS_THRESHOLD)):
        r = {
            "Range": f"{lb}<=",
            "#Instance": str(sum(total_vars[i][j] for i in range(len(BENCHMARK_SETS)))),
        }
        for s in solvers:
            r[s] = str(sum(count_vars[i][s][j] for i in range(len(BENCHMARK_SETS))))
        writer.writerow(r)
