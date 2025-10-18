"""
Test Python interpreter functionality
Tests equivalent to test_interpreter_r.py but for Python interpreter
"""
import pytest
from fz.interpreter import evaluate_formulas, replace_variables_in_content


def test_python_interpreter_basic_formula():
    """Test basic Python formula evaluation"""
    content = "Result: @{2 * $x + 1}"
    model = {
        "formulaprefix": "@",
        "delim": "{}",
        "commentline": "#"
    }
    input_variables = {"x": 5}

    result = evaluate_formulas(content, model, input_variables, interpreter="python")

    # Python should evaluate 2 * 5 + 1 = 11
    assert "11" in result
    assert "Result:" in result


def test_python_interpreter_with_context():
    """Test Python interpreter with context lines (function definitions)"""
    content = """#@import math
#@def area_circle(r):
#@    return math.pi * r ** 2
Circle area: @{area_circle($radius)}
"""
    model = {
        "formulaprefix": "@",
        "delim": "{}",
        "commentline": "#"
    }
    input_variables = {"radius": 2}

    result = evaluate_formulas(content, model, input_variables, interpreter="python")

    # Python should evaluate math.pi * 2^2 ≈ 12.566
    assert "Circle area:" in result
    assert "12.56" in result or "12.57" in result


def test_python_interpreter_multiple_formulas():
    """Test Python interpreter with multiple formulas"""
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
    result = evaluate_formulas(content, model, input_variables, interpreter="python")

    # Should have x=3, y=7, sum=10, product=21
    assert "x = 3" in result
    assert "y = 7" in result
    assert "sum = 10" in result
    assert "product = 21" in result


def test_python_interpreter_mathematical_functions():
    """Test Python interpreter with Python math module functions"""
    content = """#@import math
#@x = [1, 2, 3, 4, 5]
Mean: @{sum(x) / len(x)}
Sqrt of sum: @{math.sqrt(sum(x))}
Max: @{max(x)}
"""
    model = {
        "formulaprefix": "@",
        "delim": "{}",
        "commentline": "#"
    }
    input_variables = {}

    result = evaluate_formulas(content, model, input_variables, interpreter="python")

    # Mean of 1:5 is 3.0
    assert "Mean: 3" in result
    # Sqrt of 15 is ~3.872
    assert "3.87" in result or "3.88" in result
    # Max is 5
    assert "Max: 5" in result


def test_python_interpreter_with_imports():
    """Test Python interpreter with various imports"""
    content = """#@import math
#@import random
#@random.seed(42)
Pi: @{math.pi}
E: @{math.e}
Random: @{random.randint(1, 100)}
"""
    model = {
        "formulaprefix": "@",
        "delim": "{}",
        "commentline": "#"
    }
    input_variables = {}

    result = evaluate_formulas(content, model, input_variables, interpreter="python")

    # Should have mathematical constants
    assert "Pi: 3.14159" in result
    assert "E: 2.71828" in result
    # Random with seed 42 should be deterministic
    assert "Random:" in result


def test_python_interpreter_list_operations():
    """Test Python interpreter with list operations"""
    content = """#@data = [$x, $y, $z]
Sum: @{sum(data)}
Length: @{len(data)}
Average: @{sum(data) / len(data)}
Min: @{min(data)}
Max: @{max(data)}
Sorted: @{sorted(data)}
"""
    model = {
        "formulaprefix": "@",
        "delim": "{}",
        "commentline": "#"
    }
    input_variables = {"x": 10, "y": 5, "z": 15}

    # Replace variables first (needed for context lines with variables)
    content = replace_variables_in_content(content, input_variables, varprefix="$", delim="{}")
    result = evaluate_formulas(content, model, input_variables, interpreter="python")

    assert "Sum: 30" in result
    assert "Length: 3" in result
    assert "Average: 10" in result
    assert "Min: 5" in result
    assert "Max: 15" in result
    assert "Sorted: [5, 10, 15]" in result


