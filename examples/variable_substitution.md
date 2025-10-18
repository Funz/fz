# Variable Substitution in FZ

This document explains how variable substitution works in the FZ package, including the new default value syntax.

## Basic Syntax

Variables in template files are replaced using a prefix (default `$`) and optional delimiters:

### Simple Variables

```
Name: $name
Version: $version
```

### Delimited Variables

Use delimiters `{}` when the variable name is followed by alphanumeric characters:

```
File: ${name}_config.txt
Path: /home/${user}/documents
```

## Default Values (v0.9.1+)

You can specify default values that will be used when a variable is not provided.

### Syntax

```
${variable~default_value}
```

- Variable name: `variable`
- Separator: `~` (tilde)
- Default value: `default_value`

### Examples

```python
from fz.interpreter import replace_variables_in_content

content = """
Application Configuration:
  name: ${app_name~MyApplication}
  host: ${host~localhost}
  port: ${port~8080}
  debug: ${debug~false}
  max_connections: ${max_conn~100}
"""

# Only provide some variables
input_variables = {
    "app_name": "ProductionApp",
    "host": "example.com"
}

result = replace_variables_in_content(content, input_variables)
```

**Output:**
```
Application Configuration:
  name: ProductionApp
  host: example.com
  port: 8080
  debug: false
  max_connections: 100
```

**Warnings printed:**
```
Warning: Variable 'port' not found in input_variables, using default value: '8080'
Warning: Variable 'debug' not found in input_variables, using default value: 'false'
Warning: Variable 'max_conn' not found in input_variables, using default value: '100'
```

## Behavior Rules

### 1. Variable Provided

When a variable is provided in `input_variables`, its value is used regardless of any default:

```python
content = "Port: ${port~8080}"
input_variables = {"port": 3000}
# Result: "Port: 3000"
# No warning
```

### 2. Variable Not Provided, Has Default

When a variable is not provided but has a default value, the default is used and a warning is printed:

```python
content = "Port: ${port~8080}"
input_variables = {}
# Result: "Port: 8080"
# Warning: Variable 'port' not found in input_variables, using default value: '8080'
```

### 3. Variable Not Provided, No Default

When a variable is not provided and has no default, it remains unchanged:

```python
content = "Port: ${port}"
input_variables = {}
# Result: "Port: ${port}"
# No warning
```

## Use Cases

### Configuration Templates

Create configuration files with sensible defaults:

```yaml
# config.yaml.template
server:
  host: ${SERVER_HOST~0.0.0.0}
  port: ${SERVER_PORT~8080}
  workers: ${WORKERS~4}

database:
  url: ${DATABASE_URL~sqlite:///./app.db}
  pool_size: ${DB_POOL~5}

logging:
  level: ${LOG_LEVEL~INFO}
  file: ${LOG_FILE~/var/log/app.log}
```

### Environment-Specific Deployments

Different defaults for different environments:

```python
# Development
dev_vars = {"host": "localhost", "debug": "true"}

# Production
prod_vars = {"host": "production.example.com", "workers": "8"}

# Both use same template with defaults
template = """
Host: ${host~0.0.0.0}
Port: ${port~8080}
Debug: ${debug~false}
Workers: ${workers~4}
"""
```

### Parametric Studies with Optional Parameters

```python
from fz import fzi

# Some variables have defaults in the template
results = fzi(
    input_path="simulation.template",
    input_variables={
        "temperature": [100, 200, 300],  # Required
        # pressure uses default from template
        # time_step uses default from template
    },
    output_expression="max_temp"
)
```

## Default Value Types

### Numeric Values

```
Threads: ${threads~4}
Timeout: ${timeout~30.5}
```

### String Values

```
Name: ${name~MyApp}
Message: ${msg~Hello World}
Path: ${path~/usr/local/bin}
```

### Boolean-like Values

```
Debug: ${debug~false}
Enabled: ${enabled~true}
```

### URLs and Paths

