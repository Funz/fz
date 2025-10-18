"""
Test default value syntax in variable replacement: ${var~default}
"""
import pytest
from io import StringIO
import sys
from fz.interpreter import (
    replace_variables_in_content,
    parse_variables_from_content,
    evaluate_formulas
)


def capture_output(func, *args, **kwargs):
    """Capture stdout to check for warnings"""
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        result = func(*args, **kwargs)
        output = sys.stdout.getvalue()
        return result, output
    finally:
        sys.stdout = old_stdout


class TestDefaultValueSyntax:
    """Test ${var~default} syntax for variable replacement"""

    def test_variable_with_default_not_provided(self):
        """Test that default value is used when variable not in input_variables"""
        content = "Port: ${port~8080}"
        input_variables = {}

        result, output = capture_output(
            replace_variables_in_content,
            content, input_variables, varprefix="$", delim="{}"
        )

        assert result == "Port: 8080"
        assert "Warning" in output
        assert "port" in output
        assert "8080" in output

    def test_variable_with_default_but_provided(self):
        """Test that provided value overrides default"""
        content = "Port: ${port~8080}"
        input_variables = {"port": 3000}

        result, output = capture_output(
            replace_variables_in_content,
            content, input_variables, varprefix="$", delim="{}"
        )

        assert result == "Port: 3000"
        assert "Warning" not in output

    def test_variable_without_default_not_provided(self):
        """Test that variable without default remains unchanged when not provided"""
        content = "Port: ${port}"
        input_variables = {}

        result = replace_variables_in_content(
            content, input_variables, varprefix="$", delim="{}"
        )

        # Should remain unchanged
        assert result == "Port: ${port}"

    def test_multiple_variables_with_defaults(self):
        """Test multiple variables with default values"""
        content = """Host: ${host~localhost}
Port: ${port~8080}
Debug: ${debug~false}"""

        input_variables = {"host": "example.com"}

        result, output = capture_output(
            replace_variables_in_content,
            content, input_variables, varprefix="$", delim="{}"
        )

        assert "Host: example.com" in result
        assert "Port: 8080" in result
        assert "Debug: false" in result
        assert output.count("Warning") == 2  # port and debug not provided

    def test_default_value_with_special_characters(self):
        """Test default values containing special characters"""
        content = "URL: ${url~http://localhost:8080/api}"
        input_variables = {}

        result, output = capture_output(
            replace_variables_in_content,
            content, input_variables, varprefix="$", delim="{}"
        )

        assert result == "URL: http://localhost:8080/api"
        assert "Warning" in output

    def test_default_value_with_spaces(self):
        """Test default values containing spaces"""
        content = "Message: ${msg~Hello World}"
        input_variables = {}

        result, output = capture_output(
            replace_variables_in_content,
            content, input_variables, varprefix="$", delim="{}"
        )

        assert result == "Message: Hello World"
        assert "Warning" in output

    def test_numeric_default_values(self):
        """Test numeric default values"""
        content = """Threads: ${threads~4}
Timeout: ${timeout~30.5}
Max: ${max~1000}"""

        input_variables = {}

        result, output = capture_output(
            replace_variables_in_content,
            content, input_variables, varprefix="$", delim="{}"
        )

        assert "Threads: 4" in result
        assert "Timeout: 30.5" in result
        assert "Max: 1000" in result

    def test_empty_default_value(self):
        """Test empty string as default value"""
        content = "Optional: ${optional~}"
        input_variables = {}

        result, output = capture_output(
            replace_variables_in_content,
            content, input_variables, varprefix="$", delim="{}"
        )

        assert result == "Optional: "
        assert "Warning" in output

    def test_mixed_variables_with_and_without_defaults(self):
        """Test mix of variables with defaults, without defaults, and provided"""
        content = """Name: ${name}
Port: ${port~8080}
Host: ${host~localhost}
Path: ${path}"""

        input_variables = {"name": "MyApp", "host": "production.com"}

        result, output = capture_output(
            replace_variables_in_content,
            content, input_variables, varprefix="$", delim="{}"
        )

        assert "Name: MyApp" in result
        assert "Port: 8080" in result
        assert "Host: production.com" in result
        assert "Path: ${path}" in result  # Unchanged
        assert "port" in output  # Warning for port
        assert "host" not in output  # No warning, was provided

    def test_parse_variables_ignores_defaults(self):
        """Test that parse_variables_from_content extracts variable names, ignoring defaults"""
        content = """${var1~default1}
${var2}
${var3~default3}
$var4"""

        variables = parse_variables_from_content(content, varprefix="$", delim="{}")

        assert variables == {"var1", "var2", "var3", "var4"}

    def test_default_with_formula_prefix(self):
        """Test that default values work alongside formula evaluation"""
        content = """Port: ${port~8080}
Result: @{2 + 2}"""

        input_variables = {}
        model = {"formulaprefix": "@", "delim": "{}", "commentline": "#"}

        # First replace variables
        content_with_vars, output = capture_output(
            replace_variables_in_content,
            content, input_variables, varprefix="$", delim="{}"
        )

        # Then evaluate formulas
        result = evaluate_formulas(content_with_vars, model, input_variables, interpreter="python")

        assert "Port: 8080" in result
        assert "Result: 4" in result
        assert "Warning" in output

    def test_simple_variable_syntax_still_works(self):
        """Test that $var syntax (without delimiters) still works"""
        content = "Name: $name and Port: $port"
        input_variables = {"name": "MyApp", "port": 3000}

        result = replace_variables_in_content(
            content, input_variables, varprefix="$", delim="{}"
        )

        assert result == "Name: MyApp and Port: 3000"

    def test_default_value_with_tilde_character(self):
        """Test default value that itself contains a tilde"""
        # Note: This is a limitation - tilde in default value would need escaping
        content = "Path: ${path~~/home/user}"
        input_variables = {}

        result, output = capture_output(
            replace_variables_in_content,
            content, input_variables, varprefix="$", delim="{}"
        )

        # Should use everything after first ~ as default
        assert "/home/user" in result or "~/home/user" in result


