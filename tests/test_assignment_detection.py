#!/usr/bin/env python3
"""
Test that assignment detection correctly distinguishes between
assignments and comparison operators.
"""
import pytest
from fz.interpreter import parse_static_objects_with_expressions


def test_comparison_operators_not_detected_as_assignments():
    """Test that comparison operators (==, !=, <=, >=) are not detected as assignments"""
    code = """#@:
#@: if x == 5:
#@:     pass
#@: if y <= 10:
#@:     pass
#@: if z >= 0:
#@:     pass
#@: if a != b:
#@:     pass
"""
    expressions = parse_static_objects_with_expressions(code)

    # Should not detect any assignments
    assert len(expressions) == 0, f"Comparison operators incorrectly detected as assignments: {expressions}"


def test_actual_assignments_detected():
    """Test that actual assignments are correctly detected"""
    code = """#@:
#@: x = 5
#@: y = 10
#@: z = x + y
"""
    expressions = parse_static_objects_with_expressions(code)

    # Should detect all three assignments
    assert len(expressions) == 3
    assert 'x' in expressions
    assert 'y' in expressions
    assert 'z' in expressions
    assert expressions['x'] == '5'
    assert expressions['y'] == '10'
    assert expressions['z'] == 'x + y'


def test_mixed_assignments_and_comparisons():
    """Test mixed code with both assignments and comparisons"""
    code = """#@:
#@: value = 42
#@: if value == 42:
#@:     result = "correct"
#@: elif value != 42:
#@:     result = "incorrect"
"""
    expressions = parse_static_objects_with_expressions(code)

    # Should only detect 'value' and 'result', not the comparisons
    assert len(expressions) == 2
    assert 'value' in expressions
    assert 'result' in expressions
    assert expressions['value'] == '42'
    # Result gets the last assignment
    assert expressions['result'] == '"incorrect"'

    # Should NOT detect comparison operators as assignments
    assert 'if value' not in expressions
    assert 'elif value' not in expressions


def test_type_hints_in_assignments():
    """Test that assignments with type hints are correctly detected"""
    code = """#@:
#@: x: int = 5
#@: name: str = "test"
"""
    expressions = parse_static_objects_with_expressions(code)

    # Should detect assignments with type hints
    assert len(expressions) == 2
    assert 'x' in expressions
    assert 'name' in expressions
    assert expressions['x'] == '5'
    assert expressions['name'] == '"test"'


def test_compound_comparison_operators():
    """Test that compound comparison operators are not detected as assignments"""
    code = """#@:
#@: while x <= 100:
#@:     x = x * 2
#@: if result >= threshold:
#@:     status = "high"
"""
    expressions = parse_static_objects_with_expressions(code)

    # Should only detect actual assignments (x and status), not comparisons
    assert 'x' in expressions
    assert 'status' in expressions
    # Should NOT detect comparison operators
    assert 'while x <' not in expressions
    assert 'if result >' not in expressions


def test_equality_in_assert_statements():
    """Test that == in assert statements is not detected as assignment"""
    code = """#@:
#@: assert x == expected
#@: assert result != None
"""
    expressions = parse_static_objects_with_expressions(code)

    # Should not detect any assignments
    assert len(expressions) == 0, f"Assert comparisons incorrectly detected as assignments: {expressions}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
