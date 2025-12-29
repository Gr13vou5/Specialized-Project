import csv
import sys
import re
from pathlib import Path

csv.field_size_limit(sys.maxsize)

VAR_RE = re.compile(r"\b[a-zA-Z][a-zA-Z0-9_]*\b")

def convert_bnet_to_bn_pfvs(bnet_file: Path, bn_file: Path):
    with open(bnet_file, newline="") as f:
        reader = csv.reader(f)
        header = next(reader) 
        rows = list(reader)

    variables = []
    var_set = set()

    for target, formula in rows:
        if target not in var_set:
            variables.append(target)
            var_set.add(target)

        for v in VAR_RE.findall(formula):
            if v not in {"AND", "OR", "NOT"} and v not in var_set:
                variables.append(v)
                var_set.add(v)

    mapping = {v: f"x{i+1}" for i, v in enumerate(variables)}

    with open(bn_file, "w") as out:
        for target, formula in rows:
            lhs = mapping[target]
            rhs = formula
            for orig, new in mapping.items():
                rhs = re.sub(rf"\b{re.escape(orig)}\b", new, rhs)
            out.write(f"{lhs} = {rhs}\n")

def convert_path(path):
    path = Path(path)

    if path.is_file():
        if path.suffix != ".bnet":
            raise ValueError("Input file must have .bnet extension")

        out_file = path.with_suffix(".bn")
        convert_bnet_to_bn_pfvs(path, out_file)
        print(f"[OK] Converted {path.name} → {out_file.name}")

    elif path.is_dir():
        bnet_files = list(path.rglob("*.bnet"))
        if not bnet_files:
            print("[WARN] No .bnet files found")
            return

        for bnet in bnet_files:
            bn = bnet.with_suffix(".bn")
            convert_bnet_to_bn_pfvs(bnet, bn)
            print(f"[OK] Converted {bnet} → {bn}")

    else:
        raise ValueError("Input path does not exist")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage:")
        print("  python3 converter_pfvs.py model.bnet")
        print("  python3 converter_pfvs.py /path/to/bnet_directory")
        sys.exit(1)

    convert_path(sys.argv[1])
