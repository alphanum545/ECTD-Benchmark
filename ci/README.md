# GitHub Actions reproduction

The workflow on `research/ranking-revision-2026-11-23` reconstructs the frozen study, then runs the six original scheduling implementations in both append and insertion modes. The three overlapping cohorts are outcome-selected exploratory subsets. Their aggregate ranking was an explicit selection constraint; the CI run does not change that interpretation.

## What a successful run verifies

1. Reassemble only files listed in `transport_manifest.json`, checking every transport chunk, wire payload, original SHA-256 and Git blob SHA-1. Initial import chunks carry original bytes losslessly. On later runs the restored files are read directly.
2. Run the unchanged `rankstudy.build` over all 3,072 source instances. It checks 36,864 retained makespans against the source CSV and the frozen selections. All 18 regenerated cohort files must match their original bytes exactly. All 83 original files, including the original documentation and receipts, must match the frozen inventory and original core Git tree.
3. Replay the union of 546 unique inputs in **20 matrix jobs**, with `max-parallel: 20` and **four process workers in each job**. Each input is assigned to exactly one shard. All six policies and both placement modes produce 6,552 unique schedules, covering 11,172 schedule memberships across the 497, 209 and 225 instance cohorts.
4. Compare makespan, execution horizon, duplicate count, duplicate work and schedule SHA-256 exactly. Revalidate schedule feasibility. Recompute the three profile summaries from the new schedules and require exact agreement with their frozen summaries.
5. If every check succeeds, commit the restored original files and fresh receipts under `validation/github-actions/<run-id>/attempt-<attempt>/` to this feature branch. Delete only the manifest-listed temporary chunks. Keep the small manifest and CI code. Verify that the branch still points at the triggering commit before publishing, and use an ordinary fast-forward push. The main branch is never a write target.

The original local validation files remain byte-for-byte unchanged. Actual GitHub metadata is recorded separately for the new CI execution. Each shard records observed CPU count and runtime details; 20 parallel jobs is the configured maximum, while actual concurrency depends on the account's available runners.

The workspace artifact contains an explicit file allowlist, never `.git` or authentication material. Read jobs have `contents: read`; only the finalization job has `contents: write`. Its ordinary repository `GITHUB_TOKEN` is used through the official checkout action. No additional credentials are required. A push performed with this token does not recursively launch another push workflow.

## Rerun

Use **Re-run all jobs** on the original Actions run, or push a reviewed change to this same branch. If a newer commit has already advanced the branch, rerunning an older run will deliberately refuse publication; start a run for the new branch head instead. The workflow can run from a branch push without adding a workflow file to main.

To inspect the same computation locally without any GitHub write:

```bash
python -m pip install -r requirements.txt
python ci/run_study.py prepare --output /tmp/ectd-prepared
python /tmp/ectd-prepared/ci/run_study.py shard --index 0 --output /tmp/ectd-shards/ectd-shard-0
# Repeat the shard command for indices 1 through 19, each with its own output path.
python ci/run_study.py finalize --prepared /tmp/ectd-prepared --shards /tmp/ectd-shards
```

Use Python 3.12. Local metadata is explicitly labeled `local`. Only `--publish` inside the authorized GitHub Actions repository/branch can create a remote commit.

## Official references for the pinned infrastructure

- [Checkout v6.0.2 commit](https://github.com/actions/checkout/commit/de0fac2e4500dabe0009e67214ff5f5447ce83dd)
- [Setup Python v6.0.0 commit](https://github.com/actions/setup-python/commit/e797f83bcb11b83ae66e0230d6156d7c80228e7c)
- [Upload Artifact v6.0.0 commit](https://github.com/actions/upload-artifact/commit/b7c566a772e6b6bfb58ed0dc250532a479d7789f)
- [Download Artifact v7.0.0 commit](https://github.com/actions/download-artifact/commit/37930b1c2abaa49bbe596cd826c3c89aef350131)
- [GitHub workflow syntax and public Ubuntu runner specifications](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
- [GitHub automatic token permissions and workflow triggering](https://docs.github.com/en/actions/concepts/security/github_token)
