"""Translate ADF instances (k++ADF / ICCMA format) into BoolNet .bnet Boolean networks.

ADF input syntax (one statement per argument):

    s(a).        # a is an argument
    ac(a, f).    # f is the acceptance condition of a

where f is built from argument names, the constants c(v) / c(f), and the
connectives neg/1, and/2, or/2, xor/2, imp/2, iff/2.

Translation: every argument s
becomes a Boolean variable v_s whose update function is its acceptance
condition. The 2-valued models of the ADF are then exactly the fixed points
of the Boolean network.

The .bnet output is restricted to what every solver in this repository can
parse (fASP, H.E./bsaf, PFVS):

* only the connectives & | ! and parentheses (no XOR, no constants);
* xor/iff/imp are rewritten with & | !;
* constants are folded away; an acceptance condition that is constantly
  true (false) is written as "v_s | !v_s" ("v_s & !v_s");
* double negations are removed.

Rewriting xor/iff duplicates both operands, so deeply nested XOR formulas grow
exponentially. In "auto" mode an instance is expanded directly when its
expanded size stays below --max-expanded-nodes; otherwise every non-literal
operand of an xor/iff is replaced by an auxiliary variable aux_k whose update
function is that operand. Auxiliary variables are fully determined by the
arguments at a fixed point, so fixed points of the resulting network are in
one-to-one correspondence with the 2-valued models of the ADF (projection
onto the v_* variables). This does NOT hold for trap spaces, i.e. complete or
preferred interpretations.

Usage:
    python3 adf_to_bnet.py
        Translate the ICCMA 2019 instances in benchmarks/ADF/ICCMA2019/adf
        into benchmarks/ADF/ICCMA2019/bnet.
    python3 adf_to_bnet.py INPUT [INPUT ...] -o OUT_DIR [-j JOBS]
        [--mode auto|expand|aux] [--max-expanded-nodes N]
        Translate other instances. INPUT is an .adf file or a directory
"""

from __future__ import annotations

import argparse
import multiprocessing
import os
import re
import sys
import time
from pathlib import Path

VAR, TRUE, FALSE, NOT, AND, OR, XOR, IFF, IMP = range(9)

# node ids of the two constants (Formulas creates them first)
T_NODE, F_NODE = 0, 1

OPERATORS = {"neg": NOT, "and": AND, "or": OR, "xor": XOR, "iff": IFF, "imp": IMP}

TOKEN_RE = re.compile(r"\s*(?:([A-Za-z0-9_]+)|([(),.]))")
NAME_RE = re.compile(r"[A-Za-z0-9_]+")

DEFAULT_MAX_EXPANDED_NODES = 15 * 10**6

# default input/output: the ICCMA 2019 ADF instances used by BAss (arXiv:2604.27576)
REPO_ROOT = Path(__file__).resolve().parent.parent
ICCMA19_ADF_DIR = REPO_ROOT / "benchmarks" / "ADF" / "ICCMA2019" / "adf"
ICCMA19_BNET_DIR = REPO_ROOT / "benchmarks" / "ADF" / "ICCMA2019" / "bnet"


class AdfError(ValueError):
    pass


