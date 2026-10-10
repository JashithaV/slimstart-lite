"""SlimStart-Lite: profile-guided lazy-import optimizer (mini implementation of the paper's idea)."""
import argparse, ast, builtins, collections, importlib, json, os, random, signal, sys, time

# ---------------------------------------------------------------- profiling
class ImportTimer:
    """Records inclusive import time of each top-level package (paper Sec IV-A1)."""
    def __init__(self):
        self.times = collections.defaultdict(float)
        self.depth = 0
        self._orig = builtins.__import__

    def __enter__(self):
        def hook(name, globals=None, locals=None, fromlist=(), level=0):
            if level:  # relative import, ignore
                return self._orig(name, globals, locals, fromlist, level)
            root = name.split(".")[0]
            first = self.depth == 0 and root not in sys.modules
            self.depth += 1
            t = time.perf_counter()
            try:
                return self._orig(name, globals, locals, fromlist, level)
            finally:
                self.depth -= 1
                if first:
                    self.times[root] += (time.perf_counter() - t) * 1000
        builtins.__import__ = hook
        return self

    def __exit__(self, *a):
        builtins.__import__ = self._orig


class Sampler:
    """Timer-signal sampling of the Python stack (paper Sec IV-A2).
    A sample counts toward every library on the stack (== propagating counts up the CCT)."""
    def __init__(self, interval=0.001):
        self.interval, self.total = interval, 0
        self.lib_samples = collections.Counter()

    def _on_signal(self, signum, frame):
            libs, f, importing = set(), frame, False
            while f:
                fn = f.f_code.co_filename
                if "importlib" in fn and "_bootstrap" in fn:
                    importing = True          # sample is import/init work, not runtime usage
                for marker in ("site-packages/", "dist-packages/"):
                    if marker in fn:
                        libs.add(fn.split(marker, 1)[1].split("/")[0].split(".")[0])
                        break
                f = f.f_back
            if importing:
                return
            self.total += 1
            self.lib_samples.update(libs)

    def start(self):
        signal.signal(signal.SIGPROF, self._on_signal)
        signal.setitimer(signal.ITIMER_PROF, self.interval, self.interval)

    def stop(self):
        signal.setitimer(signal.ITIMER_PROF, 0, 0)


def cmd_profile(a):
    sys.path.insert(0, a.app_dir)
    mix = json.loads(a.mix)  # e.g. {"hash":0.9,"stats":0.08,"report":0.02}
    with ImportTimer() as it:
        mod = importlib.import_module(a.module)
    fn = getattr(mod, a.func)
    actions = random.choices(list(mix), weights=list(mix.values()), k=a.n)
    for act in mix:
        fn({"action": act})
    s = Sampler(); s.start()
    for act in actions:
        fn({"action": act})
    s.stop()
    out = {"import_ms": it.times, "total_samples": s.total,
           "lib_samples": s.lib_samples, "n_invocations": a.n, "mix": mix}
    json.dump(out, open(a.out, "w"), indent=2)
    print(f"profiled {a.n} invocations, {s.total} samples -> {a.out}")


# ---------------------------------------------------------------- analysis
def analyze(profile, util_thr, init_thr_ms):
    tot = max(profile["total_samples"], 1)
    rows = []
    for lib, ms in profile["import_ms"].items():
        if lib in sys.stdlib_module_names:
            continue
        util = profile["lib_samples"].get(lib, 0) / tot * 100
        rows.append((lib, ms, util, ms >= init_thr_ms and util < util_thr))
    return sorted(rows, key=lambda r: -r[1])


def cmd_report(a):
    p = json.load(open(a.profile))
    rows = analyze(p, a.util_threshold, a.init_threshold_ms)
    print(f"{'library':<14}{'init(ms)':>10}{'util(%)':>10}  action")
    for lib, ms, u, flag in rows:
        print(f"{lib:<14}{ms:>10.1f}{u:>10.2f}  {'LAZY-LOAD' if flag else 'keep'}")
    return [r[0] for r in rows if r[3]]


