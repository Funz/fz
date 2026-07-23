#title: NSGA-II Multi-Objective Optimization (Deb 2002)
#author: fz contributors
#type: optimization
#options: pop_size=24;generations=15;seed=42;eta_cx=15;eta_mut=20;p_cx=0.9

"""
NSGA-II as a native fzd algorithm.

Requires fzd's vector-objective support: pass output_expression as a LIST of
expressions, e.g.::

    fzd("input.txt", {"x": "[0;1]", "y": "[0;1]"}, model,
        ["19 - min(Tser)", "max(Tser) - 26"],       # objectives, all MINIMIZED
        "examples/algorithms/nsga2.py",
        algorithm_options={"pop_size": 24, "generations": 15})

Each case's output value is then a list of floats (one per expression); this
algorithm receives those lists and performs standard NSGA-II (fast
non-dominated sorting, crowding distance, binary tournament, SBX crossover,
polynomial mutation). To MAXIMIZE an objective, negate its expression.

Populations are returned as batches, so fzd evaluates each generation in
parallel across the available calculators. Failed cases (None) are treated
as dominated by everything. get_analysis() reports the final Pareto front
and writes it to nsga2_pareto.csv in the working directory.

Pure stdlib + random module: no numpy dependency, consistent with the other
example algorithms.
"""

import random