def test_python_interpreter_string_operations():
    """Test Python interpreter with string operations"""
    content = """#@name = "$name"
#@surname = "$surname"
Full name: @{name + " " + surname}
Uppercase: @{name.upper()}
Length: @{len(name)}
Initials: @{name[0] + surname[0]}
"""
    model = {
        "formulaprefix": "@",
        "delim": "{}",
        "commentline": "#"
    }
    input_variables = {"name": "John", "surname": "Doe"}

    # Replace variables first
    content = replace_variables_in_content(content, input_variables, varprefix="$", delim="{}")
    result = evaluate_formulas(content, model, input_variables, interpreter="python")

    assert "Full name: John Doe" in result
    assert "Uppercase: JOHN" in result
    assert "Length: 4" in result
    assert "Initials: JD" in result


def test_python_interpreter_power_operations():
    """Test Python interpreter with power and exponentiation"""
    content = """Base: $base
Exponent: $exp
Power (**): @{$base ** $exp}
Pow function: @{pow($base, $exp)}
Square: @{$base ** 2}
Cube: @{$base ** 3}
"""
    model = {
        "formulaprefix": "@",
        "delim": "{}",
        "commentline": "#"
    }
    input_variables = {"base": 2, "exp": 5}

    # Replace variables first
    content = replace_variables_in_content(content, input_variables, varprefix="$", delim="{}")
    result = evaluate_formulas(content, model, input_variables, interpreter="python")

    assert "Base: 2" in result
    assert "Exponent: 5" in result
    assert "Power (**): 32" in result
    assert "Pow function: 32" in result
    assert "Square: 4" in result
    assert "Cube: 8" in result


def test_python_interpreter_conditional_expressions():
    """Test Python interpreter with conditional expressions"""
    content = """#@x = $value
Result: @{"positive" if x > 0 else ("negative" if x < 0 else "zero")}
Absolute: @{abs(x)}
Sign: @{1 if x > 0 else (-1 if x < 0 else 0)}
"""
    model = {
        "formulaprefix": "@",
        "delim": "{}",
        "commentline": "#"
    }

    # Test with positive value
    input_variables = {"value": 5}
    content_processed = replace_variables_in_content(content, input_variables, varprefix="$", delim="{}")
    result = evaluate_formulas(content_processed, model, input_variables, interpreter="python")
    assert "Result: positive" in result
    assert "Absolute: 5" in result
    assert "Sign: 1" in result

    # Test with negative value
    input_variables = {"value": -3}
    content_processed = replace_variables_in_content(content, input_variables, varprefix="$", delim="{}")
    result = evaluate_formulas(content_processed, model, input_variables, interpreter="python")
    assert "Result: negative" in result
    assert "Absolute: 3" in result
    assert "Sign: -1" in result


def test_python_interpreter_comprehensions():
    """Test Python interpreter with list comprehensions"""
    content = """#@n = $n
Squares: @{[i**2 for i in range(1, n+1)]}
Evens: @{[i for i in range(1, n+1) if i % 2 == 0]}
Sum of squares: @{sum([i**2 for i in range(1, n+1)])}
"""
    model = {
        "formulaprefix": "@",
        "delim": "{}",
        "commentline": "#"
    }
    input_variables = {"n": 5}

    # Replace variables first
    content = replace_variables_in_content(content, input_variables, varprefix="$", delim="{}")
    result = evaluate_formulas(content, model, input_variables, interpreter="python")

    assert "Squares: [1, 4, 9, 16, 25]" in result
    assert "Evens: [2, 4]" in result
    assert "Sum of squares: 55" in result  # 1+4+9+16+25


