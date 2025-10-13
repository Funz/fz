#compdef fz fzi fzc fzo fzr
# Zsh completion script for fz, fzi, fzc, fzo, fzr commands

# Completion for fzi command
_fzi() {
    _arguments \
        '(-i --input_path)'{-i,--input_path}'[Input file or directory]:input file:_files' \
        '(-m --model)'{-m,--model}'[Model definition (JSON file, inline JSON, or alias)]:model file:_files -g "*.json"' \
        '(-f --format)'{-f,--format}'[Output format]:format:(json csv html markdown table)' \
        '(-h --help)'{-h,--help}'[Show help message]' \
        '--version[Show version]'
}

# Completion for fzc command
_fzc() {
    _arguments \
        '(-i --input_path)'{-i,--input_path}'[Input file or directory]:input file:_files' \
        '(-m --model)'{-m,--model}'[Model definition (JSON file, inline JSON, or alias)]:model file:_files -g "*.json"' \
        '(-v --input_variables)'{-v,--input_variables}'[Variable values (JSON file or inline JSON)]:variables file:_files -g "*.json"' \
        '(-o --output_dir)'{-o,--output_dir}'[Output directory (default: output)]:output directory:_directories' \
        '(-h --help)'{-h,--help}'[Show help message]' \
        '--version[Show version]'
}

# Completion for fzo command
_fzo() {
    _arguments \
        '(-o --output_path)'{-o,--output_path}'[Output file or directory]:output file:_files' \
        '(-m --model)'{-m,--model}'[Model definition (JSON file, inline JSON, or alias)]:model file:_files -g "*.json"' \
        '(-f --format)'{-f,--format}'[Output format]:format:(json csv html markdown table)' \
        '(-h --help)'{-h,--help}'[Show help message]' \
        '--version[Show version]'
}

# Completion for fzr command
_fzr() {
    _arguments \
        '(-i --input_path)'{-i,--input_path}'[Input file or directory]:input file:_files' \
        '(-m --model)'{-m,--model}'[Model definition (JSON file, inline JSON, or alias)]:model file:_files -g "*.json"' \
        '(-v --input_variables)'{-v,--input_variables}'[Variable values (JSON file or inline JSON)]:variables file:_files -g "*.json"' \
        '(-r --results_dir)'{-r,--results_dir}'[Results directory (default: results)]:results directory:_directories' \
        '(-c --calculators)'{-c,--calculators}'[Calculator specifications (JSON file or inline JSON)]:calculators file:_files -g "*.json"' \
        '(-f --format)'{-f,--format}'[Output format]:format:(json csv html markdown table)' \
        '(-h --help)'{-h,--help}'[Show help message]' \
        '--version[Show version]'
}

# Completion for fz main command with subcommands
_fz() {
    local curcontext="$curcontext" state line
    typeset -A opt_args

    _arguments -C \
        '(-h --help)'{-h,--help}'[Show help message]' \
        '--version[Show version]' \
        '1: :->command' \
        '*::arg:->args'

    case $state in
        command)
            local -a subcommands
            subcommands=(
                'input:Parse input to find variables'
                'compile:Compile input with variable values'
                'output:Parse output files'
                'run:Run full parametric calculations'
            )
            _describe -t commands 'fz command' subcommands
            ;;
        args)
            case $line[1] in
                input)
                    _arguments \
                        '(-i --input_path)'{-i,--input_path}'[Input file or directory]:input file:_files' \
                        '(-m --model)'{-m,--model}'[Model definition (JSON file, inline JSON, or alias)]:model file:_files -g "*.json"' \
                        '(-f --format)'{-f,--format}'[Output format]:format:(json csv html markdown table)' \
                        '(-h --help)'{-h,--help}'[Show help message]' \
                        '--version[Show version]'
                    ;;
                compile)
                    _arguments \
                        '(-i --input_path)'{-i,--input_path}'[Input file or directory]:input file:_files' \
                        '(-m --model)'{-m,--model}'[Model definition (JSON file, inline JSON, or alias)]:model file:_files -g "*.json"' \
                        '(-v --input_variables)'{-v,--input_variables}'[Variable values (JSON file or inline JSON)]:variables file:_files -g "*.json"' \
                        '(-o --output_dir)'{-o,--output_dir}'[Output directory (default: output)]:output directory:_directories' \
                        '(-h --help)'{-h,--help}'[Show help message]' \
                        '--version[Show version]'
                    ;;
                output)
                    _arguments \
                        '(-o --output_path)'{-o,--output_path}'[Output file or directory]:output file:_files' \
                        '(-m --model)'{-m,--model}'[Model definition (JSON file, inline JSON, or alias)]:model file:_files -g "*.json"' \
                        '(-f --format)'{-f,--format}'[Output format]:format:(json csv html markdown table)' \
                        '(-h --help)'{-h,--help}'[Show help message]' \
                        '--version[Show version]'
                    ;;
                run)
                    _arguments \
                        '(-i --input_path)'{-i,--input_path}'[Input file or directory]:input file:_files' \
                        '(-m --model)'{-m,--model}'[Model definition (JSON file, inline JSON, or alias)]:model file:_files -g "*.json"' \
                        '(-v --input_variables)'{-v,--input_variables}'[Variable values (JSON file or inline JSON)]:variables file:_files -g "*.json"' \
                        '(-r --results_dir)'{-r,--results_dir}'[Results directory (default: results)]:results directory:_directories' \
                        '(-c --calculators)'{-c,--calculators}'[Calculator specifications (JSON file or inline JSON)]:calculators file:_files -g "*.json"' \
                        '(-f --format)'{-f,--format}'[Output format]:format:(json csv html markdown table)' \
                        '(-h --help)'{-h,--help}'[Show help message]' \
                        '--version[Show version]'
                    ;;
            esac
            ;;
    esac
}

# Register completion functions
compdef _fz fz
compdef _fzi fzi
compdef _fzc fzc
compdef _fzo fzo
compdef _fzr fzr
