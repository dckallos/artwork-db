"""
Offline pytest-stub harness for tools/github/tests (pytest is absent in the sandbox).

Injects a minimal ``pytest`` module into sys.modules, loads conftest + every test
module under tests/{unit,integration}, resolves fixtures (incl. tmp_path, monkeypatch),
expands parametrize, and runs every ``test_*`` function. Prints a pass/fail summary.

Usage:  PYTHONDONTWRITEBYTECODE=1 python3 .ghharness_tmp.py [tools/github/tests/...]
This is a LOCAL, NON-COMMITTED validation aid (CI runs real pytest with PYTHONPATH cleared).
"""
from __future__ import annotations

import contextlib
import importlib
import importlib.util
import inspect
import os
import sys
import tempfile
import traceback
import types
from pathlib import Path


class _Skipped(Exception):
    pass


class _Failed(Exception):
    pass


class _RaisesCtx:
    def __init__(self, expected):
        self.expected = expected
        self.value = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            raise _Failed(f"DID NOT RAISE {self.expected!r}")
        if not issubclass(exc_type, self.expected):
            return False
        self.value = exc
        return True


class _Mark:
    def __getattr__(self, name):
        if name == "parametrize":
            return self._parametrize
        def deco(*a, **k):
            if len(a) == 1 and callable(a[0]) and not k:
                return a[0]
            def wrap(fn):
                return fn
            return wrap
        return deco

    @staticmethod
    def _parametrize(argnames, argvalues, *_, **__):
        names = [s.strip() for s in argnames.split(",")] if isinstance(argnames, str) else list(argnames)

        def wrap(fn):
            cases = getattr(fn, "_params", [])
            for row in argvalues:
                if len(names) == 1:
                    cases.append({names[0]: row})
                else:
                    cases.append(dict(zip(names, row)))
            fn._params = cases
            return fn
        return wrap


def _fixture(*fargs, **fkwargs):
    def mark(fn):
        fn._is_fixture = True
        return fn
    if len(fargs) == 1 and callable(fargs[0]) and not fkwargs:
        return mark(fargs[0])
    return mark


def _make_pytest():
    m = types.ModuleType("pytest")
    m.mark = _Mark()
    m.fixture = _fixture
    m.raises = lambda exc, *a, **k: _RaisesCtx(exc)
    def skip(reason=""):
        raise _Skipped(reason)
    def fail(reason=""):
        raise _Failed(reason)
    def skipif(cond, reason=""):
        def wrap(fn):
            if cond:
                fn._skip = reason or "skipif"
            return fn
        return wrap
    def importorskip(name, *a, **k):
        try:
            return importlib.import_module(name)
        except Exception:
            raise _Skipped(f"missing {name}")
    m.skip = skip
    m.fail = fail
    m.skipif = skipif
    m.importorskip = importorskip
    m.Skipped = _Skipped
    return m


class _MonkeyPatch:
    def __init__(self):
        self._undo = []

    def setattr(self, target, name, value=None, raising=True):
        if isinstance(target, str):
            mod, _, attr = target.rpartition(".")
            obj = importlib.import_module(mod)
            name, value = attr, name
        else:
            obj = target
        old = getattr(obj, name, None)
        had = hasattr(obj, name)
        self._undo.append((obj, name, old, had))
        setattr(obj, name, value)

    def setenv(self, k, v):
        old = os.environ.get(k)
        self._undo.append(("env", k, old, k in os.environ))
        os.environ[k] = v

    def delenv(self, k, raising=False):
        old = os.environ.get(k)
        self._undo.append(("env", k, old, k in os.environ))
        os.environ.pop(k, None)

    def undo(self):
        for obj, name, old, had in reversed(self._undo):
            if obj == "env":
                if had:
                    os.environ[name] = old
                else:
                    os.environ.pop(name, None)
            elif had:
                setattr(obj, name, old)
            else:
                with contextlib.suppress(Exception):
                    delattr(obj, name)
        self._undo.clear()


def _load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _collect_fixtures(*modules):
    reg = {}
    for mod in modules:
        for nm, obj in vars(mod).items():
            if callable(obj) and getattr(obj, "_is_fixture", False):
                reg[nm] = obj
    return reg


def _resolve(name, reg, cache, teardowns, tmp_root):
    if name in cache:
        return cache[name]
    if name == "tmp_path":
        d = Path(tempfile.mkdtemp(dir=tmp_root))
        cache[name] = d
        return d
    if name == "monkeypatch":
        mp = _MonkeyPatch()
        teardowns.append(mp.undo)
        cache[name] = mp
        return mp
    if name not in reg:
        raise KeyError(f"no fixture {name!r}")
    fn = reg[name]
    kwargs = {p: _resolve(p, reg, cache, teardowns, tmp_root)
              for p in inspect.signature(fn).parameters}
    val = fn(**kwargs)
    if inspect.isgenerator(val):
        gen = val
        val = next(gen)
        teardowns.append(lambda g=gen: next(g, None))
    cache[name] = val
    return val


def main(argv):
    sys.modules["pytest"] = _make_pytest()
    root = Path("/workspace").resolve()
    tests_root = root / "tools/github/tests"
    targets = [Path(a) for a in argv[1:]] or [tests_root / "unit", tests_root / "integration"]

    files = []
    for t in targets:
        t = t if t.is_absolute() else root / t
        if t.is_dir():
            files += sorted(t.glob("test_*.py"))
        elif t.name.startswith("test_"):
            files.append(t)

    conftest = _load_module(tests_root / "conftest.py", "conftest")
    tmp_root = tempfile.mkdtemp(prefix="ghharness_")

    passed = failed = skipped = 0
    failures = []
    for f in files:
        mod = _load_module(f, f"th_{f.stem}")
        base_reg = _collect_fixtures(conftest, mod)
        for nm, obj in sorted(vars(mod).items()):
            if not (nm.startswith("test_") and callable(obj) and inspect.isfunction(obj)):
                continue
            if getattr(obj, "_skip", None):
                skipped += 1
                continue
            param_sets = getattr(obj, "_params", [{}])
            for i, params in enumerate(param_sets):
                label = f"{f.stem}::{nm}" + (f"[{i}]" if len(param_sets) > 1 else "")
                cache = dict(params)
                teardowns = []
                try:
                    kwargs = {p: _resolve(p, base_reg, cache, teardowns, tmp_root)
                              for p in inspect.signature(obj).parameters}
                    obj(**kwargs)
                    passed += 1
                except _Skipped:
                    skipped += 1
                except Exception:
                    failed += 1
                    failures.append((label, traceback.format_exc()))
                finally:
                    for td in reversed(teardowns):
                        with contextlib.suppress(Exception):
                            td()

    print("=" * 70)
    for label, tb in failures:
        print(f"FAIL {label}\n{tb}")
    print("=" * 70)
    print(f"passed={passed} failed={failed} skipped={skipped}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
