# Shell Completion Scripts for fz

This directory contains shell completion scripts for the fz command-line tools.

## Available Scripts

- `fz-completion.bash` - Bash completion script
- `fz-completion.zsh` - Zsh completion script

## Installation

### Bash

#### Option 1: User-level installation (recommended)

```bash
# Create bash completion directory if it doesn't exist
mkdir -p ~/.bash_completion.d

# Copy the completion script
cp completions/fz-completion.bash ~/.bash_completion.d/

# Add to your ~/.bashrc if not already present
echo 'for f in ~/.bash_completion.d/*; do source "$f"; done' >> ~/.bashrc

# Reload your shell configuration
source ~/.bashrc
```

#### Option 2: System-wide installation (requires sudo)

```bash
# Copy to system bash completion directory
sudo cp completions/fz-completion.bash /etc/bash_completion.d/fz

# Reload your shell or start a new terminal
```

#### Option 3: Temporary (current session only)

```bash
source completions/fz-completion.bash
```

### Zsh

#### Option 1: User-level installation (recommended)

```zsh
# Create zsh completion directory if it doesn't exist
mkdir -p ~/.zsh/completion

# Copy the completion script
cp completions/fz-completion.zsh ~/.zsh/completion/_fz

# Add to your ~/.zshrc if not already present
echo 'fpath=(~/.zsh/completion $fpath)' >> ~/.zshrc
echo 'autoload -Uz compinit && compinit' >> ~/.zshrc

# Reload your shell configuration
source ~/.zshrc
```

#### Option 2: Using oh-my-zsh

```zsh
# Copy to oh-my-zsh completions directory
cp completions/fz-completion.zsh ~/.oh-my-zsh/completions/_fz

# Reload completion cache
rm -f ~/.zcompdump
exec zsh
```

#### Option 3: Temporary (current session only)

```zsh
source completions/fz-completion.zsh
```

## Usage

Once installed, the completion scripts provide intelligent tab completion for all fz commands:

### Commands with completion support

- `fz` - Main command with subcommands (input, compile, output, run, list)
- `fzi` - Parse input to find variables
- `fzc` - Compile input with variable values
- `fzo` - Parse output files
- `fzr` - Run full parametric calculations
- `fzl` - List available models and calculators

### Examples

```bash
# Press TAB after typing these to see available options:
fz <TAB>                    # Shows: input, compile, output, run, list, --help, -h
fzi --<TAB>                 # Shows: --input_path, --model, --help
fzc -<TAB>                  # Shows: -i, -m, -v, -o, -h
fzr --input_path <TAB>      # Shows available files in current directory
fzc --output_dir <TAB>      # Shows available directories
fzl --<TAB>                 # Shows: --models, --calculators, --check, --format

# Subcommand completion:
fz input --<TAB>            # Shows options for input command
fz run --results_dir <TAB>  # Shows available directories
fz list --format <TAB>      # Shows: json, markdown, table
```

### Features

- **Command completion**: All commands and subcommands are completed
- **Option completion**: Both long (`--option`) and short (`-o`) forms
- **File completion**: Intelligent file completion for input paths
- **Directory completion**: Directory-only completion for output/results directories
- **JSON file completion**: Suggests .json files for model and variable arguments
- **Help text**: Shows descriptions for each option (zsh only)

## Troubleshooting

### Bash

If completion doesn't work:

1. Verify bash-completion is installed:
   ```bash
   # On Debian/Ubuntu
   sudo apt-get install bash-completion

   # On macOS
   brew install bash-completion
   ```

2. Check if completion is sourced:
   ```bash
   type _fz
   # Should output: _fz is a function
   ```

3. Manually source the script to test:
   ```bash
   source completions/fz-completion.bash
   ```

### Zsh

If completion doesn't work:

1. Check if compinit is loaded:
   ```zsh
   echo $fpath
   # Should include your completion directory
   ```

2. Rebuild completion cache:
   ```zsh
   rm -f ~/.zcompdump
   compinit
   ```

3. Check if completion function is available:
   ```zsh
   which _fz
   # Should show: _fz () { ... }
   ```

4. Ensure fpath is set before compinit in ~/.zshrc:
   ```zsh
   fpath=(~/.zsh/completion $fpath)
   autoload -Uz compinit && compinit
   ```

## Uninstallation

### Bash

```bash
# User-level
rm ~/.bash_completion.d/fz-completion.bash

# System-wide
sudo rm /etc/bash_completion.d/fz
```

### Zsh

```zsh
# User-level
rm ~/.zsh/completion/_fz

# oh-my-zsh
rm ~/.oh-my-zsh/completions/_fz

# Rebuild completion cache
rm -f ~/.zcompdump
compinit
```

## Development

If you're developing or modifying the completion scripts:

1. Edit the script in `completions/`
2. Reload the script:
   ```bash
   # Bash
   source completions/fz-completion.bash

   # Zsh
   source completions/fz-completion.zsh
   ```
3. Test the completion by typing commands and pressing TAB
4. For zsh, you may need to clear the completion cache:
   ```zsh
   rm -f ~/.zcompdump
   compinit
   ```
