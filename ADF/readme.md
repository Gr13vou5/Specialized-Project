# ADF benchmark: ICCMA 2019 instances as Boolean networks

Phase 2 extends the benchmark with abstract dialectical frameworks (ADFs).
Following BAss (Pastva & Trinh, arXiv:2604.27576), we use the **276 ICCMA 2019
ADF instances** distributed with k++ADF and translate each one into a `.bnet`
Boolean network, so that the fixed-point solvers of this repository (fASP-c,
fASP-s, H.E., PFVS) can compute its **2-valued models**.

## Quick start

Put the 276 ICCMA 2019 instances (`*.adf`) in `benchmarks/ADF/ICCMA2019/adf/`
and run

```sh
python3 ADF/adf_to_bnet.py
```

The networks are written to `benchmarks/ADF/ICCMA2019/bnet/` (one
`<instance>.bnet` per `<instance>.adf`). The script needs only Python 3 (no
packages), runs on Linux, macOS and Windows, and takes about 1.5 minutes with
4 parallel jobs (`-j` to change). The translation is deterministic, so
`benchmarks/ADF/ICCMA2019/SHA256SUMS` lets you check that you obtained exactly
the files used in the experiments:

```sh
(cd benchmarks/ADF/ICCMA2019/bnet && sha256sum -c ../SHA256SUMS)
```

Other ADF files or folders can be translated too:

```sh
python3 ADF/adf_to_bnet.py path/to/instances -o out_dir
```

The instances come from the k++ADF repository
(`instances/iccma19/adf-instances-iccma19.zip`, commit `637c31f`), the source
BAss cites for this benchmark.

## Translation

An ADF `D = (S, C)` is written in the k++ADF format

```text
s(a).          % a is an argument
ac(a, f).      % f is the acceptance condition of a
```

with formulas built from arguments, `c(v)`, `c(f)`, `neg`, `and`, `or`,
`xor`, `imp` and `iff`. Every argument `a` becomes the Boolean variable `v_a`
with update function `f_{v_a} = phi_a`. A 2-valued interpretation is a model of
the ADF iff `I(a) = phi_a(I)` for every argument, which is exactly the
fixed-point condition of the network (Heyninck et al. 2024; Azpeitia et al.
2024), so **2-valued models and fixed points coincide**.

The `.bnet` syntax is restricted to what every solver here accepts:

| ADF | `.bnet` |
| --- | --- |
| `and(p,q)`, `or(p,q)`, `neg(p)` | `(p & q)`, `(p \| q)`, `!p` |
| `imp(p,q)` | `(!p \| q)` |
| `xor(p,q)` | `((p & !q) \| (!p & q))` |
| `iff(p,q)` | `((p & q) \| (!p & !q))` |
| `c(v)`, `c(f)` | folded away; a constant acceptance condition becomes `v_a \| !v_a` or `v_a & !v_a` |

Constants are removed because H.E.'s parser rejects `0`/`1`
(`build/proposed_src/.../BooleanNetworkParser.scala`), and `.bnet` has no XOR
operator. Argument names are prefixed with `v_` because many ICCMA names are
bare numbers, which are not valid identifiers; the prefix also keeps names
clear of the `x<N>` renaming done by `PFVS/converter_pfvs.py`.

### XOR blow-up and auxiliary variables

Rewriting `xor` duplicates both operands, so nested XOR grows exponentially.
The ICCMA 2019 instances split cleanly: 204 expand to at most 1.23·10^7
formula nodes (at most 50 MB of `.bnet`), while the other 72 need at least
1.95·10^7 and up to about 10^71. BAss excluded 72 instances for this reason;
we could not obtain their list, so we only know the counts agree. We keep the
72 by naming every non-literal operand of an `xor`/`iff` with an auxiliary
variable `aux_k` whose update function is that operand:

```text
v_20, ((aux_2 & !aux_3) | (!aux_2 & aux_3))
aux_2, ((v_a & !v_b) | (!v_a & v_b))
aux_3, ((v_c & !v_d) | (!v_c & v_d))
```

Auxiliary definitions are acyclic and only refer to arguments and earlier
auxiliary variables, so at a fixed point every `aux_k` is determined by the
`v_*` values. Hence the fixed points of these networks are in one-to-one
correspondence with the 2-valued models of the ADF, and their number is the
same. This holds for fixed points only: trap spaces (complete/preferred
interpretations) are not preserved by the auxiliary variables.

`--mode auto` (default) expands an instance directly when its expanded size is
at most `--max-expanded-nodes` (default 1.5·10^7, inside the gap above) and
uses auxiliary variables otherwise; `--mode expand` and `--mode aux` force one
of the two.
The progress output names the mode of each instance. The 72 networks with
auxiliary variables are the files containing `aux_` lines
(`grep -l '^aux_' benchmarks/ADF/ICCMA2019/bnet/*.bnet`); to reproduce BAss's
setting, leave them out.
