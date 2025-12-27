from __future__ import annotations

import csv

from common import (BBM_INSTANCE_IDS, PSEUDO_RANDOM_INSTANCE_IDS,
                    RESULTS_DIRNAME, SELECTED_INSTANCE_IDS, Solver)
from log_parser import (parse_bbm_instances, parse_fasp_instances,
                        parse_num_fixed_points, parse_num_vars)

BENCHMARK_SETS = (BBM_INSTANCE_IDS, PSEUDO_RANDOM_INSTANCE_IDS, SELECTED_INSTANCE_IDS)

NUM_FIXED_POINTS_THRESHOLD = (10**30, 10**10, 1000, 0)
NUM_VARS_THRESHOLD = (2000, 1000, 100, 0)


num_vars = parse_num_vars()
num_fixed_points = parse_num_fixed_points()


res_all = parse_bbm_instances()
res_all.update(parse_fasp_instances())

count_dicts_fps = [dict((s, [0] * len(NUM_FIXED_POINTS_THRESHOLD)) for s in Solver) for _ in BENCHMARK_SETS]
num_fps_total = [[0] * len(NUM_FIXED_POINTS_THRESHOLD) for _ in BENCHMARK_SETS]
count_dicts_vars = [dict((s, [0] * len(NUM_VARS_THRESHOLD)) for s in Solver) for _ in BENCHMARK_SETS]
num_vars_total = [[0] * len(NUM_VARS_THRESHOLD) for _ in BENCHMARK_SETS]

for i, s in enumerate(BENCHMARK_SETS):
    print("------------------------------------------------------------")
    for id_ in s:
        fp = num_fixed_points[id_]
        for j, threshold in reversed(list(enumerate(sorted(NUM_FIXED_POINTS_THRESHOLD)))):
            if fp >= threshold:
                num_fps_total[i][j] += 1
                break

        v = num_vars[id_]
        for j, threshold in reversed(list(enumerate(sorted(NUM_VARS_THRESHOLD)))):
            if v >= threshold:
                num_vars_total[i][j] += 1
                break

        for solver in Solver:
            if solver not in res_all[id_]:
                continue

            res = res_all[id_][solver]
            if res.cpu is not None:
                n = res.num_fixed_points
                assert n is not None

                for j, threshold in reversed(list(enumerate(sorted(NUM_FIXED_POINTS_THRESHOLD)))):
                    if n >= threshold:
                        count_dicts_fps[i][solver][j] += 1
                        break

                for j, threshold in reversed(list(enumerate(sorted(NUM_VARS_THRESHOLD)))):
                    if v >= threshold:
                        count_dicts_vars[i][solver][j] += 1
                        break

    print("# Range")
    print("Total:", sum(num_fps_total[i]), num_fps_total[i])
    for solver in Solver:
        print(solver, sum(count_dicts_fps[i][solver]), count_dicts_fps[i][solver])

    print("# Number of vars")
    print("Total:", sum(num_vars_total[i]), num_vars_total[i])
    for solver in Solver:
        print(solver, sum(count_dicts_vars[i][solver]), count_dicts_vars[i][solver])


with open(f"{RESULTS_DIRNAME}/solved_per_set.csv", "w") as f:
    writer = csv.DictWriter(f, ["Set", "#Instance"] + [e.value for e in Solver])
    writer.writeheader()

    for i, name in enumerate(["BBM", "Random", "Selected"]):
        r: dict[str, str] = {"Set": name, "#Instance": str(sum(num_fps_total[i]))}

        for solver in Solver:
            r[solver.value] = str(sum(count_dicts_vars[i][solver]))

        writer.writerow(r)


with open(f"{RESULTS_DIRNAME}/solved_per_fps_range.csv", "w") as f:
    writer = csv.DictWriter(f, ["Range", "#Instance"] + [e.value for e in Solver])
    writer.writeheader()

    for j, lb in enumerate(reversed(NUM_FIXED_POINTS_THRESHOLD)):
        r = {
            "Range": f"{lb}<=",
            "#Instance": str(sum([num_fps_total[i][j] for i in range(len(BENCHMARK_SETS))])),
        }

        for solver in Solver:
            r[solver.value] = str(sum([count_dicts_fps[i][solver][j] for i in range(len(BENCHMARK_SETS))]))

        writer.writerow(r)


with open(f"{RESULTS_DIRNAME}/solved_per_vars_range.csv", "w") as f:
    writer = csv.DictWriter(f, ["Range", "#Instance"] + [e.value for e in Solver])
    writer.writeheader()

    for j, lb in enumerate(reversed(NUM_VARS_THRESHOLD)):
        r = {
            "Range": f"{lb}<=",
            "#Instance": str(sum([num_vars_total[i][j] for i in range(len(BENCHMARK_SETS))])),
        }

        for solver in Solver:
            r[solver.value] = str(sum([count_dicts_vars[i][solver][j] for i in range(len(BENCHMARK_SETS))]))

        writer.writerow(r)
