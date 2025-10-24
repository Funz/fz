# FZD Content Format Handling

## Overview

`fzd` (Design of Experiments) intelligently detects and processes different content formats returned by algorithm's `get_analysis()` and `get_analysis_tmp()` methods. Content is automatically saved to appropriate files and parsed into structured Python objects.

## Supported Formats

### 1. HTML Content
**Detection**: Presence of HTML tags (`<html>`, `<div>`, `<p>`, `<h1>`, etc.)

**Processing**:
- Saved to: `analysis_<iteration>.html`
- Return structure: `{'html_file': 'analysis_<iteration>.html'}`

**Algorithm Example**:
```python
def get_analysis(self, X, Y):
    return {
        'text': '<html><body><h1>Results</h1><p>Mean: 42.5</p></body></html>',
        'data': {'mean': 42.5}
    }
```

**Result**:
- File created: `results_fzd/analysis_1.html`
- Python return: `result['display']['html_file'] == 'analysis_1.html'`
- Raw content NOT included in return (replaced with file reference)

### 2. JSON Content
**Detection**: Text starts with `{` or `[` and is valid JSON

**Processing**:
- Parsed to Python object
- Saved to: `analysis_<iteration>.json`
- Return structure:
  - `{'json_data': {...}}` - Parsed Python object
  - `{'json_file': 'analysis_<iteration>.json'}` - File reference

**Algorithm Example**:
```python
def get_analysis(self, X, Y):
    return {
        'text': '{"mean": 42.5, "std": 3.2, "samples": 100}',
        'data': {}
    }
```

**Result**:
- File created: `results_fzd/analysis_1.json`
- Python return:
  ```python
  result['display']['json_data'] == {'mean': 42.5, 'std': 3.2, 'samples': 100}
  result['display']['json_file'] == 'analysis_1.json'
  ```

### 3. Key=Value Format
**Detection**: Multiple lines with `=` signs (at least 2)

**Processing**:
- Parsed to Python dict
- Saved to: `analysis_<iteration>.txt`
- Return structure:
  - `{'keyvalue_data': {...}}` - Parsed dict
  - `{'txt_file': 'analysis_<iteration>.txt'}` - File reference

**Algorithm Example**:
```python
def get_analysis(self, X, Y):
    return {
        'text': '''mean=42.5
std=3.2
samples=100
confidence_interval=[40.1, 44.9]''',
        'data': {}
    }
```

**Result**:
- File created: `results_fzd/analysis_1.txt`
- Python return:
  ```python
  result['display']['keyvalue_data'] == {
      'mean': '42.5',
      'std': '3.2',
      'samples': '100',
      'confidence_interval': '[40.1, 44.9]'
  }
  result['display']['txt_file'] == 'analysis_1.txt'
  ```

