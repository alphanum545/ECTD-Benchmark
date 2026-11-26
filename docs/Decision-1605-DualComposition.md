## 8. Build order

1. Build **A (1,845, σ=0.18 only)** first — it establishes the pipeline and
   produces the waiver list, which is exactly the set of cells B must escalate.
2. Build **B (1,845, knob ladder)** second, reusing the same builder with the
   ladder enabled and the rung recorded per instance.
3. Compare per §6.
4. Record the outcome in this file under a new "Outcome" section.

Both outputs must be kept side by side and clearly labelled. Do not overwrite one
with the other.

### 8.1 Builder status (2026-11-26)

**The builder exists and is tested; neither variant has been built on the real
corpus yet.**

- `scripts/build_composition.py` — both variants, nine-rung ladder, per-instance
  rung recorded, waivers recorded rather than backfilled.
  `--self-check` verifies the lattice arithmetic, `-1` preservation and the D3
  round-trip.
- `scripts/verify_composition.py` — the gate. Re-parses every instance, checks
  the `-1` pattern against the exact source the manifest names, validates all
  six schedules, confirms each winner/added label, and checks the recorded rung
  against the knobs actually applied.
- `scripts/make_synth_sources.py` — synthetic D3 fixture at the real directory
  depth, so the pipeline runs without the 3.1 GB corpus.

**What has been verified, on the synthetic fixture only:** 90 cells, 1,248
instances across both variants, every instance re-parsed and validated under all
six policies. B filled 90/90 cells with zero waivers; A filled 65/90 and waived
102 instances. The A-vs-B behaviour is therefore confirmed qualitatively — A
waives, B fills — but **no figure in §3, §4 or §5 is a build result.** They
remain predictions from the measurement artifacts.

**What has not been done:** the real run. It needs the corpus and the 400-row
base set, neither of which is in this repo. Until it runs, `delivered`,
`waived`, `realised_ratio` and `cells_outside_source_regime` are unmeasured.

**One thing the real run will settle that the probes could not:** the rung
distribution. §4.2's per-rung table comes from the probes, which used their own
seed strings. The builder uses `build|<cell>|<variant>|<rung>|<cand>` and will
produce its own distribution. Neither is wrong; they are different draws. The
manifest's `rung_usage` is the number to quote for the built dataset, and the
probe table must not be presented as the build's rung distribution.
