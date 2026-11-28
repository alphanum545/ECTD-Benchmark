# Computational complexity

Derived from the code in `ectdbench/`, not from timings. Every claim below names
the function and line range it comes from, so it can be checked by reading rather
than by trusting a benchmark.

Notation: `n` tasks, `p` processors, `e` edges, `w` the big-integer digit width
(30 in CPython, not 64). `d_in(i)` and `d_out(i)` are the in- and out-degree of
task `i`, so `sum d_in = sum d_out = e`.

**Complexity here is worst case in `n` alone.** A bound is a property of the
algorithm, not of the graph it happens to be run on, so every total below is
stated at the worst case over DAGs on `n` nodes, where `e = Theta(n^2)`. A
sparser graph makes any of these algorithms faster; that is a fact about the
input, not a weaker bound, and it is not used anywhere in this document to argue
that a bound is met. See the note at the end on why that distinction matters.

## Summary

The paper's requirement is `O(n^2 p)`. Totals are worst case in `n`, at
`e = Theta(n^2)`.

| Algorithm | Entry point | Rank stage | Total (worst case) | Meets `O(n^2 p)` |
|---|---|---|---|---|
| HEFT | `baselines.py:53-55` | `O(n + e)` | `O(n^2 p)` | yes |
| LSTD | `proposed.py:216-226` | `O(n + e)` | `O(n^2 p)` | yes |
| AEFT | `extended_baselines.py:105-109` | `O(n + e)` | `O(n^2 p)` | yes |
| BPPTS | `extended_baselines.py:112-116` | `O(n + e)` | `O(n^2 p)` | yes |
| IPEFT | `ipeft.py:85-103` | `O(n + e)` | `O(n^2 p)` | yes |
| **ECTD** | `proposed.py:141-158` | `O(n + e n/w + n^2)` | **`O(n^3/w + n^2 p)`** | **no** |

Five of the six sit exactly at the requirement. ECTD exceeds it by one term,
`e n/w`, which at `e = Theta(n^2)` is `n^3/w`. That term is the whole of the
problem: nothing else in any of the six algorithms goes above `O(n^2 p)`.

For reference, the untightened totals before collapsing `e` to its worst case
are `O(e p + n^2 + n p)` for HEFT, LSTD, AEFT and BPPTS, `O(e p + n p)` for
IPEFT, and `O(e n/w + n^2 + e p + n p)` for ECTD. The collapse is only a
substitution of `e = Theta(n^2)`; it hides no assumption.

## Where the `p` comes from

The placement phase is shared by all six, so it is derived once.

**`Schedule._ready_vector`** (`engine.py:99-115`): loops over `pred(i)` and, for
each parent, builds an `arrival` list of length `p` and loops `for q in range(p)`.
Cost `O(d_in(i) p)` per task, `O(e p)` over all tasks.

**`Schedule.earliest_slots`** (`engine.py:117-147`): the outer `for processor in
range(p)` is `O(p)`. The gap search is bounded by the number of events on that
processor, and the events across all processors number at most `n`, so the search
is `O(n)` in total. Cost `O(n + p)` per task.

**`Schedule.place`** (`engine.py:153-192`): validation is `O(1)`; the calendar
update is `O(log n)` after the bisect change described below.

Per task: `O(d_in(i) p + n + p)`. Summed over all tasks:

```
placement = O(e p + n^2 + n p)
```

That is the `O(n^2 p)` term. It is inherent to insertion scheduling, not to any
one policy: a task may be placed into a gap before existing events, so the
calendar has to be searched.

IPEFT is the exception. It defaults to `insertion=False` (`ipeft.py:85`), so
`earliest_slots` takes the `max(starts[q], available[q])` branch and never
searches a calendar. Its placement is `O(e p + n p)`.

## Rank stage, per algorithm

**HEFT** `upward_ranks` (`baselines.py:20-29`): one reverse-topological pass with
a `max` over `succ(i)`. `O(n + e)`.

**LSTD** `lstd_ranks` (`proposed.py:194-214`): same shape, `max` over `succ(i)`.
`O(n + e)`.

**AEFT** `aeft_ioct` (`extended_baselines.py:15-31`): `for task in reversed(topo)`
x `for child in succ[task]` x `for q in range(p)`. `O(e p)`.

**BPPTS** `bppts_bpcm` (`extended_baselines.py:33-53`): the same triple loop.
`bppts_ranks` (`:55-64`) adds `O(n p + e)`. `O(e p)`.

**IPEFT** `tables` (`ipeft.py:35-83`): PCT and CNCT are `O(e p)` each, with
`_other_max` costing `O(p)` per child. AEST/ALST are `O(n + e)`.
`O(e p + n p)`.

**ECTD** `descendant_ranks` (`proposed.py:15-56`): the outlier, and the reason
ECTD does not meet the bound.

```python
for task in reversed(problem.topo):
    bits = 0
    for child in problem.succ[task]:
        bits |= (1 << child) | descendants[child]     # (A)
    descendants[task] = bits
    total = float(dct[task])
    if bits:
        for byte_index, byte in enumerate(bits.to_bytes(nbytes, "little")):  # (B)
            ...
```

- **(A)** is one `n`-bit big-integer OR per edge. `O(e n/w)`.
- **(B)** scans `n/8` bytes per task. `O(n^2/8)`.

Total rank: `O(n + e n/w + n^2)`.

Before the byte-scan change, (B) peeled one set bit at a time with
`bits & -bits` and `bits ^= low`. Each of those touches the whole `n`-bit value,
so one iteration cost `O(n/w)` words, and the loop ran once per distinct
descendant, which is `Theta(n^2)` over all tasks. That made (B) `O(n^3/w)`.

