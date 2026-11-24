"""ECTD benchmark: workflow instance generation, scheduling policies, scoring.

The six policies are standard-library ports of the reference implementations on
the research branch ``research/ranking-revision-2026-11-23``. Instance
generation is new: the original 3,072-instance pool is not published, so this
package builds its own suite from a declared, seeded generator.
"""

from __future__ import annotations

__version__ = "0.1.0"

POLICIES = ("ECTD", "AEFT", "BPPTS", "HEFT", "LSTD", "IPEFT")


def policy_table():
    """Return the six named policies, each taking (problem, insertion=...)."""
    from .baselines import run_heft
    from .extended_baselines import run_aeft, run_bppts
    from .ipeft import run_ipeft
    from .proposed import run_ectd, run_lstd

    return {
        "ECTD": run_ectd,
        "AEFT": run_aeft,
        "BPPTS": run_bppts,
        "HEFT": run_heft,
        "LSTD": run_lstd,
        "IPEFT": run_ipeft,
    }
