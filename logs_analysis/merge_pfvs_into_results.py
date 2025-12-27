import csv
from pathlib import Path

RESULTS_DIR = Path("results")
PFVS_COL = "PFVS"

MERGE_MAP = {
    "cpu.csv": [
        "pfvs_bbm_results.csv",
    ],
    "fixed_points.csv": [
        "pfvs_bbm_results.csv",
    ],
    "cpu_fasp.csv": [
        "pfvs_random_results.csv",
        "pfvs_selected_results.csv",
    ],
    "fixed_points_fasp.csv": [
        "pfvs_random_results.csv",
        "pfvs_selected_results.csv",
    ],
    "cpu_selected.csv": [
        "pfvs_selected_results.csv",
    ],
}

def load_target_instances(csv_path: Path) -> set[str]:
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        return {row["Instance"] for row in reader}

def match_instance(pfvs_inst: str, target_instances: set[str]) -> str | None:
    raw = pfvs_inst.lower()

    candidates = []
    for inst in target_instances:
        inst_norm = inst.lower()

        if raw == inst_norm:
            return inst

        if raw.replace("-", "_") == inst_norm.replace("-", "_"):
            return inst

        if raw in inst_norm or inst_norm in raw:
            candidates.append(inst)

    if candidates:
        return max(candidates, key=len)

    return None


def load_pfvs_results(filenames, target_instances):
    data = {}

    for fname in filenames:
        path = RESULTS_DIR / fname
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                pfvs_inst = row["instance"]
                inst = match_instance(pfvs_inst, target_instances)

                if inst is None:
                    print(f"[WARN] Unmatched PFVS instance: {pfvs_inst}")
                    continue

                status = row["status"].lower()
                time_sec = row["time_sec"]
                num_fp = row["num_fp"]

                data[inst] = (status, time_sec, num_fp)

    return data

def update_csv(csv_path, pfvs_data, is_cpu):
    tmp_path = csv_path.with_suffix(".tmp")

    with open(csv_path, newline="") as fin, open(tmp_path, "w", newline="") as fout:
        reader = csv.DictReader(fin)
        fieldnames = reader.fieldnames.copy()

        if PFVS_COL not in fieldnames:
            fieldnames.append(PFVS_COL)

        writer = csv.DictWriter(fout, fieldnames=fieldnames)
        writer.writeheader()

        for row in reader:
            inst = row["Instance"]

            if inst in pfvs_data:
                status, time_sec, num_fp = pfvs_data[inst]

                if is_cpu:
                    row[PFVS_COL] = time_sec if status == "solved" else "TIMEOUT"
                else:
                    row[PFVS_COL] = f"{num_fp}*" if status == "solved" else ""
            else:
                row[PFVS_COL] = ""

            writer.writerow(row)

    tmp_path.replace(csv_path)
    print(f"Updated {csv_path}")


def main():
    for target_csv, pfvs_sources in MERGE_MAP.items():
        csv_path = RESULTS_DIR / target_csv

        if not csv_path.exists():
            raise FileNotFoundError(csv_path)

        target_instances = load_target_instances(csv_path)
        pfvs_data = load_pfvs_results(pfvs_sources, target_instances)

        is_cpu = target_csv.startswith("cpu")
        update_csv(csv_path, pfvs_data, is_cpu)


if __name__ == "__main__":
    main()
