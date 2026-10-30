#!/usr/bin/env python3
"""
Fixed-point-preserving reductions of Boolean networks (.bnet), following
Saadatpour, Albert & Reluga (2013), "A reduction method for Boolean network
models proven to conserve attractors", with SOURCE NODES LEFT FREE (as in
fixed-point enumeration with fASP / H.E.).

Variants (each includes the previous constant propagation step):
  A   Algorithm 1 only: eliminate nodes whose function is constant and
      propagate the constant downstream (sources are NOT fixed).
  B   A + Algorithm 2 as described in Sec. 2 and applied in Sec. 3 of the
      paper: merge a mediator v with in-degree 1 (from u != v) and
      out-degree 1 (to w), u != w, and no edge between u and w in either
      direction. (The pseudo-code of Algorithm 2 also asks that w depend only
      on v, but the paper's own ABA example removes cGMP, whose target CIS
      has three regulators, so that condition is not applied here.)
  C   A + relaxed Algorithm 2 (what the paper itself applies to the ABA
      network): same mediator, but u and w may share an edge (u == w is
      allowed too, which the paper does not discuss).
  D1  A + eliminate every non-source node whose function depends on a single
      other node (any out-degree). Still formula-size-safe: the node's
      function is a literal, so substitution never grows formulas.
  D2  D1 + iteratively remove non-source "leaf" nodes (out-degree 0, no
      self-loop); their fixed-point value is determined by the rest.
  E   D2 + general elimination (Algorithm R of Veliz-Cuba 2011): substitute
      the whole function of a non-source node without a self-loop into the
      nodes that read it, whenever that does not grow the total formula size.
  M   A + leaves + general elimination of mediators only: no input of the
      node reads one of its targets (Tonello & Pauleve 2024). Every step of M
      is such an elimination (constants have no inputs, leaves no targets),
      so M also preserves the minimal trap spaces (their Theorem 3.3), which
      C, D1, D2 and E do not guarantee.

All variants preserve fixed points one-to-one (Veliz-Cuba 2011: eliminating a
node without a self-loop by substitution keeps the fixed points), so any of
them is a valid pre-processing step for fixed-point enumeration. No step makes
the total formula size grow.

Dependencies are computed semantically: read-once formulas exactly from
syntax, other formulas with <= MAX_TT variables by truth table, the rest
(flagged) syntactically.

Usage (from the repository root):
    python3 bn_reduce.py reduction.csv benchmarks/fASP/dataset/BBM/*.bnet --set BBM

writes one statistics row per model to reduction.csv (rows of the same set
and model are replaced when rerun) and the reduced networks of the variants
in --variants (default B and D2) to benchmarks/reduced/<variant>/<set>/.

time_<variant> is the CPU time in seconds to obtain that variant's network:
reading the .bnet, reducing, and writing the reduced file when it is written
(interpreter start-up excluded), to be added to the solving time of the tools.
"""
import sys, re, os, csv, argparse, time
from pathlib import Path
import numpy as np

sys.setrecursionlimit(1_000_000)
MAX_TT = 20
DEFAULT_OUT = Path(__file__).resolve().parent / 'benchmarks' / 'reduced'

# ---------------------------------------------------------------- parsing
TOK = re.compile(r'\s*([A-Za-z0-9_.]+|[!&|()])')
PREC = {'!': 3, '&': 2, '|': 1}


def tokenize(s):
    pos, toks = 0, []
    s = s.rstrip()
    while pos < len(s):
        m = TOK.match(s, pos)
        if not m:
            raise ValueError(f"cannot tokenize at {pos}: {s[pos:pos+30]!r}")
        toks.append(m.group(1))
        pos = m.end()
    return toks


def parse_expr(s):
    out, ops = [], []

    def apply(op):
        if op == '!':
            out.append(('!', out.pop()))
        else:
            b, a = out.pop(), out.pop()
            out.append((op, (a, b)))

    for t in tokenize(s):
        if t == '(':
            ops.append(t)
        elif t == ')':
            while ops[-1] != '(':
                apply(ops.pop())
            ops.pop()
        elif t == '!':
            ops.append(t)
        elif t in ('&', '|'):
            while ops and ops[-1] != '(' and PREC[ops[-1]] >= PREC[t]:
                apply(ops.pop())
            ops.append(t)
        elif t in ('0', 'false', 'False'):
            out.append(('c', False))
        elif t in ('1', 'true', 'True'):
            out.append(('c', True))
        else:
            out.append(('v', t))
    while ops:
        apply(ops.pop())
    assert len(out) == 1, s
    return out[0]


