#!/usr/bin/env python3
"""Run fASP-c, fASP-s, H.E. and PFVS on the benchmark sets and write the logs
that logs_analysis/ reads.

The protocol follows the original SAC4BN runs whose logs are in logs/:

* every solver runs in its Docker image (build/docker/fasp -> "fasp",
  build/docker/proposed -> "bsaf") under GNU time (`time -v`);
* CPU time is limited per process to --time-limit seconds, like `ulimit -t`
  (default 1800 = 30 minutes), and memory to --memory (no swap);
* fASP-c / fASP-s run `fASP FILE -c -m 0 [-e source]`, H.E. runs
  `/app/solve-bmsa.sh HEAP 1g h3 FILE` (on the biodivine SBML files for BBM,
  as in the original runs, and on SBML copies of reduced BBM networks written by
  bnet_to_sbml.py) and PFVS runs `java -jar FPCollector.jar FILE.bn -m`.

Every log starts with the machine, date and limits it was produced with.
Finished logs are never rerun, so an interrupted run continues where it
stopped (use --force to redo).

Usage, from the repository root in Linux or WSL with Docker running:

    python3 run_benchmarks.py                     # all tools on BBM, Selected, Random
    python3 run_benchmarks.py --sets selected --limit 2      # quick smoke test
    python3 run_benchmarks.py --sets adf          # the ICCMA 2019 ADF networks
    python3 run_benchmarks.py --reduced B D2      # networks reduced by bn_reduce.py
                                                  # (for H.E. on BBM: bnet_to_sbml.py first)

Logs are written to logs_rerun/ (the original logs/ stay untouched), or to
logs_reduced/<variant>/ for reduced networks, in the same layout. See
readme.md for analysing them.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import itertools
import os
import platform
import re
import shlex
import socket
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "benchmarks" / "fASP" / "dataset"
BBM_MODELS = ROOT / "benchmarks" / "biodivine-boolean-models" / "models"
ADF_BNET = ROOT / "benchmarks" / "ADF" / "ICCMA2019" / "bnet"
REDUCED = ROOT / "benchmarks" / "reduced"
PFVS_DIR = ROOT / "PFVS"

SETS = ("bbm", "selected", "random", "adf")
DEFAULT_SETS = ("bbm", "selected", "random")
TOOLS = ("fasp_c", "fasp_s", "he", "pfvs")
VARIANTS = ("A", "B", "C", "D1", "D2", "E", "M")  #variants
REDUCED_SET_DIRS = {"bbm": ("BBM",), "random": ("Random",), "selected": ("Selected",), "adf": ("ADF", "bnet")}

SET_DIR = {"bbm": "bbm", "random": "fasp/Random", "selected": "fasp/Selected", "adf": "adf"}
TOOL_DIR = {"fasp_c": "fasp_conj", "fasp_s": "fasp_src", "he": "hybrid_bmsa"}

TIME_FIELDS = {
    "user": re.compile(r"^\s+User time \(seconds\): ([\d.]+)", re.M),
    "sys": re.compile(r"^\s+System time \(seconds\): ([\d.]+)", re.M),
    "rss": re.compile(r"^\s+Maximum resident set size \(kbytes\): (\d+)", re.M),
}


@dataclass(frozen=True)
class Instance:
    set: str
    name: str  # file stem
    bnet: Path
    sbml_dir: Path | None = None  # BBM only for he
    variant: str | None = None  # bn_reduce.py


@dataclass
class Config:
    logs: Path
    time_limit: int
    wall_limit: int
    memory: str
    memory_kb: int
    heap: str
    fasp_image: str
    he_image: str
    user: str | None
    force: bool


def parse_size_kb(text):
    m = re.fullmatch(r"(\d+)([kmgKMG])", text.strip())
    if not m:
        raise argparse.ArgumentTypeError(f"size must look like 12g or 4096m, got {text!r}")
    return int(m.group(1)) * {"k": 1, "m": 1024, "g": 1024**2}[m.group(2).lower()]


def find_instances(set_name, variant=None, reduced_dir=REDUCED):
    if variant:
        candidates = [reduced_dir / variant / d for d in REDUCED_SET_DIRS[set_name]]
        folder = next((c for c in candidates if any(c.glob("*.bnet"))), candidates[0])
    else:
        folder = ADF_BNET if set_name == "adf" else DATASET / {
            "bbm": "BBM", "random": "Random", "selected": "Selected"}[set_name]
    files = sorted(folder.glob("*.bnet"), key=lambda p: (p.stat().st_size, p.name))
    if not files:
        if variant:
            hint = (f" (reduce the set first, e.g. python3 bn_reduce.py reduction.csv "
                    f"<{set_name} .bnet files> --set {REDUCED_SET_DIRS[set_name][0]} --variants {variant})")
        else:
            hint = " (run python3 ADF/adf_to_bnet.py first)" if set_name == "adf" else ""
        sys.exit(f"no .bnet files in {folder}{hint}")
    out = []
    for f in files:
        sbml_dir = None
        if set_name == "bbm":
            number = f.stem.rsplit("_", 1)[-1]  # model_001 -> 001
            hits = sorted(BBM_MODELS.glob(f"[[]id-{number}[]]*"))
            if len(hits) != 1 or not (hits[0] / "model.sbml").exists():
                sys.exit(f"no unique biodivine model directory with model.sbml for {f.name}")
            sbml_dir = hits[0]
        out.append(Instance(set_name, f.stem, f, sbml_dir, variant))
    return out


def logs_root(cfg, inst):
    return cfg.logs / inst.variant if inst.variant else cfg.logs


def solver_input(tool, inst):
    """File the solver reads: SBML for H.E. on BBM, as in the original runs (the biodivine model,
    or for a reduced network the .sbml that bnet_to_sbml.py writes next to it); else the .bnet."""
    if tool == "he" and inst.set == "bbm":
        return inst.bnet.with_suffix(".sbml") if inst.variant else inst.sbml_dir / "model.sbml"
    return inst.bnet


def log_path(cfg, tool, inst):
    root = logs_root(cfg, inst)
    if tool == "pfvs":
        return root / "pfvs" / inst.set / f"{inst.name}.log"
    base = root / TOOL_DIR[tool] / SET_DIR[inst.set]
    if tool == "he" and inst.set == "bbm":
        return base / inst.sbml_dir.name / f"{solver_input(tool, inst).name}.log"
    return base / f"{inst.name}.bnet.log"


def pfvs_work(cfg, inst):
    return logs_root(cfg, inst) / "pfvs" / "work" / inst.set


def docker_run(cfg, container, image, mounts, args):
    cmd = ["docker", "run", "--rm", "--name", container, "--network", "none",
           "--ulimit", f"cpu={cfg.time_limit}:{cfg.time_limit}",
           "--memory", cfg.memory, "--memory-swap", cfg.memory]
    if cfg.user:
        cmd += ["--user", cfg.user]
    for host, target, read_only in mounts:
        cmd += ["-v", f"{host}:{target}" + (":ro" if read_only else "")]
    return cmd + [image] + args


def command(cfg, tool, inst, container):
    if tool in ("fasp_c", "fasp_s"):
        args = [inst.bnet.name, "-c", "-m", "0"] + (["-e", "source"] if tool == "fasp_s" else [])
        return docker_run(cfg, container, cfg.fasp_image, [(inst.bnet.parent, "/benchmark", True)], args)
    if tool == "he":
        f = solver_input(tool, inst)
        return docker_run(cfg, container, cfg.he_image, [(f.parent, "/benchmark", True)],
                          ["/app/solve-bmsa.sh", cfg.heap, "1g", "h3", f.name])
    return docker_run(cfg, container, cfg.he_image,
                      [(pfvs_work(cfg, inst), "/benchmark", False), (PFVS_DIR, "/pfvs", True)],
                      ["java", f"-Xmx{cfg.heap}", "-jar", "/pfvs/FPCollector.jar", f"{inst.name}.bn", "-m"])


_converter = None
_converter_lock = threading.Lock()


def prepare_pfvs(cfg, inst):
    """Convert the .bnet into PFVS's .bn format (once) and remove stale output."""
    global _converter
    with _converter_lock:
        if _converter is None:
            spec = importlib.util.spec_from_file_location("converter_pfvs", PFVS_DIR / "converter_pfvs.py")
            _converter = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(_converter)
    work = pfvs_work(cfg, inst)
    work.mkdir(parents=True, exist_ok=True)
    bn = work / f"{inst.name}.bn"
    if not bn.exists():
        tmp = work / f"{inst.name}.bn.tmp"
        _converter.convert_bnet_to_bn_pfvs(inst.bnet, tmp)
        tmp.replace(bn)
    (work / f"{inst.name}.fp").unlink(missing_ok=True)


