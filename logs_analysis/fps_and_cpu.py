from __future__ import annotations

import csv

from common import (BBM_INSTANCE_IDS, FASP_INSTANCE_IDS,
                    PSEUDO_RANDOM_INSTANCE_IDS, RESULTS_DIRNAME,
                    SELECTED_INSTANCE_IDS, Solver, format_time)
from log_parser import parse_bbm_instances, parse_fasp_instances

# BBM
res_all = parse_bbm_instances()

# fixed points
with open(f"{RESULTS_DIRNAME}/fixed_points.csv", "w") as f:
    writer = csv.DictWriter(f, ["Instance"] + [e.value for e in Solver])
    writer.writeheader()

    for id_ in BBM_INSTANCE_IDS:
        r: dict[str, str] = {"Instance": id_}
        for solver in Solver:
            if solver not in res_all[id_]:
                r[solver.value] = "-"
                continue

            res = res_all[id_][solver]
            if res.num_fixed_points is None:
                r[solver.value] = ""
            else:
                n = res.num_fixed_points
                s = str(n)
                if res.cpu is not None:
                    s += "*"

                r[solver.value] = s

        writer.writerow(r)


# cpu time
with open(f"{RESULTS_DIRNAME}/cpu.csv", "w") as f:
    writer = csv.DictWriter(f, ["Instance"] + [e.value for e in Solver])
    writer.writeheader()

    for id_ in BBM_INSTANCE_IDS:
        r = {"Instance": id_}
        for solver in Solver:
            if solver not in res_all[id_]:
                r[solver.value] = ""
                continue

            res = res_all[id_][solver]
            if res.cpu is None:
                assert res.abort_type is not None
                r[solver.value] = res.abort_type.value
            else:
                r[solver.value] = format_time(res.cpu)

        writer.writerow(r)


# ------------------------------------------------------------------------


# fASP
res_all = parse_fasp_instances()

# fixed points
with open(f"{RESULTS_DIRNAME}/fixed_points_fasp.csv", "w") as f:
    writer = csv.DictWriter(f, ["Instance"] + [e.value for e in Solver])
    writer.writeheader()

    for id_ in sorted(FASP_INSTANCE_IDS):
        r = {"Instance": id_}
        for solver in Solver:
            if solver not in res_all[id_]:
                r[solver.value] = "-"
                continue

            res = res_all[id_][solver]
            if res.num_fixed_points is None:
                r[solver.value] = ""
            else:
                n = res.num_fixed_points
                s = str(n)
                if res.cpu is not None:
                    s += "*"

                r[solver.value] = s

        writer.writerow(r)


# cpu time
with open(f"{RESULTS_DIRNAME}/cpu_fasp.csv", "w") as f:
    writer = csv.DictWriter(f, ["Instance"] + [e.value for e in Solver])
    writer.writeheader()

    for id_ in sorted(FASP_INSTANCE_IDS):
        r = {"Instance": id_}
        for solver in Solver:
            if solver not in res_all[id_]:
                r[solver.value] = ""
                continue

            res = res_all[id_][solver]
            if res.cpu is None:
                assert res.abort_type is not None
                r[solver.value] = res.abort_type.value
            else:
                r[solver.value] = format_time(res.cpu)

        writer.writerow(r)


# cpu time (Selected)
with open(f"{RESULTS_DIRNAME}/cpu_selected.csv", "w") as f:
    writer = csv.DictWriter(f, ["Instance"] + [e.value for e in Solver])
    writer.writeheader()

    for id_ in sorted(SELECTED_INSTANCE_IDS):
        r = {"Instance": id_}
        for solver in Solver:
            if solver not in res_all[id_]:
                r[solver.value] = ""
                continue

            res = res_all[id_][solver]
            if res.cpu is None:
                assert res.abort_type is not None
                r[solver.value] = res.abort_type.value
            else:
                r[solver.value] = format_time(res.cpu)

        writer.writerow(r)