class Formulas:
    """Hash-consed formula DAG with constant folding and double-negation removal."""

    def __init__(self):
        self.kind = [TRUE, FALSE]
        self.args = [(), ()]
        self.index = {}

    def _node(self, kind, args):
        key = (kind, args)
        n = self.index.get(key)
        if n is None:
            n = len(self.kind)
            self.kind.append(kind)
            self.args.append(args)
            self.index[key] = n
        return n

    def var(self, name):
        return self._node(VAR, name)

    def neg(self, a):
        k = self.kind[a]
        if k == TRUE:
            return F_NODE
        if k == FALSE:
            return T_NODE
        if k == NOT:
            return self.args[a][0]
        return self._node(NOT, (a,))

    def conj(self, a, b):
        if self.kind[a] == FALSE or self.kind[b] == FALSE:
            return F_NODE
        if self.kind[a] == TRUE:
            return b
        if self.kind[b] == TRUE:
            return a
        return self._node(AND, (a, b))

    def disj(self, a, b):
        if self.kind[a] == TRUE or self.kind[b] == TRUE:
            return T_NODE
        if self.kind[a] == FALSE:
            return b
        if self.kind[b] == FALSE:
            return a
        return self._node(OR, (a, b))

    def xor(self, a, b):
        for x, y in ((a, b), (b, a)):
            if self.kind[x] == TRUE:
                return self.neg(y)
            if self.kind[x] == FALSE:
                return y
        return self._node(XOR, (a, b))

    def iff(self, a, b):
        for x, y in ((a, b), (b, a)):
            if self.kind[x] == TRUE:
                return y
            if self.kind[x] == FALSE:
                return self.neg(y)
        return self._node(IFF, (a, b))

    def imp(self, a, b):
        if self.kind[a] == FALSE or self.kind[b] == TRUE:
            return T_NODE
        if self.kind[a] == TRUE:
            return b
        if self.kind[b] == FALSE:
            return self.neg(a)
        return self._node(IMP, (a, b))

    def build(self, op, children):
        if op == NOT:
            if len(children) != 1:
                raise AdfError(f"neg expects 1 argument, got {len(children)}")
            return self.neg(children[0])
        if op in (AND, OR):
            if not children:
                raise AdfError("and/or expect at least 1 argument")
            f = self.conj if op == AND else self.disj
            acc = children[0]
            for c in children[1:]:
                acc = f(acc, c)
            return acc
        if len(children) != 2:
            raise AdfError(f"xor/iff/imp expect 2 arguments, got {len(children)}")
        return {XOR: self.xor, IFF: self.iff, IMP: self.imp}[op](*children)

    def is_literal(self, n):
        k = self.kind[n]
        return k == VAR or (k == NOT and self.kind[self.args[n][0]] == VAR)

    def topological(self, roots):
        """Nodes reachable from roots, children before parents."""
        seen = set()
        order = []
        for r in roots:
            if r in seen:
                continue
            stack = [(r, False)]
            while stack:
                n, done = stack.pop()
                if done:
                    order.append(n)
                    continue
                if n in seen:
                    continue
                seen.add(n)
                stack.append((n, True))
                if self.kind[n] not in (VAR, TRUE, FALSE):
                    for c in self.args[n]:
                        if c not in seen:
                            stack.append((c, False))
        return order

    def expanded_sizes(self, roots):
        """Number of tokens of each root after rewriting xor/iff/imp with & | !."""
        size = {}
        for n in self.topological(roots):
            k = self.kind[n]
            if k in (VAR, TRUE, FALSE):
                size[n] = 1
            elif k == NOT:
                size[n] = size[self.args[n][0]] + 1
            elif k in (AND, OR):
                size[n] = size[self.args[n][0]] + size[self.args[n][1]] + 1
            elif k in (XOR, IFF):
                size[n] = 2 * (size[self.args[n][0]] + size[self.args[n][1]]) + 5
            else:  # IMP
                size[n] = size[self.args[n][0]] + size[self.args[n][1]] + 2
        return [size[r] for r in roots]


def tokenize(text):
    pos = 0
    end = len(text)
    while True:
        m = TOKEN_RE.match(text, pos)
        if m is None:
            rest = text[pos:]
            if rest.strip() == "":
                return
            line = text.count("\n", 0, pos) + 1
            raise AdfError(f"line {line}: unexpected input {rest.lstrip()[:30]!r}")
        pos = m.end()
        yield m.group(1) or m.group(2)
        if pos >= end:
            return


class Tokens:
    def __init__(self, text):
        self._it = tokenize(text)
        self._peek = None

    def peek(self):
        if self._peek is None:
            self._peek = next(self._it, "")
        return self._peek

    def next(self):
        t = self.peek()
        self._peek = None
        return t

    def expect(self, t):
        got = self.next()
        if got != t:
            raise AdfError(f"expected {t!r}, got {got!r}")


def parse_formula(tokens, fs, arg_nodes):
    """Iteratively parse one formula; deep nesting is common in ICCMA'19."""
    stack = []  # frames: [operator, children]
    while True:
        t = tokens.next()
        if not t or not NAME_RE.fullmatch(t):
            raise AdfError(f"unexpected token {t!r} in formula")
        if tokens.peek() == "(":
            tokens.next()
            if t == "c":
                v = tokens.next()
                tokens.expect(")")
                if v not in ("v", "f"):
                    raise AdfError(f"unknown constant c({v})")
                node = T_NODE if v == "v" else F_NODE
            elif t in OPERATORS:
                stack.append([OPERATORS[t], []])
                continue
            else:
                raise AdfError(f"unknown operator {t!r}")
        else:
            node = arg_nodes.get(t)
            if node is None:
                node = arg_nodes[t] = fs.var(t)
        while True:
            if not stack:
                return node
            stack[-1][1].append(node)
            sep = tokens.next()
            if sep == ",":
                break
            if sep != ")":
                raise AdfError(f"expected ',' or ')', got {sep!r}")
            op, children = stack.pop()
            node = fs.build(op, children)