def machine_description():
    cpu = platform.processor() or platform.machine()
    try:
        with open("/proc/cpuinfo") as f:
            m = re.search(r"^model name\s*:\s*(.+)$", f.read(), re.M)
            cpu = m.group(1).strip() if m else cpu
        with open("/proc/meminfo") as f:
            ram = int(re.search(r"^MemTotal:\s+(\d+)", f.read(), re.M).group(1)) / 1024**2
        ram = f"{ram:.1f} GiB RAM"
    except (OSError, AttributeError):
        ram = "RAM unknown"
    return f"{cpu}; {os.cpu_count()} logical CPUs; {ram}; {platform.platform()}"


class Runner:
    def __init__(self, cfg):
        self.cfg = cfg
        self.host = socket.gethostname()
        self.machine = machine_description()
        self.counter = itertools.count(1)
        self.active = set()
        self.lock = threading.Lock()
        self.stopping = threading.Event()

    def header(self, cmd, tool, inst):
        cfg = self.cfg
        f = solver_input(tool, inst)
        source = f"bn_reduce.py variant {inst.variant}" if inst.variant else "original"
        return (f"# Host: {self.host}\n"
                f"# Start date: {datetime.now().astimezone().strftime('%a %b %d %H:%M:%S %Z %Y')}\n"
                f"# Machine: {self.machine}\n"
                f"# Limits: cpu_time_s={cfg.time_limit} memory_kb={cfg.memory_kb} wall_s={cfg.wall_limit}\n"
                f"# Input: {f.relative_to(ROOT) if f.is_relative_to(ROOT) else f} ({source})\n"
                f"# Command: {shlex.join(map(str, cmd))}\n"
                + "-" * 60 + "\n")

    def run(self, tool, inst):
        """Run one solver on one instance; returns a short status for the progress line."""
        cfg = self.cfg
        log = log_path(cfg, tool, inst)
        if log.exists() and not cfg.force:
            return "already done"
        if self.stopping.is_set():
            return "cancelled"
        log.parent.mkdir(parents=True, exist_ok=True)
        superseded = None
        if tool == "he" and inst.set == "bbm" and inst.variant:
            old = log.with_name(f"{inst.bnet.name}.log")
            if old.exists():
                superseded = old.rename(old.with_name(old.name + ".superseded"))
        if tool == "pfvs":
            prepare_pfvs(cfg, inst)
        container = f"bench-{os.getpid()}-{next(self.counter)}"
        cmd = command(cfg, tool, inst, container)
        tmp = log.with_name(log.name + ".tmp")
        wall_hit = False
        start = time.monotonic()
        with open(tmp, "w") as fh:
            fh.write(self.header(cmd, tool, inst))
            fh.flush()
            with self.lock:
                self.active.add(container)
            try:
                proc = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT, start_new_session=True)
                try:
                    proc.wait(timeout=cfg.wall_limit)
                except subprocess.TimeoutExpired:
                    wall_hit = True
                    subprocess.run(["docker", "exec", container, "sh", "-c", "kill -9 -1"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    try:
                        proc.wait(timeout=60)
                    except subprocess.TimeoutExpired:
                        subprocess.run(["docker", "kill", container],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        proc.wait()
            finally:
                with self.lock:
                    self.active.discard(container)
        if self.stopping.is_set():
            tmp.unlink(missing_ok=True)
            return "cancelled"

        wall = time.monotonic() - start
        notes = []
        if wall_hit:
            notes.append(f"# Runner: wall-clock limit of {cfg.wall_limit}s reached; solver processes killed")
        status = f"wall {wall:.1f}s"
        if tool == "pfvs":
            fp = pfvs_work(cfg, inst) / f"{inst.name}.fp"
            text = tmp.read_text(errors="replace")
            if fp.exists() and re.search(r"^Ready ", text, re.M) and proc.returncode == 0:
                with open(fp) as f:
                    n = sum(1 for line in f if line.strip())
                notes.append(f"# Runner: fixed points = {n}")
                status += f", {n} fixed points"
            fp.unlink(missing_ok=True)
        notes.append(f"# Runner: docker exit code {proc.returncode}, wall time {wall:.1f}s")
        with open(tmp, "a") as fh:
            fh.write("\n".join(notes) + "\n")
        tmp.replace(log)
        if superseded:
            status += f" (earlier .bnet run kept as {superseded.name})"
        return status

    def stop(self):
        self.stopping.set()
        with self.lock:
            containers = list(self.active)
        for c in containers:
            subprocess.run(["docker", "kill", c], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def time_block(text):
    vals = {k: p.search(text) for k, p in TIME_FIELDS.items()}
    if not all(vals.values()):
        return None, None
    return float(vals["user"].group(1)) + float(vals["sys"].group(1)), int(vals["rss"].group(1))


def pfvs_result(text, cfg):
    cpu, rss = time_block(text)
    m = re.search(r"^# Runner: fixed points = (\d+)$", text, re.M)
    if m and cpu is not None and cpu <= cfg.time_limit:
        return "solved", cpu, m.group(1)
    if "No fixed points will be calculated" in text:
        return "refused", cpu, "NA"
    if "# Runner: wall-clock limit" in text or (cpu is not None and cpu > cfg.time_limit - 3):
        return "timeout", cpu, "NA"
    if ("OutOfMemoryError" in text or (rss is not None and rss > 0.75 * cfg.memory_kb)
            or "Command terminated by signal 9" in text):
        return "out_of_memory", cpu, "NA"
    return "error", cpu, "NA"


def write_pfvs_csv(cfg, set_name, insts):
    """Results table in the format of logs_analysis/merge_pfvs_into_results.py."""
    if not insts:
        return None, 0
    out = logs_root(cfg, insts[0]) / "pfvs" / f"pfvs_{set_name}_results.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for inst in insts:
        log = log_path(cfg, "pfvs", inst)
        if log.exists():
            status, cpu, n = pfvs_result(log.read_text(errors="replace"), cfg)
            rows.append([inst.name, "PFVS", status, "" if cpu is None else f"{cpu:.2f}", n])
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["instance", "solver", "status", "time_sec", "num_fp"])
        w.writerows(rows)
    return out, len(rows)


def check_docker():
    """Exit with Docker's own error message if the docker command or daemon is unavailable."""
    try:
        r = subprocess.run(["docker", "version"], capture_output=True, text=True)
    except FileNotFoundError:
        sys.exit("the docker command is not available here; on Windows, turn on Docker Desktop > "
                 "Settings > Resources > WSL integration for this Linux distribution")
    if r.returncode != 0:
        detail = (r.stderr or r.stdout).strip().splitlines()[-3:]
        sys.exit("Docker is not reachable:\n  " + "\n  ".join(detail) + "\n"
                 "start Docker Desktop and wait for 'Engine running' (or start the docker service), "
                 "then try again")


def docker_ok(args):
    return subprocess.run(["docker", *args], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode == 0


def docker_memory_kb():
    r = subprocess.run(["docker", "info", "--format", "{{.MemTotal}}"], capture_output=True, text=True)
    try:
        return int(r.stdout.strip()) // 1024
    except ValueError:
        return None


def main(argv=None):
    ap = argparse.ArgumentParser(description="Run fASP-c, fASP-s, H.E. and PFVS on the benchmark sets.")
    ap.add_argument("--sets", nargs="+", choices=SETS, default=list(DEFAULT_SETS),
                    help="benchmark sets (default: bbm selected random)")
    ap.add_argument("--tools", nargs="+", choices=TOOLS, default=list(TOOLS),
                    help="solvers (default: all)")
    ap.add_argument("--reduced", nargs="+", choices=VARIANTS, metavar="VARIANT",
                    help="run the networks reduced by bn_reduce.py with these variants (A B C D1 D2 E M) "
                         "instead of the original ones")
    ap.add_argument("--reduced-dir", type=Path, default=REDUCED,
                    help="where bn_reduce.py wrote the reduced networks (default: benchmarks/reduced)")
    ap.add_argument("--logs", type=Path,
                    help="log directory (default: logs_rerun, or logs_reduced/<variant> with --reduced)")
    ap.add_argument("--time-limit", type=int, default=1800, help="CPU seconds per process (default: 1800)")
    ap.add_argument("--memory", help="memory per run, e.g. 12g (default: 80%% of Docker's memory)")
    ap.add_argument("--heap", help="Java heap for H.E. and PFVS (default: memory minus 2g)")
    ap.add_argument("-j", "--jobs", type=int, default=1,
                    help="runs in parallel (default: 1; more jobs make the timings less comparable)")
    ap.add_argument("--only", help="run only instances whose name matches this pattern, e.g. 'model_00*'")
    ap.add_argument("--limit", type=int, help="run only the N smallest instances of each set")
    ap.add_argument("--force", action="store_true", help="rerun instances that already have a log")
    ap.add_argument("--dry-run", action="store_true", help="print the commands without running them")
    ap.add_argument("--fasp-image", default="fasp")
    ap.add_argument("--he-image", default="bsaf")
    args = ap.parse_args(argv)

    check_docker()
    images = {args.fasp_image} if set(args.tools) & {"fasp_c", "fasp_s"} else set()
    images |= {args.he_image} if set(args.tools) & {"he", "pfvs"} else set()
    missing = [i for i in sorted(images) if not docker_ok(["image", "inspect", i])]
    if missing and not args.dry_run:
        sys.exit(f"missing Docker image(s) {missing}; build them with "
                 "sh build/docker/fasp/build.sh and sh build/docker/proposed/build.sh")

    docker_kb = docker_memory_kb()
    if args.memory:
        memory_kb = parse_size_kb(args.memory)
    elif docker_kb:
        memory_kb = max(2 * 1024**2, int(docker_kb * 0.8) // 1024**2 * 1024**2)
    else:
        sys.exit("could not read Docker's memory size; pass --memory, e.g. --memory 12g")
    if docker_kb and memory_kb * args.jobs > docker_kb:
        sys.exit(f"{args.jobs} job(s) x {memory_kb / 1024**2:.1f} GiB exceed the {docker_kb / 1024**2:.1f} GiB "
                 "Docker can use; lower --memory or --jobs, or give Docker/WSL more memory")
    heap_kb = parse_size_kb(args.heap) if args.heap else max(1024**2, memory_kb - 2 * 1024**2)
    if heap_kb >= memory_kb:
        sys.exit("--heap must be smaller than --memory")

    logs = args.logs or ROOT / ("logs_reduced" if args.reduced else "logs_rerun")
    cfg = Config(
        logs=logs.resolve(), time_limit=args.time_limit,
        wall_limit=2 * args.time_limit + 120,
        memory=f"{memory_kb // 1024}m", memory_kb=memory_kb, heap=f"{heap_kb // 1024}m",
        fasp_image=args.fasp_image, he_image=args.he_image,
        user=f"{os.getuid()}:{os.getgid()}" if hasattr(os, "getuid") else None,
        force=args.force)

    variants = args.reduced or [None]
    insts = {}
    for v in variants:
        for s in args.sets:
            found = [i for i in find_instances(s, v, args.reduced_dir.resolve())
                     if not args.only or fnmatch(i.name, args.only)]
            insts[v, s] = found[: args.limit] if args.limit else found
    jobs = [(t, i) for v in variants for s in args.sets for t in args.tools for i in insts[v, s]]
    no_sbml = sorted({solver_input(t, i).parent for t, i in jobs if not solver_input(t, i).exists()})
    if no_sbml and not args.dry_run:
        sys.exit("H.E. reads BBM networks as SBML, like the original runs; write the reduced ones first:\n"
                 f"  python3 bnet_to_sbml.py {' '.join(os.path.relpath(d) for d in no_sbml)}")
    todo = [(t, i) for t, i in jobs if cfg.force or not log_path(cfg, t, i).exists()]

    where = ", ".join(str(cfg.logs / v) for v in args.reduced) if args.reduced else cfg.logs
    print(f"{len(jobs)} runs ({len(jobs) - len(todo)} already done), logs in {where}")
    print(f"limits: {cfg.time_limit}s CPU per process, {memory_kb / 1024**2:.1f} GiB memory, "
          f"Java heap {heap_kb / 1024**2:.1f} GiB, {args.jobs} job(s)")
    print(f"worst case {len(todo) * cfg.time_limit / args.jobs / 3600:.1f} h if every run hits the time limit")
    if args.dry_run:
        for t, i in todo[:10]:
            print(shlex.join(map(str, command(cfg, t, i, "NAME"))))
        return 0

    runner = Runner(cfg)
    started = time.monotonic()
    done = 0
    pool = ThreadPoolExecutor(max_workers=args.jobs)
    futures = {pool.submit(runner.run, t, i): (t, i) for t, i in todo}
    try:
        for fut in as_completed(futures):
            t, i = futures[fut]
            done += 1
            try:
                status = fut.result()
            except Exception as e:
                status = f"FAILED: {e}"
            elapsed = time.monotonic() - started
            eta = elapsed / done * (len(todo) - done)
            label = f"{i.name} [reduced {i.variant}]" if i.variant else i.name
            print(f"[{done}/{len(todo)}] {t:6s} {i.set:8s} {label}: {status}"
                  f"  (elapsed {elapsed / 3600:.1f} h, remaining about {eta / 3600:.1f} h)", flush=True)
    except KeyboardInterrupt:
        print("\ninterrupted: stopping running containers; rerun the same command to continue", file=sys.stderr)
        runner.stop()
        pool.shutdown(wait=True, cancel_futures=True)
        return 130
    pool.shutdown()

    if "pfvs" in args.tools:
        for v in variants:
            for s in args.sets:
                out, n = write_pfvs_csv(cfg, s, find_instances(s, v, args.reduced_dir.resolve()))
                print(f"PFVS results for {n} {s} instances{f' (reduced {v})' if v else ''}: {out}")
    for v in args.reduced or []:
        print(f"analyse variant {v} with: cd logs_analysis && LOGS_DIR={cfg.logs / v} python3 fps_and_cpu.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
