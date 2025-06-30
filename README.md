Suite of Funz commands ``fz*`:

* `fzc`: compile input files (almost like `Funz CompileInput ...`). Output files
  keep the same extension as the source (e.g. `sample.pij` -> `sample_X=1.pij`).
  A file ``generated_files.csv`` lists the relative paths of all generated
  datasets along with their scenario variable values for easier inspection.
  File names can be customized with the ``filename_template`` option of
  ``CompileInput``.
  Example:
    CompileInput(..., filename_template="{prefix}_R{r0:.0f}{ext}")
* `fzp`: parse output files (almost like `Funz ParseResults ...`)
* `fzr`: run input files (almost like `Funz Run ...`)
* `fzd`: apply design/algorithm on command (almost like `Funz Design ...`)
* `fzrd`: apply algorithm and run (almost like `Funz RunDesign ...`)
