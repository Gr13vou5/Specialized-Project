from __future__ import annotations

import glob
import re
from dataclasses import dataclass
from enum import Enum, unique
from typing import Optional
from pathlib import Path

from common import BBM_INSTANCE_IDS, FASP_INSTANCE_IDS, LOGS_DIR, Solver

TIMEOUT_SEC = 1800
TIMEOUT_SEC_MARGIN = 3
MEMORY_THRESHOLD = 6 * 10**7


fixed_points_patterns = {
    "aeon": re.compile(r"Found (\d+) fixed points"),
    "fasp": re.compile(r"^(\d+)", flags=re.MULTILINE),
    "bmsa": re.compile(r"SAT \(full\)\s*:\s*(\d+)"),
    "pyboolnet": re.compile(r"Found (\d+) steady states"),
    "mc": re.compile(r"exact arb int (\d+)"),
}


@unique
class AbortType(Enum):
    TIMEOUT = "TIMEOUT"
    OUT_OF_MEMORY = "OUT_OF_MEMORY"
    UNKNOWN_ERROR = "ERROR"


@dataclass
class Result:
    num_fixed_points: Optional[int] = None
    cpu: Optional[float] = None
    abort_type: Optional[AbortType] = None


def parse_time_command_output(output: str) -> tuple[float, int]:
    # verbose
    user_time_m = re.search(r"^\s+User time \(seconds\): (\d+\.\d+)", output, flags=re.MULTILINE)
    sys_time_m = re.search(r"^\s+System time \(seconds\): (\d+\.\d+)", output, flags=re.MULTILINE)
    assert user_time_m and sys_time_m
    cpu = sum(map(lambda x: float(x.group(1)), (user_time_m, sys_time_m)))

    mem_m = re.search(r"^\s+Maximum resident set size \(kbytes\): (\d+)", output, flags=re.MULTILINE)
    assert mem_m
    mem = int(mem_m.group(1))

    return cpu, mem


def parse_log_default(log_file: str, p: re.Pattern[str]) -> Result:
    with open(log_file, "r") as f:
        content_raw = f.read()

    res = Result()

    fixed_points_m = p.search(content_raw)
    cpu, mem = parse_time_command_output(content_raw)
    if fixed_points_m:
        res.num_fixed_points = int(fixed_points_m.group(1))
        assert cpu <= TIMEOUT_SEC
        res.cpu = cpu
    elif cpu > TIMEOUT_SEC - TIMEOUT_SEC_MARGIN:
        res.abort_type = AbortType.TIMEOUT
    elif mem > MEMORY_THRESHOLD:
        res.abort_type = AbortType.OUT_OF_MEMORY
    else:
        res.abort_type = AbortType.UNKNOWN_ERROR

    return res


def parse_pyboolnet_log(log_file: str) -> Result:
    with open(log_file, "r") as f:
        content_raw = f.read()

    res = Result()

    fixed_points_m = fixed_points_patterns["pyboolnet"].search(content_raw)
    cpu, mem = parse_time_command_output(content_raw)
    if cpu > TIMEOUT_SEC - TIMEOUT_SEC_MARGIN:
        res.abort_type = AbortType.TIMEOUT
    elif fixed_points_m:
        res.num_fixed_points = int(fixed_points_m.group(1))
        res.cpu = cpu
    elif mem > MEMORY_THRESHOLD:
        res.abort_type = AbortType.OUT_OF_MEMORY
    else:
        res.abort_type = AbortType.UNKNOWN_ERROR

    return res


def parse_saf_logs(biolqm_log_file: str, log_file: Optional[str]) -> Result:
    with open(biolqm_log_file, "r") as f:
        content_raw = f.read()

    if "javax.xml.stream.XMLStreamException" in content_raw or "java.lang.NegativeArraySizeException" in content_raw:
        assert log_file is None
        return Result(abort_type=AbortType.UNKNOWN_ERROR)

    biolqm_cpu, _ = parse_time_command_output(content_raw)

    if biolqm_cpu > TIMEOUT_SEC - TIMEOUT_SEC_MARGIN:
        return Result(abort_type=AbortType.TIMEOUT)

    assert "+ exit_status=0" in content_raw and log_file is not None

    with open(log_file, "r") as f:
        content_raw = f.read()

    res = parse_log_default(log_file, fixed_points_patterns["bmsa"])
    if res.cpu is not None:
        cpu = biolqm_cpu + res.cpu
        if cpu > TIMEOUT_SEC:
            res = Result(abort_type=AbortType.TIMEOUT)
        else:
            res.cpu = cpu

    return res


