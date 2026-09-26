# SLURM execution: architecture note

**Decision (P1-2)**: keep a native `sbatch`/`sacct` implementation for now; do not add PSI/J yet.

- `slurm://` = blocking `srun` per case (unchanged). `slurm-array://` = local job arrays:
  cases are batched (`ArrayBatcher`) into one `sbatch --array`; each task `cd`s into its case
  directory listed in a manifest file; one shared monitor thread (`fz/slurm_async.py`) polls
  `sacct` (fallback `squeue`) for all pending tasks. The protocol replaces the former mode switch.
- Rationale: no new dependency, small surface, behaviour testable with mocked commands.
- PSI/J (ExaWorks) would cover PBS, LSF and Flux behind one API. Revisit when a second
  scheduler is requested: `slurm_async.submit_array/query_states/cancel` is the seam to replace.
- Open work: remote (SSH) job arrays; the manifest assumes a filesystem shared with the nodes.