def parse_adf(text):
    """Return (arguments in declaration order, {argument: formula node}, Formulas)."""
    fs = Formulas()
    arg_nodes = {}
    declared = []
    declared_set = set()
    acs = {}
    tokens = Tokens(text)
    while tokens.peek():
        head = tokens.next()
        tokens.expect("(")
        if head == "s":
            name = tokens.next()
            if not NAME_RE.fullmatch(name):
                raise AdfError(f"bad argument name {name!r}")
            tokens.expect(")")
            if name in declared_set:
                raise AdfError(f"argument {name!r} declared twice")
            declared.append(name)
            declared_set.add(name)
        elif head == "ac":
            name = tokens.next()
            tokens.expect(",")
            if name in acs:
                raise AdfError(f"two acceptance conditions for {name!r}")
            acs[name] = parse_formula(tokens, fs, arg_nodes)
            tokens.expect(")")
        else:
            raise AdfError(f"unknown statement {head!r}")
        tokens.expect(".")

    for name in acs:
        if name not in declared_set:
            raise AdfError(f"acceptance condition for undeclared argument {name!r}")
    for name in arg_nodes:
        if name not in declared_set:
            raise AdfError(f"undeclared argument {name!r} used in an acceptance condition")
    missing = [s for s in declared if s not in acs]
    if missing:
        raise AdfError(f"no acceptance condition for {missing[:5]}")
    return declared, acs, fs


def introduce_aux(fs, roots):
    """Replace every non-literal operand of xor/iff by an auxiliary variable.

    Returns (new roots, [(aux name, definition node)]). Definitions only use
    argument variables and earlier auxiliary variables, so aux values are
    uniquely determined by the arguments at a fixed point.
    """
    new = {}
    aux_of = {}
    aux_defs = []

    def name_operand(n):
        if fs.is_literal(n):
            return n
        a = aux_of.get(n)
        if a is None:
            name = f"aux_{len(aux_defs) + 1}"
            # keyed apart from argument names, so an argument called "aux_1" cannot clash
            a = aux_of[n] = fs.var(("aux", name))
            aux_defs.append((name, n))
        return a

    for n in fs.topological(roots):
        k = fs.kind[n]
        if k in (VAR, TRUE, FALSE):
            new[n] = n
        elif k == NOT:
            new[n] = fs.neg(new[fs.args[n][0]])
        else:
            a, b = (new[c] for c in fs.args[n])
            if k == AND:
                new[n] = fs.conj(a, b)
            elif k == OR:
                new[n] = fs.disj(a, b)
            elif k == IMP:
                new[n] = fs.imp(a, b)
            elif k == XOR:
                new[n] = fs.xor(name_operand(a), name_operand(b))
            else:
                new[n] = fs.iff(name_operand(a), name_operand(b))
    return [new[r] for r in roots], aux_defs


def emit(fs, root, names, out):
    """Append the .bnet text of root to out (a list of strings).

    Iterative; n-ary &/| chains are flattened while printing.
    """
    kind, args = fs.kind, fs.args
    stack = [root]
    while stack:
        item = stack.pop()
        if isinstance(item, str):
            out.append(item)
            continue
        n = item
        k = kind[n]
        if k == VAR:
            out.append(names[args[n]])
        elif k == NOT:
            c = args[n][0]
            out.append("!")
            stack.append(c)
        elif k in (AND, OR):
            sep = " & " if k == AND else " | "
            leaves = []
            todo = [n]
            while todo:
                m = todo.pop()
                if kind[m] == k:
                    todo.append(args[m][1])
                    todo.append(args[m][0])
                else:
                    leaves.append(m)
            out.append("(")
            stack.append(")")
            for i in range(len(leaves) - 1, -1, -1):
                stack.append(leaves[i])
                if i:
                    stack.append(sep)
        elif k in (XOR, IFF, IMP):
            p, q = args[n]
            np_, nq = fs.neg(p), fs.neg(q)
            if k == XOR:
                parts = ["((", p, " & ", nq, ") | (", np_, " & ", q, "))"]
            elif k == IFF:
                parts = ["((", p, " & ", q, ") | (", np_, " & ", nq, "))"]
            else:
                parts = ["(", np_, " | ", q, ")"]
            stack.extend(reversed(parts))
        else:
            raise AssertionError("constants must be folded before printing")


def bnet_names(arguments):
    names = {}
    used = set()
    for a in arguments:
        base = "v_" + re.sub(r"[^A-Za-z0-9_]", "_", a)
        name = base
        i = 1
        while name in used:
            i += 1
            name = f"{base}__{i}"
        used.add(name)
        names[a] = name
    return names