def parse_saf_sstd_logs(biolqm_log_file: str, log_file: Optional[str]) -> Result:
    with open(biolqm_log_file, "r") as f:
        content_raw = f.read()

    if "javax.xml.stream.XMLStreamException" in content_raw or "java.lang.NegativeArraySizeException" in content_raw:
        assert log_file is None
        return Result(abort_type=AbortType.UNKNOWN_ERROR)

    biolqm_cpu, _ = parse_time_command_output(content_raw)

    if biolqm_cpu > TIMEOUT_SEC - TIMEOUT_SEC_MARGIN:
        return Result(abort_type=AbortType.TIMEOUT)

    assert "+ exit_status=0" in content_raw and log_file is not None

    with open(log_file, "r") as f:
        content_raw = f.read()

    res = parse_log_default(log_file, fixed_points_patterns["mc"])
    if res.cpu is not None:
        cpu = biolqm_cpu + res.cpu
        if cpu > TIMEOUT_SEC:
            res = Result(abort_type=AbortType.TIMEOUT)
        else:
            res.cpu = cpu

    return res


def parse_proposed_bmsa_log(log_file: str) -> Result:
    with open(log_file, "r") as f:
        content_raw = f.read()

    cpu, _ = parse_time_command_output(content_raw)

    if re.search(r"^s UNSATISFIABLE", content_raw, flags=re.MULTILINE):
        assert cpu <= TIMEOUT_SEC
        return Result(0, cpu)

    return parse_log_default(log_file, fixed_points_patterns["bmsa"])


def parse_bbm_instances() -> dict[str, dict[Solver, Result]]:
    res_all: dict[str, dict[Solver, Result]] = dict()
    for id_ in BBM_INSTANCE_IDS:
        print(id_)
        d: dict[Solver, Result] = dict()

        # fASP
        d[Solver.FASP_CONJ] = parse_log_default(
            glob.glob(f"{LOGS_DIR}/fasp_conj/bbm/*{id_}*.log")[0], fixed_points_patterns["fasp"]
        )
        d[Solver.FASP_SRC] = parse_log_default(
            glob.glob(f"{LOGS_DIR}/fasp_src/bbm/*{id_}*.log")[0], fixed_points_patterns["fasp"]
        )

        # Proposed BMSA
        d[Solver.HYBRID_BMSA] = parse_proposed_bmsa_log(glob.glob(f"{LOGS_DIR}/hybrid_bmsa/bbm/*id-{id_}*/*.log")[0])

        res_all[id_] = d

    return res_all


def parse_fasp_instances() -> dict[str, dict[Solver, Result]]:
    res_all: dict[str, dict[Solver, Result]] = dict()
    for id_ in FASP_INSTANCE_IDS:
        print(id_)
        d: dict[Solver, Result] = dict()

        # fASP
        d[Solver.FASP_CONJ] = parse_log_default(
            glob.glob(f"{LOGS_DIR}/fasp_conj/fasp/**/{id_}.bnet.log", recursive=True)[0], fixed_points_patterns["fasp"]
        )
        d[Solver.FASP_SRC] = parse_log_default(
            glob.glob(f"{LOGS_DIR}/fasp_src/fasp/**/{id_}.bnet.log", recursive=True)[0], fixed_points_patterns["fasp"]
        )

        # Proposed BMSA
        d[Solver.HYBRID_BMSA] = parse_proposed_bmsa_log(
            glob.glob(f"{LOGS_DIR}/hybrid_bmsa/fasp/**/{id_}.bnet.log", recursive=True)[0]
        )


        res_all[id_] = d

    return res_all


def count_vars_bnet(path: Path) -> int:
    with open(path) as f:
        lines = [
            ln for ln in f
            if ln.strip() and not ln.strip().startswith("#")
        ]
    # subtract header: "targets,factors"
    return len(lines) - 1


def parse_num_vars() -> dict[str, int]:
    num_vars: dict[str, int] = {}

    base = Path(__file__).resolve().parent.parent / "benchmarks" / "fASP" / "dataset"

    # BBM:
    bbm_dir = base / "BBM"
    for p in bbm_dir.glob("model_*.bnet"):
        inst = p.stem.replace("model_", "")
        num_vars[inst] = count_vars_bnet(p)

    # Random
    random_dir = base / "Random"
    for p in random_dir.glob("*.bnet"):
        inst = p.stem
        num_vars[inst] = count_vars_bnet(p)

    # Selected
    selected_dir = base / "Selected"
    for p in selected_dir.glob("*.bnet"):
        inst = p.stem
        num_vars[inst] = count_vars_bnet(p)

    return num_vars


def parse_num_fixed_points() -> dict[str, int]:
    num_fixed_points: dict[str, int] = {}

    def pick_fp(results: dict[Solver, Result]) -> Optional[int]:
        for solver in (
            Solver.HYBRID_BMSA,
            Solver.FASP_SRC,
            Solver.FASP_CONJ,
        ):
            res = results.get(solver)
            if res and res.num_fixed_points is not None:
                return res.num_fixed_points
        return None

    # BBM 
    bbm_results = parse_bbm_instances()
    for id_, results in bbm_results.items():
        fp = pick_fp(results)
        if fp is None:
            fp = 10**30
        num_fixed_points[id_] = fp

    # fASP (Random + Selected)
    fasp_results = parse_fasp_instances()
    for id_, results in fasp_results.items():
        fp = pick_fp(results)
        if fp is None:
            fp = 10**30
        num_fixed_points[id_] = fp

    return num_fixed_points


