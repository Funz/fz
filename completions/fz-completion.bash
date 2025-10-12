#!/usr/bin/env bash
# Bash completion script for fz, fzi, fzc, fzo, fzr commands

# Helper function to complete file paths
_fz_complete_files() {
    COMPREPLY=($(compgen -f -- "$1"))
}

# Helper function to complete directories
_fz_complete_dirs() {
    COMPREPLY=($(compgen -d -- "$1"))
}

# Completion for fzi command
_fzi() {
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    opts="--input_path -i --model -m --format -f --help -h --version"

    case "${prev}" in
        --input_path|-i)
            _fz_complete_files "${cur}"
            return 0
            ;;
        --model|-m)
            _fz_complete_files "${cur}"
            return 0
            ;;
        --format|-f)
            COMPREPLY=($(compgen -W "json csv html markdown table" -- ${cur}))
            return 0
            ;;
        *)
            ;;
    esac

    COMPREPLY=($(compgen -W "${opts}" -- ${cur}))
    return 0
}

# Completion for fzc command
_fzc() {
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    opts="--input_path -i --model -m --input_variables -v --output_dir -o --help -h --version"

    case "${prev}" in
        --input_path|-i)
            _fz_complete_files "${cur}"
            return 0
            ;;
        --model|-m)
            _fz_complete_files "${cur}"
            return 0
            ;;
        --input_variables|-v)
            _fz_complete_files "${cur}"
            return 0
            ;;
        --output_dir|-o)
            _fz_complete_dirs "${cur}"
            return 0
            ;;
        *)
            ;;
    esac

    COMPREPLY=($(compgen -W "${opts}" -- ${cur}))
    return 0
}

# Completion for fzo command
_fzo() {
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    opts="--output_path -o --model -m --format -f --help -h --version"

    case "${prev}" in
        --output_path|-o)
            _fz_complete_files "${cur}"
            return 0
            ;;
        --model|-m)
            _fz_complete_files "${cur}"
            return 0
            ;;
        --format|-f)
            COMPREPLY=($(compgen -W "json csv html markdown table" -- ${cur}))
            return 0
            ;;
        *)
            ;;
    esac

    COMPREPLY=($(compgen -W "${opts}" -- ${cur}))
    return 0
}

# Completion for fzr command
_fzr() {
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    opts="--input_path -i --model -m --input_variables -v --results_dir -r --calculators -c --format -f --help -h --version"

    case "${prev}" in
        --input_path|-i)
            _fz_complete_files "${cur}"
            return 0
            ;;
        --model|-m)
            _fz_complete_files "${cur}"
            return 0
            ;;
        --input_variables|-v)
            _fz_complete_files "${cur}"
            return 0
            ;;
        --results_dir|-r)
            _fz_complete_dirs "${cur}"
            return 0
            ;;
        --calculators|-c)
            _fz_complete_files "${cur}"
            return 0
            ;;
        --format|-f)
            COMPREPLY=($(compgen -W "json csv html markdown table" -- ${cur}))
            return 0
            ;;
        *)
            ;;
    esac

    COMPREPLY=($(compgen -W "${opts}" -- ${cur}))
    return 0
}

# Completion for fz main command
_fz() {
    local cur prev opts subcommand
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # Find the subcommand if any
    subcommand=""
    for ((i=1; i < COMP_CWORD; i++)); do
        case "${COMP_WORDS[i]}" in
            input|compile|output|run)
                subcommand="${COMP_WORDS[i]}"
                break
                ;;
        esac
    done

    # If no subcommand yet, offer subcommands and main options
    if [[ -z "$subcommand" ]]; then
        opts="input compile output run --help -h --version"
        COMPREPLY=($(compgen -W "${opts}" -- ${cur}))
        return 0
    fi

    # Handle subcommand-specific completion
    case "${subcommand}" in
        input)
            opts="--input_path -i --model -m --format -f --help -h --version"
            case "${prev}" in
                --input_path|-i)
                    _fz_complete_files "${cur}"
                    return 0
                    ;;
                --model|-m)
                    _fz_complete_files "${cur}"
                    return 0
                    ;;
                --format|-f)
                    COMPREPLY=($(compgen -W "json csv html markdown table" -- ${cur}))
                    return 0
                    ;;
                *)
                    COMPREPLY=($(compgen -W "${opts}" -- ${cur}))
                    return 0
                    ;;
            esac
            ;;
        compile)
            opts="--input_path -i --model -m --input_variables -v --output_dir -o --help -h --version"
            case "${prev}" in
                --input_path|-i)
                    _fz_complete_files "${cur}"
                    return 0
                    ;;
                --model|-m)
                    _fz_complete_files "${cur}"
                    return 0
                    ;;
                --input_variables|-v)
                    _fz_complete_files "${cur}"
                    return 0
                    ;;
                --output_dir|-o)
                    _fz_complete_dirs "${cur}"
                    return 0
                    ;;
                *)
                    COMPREPLY=($(compgen -W "${opts}" -- ${cur}))
                    return 0
                    ;;
            esac
            ;;
        output)
            opts="--output_path -o --model -m --format -f --help -h --version"
            case "${prev}" in
                --output_path|-o)
                    _fz_complete_files "${cur}"
                    return 0
                    ;;
                --model|-m)
                    _fz_complete_files "${cur}"
                    return 0
                    ;;
                --format|-f)
                    COMPREPLY=($(compgen -W "json csv html markdown table" -- ${cur}))
                    return 0
                    ;;
                *)
                    COMPREPLY=($(compgen -W "${opts}" -- ${cur}))
                    return 0
                    ;;
            esac
            ;;
        run)
            opts="--input_path -i --model -m --input_variables -v --results_dir -r --calculators -c --format -f --help -h --version"
            case "${prev}" in
                --input_path|-i)
                    _fz_complete_files "${cur}"
                    return 0
                    ;;
                --model|-m)
                    _fz_complete_files "${cur}"
                    return 0
                    ;;
                --input_variables|-v)
                    _fz_complete_files "${cur}"
                    return 0
                    ;;
                --results_dir|-r)
                    _fz_complete_dirs "${cur}"
                    return 0
                    ;;
                --calculators|-c)
                    _fz_complete_files "${cur}"
                    return 0
                    ;;
                --format|-f)
                    COMPREPLY=($(compgen -W "json csv html markdown table" -- ${cur}))
                    return 0
                    ;;
                *)
                    COMPREPLY=($(compgen -W "${opts}" -- ${cur}))
                    return 0
                    ;;
            esac
            ;;
    esac

    return 0
}

# Register completion functions
complete -F _fz fz
complete -F _fzi fzi
complete -F _fzc fzc
complete -F _fzo fzo
complete -F _fzr fzr
