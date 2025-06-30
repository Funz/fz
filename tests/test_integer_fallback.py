import sys
import types

# create mock rpy2 with minimal API
module = types.ModuleType("rpy2")
class DummyR:
    def assign(self, name, val):
        pass
    def __call__(self, code):
        return [42.3]
robjects = types.SimpleNamespace(r=DummyR())
module.robjects = robjects
sys.modules['rpy2'] = module
sys.modules['rpy2.robjects'] = robjects


def test_integer_format_with_zero_fallback():
    import importlib
    import fz as fz_module
    importlib.reload(fz_module)
    f = fz_module.fz()
    output = f._parse_and_replace_at_braces_format("value @{expr|0}")
    assert output == "value 42"