def read_bnet(path):
    funcs = {}
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            tgt, _, rhs = line.partition(',')
            tgt = tgt.strip()
            if tgt == 'targets':
                continue
            funcs[tgt] = parse_expr(rhs)
    return funcs


# ------------------------------------------------------------ expressions
def simp(e):
    t = e[0]
    if t in ('v', 'c'):
        return e
    if t == '!':
        a = simp(e[1])
        if a[0] == 'c':
            return ('c', not a[1])
        if a[0] == '!':
            return a[1]
        return ('!', a)
    absorb = (t == '|')
    kids = []
    for k in e[1]:
        k = simp(k)
        if k[0] == 'c':
            if k[1] == absorb:
                return ('c', absorb)
            continue
        if k[0] == t:
            kids.extend(k[1])
        else:
            kids.append(k)
    seen, uniq = set(), []
    for k in kids:
        if k not in seen:
            seen.add(k)
            uniq.append(k)
    for k in uniq:
        if ('!', k) in seen:
            return ('c', absorb)
    if not uniq:
        return ('c', not absorb)
    if len(uniq) == 1:
        return uniq[0]
    return (t, tuple(uniq))


def var_occurrences(e, acc):
    stack = [e]
    while stack:
        x = stack.pop()
        if x[0] == 'v':
            acc[x[1]] = acc.get(x[1], 0) + 1
        elif x[0] == '!':
            stack.append(x[1])
        elif x[0] in ('&', '|'):
            stack.extend(x[1])
    return acc


def subst(e, v, repl):
    t = e[0]
    if t == 'v':
        return repl if e[1] == v else e
    if t == 'c':
        return e
    if t == '!':
        return ('!', subst(e[1], v, repl))
    return (t, tuple(subst(k, v, repl) for k in e[1]))


def truth_table(e, order):
    k = len(order)
    base = np.arange(1 << k, dtype=np.uint32)
    idx = {x: i for i, x in enumerate(order)}

    def ev(x):
        t = x[0]
        if t == 'v':
            return ((base >> idx[x[1]]) & 1).astype(bool)
        if t == 'c':
            return np.full(1 << k, x[1])
        if t == '!':
            return ~ev(x[1])
        arrs = [ev(c) for c in x[1]]
        return np.logical_and.reduce(arrs) if t == '&' else np.logical_or.reduce(arrs)
    return ev(e)


def analyze(e):
    """-> (expr, support:set, const:None|bool, exact:bool)"""
    e = simp(e)
    if e[0] == 'c':
        return e, set(), e[1], True
    occ = var_occurrences(e, {})
    if all(c == 1 for c in occ.values()):
        return e, set(occ), None, True
    order = sorted(occ)
    if len(order) > MAX_TT:
        return e, set(occ), None, False
    T = truth_table(e, order)
    if T.all() or not T.any():
        val = bool(T[0])
        return ('c', val), set(), val, True
    sup = set()
    for i, x in enumerate(order):
        R = T.reshape(-1, 2, 1 << i)
        if (R[:, 0, :] != R[:, 1, :]).any():
            sup.add(x)

    for x in set(order) - sup:
        e = subst(e, x, ('c', False))
    e = simp(e)
    assert set(var_occurrences(e, {})) == sup
    return e, sup, None, True


def literal_of(e, u):
    """e depends semantically only on u: return ('v',u) or ('!',('v',u))."""
    occ = var_occurrences(e, {})
    order = sorted(occ)
    T = truth_table(e, order)
    i = order.index(u)
    R = T.reshape(-1, 2, 1 << i)
    pos = bool(R[0, 1, 0])
    return ('v', u) if pos else ('!', ('v', u))