### 4. Markdown Content
**Detection**: Presence of markdown syntax (`#`, `##`, `*`, `-`, ` ``` `, etc.)

**Processing**:
- Saved to: `analysis_<iteration>.md`
- Return structure: `{'md_file': 'analysis_<iteration>.md'}`

**Algorithm Example**:
```python
def get_analysis(self, X, Y):
    return {
        'text': '''# Analysis Results

## Statistics
- Mean: 42.5
- Standard Deviation: 3.2

```python
# Algorithm configuration
samples = 100
```
''',
        'data': {'mean': 42.5, 'std': 3.2}
    }
```

**Result**:
- File created: `results_fzd/analysis_1.md`
- Python return: `result['display']['md_file'] == 'analysis_1.md'`
- Raw markdown NOT included in return (replaced with file reference)

### 5. Plain Text
**Detection**: None of the above formats detected

**Processing**:
- Kept as-is in the return dict
- Return structure: `{'text': 'plain text content...'}`

**Algorithm Example**:
```python
def get_analysis(self, X, Y):
    return {
        'text': 'Mean: 42.5, Std: 3.2, Samples: 100',
        'data': {'mean': 42.5, 'std': 3.2}
    }
```

**Result**:
- No file created
- Python return: `result['display']['text'] == 'Mean: 42.5, Std: 3.2, Samples: 100'`

## Multiple Content Types

Algorithms can return both 'text' and 'html' fields separately:

```python
def get_analysis(self, X, Y):
    return {
        'text': 'Summary: Mean is 42.5 with 100 samples',
        'html': '<div class="plot"><img src="histogram.png"/></div>',
        'data': {'mean': 42.5, 'samples': 100}
    }
```

**Result**:
- File created: `results_fzd/analysis_1.html` (from 'html' field)
- Python return:
  ```python
  result['display']['text'] == 'Summary: Mean is 42.5 with 100 samples'
  result['display']['html_file'] == 'analysis_1.html'
  result['display']['data'] == {'mean': 42.5, 'samples': 100}
  ```

## FZD Return Structure

The complete structure returned by `fzd()`:

```python
result = {
    'XY': pd.DataFrame,           # All input variables and output values

    'display': {                  # Processed analysis from get_analysis()
        'data': {...},            # Numeric/structured data from algorithm

        # Content-specific fields (depending on format detected):
        'html_file': 'analysis_N.html',      # If HTML detected
        'json_data': {...},                   # If JSON detected (parsed)
        'json_file': 'analysis_N.json',      # JSON file reference
        'keyvalue_data': {...},               # If key=value detected (parsed)
        'txt_file': 'analysis_N.txt',        # Key=value file reference
        'md_file': 'analysis_N.md',          # If markdown detected
        'text': '...',                        # Plain text (no format detected)

        '_raw': {                             # Original algorithm output (for debug)
            'text': '...',
            'html': '...',
            'data': {...}
        }
    },

    'algorithm': 'path/to/algorithm.py',
    'iterations': 5,
    'total_evaluations': 100,
    'summary': 'algorithm completed: 5 iterations, 100 evaluations (95 valid)'
}
```

## Accessing Results

### Access parsed data:
```python
# For JSON format
mean = result['display']['json_data']['mean']

# For key=value format
mean = float(result['display']['keyvalue_data']['mean'])

# For data dict (always available)
mean = result['display']['data']['mean']
```

### Access file paths:
```python
from pathlib import Path

# HTML file
html_file = Path('results_fzd') / result['display']['html_file']
with open(html_file) as f:
    html_content = f.read()

# JSON file
json_file = Path('results_fzd') / result['display']['json_file']
with open(json_file) as f:
    data = json.load(f)
```

### Access raw algorithm output:
```python
# Get original text before processing
original_text = result['display']['_raw']['text']
original_html = result['display']['_raw']['html']
```

## Iteration Files

For each iteration, `fzd` creates:

1. **Input data**: `X_<iteration>.csv` - All input variable values
2. **Output data**: `Y_<iteration>.csv` - All output values
3. **HTML summary**: `results_<iteration>.html` - Iteration overview with embedded analysis
4. **Analysis files**: `analysis_<iteration>.[html|json|txt|md]` - Processed algorithm output

## Implementation Details

### Content Detection (fz/io.py)
```python
def detect_content_type(text: str) -> str:
    """Returns: 'html', 'json', 'keyvalue', 'markdown', or 'plain'"""
```

### Content Processing (fz/io.py)
```python
def process_display_content(
    display_dict: Dict[str, Any],
    iteration: int,
    results_dir: Path
) -> Dict[str, Any]:
    """Process get_analysis() output, detect formats, and save files"""
```

### Integration (fz/core.py)
- `_get_and_process_analysis()` - Calls process_display_content for each iteration
- Called for both `get_analysis()` (final) and `get_analysis_tmp()` (intermediate)

## Testing

Run content detection tests:
```bash
python -m pytest tests/test_fzd.py::TestContentDetection -v
```

Run demo:
```bash
python demo_fzd_content_formats.py
```

## Best Practices for Algorithm Developers

1. **Use the 'data' field for structured numeric data**
   ```python
   return {'data': {'mean': 42.5, 'std': 3.2}, 'text': 'Summary...'}
   ```

2. **Return JSON for complex structured data**
   ```python
   import json
   return {'text': json.dumps({'results': [...], 'stats': {...}})}
   ```

3. **Use markdown for formatted text with structure**
   ```python
   return {'text': '# Results\n\n## Statistics\n- Mean: 42.5\n- Std: 3.2'}
   ```

4. **Use HTML for rich visualizations**
   ```python
   return {'html': '<div><img src="plot.png"/></div>', 'text': 'See plot'}
   ```

5. **Use key=value for simple parameter lists**
   ```python
   return {'text': 'mean=42.5\nstd=3.2\nsamples=100'}
   ```

## Backward Compatibility

- Original raw content is preserved in `display['_raw']`
- If algorithms don't return structured formats, content remains in `display['text']`
- All existing code continues to work unchanged
