---
description: Wrap a simulation code with fz and verify it step by step
argument-hint: [path to the solver/script + input file, or a short description]
---
Wrap a simulation code with the **fz** package so it can be driven as a parametric
study, following the fz Agent Skill workflow. Do the steps in order and verify each
one before moving on — this isolates errors on one cheap case instead of a failed batch.

Target: $ARGUMENTS

0. **Check for an official wrapper**: `fz install model <code>` (browse
   <https://github.com/orgs/Funz/repositories?q=fz->). If one fits, install it,
   run `fz list --check --format json`, and skip to step 3.
1. **Parameterize the input file(s)**: replace the values to vary with `$var` markers;
   use `@{expr}` for compile-time formulas and `#@` lines for formula context.
2. **Define the model** (only if step 0 found nothing): a JSON file under `.fz/models/`
   with the variable syntax and one `output` parser per value of interest — prefer
   shell-free `python://` parsers.
3. `fzi` — confirm it reports **exactly** the variables you expect (stray names ⇒
   `varprefix` collides with the code's syntax; change it).
4. `fzc` with one set of values — inspect the compiled file.
5. Run the real simulation command once on the compiled input.
6. `fzo` on the result directory — confirm every output parses.

Stop and report once steps 3–6 pass. Do not launch a full study unless asked. If the
wrapper should be reusable or published as `fz-<code>`, follow the skill's
code-wrapper guide.