def to_str(e):
    t = e[0]
    if t == 'v':
        return e[1]
    if t == 'c':
        return '1' if e[1] else '0'
    if t == '!':
        return '!' + to_str(e[1])
    op = ' & ' if t == '&' else ' | '
    return '(' + op.join(to_str(k) for k in e[1]) + ')'


# --------------------------------------------------------------- network
class Network:
    def __init__(self, funcs):
        self.f, self.dep, self.approx = {}, {}, set()
        names = set(funcs)
        for v, e in funcs.items():
            for x in var_occurrences(e, {}):
                if x not in names:
                    names.add(x)
        for v in names:
            e = funcs.get(v, ('v', v))
            self._set(v, e)
        self.succ = {v: set() for v in self.f}
        for v, d in self.dep.items():
            for u in d:
                self.succ[u].add(v)
        self.removed = {}

    def _set(self, v, e):
        e, sup, const, exact = analyze(e)
        self.f[v], self.dep[v] = e, sup
        if exact:
            self.approx.discard(v)
        else:
            self.approx.add(v)

    def is_source(self, v):
        return self.f[v] == ('v', v)

    def const(self, v):
        return self.f[v][1] if self.f[v][0] == 'c' else None

    def _reanalyze(self, w):
        old = self.dep[w]
        self._set(w, self.f[w])
        new = self.dep[w]
        for u in old - new:
            self.succ[u].discard(w)
        for u in new - old:
            self.succ[u].add(w)

    def eliminate(self, v, repl, how):
        """substitute repl for v in all successors, then drop v."""
        for w in list(self.succ[v]):
            if w == v:
                continue
            self.f[w] = subst(self.f[w], v, repl)
            self._reanalyze(w)
        for u in self.dep[v]:
            self.succ[u].discard(v)
        del self.f[v], self.dep[v], self.succ[v]
        self.approx.discard(v)
        self.removed[v] = how

    def substitutable(self, v, general):
        """v can be eliminated by substituting its whole function into the nodes that read it
        (Veliz-Cuba's Algorithm R): no self-loop, read by another node, and the total formula
        size does not grow. general='mediator': also no input of v reads a target of v."""
        d = self.dep[v]
        outs = self.succ[v] - {v}
        if v in d or not outs:
            return False
        if general == 'mediator' and any(u in self.dep[w] for u in d for w in outs):
            return False
        occ = sum(var_occurrences(self.f[w], {}).get(v, 0) for w in outs)
        size = sum(var_occurrences(self.f[v], {}).values())
        return (occ - 1) * size <= occ 

    def reduce(self, mode=None, leaves=False, general=None):
        changed = True
        while changed:
            changed = False
            for v in sorted(self.f):
                if v not in self.f:
                    continue
                c = self.const(v)
                if c is not None:
                    self.eliminate(v, ('c', c), 'const')
                    changed = True
                    continue
                d = self.dep[v]
                if mode and len(d) == 1 and v not in d:
                    (u,) = tuple(d)
                    outs = self.succ[v] - {v}
                    ok = False
                    if mode == 'indeg1':
                        ok = True
                    elif len(outs) == 1:
                        (w,) = tuple(outs)
                        if mode == 'relaxed':
                            ok = True
                        elif mode == 'strict':
                            ok = (w != u and u not in self.dep[w]
                                  and w not in self.dep[u])
                    if ok:
                        self.eliminate(v, literal_of(self.f[v], u), 'mediator')
                        changed = True
                        continue
                if (leaves and not self.is_source(v) and v not in d
                        and not (self.succ[v] - {v})):
                    self.eliminate(v, None, 'leaf')
                    changed = True
                    continue
                if general and self.substitutable(v, general):
                    self.eliminate(v, self.f[v], 'general')
                    changed = True
        return self

    def write_bnet(self, path):
        for v, e in self.f.items():
            assert set(var_occurrences(e, {})) <= set(self.f), (path, v)
        with open(path, 'w') as fh:
            fh.write('targets, factors\n')
            for v in sorted(self.f):
                fh.write(f'{v}, {to_str(self.f[v])}\n')


# ------------------------------------------------------------------ main
VARIANTS = [('A', None, False, None), ('B', 'strict', False, None), ('C', 'relaxed', False, None),
            ('D1', 'indeg1', False, None), ('D2', 'indeg1', True, None),
            ('E', 'indeg1', True, 'any'), ('M', None, True, 'mediator')]


