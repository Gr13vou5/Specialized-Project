import csv
import sys
from pathlib import Path

csv.field_size_limit(sys.maxsize)

def convert_bnet_to_bn_fast(bnet_file, bn_file):
    with open(bnet_file, newline="") as f:
        reader = csv.reader(f)
        header = next(reader)

        with open(bn_file, "w") as out:
            for target, formula in reader:
                out.write(f"{target} = {formula}\n")

def convert_path(path):
    path = Path(path)

    if path.is_file():
        if path.suffix != ".bnet":
            raise ValueError("Input file must have .bnet extension")

        out_file = path.with_suffix(".bn")
        convert_bnet_to_bn_fast(path, out_file)
        print(f"[OK] Converted {path.name} → {out_file.name}")

    elif path.is_dir():
        bnet_files = list(path.rglob("*.bnet"))
        if not bnet_files:
            print("[WARN] No .bnet files found")
            return

        for bnet in bnet_files:
            bn = bnet.with_suffix(".bn")
            convert_bnet_to_bn_fast(bnet, bn)
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
