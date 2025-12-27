from __future__ import annotations

import os
from enum import Enum, unique

LOGS_DIR = "../logs"
RESULTS_DIRNAME = "results"


BBM_INSTANCE_IDS = tuple(f"{i:03d}" for i in range(1, 231))


os.makedirs(RESULTS_DIRNAME, exist_ok=True)


def get_fasp_instance_ids() -> set[str]:
    with open("fasp_instance_ids.txt", "r") as f:
        ids = set(map(str.strip, f.read().strip().split("\n")))
    assert len(ids) == 413
    return ids


def get_selected_instance_ids() -> set[str]:
    with open("selected_instance_ids.txt", "r") as f:
        ids = set(map(str.strip, f.read().strip().split("\n")))
    assert len(ids) == 13
    return ids


FASP_INSTANCE_IDS = tuple(sorted(get_fasp_instance_ids()))
SELECTED_INSTANCE_IDS = tuple(sorted(get_selected_instance_ids()))
PSEUDO_RANDOM_INSTANCE_IDS = tuple(filter(lambda x: x not in SELECTED_INSTANCE_IDS, FASP_INSTANCE_IDS))


@unique
class Solver(Enum):
    FASP_CONJ = "fASP_conj"   
    FASP_SRC = "fASP_src"      
    HYBRID_BMSA = "Hybrid_BMSA"  


def format_time(t: float) -> str:
    return f"{t:.2f}"
