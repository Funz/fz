# SLURM execution: architecture note

**Decision (P1-2)**: keep a native `sbatch`/`sacct` implementation for now; do not add PSI/J yet.

- Local `slurm://` submits with `sbatch --parsable` and a single shared monitor thread
  (`fz/slurm_async.py`) polls `sacct` (fallback `squeue`) for all pending jobs.
- Rationale: no new dependency, small surface, behaviour testable with mocked commands.
- PSI/J (ExaWorks) would cover PBS, LSF and Flux behind one API. Revisit when a second
  scheduler is requested: `slurm_async.submit/query_states/cancel` is the seam to replace.
- Open work: job arrays for N-case plans (needs case-directory mapping to
  `SLURM_ARRAY_TASK_ID`), remote sbatch over SSH.
