# Upload status: incomplete pending public-data approval

The research branch exists and the transfer is partially committed. The branch
cannot yet reproduce the study because 94 of the original transport
files remain to be uploaded. No GitHub Actions run has been started.

The automatic approval review stopped a later public-data upload batch and
requires explicit user confirmation of public disclosure for the eight exact
files below. An exhaustive decoded-content audit is recorded in
[`ci/data_publication_audit.json`](ci/data_publication_audit.json). It found no
unexplained free-text values or credential-pattern matches in 431,763 inspected
strings. All files contain synthetic numerical benchmark data, scheduling
results, technical identifiers, or the documented Git ignore patterns.
The audit is content evidence; it does not override approval review.

## Exact files awaiting confirmation

| Original destination | Bytes | SHA-256 |
| --- | ---: | --- |
| `source_evidence/candidates.jsonl.gz` | 15,512,167 | `1ce1e373de8d9b52574c45abee872c25424870c1df0b55c417858b1729addd77` |
| `source_evidence/full_pool_all_3072_results.csv` | 3,167,196 | `3b8142578095b99ebadc0fe247e699aaf22b0f25512b6c9637192a5b41a0110e` |
| `source_evidence/ipeft_pool_results.jsonl.gz` | 487,773 | `2e6e5896ea61af7c45577b2b9c0219c4162ddea523d4a42af3b327c813131567` |
| `source_evidence/original_results.jsonl.gz` | 3,153,207 | `a724e8c93e3b160105db2aa7b23fa6ab9d7f1f3371cf3041f71793042fbfdcd7` |
| `validation/replay-full_order_209/replayed_results.jsonl.gz` | 128,864 | `352a949f8260d00747eace34c9ab1dd81ea5d0ba287ecf2fa9be3c339eebbf6a` |
| `validation/replay-full_order_225/replayed_results.jsonl.gz` | 139,127 | `71c33a1e49e718f1dc07485f96db12e8d325c5a9cdac3ea94d578c0cfab2c482` |
| `validation/replay-latest_497/replayed_results.jsonl.gz` | 300,274 | `fee936b2c052234c7cc3d3302764307de2fe2f00ce1c99c0850952c313d0c33f` |
| `.gitignore` | 111 | `827cf57848c528e07eca7a61f436ac0b0c4d9da4cc28cf919c30bdc9e53b2764` |

The selected cohorts are deterministic derivatives of these source files.
The proposed publication includes those generated cohorts and the fresh CI
replay receipts on this same public research branch.

## Work already complete

- The algorithms, research reports, selection records, source inventory, and
  existing local validation receipts are committed.
- Every successful transfer is recorded locally for resumable continuation.
- The original 83-file study is frozen by file size, SHA-256, and Git blob SHA-1.
- Local reconstruction regenerated 18 cohort files byte for byte.
- A complete local dry run of 20 four-worker shards replayed 546 unique inputs
  and 6,552 schedules, covering 11,172 profile memberships, with zero invalid
  schedules or mismatches. This is local evidence, not a GitHub CI result.

## Prepared GitHub workflow

The tested YAML is saved for review as the **inactive text template**
[`ci/reproduce-ranking-revision.workflow-template.txt`](ci/reproduce-ranking-revision.workflow-template.txt).
This file is outside `.github/workflows/`, has a `.txt` extension, and does not
register or run a GitHub workflow.

After explicit public-data approval, the remaining verified parts can be
uploaded, their remote Git hashes checked, and this workflow installed using
the workflow-specific connector operation. It requests 20 parallel replay jobs
and four worker processes per job. Only after all checks pass does its final job
restore the complete original files and save actual CI results to this feature
branch. The main branch is not a write target.