class Nsga2:
    """NSGA-II for fzd: multi-objective, generational, batch-parallel."""

    def __init__(self, **options):
        self.N = int(float(options.get('pop_size', 24)))
        self.G = int(float(options.get('generations', 15)))
        self.seed = int(float(options.get('seed', 42)))
        self.eta_cx = float(options.get('eta_cx', 15))
        self.eta_mut = float(options.get('eta_mut', 20))
        self.p_cx = float(options.get('p_cx', 0.9))
        self.rng = random.Random(self.seed)
        self.names, self.lo, self.hi = [], [], []
        self.X, self.F = [], []        # current population (lists)
        self.gen = 0
        self.consumed = 0
        self._pending = []

    # ------------------------------------------------------------------ utils
    def _clip(self, x):
        return [min(self.hi[i], max(self.lo[i], v)) for i, v in enumerate(x)]

    def _todict(self, x):
        return {n: float(v) for n, v in zip(self.names, x)}

    @staticmethod
    def _as_vector(out):
        """Normalize one case output to a list of floats, or None if invalid."""
        if out is None:
            return None
        if isinstance(out, (list, tuple)):
            if any(v is None for v in out):
                return None
            return [float(v) for v in out]
        return [float(out)]           # degenerate mono-objective use

    @staticmethod
    def _dominates(a, b):
        return all(x <= y for x, y in zip(a, b)) and any(x < y for x, y in zip(a, b))

    def _fronts(self, F):
        n = len(F)
        S = [[] for _ in range(n)]
        nd = [0]*n
        fronts = [[]]
        for p in range(n):
            for q in range(n):
                if self._dominates(F[p], F[q]):
                    S[p].append(q)
                elif self._dominates(F[q], F[p]):
                    nd[p] += 1
            if nd[p] == 0:
                fronts[0].append(p)
        i = 0
        while fronts[i]:
            nxt = []
            for p in fronts[i]:
                for q in S[p]:
                    nd[q] -= 1
                    if nd[q] == 0:
                        nxt.append(q)
            i += 1
            fronts.append(nxt)
        return fronts[:-1]

    @staticmethod
    def _crowding(F):
        n = len(F)
        if n == 0:
            return []
        m = len(F[0])
        d = [0.0]*n
        for k in range(m):
            order = sorted(range(n), key=lambda i: F[i][k])
            d[order[0]] = d[order[-1]] = float('inf')
            span = F[order[-1]][k] - F[order[0]][k]
            if span > 0:
                for j in range(1, n - 1):
                    d[order[j]] += (F[order[j+1]][k] - F[order[j-1]][k]) / span
        return d

    # ------------------------------------------------------- genetic operators
    def _sbx(self, p1, p2):
        c1, c2 = list(p1), list(p2)
        if self.rng.random() > self.p_cx:
            return c1, c2
        for i in range(len(self.names)):
            if self.rng.random() > 0.5 or abs(p1[i] - p2[i]) < 1e-12:
                continue
            u = self.rng.random()
            if u <= 0.5:
                beta = (2*u)**(1/(self.eta_cx + 1))
            else:
                beta = (1/(2*(1 - u)))**(1/(self.eta_cx + 1))
            c1[i] = 0.5*((1 + beta)*p1[i] + (1 - beta)*p2[i])
            c2[i] = 0.5*((1 - beta)*p1[i] + (1 + beta)*p2[i])
        return c1, c2

    def _mutate(self, x):
        p_mut = 1.0/len(self.names)
        for i in range(len(self.names)):
            if self.rng.random() < p_mut:
                u = self.rng.random()
                if u < 0.5:
                    delta = (2*u)**(1/(self.eta_mut + 1)) - 1
                else:
                    delta = 1 - (2*(1 - u))**(1/(self.eta_mut + 1))
                x[i] += delta*(self.hi[i] - self.lo[i])
        return x

    def _tournament(self, ranks, crowd):
        i = self.rng.randrange(self.N)
        j = self.rng.randrange(self.N)
        if ranks[i] != ranks[j]:
            return i if ranks[i] < ranks[j] else j
        return i if crowd[i] >= crowd[j] else j

    def _reproduce(self):
        fronts = self._fronts(self.F)
        ranks = [0]*self.N
        crowd = [0.0]*self.N
        for r, fr in enumerate(fronts):
            cd = self._crowding([self.F[i] for i in fr])
            for i, c in zip(fr, cd):
                ranks[i] = r
                crowd[i] = c
        children = []
        while len(children) < self.N:
            a = self.X[self._tournament(ranks, crowd)]
            b = self.X[self._tournament(ranks, crowd)]
            c1, c2 = self._sbx(a, b)
            children.append(self._clip(self._mutate(c1)))
            if len(children) < self.N:
                children.append(self._clip(self._mutate(c2)))
        return children

    # ------------------------------------------------------------ fzd interface
    def get_initial_design(self, input_vars, output_vars):
        self.names = list(input_vars.keys())
        for n in self.names:
            lo, hi = input_vars[n]
            self.lo.append(float(lo))
            self.hi.append(float(hi))
        self._pending = [[self.lo[i] + self.rng.random()*(self.hi[i] - self.lo[i])
                          for i in range(len(self.names))]
                         for _ in range(self.N)]
        return [self._todict(x) for x in self._pending]

    def get_next_design(self, all_inputs, all_outputs):
        # collect this generation's evaluations
        new_X, new_F = [], []
        worst = None
        for inp, out in zip(all_inputs[self.consumed:], all_outputs[self.consumed:]):
            new_X.append([float(inp[n]) for n in self.names])
            new_F.append(self._as_vector(out))
        self.consumed = len(all_outputs)
        n_obj = next((len(f) for f in new_F + self.F if f is not None), 1)
        big = [float('inf')]*n_obj
        new_F = [f if f is not None else big for f in new_F]

        if not self.F:                      # generation 0
            self.X, self.F = new_X, new_F
        else:                               # (mu + lambda) environmental selection
            X_all = self.X + new_X
            F_all = self.F + new_F
            keep = []
            for fr in self._fronts(F_all):
                if len(keep) + len(fr) <= self.N:
                    keep += fr
                else:
                    cd = self._crowding([F_all[i] for i in fr])
                    ranked = sorted(zip(fr, cd), key=lambda t: -t[1])
                    keep += [i for i, _ in ranked[: self.N - len(keep)]]
                    break
            self.X = [X_all[i] for i in keep]
            self.F = [F_all[i] for i in keep]

        self.gen += 1
        if self.gen >= self.G:
            return []
        self._pending = self._reproduce()
        return [self._todict(x) for x in self._pending]

    def get_analysis(self, all_inputs, all_outputs):
        import csv
        import os
        front_idx = self._fronts(self.F)[0] if self.F else []
        finite = [i for i in front_idx if all(v != float('inf') for v in self.F[i])]
        n_obj = len(self.F[0]) if self.F else 0
        path = os.path.abspath("nsga2_pareto.csv")
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(self.names + [f"objective_{k+1}" for k in range(n_obj)])
            for i in finite:
                w.writerow(self.X[i] + self.F[i])
        lines = [f"NSGA-II: {self.gen} generations, {self.consumed} evaluations, "
                 f"Pareto front: {len(finite)} points -> {path}"]
        for i in finite[:10]:
            objs = ", ".join(f"{v:.4g}" for v in self.F[i])
            lines.append("  " + self._todict(self.X[i]).__repr__() + f" -> [{objs}]")
        return {"text": "\n".join(lines),
                "data": {"pareto_X": [self.X[i] for i in finite],
                         "pareto_F": [self.F[i] for i in finite]}}
