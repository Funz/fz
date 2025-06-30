import sys
import types
import pytest

# create mock rpy2 with minimal API
module = types.ModuleType("rpy2")
class DummyR:
    def assign(self, name, val):
        pass
    def __call__(self, code):
        return [0]
robjects = types.SimpleNamespace(r=DummyR())
module.robjects = robjects
sys.modules['rpy2'] = module
sys.modules['rpy2.robjects'] = robjects

from fz import fz


def test_unknown_placeholder_in_filename_template(tmp_path):
    input_file = tmp_path / "in.txt"
    input_file.write_text("simple")
    f = fz()
    with pytest.raises(ValueError, match="Unknown variable in filename_template: unknown"):
        f.CompileInput(
            input_file=str(input_file),
            input_variables={"x": [1]},
            filename_template="{prefix}_{unknown}{ext}"
        )

