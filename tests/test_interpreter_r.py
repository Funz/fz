"""
Test R interpreter functionality using rpy2
"""
import pytest
from fz.interpreter import evaluate_formulas


def _check_rpy2_available():
    """Helper function to check if rpy2 is installed"""
    try:
        import rpy2
        return True
    except ImportError:
        return False


def test_r_interpreter_not_installed():
    """Test that R interpreter handles missing rpy2 gracefully"""
    # Create sample content with R formula
    content = "Result: @{2 * $x + 1}"
    model = {
        "formulaprefix": "@",
        "delim": "{}",
        "commentline": "#"
    }
    input_variables = {"x": 5}

    # Try to use R interpreter
    result = evaluate_formulas(content, model, input_variables, interpreter="R")

    # If rpy2 is not installed, it should return original content with warning
    # If rpy2 is installed, it should evaluate to "Result: 11"
    assert result in ["Result: @{2 * $x + 1}", "Result: 11.0", "Result: 11"]


@pytest.mark.skipif(
    not _check_rpy2_available(),
    reason="rpy2 not installed"
)
def test_r_interpreter_basic_formula():
    """Test basic R formula evaluation"""
    content = "Result: @{2 * $x + 1}"
    model = {
        "formulaprefix": "@",
        "delim": "{}",
        "commentline": "#"
    }
    input_variables = {"x": 5}

    result = evaluate_formulas(content, model, input_variables, interpreter="R")

    # R should evaluate 2 * 5 + 1 = 11
    assert "11" in result
    assert "Result:" in result


@pytest.mark.skipif(
    not _check_rpy2_available(),
    reason="rpy2 not installed"
)
def test_r_interpreter_with_context():
    """Test R interpreter with context lines (function definitions)"""
    content = """#@area_circle <- function(r) { pi * r^2 }
Circle area: @{area_circle($radius)}
"""
    model = {
        "formulaprefix": "@",
        "delim": "{}",
        "commentline": "#"
    }
    input_variables = {"radius": 2}

    result = evaluate_formulas(content, model, input_variables, interpreter="R")

    # R should evaluate pi * 2^2 ≈ 12.566
    assert "Circle area:" in result
    assert "12.56" in result or "12.57" in result


@pytest.mark.skipif(
    not _check_rpy2_available(),
    reason="rpy2 not installed"
)
def test_r_interpreter_multiple_formulas():
    """Test R interpreter with multiple formulas"""
    from fz.interpreter import replace_variables_in_content

    content = """x = $x
y = $y
sum = @{$x + $y}
product = @{$x * $y}
"""
    model = {
        "formulaprefix": "@",
        "delim": "{}",
        "commentline": "#"
    }
    input_variables = {"x": 3, "y": 7}

    # First replace variables, then evaluate formulas (as done in helpers.py)
    content = replace_variables_in_content(content, input_variables, varprefix="$", delim="{}")
    result = evaluate_formulas(content, model, input_variables, interpreter="R")

    # Should have x=3, y=7, sum=10, product=21
    assert "x = 3" in result
    assert "y = 7" in result
    assert "sum = 10" in result
    assert "product = 21" in result


@pytest.mark.skipif(
    not _check_rpy2_available(),
    reason="rpy2 not installed"
)
def test_r_interpreter_statistical_functions():
    """Test R interpreter with R-specific statistical functions"""
    content = """#@x <- c(1, 2, 3, 4, 5)
Mean: @{mean(x)}
SD: @{sd(x)}
"""
    model = {
        "formulaprefix": "@",
        "delim": "{}",
        "commentline": "#"
    }
    input_variables = {}

    result = evaluate_formulas(content, model, input_variables, interpreter="R")

    # Mean of 1:5 is 3, SD is ~1.58
    assert "Mean: 3" in result
    assert "SD:" in result


if __name__ == "__main__":
    # Run basic test
    print("Testing R interpreter...")
    test_r_interpreter_not_installed()
    print("✓ Graceful handling test passed")

    if _check_rpy2_available():
        print("\nrpy2 is installed, running full tests...")
        test_r_interpreter_basic_formula()
        print("✓ Basic formula test passed")

        test_r_interpreter_with_context()
        print("✓ Context test passed")

        test_r_interpreter_multiple_formulas()
        print("✓ Multiple formulas test passed")

        test_r_interpreter_statistical_functions()
        print("✓ Statistical functions test passed")

        print("\nAll tests passed!")
    else:
        print("\nrpy2 not installed. Install with: pip install rpy2")
        print("To run full tests after installation: pytest tests/test_interpreter_r.py")