FIELDS = ['set', 'model', 'n', 'sources', 'nonsource', 'const0', 'approx_funcs'] + [
    f'{k}_{name}' for name, *_ in VARIANTS for k in ('rm', 'src')] + [
    f'time_{name}' for name, *_ in VARIANTS]


def run(path, outdir=None, set_name='', write_variants=('B', 'D2')):
    start = time.process_time()
    funcs = read_bnet(path)
    read_time = time.process_time() - start
    base = Network(funcs)
    n = len(base.f)
    sources = sum(base.is_source(v) for v in base.f)
    row = dict(n=n, sources=sources, nonsource=n - sources,
               const0=sum(base.const(v) is not None for v in base.f),
               approx_funcs=len(base.approx))
    for name, mode, leaves, general in VARIANTS:
        start = time.process_time()
        net = Network(funcs).reduce(mode, leaves, general)
        if outdir and name in write_variants:
            target = Path(outdir) / name / set_name
            target.mkdir(parents=True, exist_ok=True)
            net.write_bnet(str(target / os.path.basename(path)))
        row[f'time_{name}'] = f'{read_time + time.process_time() - start:.4f}'
        row[f'rm_{name}'] = n - len(net.f)
        row[f'src_{name}'] = sum(net.is_source(v) for v in net.f)
    return row


def save_rows(csv_path, rows):
    """Write rows to csv_path, replacing earlier rows of the same set and model.

    A file from an older version (without some columns, e.g. time_*) keeps its
    other rows, with those columns left empty."""
    old = []
    if os.path.exists(csv_path):
        with open(csv_path, newline='') as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames and not set(reader.fieldnames) <= set(FIELDS):
                sys.exit(f'{csv_path} has different columns; write to a new file')
            new_keys = {(r['set'], r['model']) for r in rows}
            old = [r for r in reader if (r['set'], r['model']) not in new_keys]
    tmp = csv_path + '.tmp'
    with open(tmp, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, restval='')
        w.writeheader()
        w.writerows(old + rows)
    os.replace(tmp, csv_path)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Fixed-point-preserving reductions of .bnet networks.')
    ap.add_argument('csv_out', help='statistics CSV (created or updated)')
    ap.add_argument('files', nargs='+', help='.bnet files')
    ap.add_argument('--set', default='',
                    help='benchmark set name, e.g. BBM (default: folder of each input file)')
    ap.add_argument('--write', default=str(DEFAULT_OUT),
                    help='root folder for reduced .bnet files (default: benchmarks/reduced)')
    ap.add_argument('--no-write', action='store_true', help='only write the statistics CSV')
    ap.add_argument('--variants', nargs='+', default=['B', 'D2'],
                    choices=[name for name, *_ in VARIANTS],
                    help='variants whose reduced networks are written (default: B D2)')
    a = ap.parse_args()
    import threading
    threading.stack_size(1 << 29)
    rows, failed = [], []

    def main():
        for p in a.files:
            set_name = a.set or os.path.basename(os.path.dirname(os.path.abspath(p)))
            try:
                r = run(p, None if a.no_write else a.write, set_name, a.variants)
            except Exception as e:  # keep going; report at the end
                failed.append(p)
                print(f'FAILED {p}: {type(e).__name__}: {e}', file=sys.stderr, flush=True)
                continue
            r = dict(set=set_name, model=os.path.basename(p)[:-5], **r)
            rows.append(r)
            print(r['model'], r['n'], r['sources'],
                  *(r[f'rm_{v[0]}'] for v in VARIANTS), '| src', r['src_D2'],
                  '| s', *(r[f'time_{v}'] for v in a.variants), flush=True)
    th = threading.Thread(target=main)
    th.start()
    th.join()
    if rows:
        save_rows(a.csv_out, rows)
    print(f'{len(rows)} of {len(a.files)} models reduced; statistics in {a.csv_out}'
          + ('' if a.no_write else f'; networks in {a.write}/<variant>/<set>/'), file=sys.stderr)
    if failed:
        print(f'{len(failed)} failed: ' + ', '.join(failed), file=sys.stderr)
        sys.exit(1)
