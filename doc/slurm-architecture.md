# SLURM execution: architecture note



**Decision (P1-2)**: keep a native `sbatch`/`sacct` implementation for now; do not add PSI/J yet.

- `slurm://` (`fz/runners/slurm.py`) = blocking `srun` per case (unchanged).
- `slurm-array://` (`fz/runners/slurm_array.py`) = local job arrays: cases are batched
  (`fz.slurm_async.ArrayBatcher`) into one `sbatch --array`; each task `cd`s into its
  case directory listed in a manifest file; one shared monitor thread
  (`fz.slurm_async.SlurmJobMonitor`) polls `sacct` (fallback `squeue`) for all pending
  tasks. This protocol replaces the earlier `FZ_SLURM_MODE` env-var switch idea: the
  URI scheme now picks the execution strategy.
- Rationale: no new dependency, small surface, behaviour testable with mocked commands.
- PSI/J (ExaWorks) would cover PBS, LSF and Flux behind one API. Revisit when a second
  scheduler is requested: `slurm_async.submit_array/query_states/cancel` and the
  `Calculator` interface in `fz/runners/base.py` are the seams to replace.
- Open work: remote (SSH) job arrays; the manifest assumes a filesystem shared with the
  compute nodes.
