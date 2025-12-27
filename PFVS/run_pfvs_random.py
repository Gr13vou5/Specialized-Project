import subprocess
import time
import csv
from pathlib import Path

# CONFIG
PFVS_JAR = "../../FPCollector.jar"
TIME_LIMIT = 900  # 30 minutes
MODE = "-m"        # deterministic PFVS

RANDOM_DIR = Path("examples/Random")
OUT_CSV = "pfvs_random_results.csv"

def run_pfvs(bn_file, writer):
    instance = bn_file.stem
    start = time.time()

    try:
        subprocess.run(
            ["java", "-jar", PFVS_JAR, bn_file.name, MODE],
            cwd=bn_file.parent,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=TIME_LIMIT
        )

        elapsed = time.time() - start
        fp_file = bn_file.with_suffix(".fp")

        if fp_file.exists():
            with open(fp_file) as f:
                num_fp = sum(1 for line in f if line.strip())
            status = "solved"
        else:
            num_fp = "NA"
            status = "timeout"

    except subprocess.TimeoutExpired:
        elapsed = TIME_LIMIT
        num_fp = "NA"
        status = "timeout"

    except Exception:
        elapsed = time.time() - start
        num_fp = "NA"
        status = "error"

    writer.writerow([instance, "PFVS", status, f"{elapsed:.2f}", num_fp])
    print(f"[DONE] {instance} | {status} | {elapsed:.1f}s")

def main():
    bn_files = sorted(RANDOM_DIR.glob("*.bn"))

    with open(OUT_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["instance", "solver", "status", "time_sec", "num_fp"])

        for bn in bn_files:
            print(f"[RUN] PFVS on {bn.name}")
            run_pfvs(bn, writer)

if __name__ == "__main__":
    main()