```
API: ${api_url~http://localhost:8080/api}
Config: ${config_path~./config/default.json}
```

### Empty Strings

Use empty default to make variable optional:

```
Suffix: ${suffix~}
Optional: ${opt~}
```

## Advanced Usage

### With Formulas

Default values work alongside formula evaluation:

```
# Template
Port: ${port~8080}
URL: http://localhost:@{$port}/api

# Python code
content = replace_variables_in_content(template, {"port": 3000})
result = evaluate_formulas(content, model, {"port": 3000})
# Result: "Port: 3000" and "URL: http://localhost:3000/api"
```

### Parsing Variables

The `parse_variables_from_content` function extracts variable names, ignoring defaults:

```python
from fz.interpreter import parse_variables_from_content

content = "${var1~default1}, ${var2}, ${var3~default3}"
variables = parse_variables_from_content(content)
# Returns: {"var1", "var2", "var3"}
```

## Limitations

### Tilde in Default Values

If your default value contains a tilde `~`, only the part before the first `~` in the variable definition is treated as the variable name:

```
# This may not work as expected:
${path~~~home/user}  # Variable: path, Default: ~home/user
```

### Braces in Default Values

If your default value contains the closing delimiter `}`, it will prematurely close the variable pattern:

```
# Problematic:
${json~{key: value}}  # Will only capture up to first }
```

## Migration from Earlier Versions

If you're upgrading from an earlier version of FZ:

### Before (v0.9.0 and earlier)

All variables had to be provided, or they would remain as placeholders:

```python
content = "Port: ${port}"
input_variables = {}
# Result: "Port: ${port}"
```

### After (v0.9.1+)

You can now specify defaults:

```python
content = "Port: ${port~8080}"
input_variables = {}
# Result: "Port: 8080"
# Warning: Variable 'port' not found in input_variables, using default value: '8080'
```

### Backward Compatibility

The old syntax still works exactly as before. Default values are opt-in:

- `$var` - Simple variable (unchanged)
- `${var}` - Delimited variable (unchanged)
- `${var~default}` - New: variable with default

## Best Practices

1. **Use descriptive default values** that make sense in a development/testing context
2. **Document your template variables** and their defaults
3. **Keep defaults simple** - avoid complex expressions or special characters
4. **Use defaults for optional configuration** but require critical parameters
5. **Review warnings** - they indicate which variables are using defaults

## Examples

### Docker Configuration

```dockerfile
# Dockerfile.template
FROM ${BASE_IMAGE~python:3.11-slim}

ENV APP_HOME=${APP_HOME~/app}
ENV PORT=${PORT~8080}
ENV WORKERS=${WORKERS~4}

WORKDIR $APP_HOME
COPY . .

CMD gunicorn -w $WORKERS -b 0.0.0.0:$PORT app:app
```

### Kubernetes ConfigMap

```yaml
# configmap.yaml.template
apiVersion: v1
kind: ConfigMap
metadata:
  name: ${APP_NAME~myapp}-config
data:
  database.url: ${DATABASE_URL~postgresql://localhost:5432/mydb}
  cache.ttl: "${CACHE_TTL~3600}"
  log.level: ${LOG_LEVEL~INFO}
  feature.beta: "${FEATURE_BETA~false}"
```

### Scientific Simulation

```
# simulation.template
Simulation Parameters:
  particles: $n_particles
  time_steps: ${time_steps~1000}
  dt: ${dt~0.001}
  temperature: ${temp~300.0}
  pressure: ${pressure~1.0}
  output_freq: ${output_freq~100}
```

## Summary

Default values provide a powerful way to create flexible, reusable templates with sensible fallback values. They're especially useful for:

- Configuration management
- Environment-specific deployments
- Optional parameters in parametric studies
- Template files with development defaults
- Reducing the number of required variables

The syntax is simple: `${variable~default}`, and the behavior is predictable: use the provided value if available, otherwise use the default and warn.
