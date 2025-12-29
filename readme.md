# Specialized Project

This repository extends the supplementary material of **SAC4BN**:

> **SAT-based Method for Counting All Singleton Attractors in Boolean Networks**  
> Rei Higuchi, Takehide Soh, Daniel Le Berre, Morgan Magnin,  
> Mutsunori Banbara, Naoyuki Tamura  
> *IJCAI 2025 (in print)*

It integrates an additional **PFVS-based method** and provides a  
**fully reproducible experimental pipeline** for:

- **fASP-c** (conjunctive encoding)
- **fASP-s** (source encoding)
- **H.E.** (Hybrid Enumeration / BMSA)
- **PFVS** (Positive Feedback Vertex Set)
- Unified log analysis, tables, and cactus plots

---

## Directory Structure

```text
.
├── benchmarks
│   ├── biodivine-boolean-models
│   │   └── models
│   └── fASP
│       └── dataset
│           ├── BBM
│           ├── Random
│           └── Selected
├── build
│   ├── docker
│   │   ├── fasp
│   │   └── proposed
│   └── proposed_src
│       ├── lib
│       ├── project
│       └── src
│           └── main
│               └── scala
├── logs
│   ├── fasp_conj
│   ├── fasp_src
│   └── hybrid_bmsa
├── logs_analysis
│   ├── results
│   ├── fps_and_cpu.py
│   ├── num_solved.py
│   ├── merge_pfvs_into_results.py
│   ├── gen_dat.py
│   ├── regen_solved_csv.py
│   ├── cactus_log.plt
│   ├── cactus_random_log.plt
│   ├── cactus_selected_log.plt
│   └── cactus_all_log.plt
├── PFVS
│   ├── Examples
│   │   ├── BBM
│   │   ├── Random
│   │   └── Selected
│   ├── converter_pfvs.py
│   ├── run_pfvs_bbm.py
│   ├── run_pfvs_random.py
│   ├── run_pfvs_selected.py
│   ├── fpcollector.jar
│   ├── pfvs_bbm_results.csv
│   ├── pfvs_random_results.csv
│   └── pfvs_selected_results.csv
├── LICENSE
└── README.md
```
## Build Docker Images
```sh
cd build/docker/fasp
./build.sh

cd ../proposed
./build.sh
```
This builds:

fASP (conjunctive and source encodings)

H.E. (Hybrid Enumeration / BMSA)

## Running the Tools
fASP-c (conjunctive encoding)
```sh
docker run -t --rm \
  -v <DIR_CONTAINING_INPUT_FILE>:/benchmark \
  fasp <INPUT_FILENAME> -c
```
fASP-s (source encoding)
```sh
docker run -t --rm \
  -v <DIR_CONTAINING_INPUT_FILE>:/benchmark \
  fasp <INPUT_FILENAME> -c -e source
```
H.E. (Hybrid Enumeration / BMSA)
```sh
docker run -t --rm \
  -v <DIR_CONTAINING_INPUT_FILE>:/benchmark \
  bsaf /app/solve-bmsa.sh <JAVA_HEAP_SIZE> <JAVA_STACK_SIZE> h3 <INPUT_FILENAME>
```
Solver logs are generated under the logs/ directory.

## Running the PFVS Tool
Step 1: Convert .bnet to .bn
PFVS requires .bn input files.

```sh
cd PFVS
python3 converter_pfvs.py Examples/BBM
python3 converter_pfvs.py Examples/Random
python3 converter_pfvs.py Examples/Selected
```
Step 2: Run PFVS
```sh
python3 run_pfvs_bbm.py
python3 run_pfvs_random.py
python3 run_pfvs_selected.py
```
This generates:

pfvs_bbm_results.csv

pfvs_random_results.csv

pfvs_selected_results.csv

Move them into the analysis folder:

```sh
mv pfvs_*_results.csv ../logs_analysis/results/
```
Log Analysis and Result Generation
All commands below are executed from logs_analysis/.

```sh
cd logs_analysis
```
Step 1: Generate Base Result CSVs
```sh
python3 fps_and_cpu.py
python3 num_solved.py
```
Step 2: Merge PFVS Results
```sh
python3 merge_pfvs_into_results.py
```
Step 3: Regenerate .dat Files
```sh
python3 gen_dat.py
```
Step 4: Regenerate Solved-Instance Tables
```sh
python3 regen_solved_csv.py
```
Step 5: Merge .dat Files for Cactus Plots
```sh
cat results/time_for_cactus.dat results/time_fasp_for_cactus.dat \
  > results/time_all_for_cactus.dat
```
## Generating Cactus Plots
```sh
gnuplot cactus_log.plt
gnuplot cactus_random_log.plt
gnuplot cactus_selected_log.plt
gnuplot cactus_all_log.plt
```
The generated plots (.pdf / .eps) are stored in:

```text
logs_analysis/results/
```