class TestDefaultValuesInFiles:
    """Test default values with file-based inputs"""

    def test_template_with_defaults(self):
        """Test template file using default values"""
        content = """# Configuration File
server:
  host: ${host~0.0.0.0}
  port: ${port~8080}
  debug: ${debug~false}

database:
  url: ${db_url~sqlite:///./data.db}
  pool_size: ${db_pool~5}
"""

        input_variables = {
            "host": "127.0.0.1",
            "port": 3000,
            # db_url and db_pool not provided, should use defaults
        }

        result, output = capture_output(
            replace_variables_in_content,
            content, input_variables, varprefix="$", delim="{}"
        )

        assert "host: 127.0.0.1" in result
        assert "port: 3000" in result
        assert "debug: false" in result
        assert "url: sqlite:///./data.db" in result
        assert "pool_size: 5" in result

        # Should warn about debug, db_url, and db_pool
        assert output.count("Warning") == 3


class TestDefaultValuesEdgeCases:
    """Test edge cases and error conditions"""

    def test_nested_braces_in_default(self):
        """Test default value containing braces"""
        # This is a limitation - braces in default value would close the pattern
        content = "Data: ${data~{key: value}}"
        input_variables = {}

        result, output = capture_output(
            replace_variables_in_content,
            content, input_variables, varprefix="$", delim="{}"
        )

        # Will only capture up to first closing brace
        assert "Warning" in output

    def test_multiple_tildes_in_variable(self):
        """Test variable name with multiple tildes"""
        content = "Value: ${var~default1~default2}"
        input_variables = {}

        result, output = capture_output(
            replace_variables_in_content,
            content, input_variables, varprefix="$", delim="{}"
        )

        # Should use everything after first ~ as default
        assert "default1~default2" in result

    def test_variable_name_extraction_with_default(self):
        """Test that variable name is correctly extracted when default is present"""
        content = "${myvar~default}"
        variables = parse_variables_from_content(content, varprefix="$", delim="{}")

        assert "myvar" in variables
        assert "default" not in variables
        assert len(variables) == 1


if __name__ == "__main__":
    # Run tests
    print("=" * 70)
    print("Testing Default Value Syntax: ${var~default}")
    print("=" * 70)

    test_basic = TestDefaultValueSyntax()

    print("\n1. Testing variable with default (not provided)...")
    test_basic.test_variable_with_default_not_provided()
    print("✓ Passed")

    print("\n2. Testing variable with default (but provided)...")
    test_basic.test_variable_with_default_but_provided()
    print("✓ Passed")

    print("\n3. Testing variable without default (not provided)...")
    test_basic.test_variable_without_default_not_provided()
    print("✓ Passed")

    print("\n4. Testing multiple variables with defaults...")
    test_basic.test_multiple_variables_with_defaults()
    print("✓ Passed")

    print("\n5. Testing numeric default values...")
    test_basic.test_numeric_default_values()
    print("✓ Passed")

    print("\n6. Testing empty default value...")
    test_basic.test_empty_default_value()
    print("✓ Passed")

    print("\n7. Testing parse_variables ignores defaults...")
    test_basic.test_parse_variables_ignores_defaults()
    print("✓ Passed")

    print("\n8. Testing simple variable syntax still works...")
    test_basic.test_simple_variable_syntax_still_works()
    print("✓ Passed")

    test_files = TestDefaultValuesInFiles()

    print("\n9. Testing template with defaults...")
    test_files.test_template_with_defaults()
    print("✓ Passed")

    print("\n" + "=" * 70)
    print("ALL TESTS PASSED!")
    print("=" * 70)