def convert(text, mode="auto", max_expanded_nodes=DEFAULT_MAX_EXPANDED_NODES):
    """Return (bnet lines generator factory, stats dict)."""
    arguments, acs, fs = parse_adf(text)
    roots = [acs[a] for a in arguments]
    expanded = sum(fs.expanded_sizes(roots))

    if mode == "auto":
        mode = "expand" if expanded <= max_expanded_nodes else "aux"
    aux_defs = []
    if mode == "aux":
        roots, aux_defs = introduce_aux(fs, roots)
    elif mode != "expand":
        raise ValueError(f"unknown mode {mode!r}")

    names = bnet_names(arguments)
    names.update({("aux", a): a for a, _ in aux_defs})

    constant = sum(1 for r in roots if fs.kind[r] in (TRUE, FALSE))
    stats = {
        "arguments": len(arguments),
        "aux_variables": len(aux_defs),
        "constant_functions": constant,
        "mode": mode,
        "expanded_nodes": expanded,
    }

    def lines():
        yield "targets, factors\n"
        for target, root in [(names[a], r) for a, r in zip(arguments, roots)] + aux_defs:
            if fs.kind[root] == TRUE:
                yield f"{target}, {target} | !{target}\n"
            elif fs.kind[root] == FALSE:
                yield f"{target}, {target} & !{target}\n"
            else:
                out = [target, ", "]
                emit(fs, root, names, out)
                out.append("\n")
                yield "".join(out)

    return lines, stats


def collect_inputs(paths):
    files = []
    for p in map(Path, paths):
        if p.is_dir():
            files.extend(sorted(p.rglob("*.adf")))
        elif p.is_file():
            files.append(p)
        else:
            raise FileNotFoundError(p)
    return files


def output_name(adf_file):
    name = adf_file.name
    return (name[: -len(".adf")] if name.endswith(".adf") else name) + ".bnet"


def convert_file(task):
    """Worker: translate one .adf file. Returns (file name, stats or None, error or None)."""
    src, out, mode, max_expanded_nodes = task
    try:
        lines, stats = convert(src.read_text(encoding="utf-8"), mode, max_expanded_nodes)
        tmp = out.with_suffix(".bnet.tmp")
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            for line in lines():
                fh.write(line)
        tmp.replace(out)
        return src.name, stats, None
    except (AdfError, RecursionError, MemoryError, UnicodeDecodeError) as e:
        return src.name, None, str(e) or type(e).__name__


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Translate ADF instances into .bnet Boolean networks. Without arguments, "
                    "translates the ICCMA 2019 instances of this repository.")
    ap.add_argument("inputs", nargs="*", type=Path,
                    help=f".adf files or directories (default: {ICCMA19_ADF_DIR.relative_to(REPO_ROOT)})")
    ap.add_argument("-o", "--out-dir", type=Path,
                    help=f"output directory (default: {ICCMA19_BNET_DIR.relative_to(REPO_ROOT)})")
    ap.add_argument("-j", "--jobs", type=int, default=min(4, os.cpu_count() or 1),
                    help="instances translated in parallel (default: min(4, CPUs))")
    ap.add_argument("--mode", choices=["auto", "expand", "aux"], default="auto",
                    help="xor/iff handling: expand directly, use auxiliary variables, "
                         "or choose per instance (default)")
    ap.add_argument("--max-expanded-nodes", type=int, default=DEFAULT_MAX_EXPANDED_NODES,
                    help="auto mode: largest expanded size converted without auxiliary variables "
                         f"(default {DEFAULT_MAX_EXPANDED_NODES})")
    args = ap.parse_args(argv)

    if not args.inputs:
        args.inputs = [ICCMA19_ADF_DIR]
        args.out_dir = args.out_dir or ICCMA19_BNET_DIR
    elif args.out_dir is None:
        ap.error("-o/--out-dir is required when inputs are given")

    try:
        files = collect_inputs(args.inputs)
    except FileNotFoundError as e:
        ap.error(f"{e} does not exist")
    if not files:
        ap.error(f"no .adf files found in {', '.join(map(str, args.inputs))}")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    # largest first, so the slow instances do not end up alone at the end
    files.sort(key=lambda f: -f.stat().st_size)
    tasks = [(f, args.out_dir / output_name(f), args.mode, args.max_expanded_nodes) for f in files]

    start = time.perf_counter()
    modes = {"expand": 0, "aux": 0}
    failed = 0
    if args.jobs > 1 and len(tasks) > 1:
        pool = multiprocessing.Pool(args.jobs)
        results = pool.imap_unordered(convert_file, tasks)
    else:
        pool = None
        results = map(convert_file, tasks)
    for i, (name, stats, err) in enumerate(results, 1):
        if err is not None:
            failed += 1
            print(f"[{i}/{len(tasks)}] FAIL {name}: {err}", file=sys.stderr)
            continue
        modes[stats["mode"]] += 1
        aux = f", {stats['aux_variables']} aux" if stats["aux_variables"] else ""
        print(f"[{i}/{len(tasks)}] {name} ({stats['mode']}, {stats['arguments']} args{aux})",
              flush=True)
    if pool is not None:
        pool.close()
        pool.join()

    print(f"translated {len(tasks) - failed}/{len(tasks)} instances into {args.out_dir} "
          f"({modes['expand']} expanded, {modes['aux']} with auxiliary variables) "
          f"in {time.perf_counter() - start:.0f}s", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