# ---------------------------------------------------------------- optimizer
class Deferrer(ast.NodeTransformer):
    """Moves top-level imports of flagged libs into the functions that use them (paper Sec IV-B)."""
    def __init__(self, libs):
        self.libs, self.removed, self.warnings = set(libs), [], []

    def visit_Module(self, node):
        keep = []
        for st in node.body:
            if isinstance(st, ast.Import) and all(n.name.split(".")[0] in self.libs for n in st.names):
                self.removed.append(st)
            elif isinstance(st, ast.ImportFrom) and st.level == 0 and st.module.split(".")[0] in self.libs:
                self.removed.append(st)
            else:
                keep.append(st)
        node.body = keep
        self.generic_visit(node)  # rewrite functions
        # warn about module-level use of removed names
        flat = set().union(*[self._bound(st) for st in self.removed]) if self.removed else set()
        for st in node.body:
            if not isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                used = {n.id for n in ast.walk(st) if isinstance(n, ast.Name)}
                if used & flat:
                    self.warnings.append(f"line {st.lineno}: module-level use of {sorted(used & flat)}")
        return node

    @staticmethod
    def _bound(st):
        return {(n.asname or n.name.split(".")[0]) for n in st.names}

    @staticmethod
    def _names(nodes):
        return {n.id for x in nodes for n in ast.walk(x) if isinstance(n, ast.Name)}

    def _place(self, stmts, pending):
        """Insert each import right before the first statement that needs it (descending into
        branches whose header doesn't use it), so cold-start paths that never reach it skip it."""
        out, done = [], set()
        for st in stmts:
            need = [i for i in pending if i not in done and self._bound(self.removed[i]) & self._names([st])]
            if need and isinstance(st, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                if isinstance(st, (ast.If, ast.While)):
                    head = [st.test]
                elif isinstance(st, ast.For):
                    head = [st.iter]
                elif isinstance(st, ast.With):
                    head = [i.context_expr for i in st.items]
                else:
                    head = []
                hused = self._names(head)
                direct = [i for i in need if self._bound(self.removed[i]) & hused]
                for i in direct:
                    out.append(self.removed[i]); done.add(i)
                rest = [i for i in need if i not in direct]
                for field in ("body", "orelse", "finalbody"):
                    if hasattr(st, field):
                        setattr(st, field, self._place(getattr(st, field), rest))
                if hasattr(st, "handlers"):
                    for h in st.handlers: h.body = self._place(h.body, rest)
            elif need:
                for i in need:
                    out.append(self.removed[i]); done.add(i)
            out.append(st)
        return out

    def visit_FunctionDef(self, node):
        used = self._names([node])
        pending = [i for i, st in enumerate(self.removed) if self._bound(st) & used]
        if pending:
            node.body = self._place(node.body, pending)
        return node  # nested defs see imports via closure

    visit_AsyncFunctionDef = visit_FunctionDef


def cmd_optimize(a):
    libs = a.libs or cmd_report(a)
    src = open(a.src).read()
    d = Deferrer(libs)
    tree = d.visit(ast.parse(src))
    ast.fix_missing_locations(tree)
    open(a.dst, "w").write(ast.unparse(tree) + "\n")
    print(f"\nlazy-loaded: {libs} -> {a.dst}")
    for w in d.warnings:
        print("WARNING:", w)


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(required=True)
    p = sp.add_parser("profile"); p.set_defaults(f=cmd_profile)
    p.add_argument("--app-dir", default="app"); p.add_argument("--module", default="handler")
    p.add_argument("--func", default="handler"); p.add_argument("--n", type=int, default=500)
    p.add_argument("--mix", default='{"hash":0.90,"stats":0.08,"report":0.02}')
    p.add_argument("--out", default="profile.json")
    r = sp.add_parser("report"); r.set_defaults(f=cmd_report)
    for q in (r,):
        q.add_argument("--profile", default="profile.json")
        q.add_argument("--util-threshold", type=float, default=5.0)
        q.add_argument("--init-threshold-ms", type=float, default=20.0)
    o = sp.add_parser("optimize"); o.set_defaults(f=cmd_optimize)
    o.add_argument("--src", default="app/handler.py"); o.add_argument("--dst", default="app_opt/handler.py")
    o.add_argument("--profile", default="profile.json"); o.add_argument("--libs", nargs="*")
    o.add_argument("--util-threshold", type=float, default=5.0)
    o.add_argument("--init-threshold-ms", type=float, default=20.0)
    a = ap.parse_args(); a.f(a)

if __name__ == "__main__":
    main()