def test_python_interpreter_complex_functions():
    """Test Python interpreter with complex multi-line functions"""
    content = """#@import math
#@def stats(values):
#@    n = len(values)
#@    mean = sum(values) / n
#@    variance = sum((x - mean) ** 2 for x in values) / n
#@    std = math.sqrt(variance)
#@    return {"mean": mean, "std": std, "n": n}
#@
#@data = [$a, $b, $c, $d]
#@result = stats(data)
Mean: @{result["mean"]}
Std: @{result["std"]}
Count: @{result["n"]}
"""
    model = {
        "formulaprefix": "@",
        "delim": "{}",
        "commentline": "#"
    }
    input_variables = {"a": 10, "b": 20, "c": 30, "d": 40}

    # Replace variables first
    content = replace_variables_in_content(content, input_variables, varprefix="$", delim="{}")
    result = evaluate_formulas(content, model, input_variables, interpreter="python")

    assert "Mean: 25" in result
    assert "Std:" in result
    assert "Count: 4" in result


def test_python_interpreter_dictionary_operations():
    """Test Python interpreter with dictionary operations"""
    content = """#@config = {"width": $width, "height": $height}
Width: @{config["width"]}
Height: @{config["height"]}
Area: @{config["width"] * config["height"]}
Keys: @{list(config.keys())}
"""
    model = {
        "formulaprefix": "@",
        "delim": "{}",
        "commentline": "#"
    }
    input_variables = {"width": 10, "height": 20}

    # Replace variables first
    content = replace_variables_in_content(content, input_variables, varprefix="$", delim="{}")
    result = evaluate_formulas(content, model, input_variables, interpreter="python")

    assert "Width: 10" in result
    assert "Height: 20" in result
    assert "Area: 200" in result
    assert "['width', 'height']" in result or "['height', 'width']" in result


def test_python_interpreter_format_strings():
    """Test Python interpreter with formatted strings and rounding"""
    content = """#@value = $value
#@precision = $precision
Rounded: @{round(value, precision)}
As string: @{str(value)[:6]}
Type: @{type(value).__name__}
Length: @{len(str(value))}
"""
    model = {
        "formulaprefix": "@",
        "delim": "{}",
        "commentline": "#"
    }
    input_variables = {"value": 3.14159, "precision": 2}

    # Replace variables first
    content = replace_variables_in_content(content, input_variables, varprefix="$", delim="{}")
    result = evaluate_formulas(content, model, input_variables, interpreter="python")

    assert "Rounded: 3.14" in result
    assert "As string: 3.1415" in result
    assert "Type: float" in result
    assert "Length:" in result


if __name__ == "__main__":
    # Run all tests
    print("=" * 70)
    print("Testing Python Interpreter")
    print("=" * 70)

    print("\n1. Testing basic formula...")
    test_python_interpreter_basic_formula()
    print("✓ Passed")

    print("\n2. Testing with context...")
    test_python_interpreter_with_context()
    print("✓ Passed")

    print("\n3. Testing multiple formulas...")
    test_python_interpreter_multiple_formulas()
    print("✓ Passed")

    print("\n4. Testing mathematical functions...")
    test_python_interpreter_mathematical_functions()
    print("✓ Passed")

    print("\n5. Testing with imports...")
    test_python_interpreter_with_imports()
    print("✓ Passed")

    print("\n6. Testing list operations...")
    test_python_interpreter_list_operations()
    print("✓ Passed")

    print("\n7. Testing string operations...")
    test_python_interpreter_string_operations()
    print("✓ Passed")

    print("\n8. Testing power operations...")
    test_python_interpreter_power_operations()
    print("✓ Passed")

    print("\n9. Testing conditional expressions...")
    test_python_interpreter_conditional_expressions()
    print("✓ Passed")

    print("\n10. Testing comprehensions...")
    test_python_interpreter_comprehensions()
    print("✓ Passed")

    print("\n11. Testing complex functions...")
    test_python_interpreter_complex_functions()
    print("✓ Passed")

    print("\n12. Testing dictionary operations...")
    test_python_interpreter_dictionary_operations()
    print("✓ Passed")

    print("\n13. Testing format strings...")
    test_python_interpreter_format_strings()
    print("✓ Passed")

    print("\n" + "=" * 70)
    print("ALL TESTS PASSED!")
    print("=" * 70)
