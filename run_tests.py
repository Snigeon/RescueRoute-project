import inspect
import itertools
import shutil
import sys
import traceback
import types
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / 'tests'))
counter = itertools.count()

def install_pytest_stub():
    if 'pytest' in sys.modules:
        return
    fake = types.ModuleType('pytest')

    def fixture(*args, **kwargs):
        if args and callable(args[0]):
            return args[0]

        def decorate(func):
            return func
        return decorate

    class _Approx:

        def __init__(self, value, rel=1e-06, abs=1e-12):
            self.value = value
            self.rel = rel
            self.abs = abs

        def __eq__(self, other):
            return abs(other - self.value) <= max(self.abs, self.rel * abs(self.value))

        def __repr__(self):
            return f'approx({self.value})'

    class _Raises:

        def __init__(self, expected, match=None):
            self.expected = expected
            self.match = match
            self.value = None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            if exc_type is None:
                raise AssertionError(f'DID NOT RAISE {self.expected}')
            if not issubclass(exc_type, self.expected):
                return False
            self.value = exc
            if self.match is not None:
                import re
                if not re.search(self.match, str(exc)):
                    raise AssertionError(f'{exc!r} does not match {self.match!r}')
            return True
    fake.fixture = fixture
    fake.approx = lambda value, rel=1e-06, abs=1e-12: _Approx(value, rel, abs)
    fake.raises = lambda expected, match=None: _Raises(expected, match)

    class _Mark:

        @staticmethod
        def parametrize(names, values):
            keys = [name.strip() for name in names.split(',')]

            def decorate(func):
                cases = getattr(func, '_dsh_cases', [])
                for value in values:
                    row = value if isinstance(value, (tuple, list)) else (value,)
                    cases.append(dict(zip(keys, row)))
                func._dsh_cases = cases
                return func
            return decorate
    fake.mark = _Mark
    sys.modules['pytest'] = fake
install_pytest_stub()
import conftest

def call(func):
    kwargs = dict(getattr(func, '_dsh_kwargs', {}))
    parameters = inspect.signature(func).parameters
    if 'now' in parameters:
        kwargs['now'] = conftest.NOW
    if 'tmp_path' in parameters:
        base = HERE / '.tmp-test'
        tmp_path = base / f'case-{next(counter)}'
        shutil.rmtree(tmp_path, ignore_errors=True)
        tmp_path.mkdir(parents=True, exist_ok=True)
        try:
            return func(tmp_path=tmp_path, **kwargs)
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)
    return func(**kwargs)

def load_module(path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    return module

def expand(func, label):
    cases = getattr(func, '_dsh_cases', None)
    if not cases:
        yield (label, func)
        return
    for index, case in enumerate(cases, start=1):
        func._dsh_kwargs = case
        yield (f'{label}[{index}]', func)

def collect():
    for path in sorted((HERE / 'tests').glob('test_*.py')):
        module = load_module(path)
        for name, obj in sorted(vars(module).items()):
            if name.startswith('Test') and inspect.isclass(obj):
                instance = obj()
                for method_name in sorted(dir(instance)):
                    if method_name.startswith('test_'):
                        func = getattr(instance, method_name)
                        yield from expand(func, f'{path.stem}::{name}::{method_name}')
            elif name.startswith('test_') and inspect.isfunction(obj):
                yield from expand(obj, f'{path.stem}::{name}')

def run_suite():
    passed = failed = 0
    failures = []
    for label, func in collect():
        try:
            call(func)
            passed += 1
        except Exception:
            failed += 1
            failures.append((label, traceback.format_exc()))
    for label, tb in failures:
        print('=' * 78)
        print('FAILED:', label)
        print(tb)
    print(f'{passed} passed, {failed} failed')
    return 1 if failed else 0
if __name__ == '__main__':
    raise SystemExit(run_suite())