## Does ECTD meet `O(n^2 p)`?

No. The rank is `O(e n/w + n^2)` and the total is

```
O(e n/w + n^2 + e p + n p)
```

At the worst case `e = Theta(n^2)` this is `O(n^3/w + n^2 p)`. The `e n/w` term
is `n^3/w`, which exceeds `O(n^2 p)` whenever `p < n/w`.

The honest statement for the paper: **five algorithms provably meet
`O(n^2 p)`; ECTD does not.** The gap is term (A), the per-edge big-integer
union, and no amount of scanning cleverness removes it.

### Why the corpus does not settle this

On the benchmark corpus `e/n` is about 1.41, so `e = O(n)` and ECTD's total
collapses to `O(n^2 p)` there. It is tempting to conclude that the bound is met
in practice and move on. That conclusion is not available, for two reasons.

First, a bound is a claim about the algorithm over all inputs of size `n`. If it
holds only when the graph is sparse, then what has been proved is a bound on a
restricted input class, and it has to be stated that way. Saying "`O(n^2 p)`"
and meaning "`O(n^2 p)` for `e = O(n p w)`" is a different and weaker claim.

Second, the sparsity is a property of this corpus, not of the problem. A
different workload, a denser dependency graph, or a synthetic stress case would
move `e/n` and the bound would move with it. An algorithm whose complexity
depends on the input's density is not `O(n^2 p)`; it is `O(n^2 p)` on the inputs
where that happens to be true.

So the corpus measurement is evidence about performance on this benchmark. It is
not evidence about the bound.

## Space

| Algorithm | Space |
|---|---|
| HEFT, LSTD | `Theta(n + p)` |
| AEFT, BPPTS, IPEFT | `Theta(n p)` |
| **ECTD** | **`Theta(n^2/w + n p)`** |

ECTD stores `n` bitmasks of `n` bits each:

```
bits stored  = n * n = n^2
packed bytes = n^2 / 8
CPython      = (n/30 digits * 4 bytes) per mask = 0.133 n^2
             + 28-byte object header per mask
total        = 0.133 n^2 + 28 n  bytes
```

Measured against that formula:

| n | measured | `n^2/8` packed | ratio |
|---:|---:|---:|---:|
| 500 | 0.049 MB | 0.031 MB | 1.57x |
| 1,000 | 0.164 MB | 0.125 MB | 1.32x |
| 2,000 | 0.582 MB | 0.500 MB | 1.16x |
| 4,000 | 2.199 MB | 2.000 MB | 1.10x |

The ratio tends to about 1.1x; the excess at small `n` is the `28n` header term.

This is the difference that matters in practice. HEFT and LSTD store `Theta(n)`
floats; ECTD stores `Theta(n^2)` bits, so the gap widens linearly with `n`. At
`n = 100,000` the bitmask alone is 1.25 GB.

## Refactors landed, and what they do and do not buy

Both are behaviour preserving and both are verified by the equivalence workflow
against a committed baseline: 282 instances x 14 policies, exact makespan
equality, 482 rank cases. Neither changes any schedule.

**Byte-scan the descendant mask** (`proposed.py`). Removes the per-set-bit walk:
`O(n^3/w)` becomes `O(n^2/8)`. Does not touch term (A). The rank goes from
`O(n^3/w + e n/w)` to `O(n^2 + e n/w)`.

This is a constant-factor win, not a bound fix. It removes one of the two
`n^3/w` terms, and on a dense DAG the remaining one, `e n/w`, still dominates.
ECTD is `O(n^3/w + n^2 p)` before the change and `O(n^3/w + n^2 p)` after it.
The measured speedup is 2.4x to 3.9x on the rank phase; that is the whole of
what it buys, and it is worth having, but it does not move the exponent.

**Bisect the calendar** (`engine.py`). The gap search walked every event from
index 0 and `place` located its insertion point with a linear `next(...)`. Events
on a processor never overlap, so their starts and finishes are both ascending:
`bisect_right` over the finishes finds the first event that can still affect a
candidate, and `bisect_right` over the starts gives the insertion index. Removes
the `O(n^2)` placement term's linear scan. It is a low-order win inside an
already-`O(n^2 p)` phase, not a bound fix.

## What would actually close the gap

Term (A) is the obstacle: one `n`-bit OR per edge. Options, none of which is a
pure refactor:

- **Append-only placement.** Drops the `n^2` placement term but changes the
  policy and regresses schedule quality. It also does not touch (A), so it does
  not close this gap at all.
- **A cheaper rank functional.** Already tried: `v:own_cost_aeft_ranks` replaces
  `descendant_ranks` with a mean own-cost-plus-tail order and measured 0.74%
  worse. See `docs/optimizations/OPTIMIZATIONS.md`. This is the only route that
  removes (A), because it removes the need for descendant sets entirely.
- **Approximate descendant weights.** A sketch with error `Omega(1/sqrt(p))` is
  12.5% at `p=64` and 71% at `p=2`, against a registry resolution of 0.12%. Not
  viable at this precision.

The exact distinct-descendant weighted sum is transitive-closure shaped, and
bitset closure at `O(n^3/w)` is the standard exact method for it. Every rank in
the other five algorithms is `O(n + e)` or `O(e p)`, which is why they clear the
bound without effort: none of them needs a descendant set.

Meeting `O(n^2 p)` therefore requires changing the functional, not computing it
faster. That makes the rank replacement the main line of work, and it makes the
per-family quality question (GE and LA) part of the same decision rather than a
side quest: whichever `O(n^2 p)` rank is adopted has to be chosen on what it
costs per family.
