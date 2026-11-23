"""The six unchanged scheduling policies used in the mixed cohort."""
from ectdbench.baselines import run_heft
from ectdbench.extended_baselines import run_aeft, run_bppts
from ectdbench.proposed import run_ectd, run_lstd
from ectdbench.ipeft import run_ipeft

ALGORITHMS = {
    "ECTD": run_ectd,
    "AEFT": run_aeft,
    "LSTD": run_lstd,
    "BPPTS": run_bppts,
    "HEFT": run_heft,
    "IPEFT": run_ipeft,
}
