#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

try:
    import biodivine_aeon as ba
except ImportError:
    sys.exit("needs the AEON Python bindings: pip install biodivine_aeon")


def convert(bnet):
    bn = ba.BooleanNetwork.from_file(str(bnet)).infer_valid_graph() 
    sbml = bnet.with_suffix('.sbml')
    sbml.write_text(bn.to_sbml())
    return sbml


def main():
    ap = argparse.ArgumentParser(description='Write an SBML copy of .bnet networks for H.E.')
    ap.add_argument('paths', nargs='+', type=Path, help='.bnet files or folders of them')
    a = ap.parse_args()
    files = sorted(f for p in a.paths for f in (p.glob('*.bnet') if p.is_dir() else [p]))
    if not files:
        sys.exit('no .bnet files in ' + ', '.join(map(str, a.paths)))
    failed = []
    for f in files:
        try:
            convert(f)
        except Exception as e:
            failed.append(f)
            print(f'FAILED {f}: {type(e).__name__}: {e}', file=sys.stderr)
    print(f'{len(files) - len(failed)} of {len(files)} networks written as .sbml next to their .bnet')
    if failed:
        sys.exit(1)


if __name__ == '__main__':
    main()
