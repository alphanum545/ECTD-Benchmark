"""Locate the package and the corpus, wherever this checkout happens to sit.

Every script in this directory needs the same two things: the directory that
holds the ``ectdbench`` package, and the directory that holds
``scheduling-benchmark/data``. Neither is fixed by the repo layout.

The old assumption was::

    HERE = os.path.dirname(os.path.abspath(__file__))
    ROOT = os.path.dirname(HERE)          # "the parent workspace"

That is only true when the script sits at the repo root. These scripts sit in
``scripts/``, so ``dirname(HERE)`` is the *repo* root, and the package path
built from it became ``<repo>/ECTD-Benchmark/ECTD-Benchmark``, which does not
exist. The scripts only appeared to work when run from the repo root, because
the current directory happened to be on ``sys.path``.

So: search the plausible locations instead of assuming one, and honour
``ECTD_DATA_ROOT`` for a machine that keeps the corpus somewhere else.

Corpus precedence matters. ``make_synth_sources.py`` writes a 90-file synthetic
fixture to ``<repo>/scheduling-benchmark/data`` for smoke tests. If the real
corpus is also present at ``<workspace>/scheduling-benchmark/data``, the real
one must win: silently building from the fixture would produce a 1,845-instance
composition that means nothing. Parent workspace first, local fixture second,
and ``ECTD_DATA_ROOT`` overrides both.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)

# Committed measurement artifacts live here, and the scripts write here so that
# re-running reproduces the committed JSON in place rather than in a side dir.
OUT_DIR = os.path.join(REPO_ROOT, "docs", "measurements")


def find_package_root():
    """Return the directory that contains the ``ectdbench`` package."""
    candidates = (
        REPO_ROOT,                                            # plain clone
        os.path.join(os.path.dirname(REPO_ROOT), "ECTD-Benchmark"),  # canonical workspace
        HERE,
    )
    for candidate in candidates:
        if os.path.isfile(os.path.join(candidate, "ectdbench", "__init__.py")):
            return candidate
    raise SystemExit(
        "cannot find the ectdbench package. Looked in:\n  %s"
        % "\n  ".join(candidates))


def find_data_root():
    """Return the directory that contains ``<Family>/<N>Nodes/<P>PROCESSORS``."""
    override = os.environ.get("ECTD_DATA_ROOT")
    if override:
        if not os.path.isdir(override):
            raise SystemExit("ECTD_DATA_ROOT is set but is not a directory: %s" % override)
        return override

    parent = os.path.join(os.path.dirname(REPO_ROOT), "scheduling-benchmark", "data")
    local = os.path.join(REPO_ROOT, "scheduling-benchmark", "data")
    for candidate in (parent, local):
        if os.path.isdir(candidate):
            return candidate
    raise SystemExit(
        "cannot find scheduling-benchmark/data. Set ECTD_DATA_ROOT to the "
        "directory that holds the <Family>/<N>Nodes/<P>PROCESSORS/*.txt corpus.\n"
        "Looked in:\n  %s\n  %s" % (parent, local))


def describe():
    """One-line provenance for a run header, so a build cannot be ambiguous."""
    try:
        data = find_data_root()
        n = sum(len(files) for _, _, files in os.walk(data) if files)
        return "package=%s data=%s (%d files)" % (find_package_root(), data, n)
    except SystemExit as exc:
        return str(exc)
