#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import os
from itertools import product
import rpy2.robjects as robjects

class fz:
    """
    Classe pour analyser (ParseInput) et compiler (CompileInput) un fichier JDD paramétré.
    """

    def __init__(self):
        pass

    # --------------------------------------------------------------------------
    # Méthodes publiques
    # --------------------------------------------------------------------------

    def ParseInput(self, input_file):
        """
        Lit un fichier paramétré (ex. Pumet2.pij) et détecte les variables
        définies sous la forme $(var~...) ou $var.
        Retourne un set (ensemble) des noms de variables.
        """
        text = self._load_jdd(input_file)
        found_vars = self._detect_variables(text)
        return found_vars

    def CompileInput(self, input_file, input_variables, output_prefix=None, group_variables=None, use_dirs=False, filename_template=None):
        """
        Lit un fichier paramétré (input_file),
        et pour chaque combinaison des valeurs spécifiées dans input_variables
        (dict: {var_name: [liste_valeurs]}), génère un fichier de sortie.

        Exemples d'utilisation :
        - Sans group_variables (produit cartésien de toutes les valeurs) :
          input_variables = {
              "H_X": [10, 100],
              "r0": [0.17000, 0.1800],
              "r1": [0.64706, 0.6500],
              "r2": [0.09091, 0.1000],
          }
          => 16 jeux de données générés.

        - Avec group_variables :
          group_variables = ["r0", "r1", "r2"]
          => les valeurs de r0, r1 et r2 sont liées entre elles (elles doivent avoir le même nombre d'éléments)
          et seules 4 combinaisons sont générées (2 valeurs pour H_X multipliées par 2 groupes).

        - output_prefix : préfixe pour les fichiers générés.
          Par défaut, on utilise le nom de base du fichier d'entrée.
        - filename_template : gabarit ``str.format`` pour nommer les fichiers.
          Les clés disponibles sont ``prefix``, ``ext``, ``scenario`` et les
          noms de variables.
            Exemple d'appel : f.CompileInput(..., filename_template="{prefix}_R{r0:.0f}{ext}") pour formater r0 en entier.
        - use_dirs : si True, crée une arborescence de répertoires basée sur
          les valeurs des variables non groupées. Les dossiers sont classés
          par variable en commençant par celles ayant le moins de valeurs
          afin de limiter le nombre de répertoires créés. Les fichiers générés
          sont alors placés dans ces répertoires et ne contiennent plus ces
          variables dans leur nom
        - À la fin de l'exécution, un fichier ``generated_files.csv`` listant
          les chemins relatifs et les valeurs de variables de chaque scénario
          est sauvegardé dans le répertoire du fichier d'entrée
        """
        template_text = self._load_jdd(input_file)
        group_vars = list(group_variables) if group_variables else []
        input_dir = os.path.dirname(os.path.abspath(input_file)) or "."
        scenario_infos = []

                # Détermination de l'ordre des variables non groupées
        if use_dirs:
            sort_key = lambda k: (len(input_variables[k]), k)
        else:
            sort_key = lambda k: k
        ungroup_vars = sorted([k for k in input_variables.keys() if k not in group_vars], key=sort_key)

        # Construction des combinaisons en fonction de group_variables
        if not group_vars:
            # Produit cartésien sur toutes les variables
            keys = ungroup_vars
            lists_of_values = [input_variables[k] for k in keys]
            combos = [dict(zip(keys, combo)) for combo in product(*lists_of_values)]
        else:           
            # Combinaisons pour les variables non groupées
            if ungroup_vars:
                ungroup_lists = [input_variables[k] for k in ungroup_vars]
                ungroup_combos = list(product(*ungroup_lists))
            else:
                ungroup_combos = [()]
            
            # Préparation des combinaisons pour les variables groupées
            group_lists = [input_variables[k] for k in group_vars]
            if len({len(lst) for lst in group_lists}) != 1:
                raise ValueError("Toutes les variables groupées doivent avoir la même longueur")
            grouped_combos = list(zip(*group_lists))
            
            # Produit cartésien entre les combinaisons non groupées et les groupes liés
            combos = []
            for ungroup_combo in ungroup_combos:
                for group_combo in grouped_combos:
                    scenario_dict = {}
                    for i, k in enumerate(ungroup_vars):
                        scenario_dict[k] = ungroup_combo[i]
                    for i, k in enumerate(group_vars):
                        scenario_dict[k] = group_combo[i]
                    combos.append(scenario_dict)

        basename = os.path.basename(input_file)
        output_prefix_from_file, ext = os.path.splitext(basename)
        if output_prefix is None:
            output_prefix = output_prefix_from_file

        for scenario_dict in combos:
            # 1) Utilisation directe du texte
            processed_text = template_text

            # 2) Assignation des variables dans R
            for var_name, val in scenario_dict.items():
                robjects.r.assign(var_name, val)

            # 3) Exécution du code R multi-ligne
            text_after_rblocks = self._process_multiline_r_code(processed_text)

            # 4) Gestion de @{ code | fallback }
            final_text = self._parse_and_replace_at_braces_format(text_after_rblocks)

            # 5) Écriture dans un fichier de sortie
            # Construction du chemin de sortie selon use_dirs
            if use_dirs and ungroup_vars:
                dir_path = os.path.join(*(f"{k}={scenario_dict[k]}" for k in ungroup_vars))
                os.makedirs(dir_path, exist_ok=True)
            else:
                dir_path = ""

            # Détermination des variables à inclure dans le nom de fichier
            if use_dirs:
                suffix_keys = group_vars
            else:
                suffix_keys = sorted(scenario_dict.keys())

            scenario_suffix = "_".join(f"{k}={scenario_dict[k]}" for k in suffix_keys)

            if filename_template is None:
                if scenario_suffix:
                    fname = f"{output_prefix}_{scenario_suffix}{ext}"
                else:
                    fname = f"{output_prefix}{ext}"
            else:
                format_vars = {
                    "prefix": output_prefix,
                    "ext": ext,
                    "scenario": scenario_suffix,
                    **scenario_dict,
                }
                try:
                    fname = filename_template.format(**format_vars)
                except KeyError as e:
                    raise ValueError(
                        f"Unknown variable in filename_template: {e.args[0]}"
                    )

            out_filename = os.path.join(dir_path, fname)

            with open(out_filename, 'w', encoding='utf-8') as f:
                f.write(final_text)

            print(f"Generated : {out_filename} with {scenario_dict}")
            rel_path = os.path.relpath(out_filename, start=input_dir)
            scenario_infos.append({"file": rel_path, **scenario_dict})

        # Write detailed scenario information to CSV
        if scenario_infos:
            csv_file = os.path.join(input_dir, "generated_files.csv")
            var_names = sorted({k for d in scenario_infos for k in d.keys() if k != "file"})
            with open(csv_file, "w", encoding="utf-8", newline="") as cf:
                cf.write("file," + ",".join(var_names) + "\n")
                for info in scenario_infos:
                    row = [info.get(var, "") for var in var_names]
                    cf.write(",".join([info["file"]] + [str(x) for x in row]) + "\n")
            print(f"Detailed scenario info written to {csv_file}")

        # Write detailed scenario information to CSV
        if scenario_infos:
            csv_file = os.path.join(input_dir, "generated_files.csv")
            var_names = sorted({k for d in scenario_infos for k in d.keys() if k != "file"})
            with open(csv_file, "w", encoding="utf-8", newline="") as cf:
                cf.write("file," + ",".join(var_names) + "\n")
                for info in scenario_infos:
                    row = [info.get(var, "") for var in var_names]
                    cf.write(",".join([info["file"]] + [str(x) for x in row]) + "\n")
            print(f"Detailed scenario info written to {csv_file}")

    # --------------------------------------------------------------------------
    # Méthodes "privées"
    # --------------------------------------------------------------------------

    def _load_jdd(self, file_path):
        """Charge le fichier JDD en texte brut."""
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()

    def _detect_variables(self, text):
        """Détecte $(var~...) et $var."""
        pattern_def = re.compile(r'\$\(\s*([A-Za-z0-9_]+)\s*~\s*([^)]*)\)')
        vars_def = set(match.group(1).strip() for match in pattern_def.finditer(text))

        pattern_var = re.compile(r'\$(?!\()([A-Za-z0-9_]+)')
        vars_used = set(match.group(1).strip() for match in pattern_var.finditer(text))

        return vars_def.union(vars_used)

    def _fix_dollar_vars(self, expr):
        """Remplace $var par var, pour rendre l'expression valide en R."""
        return re.sub(r'\$([A-Za-z0-9_]+)', r'\1', expr)

    def _process_multiline_r_code(self, text):
        """
        Regroupe les lignes commençant par "*@:" en blocs, remplace $var par var,
        exécute le bloc dans R, et recopie le reste.
        """
        lines = text.splitlines()
        output_lines = []
        current_block = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("*@:"):
                code_part = stripped.replace("*@:", "", 1).strip()
                code_part_fixed = self._fix_dollar_vars(code_part)
                current_block.append(code_part_fixed)
                output_lines.append(line)  # recopie la ligne d'origine
            else:
                if current_block:
                    block_str = "\n".join(current_block)
                    try:
                        robjects.r(block_str)
                    except Exception as e:
                        output_lines.append(f"Erreur R: {e}")
                    current_block = []
                output_lines.append(line)

        if current_block:
            block_str = "\n".join(current_block)
            try:
                robjects.r(block_str)
            except Exception as e:
                output_lines.append(f"Erreur R: {e}")

        return "\n".join(output_lines)

    def _fallback_to_python_format(self, fallback_str):
        """
        Interprète fallback_str comme ex.
          "0"         => .0f  (format entier)
          "0.00"       => .2f  (2 décimales en notation fixe)
          "0.0000"     => .4f  (4 décimales en notation fixe)
          "0.0000E00"  => .4E  (4 décimales en notation scientifique)
        """
        if fallback_str == "0":
            return ".0f"
        m_decimal = re.match(r'^0\.(0+)$', fallback_str)
        if m_decimal:
            count_zero = len(m_decimal.group(1))
            return f".{count_zero}f"
    
        m_scient = re.match(r'^0\.(0+)E00$', fallback_str)
        if m_scient:
            count_zero = len(m_scient.group(1))
            return f".{count_zero}E"
    
        return ".5E"

    def _parse_and_replace_at_braces_format(self, text):
        """
        Gère @{ code | fallback }, ex. @{Pu240($r0)|0.00}
        - Évalue le code en R
        - Formate en .2f si fallback=0.00
        - En cas d'erreur, renvoie fallback tel quel
        """
        pattern = re.compile(r'@\{([^|]+)\|([^}]+)\}')

        def repl(match):
            code_part = match.group(1).strip()
            fallback_part = match.group(2).strip()
            code_part_fixed = self._fix_dollar_vars(code_part)
            pyfmt = self._fallback_to_python_format(fallback_part)

            try:
                result = robjects.r(code_part_fixed)
                if len(result) == 1:
                    val = float(result[0])
                    return format(val, pyfmt)
                else:
                    arr = [float(x) for x in result]
                    return " ".join(format(x, pyfmt) for x in arr)
            except Exception:
                return fallback_part

        return pattern.sub(repl, text)

# --------------------------------------------------------------------------
# Exemple d'utilisation interne (sans fichier externe)
# --------------------------------------------------------------------------
if __name__ == "__main__":
    f = fz()

    jdd_text = """\
* Exemple de JDD paramétré
* Variables :
*          r0 = @{$r0|0.0000}
*          r1 = @{$r1|0.0000}
*          r2 = @{$r2|0.0000}
*          Pu240_pc = @{Pu240($r0)|0.00}
*          Pu241_pc = @{Pu241($r0, $r1)|0.00}
*          Pu242_pc = @{Pu242($r0,$r1,$r2)|0.00}
*          Pu239_pc = @{Pu239($r0,$r1,$r2)|0.00}

*@: Pu240 <- function(r0){r0*100}
*@: Pu241 <- function(r0, r1){(r0*r1)*100}
*@: Pu242 <- function(r0, r1, r2){(r0*r1*r2)*100}
*@: Pu239 <- function(r0, r1, r2){100 - r0*(1+r1*(1+r2))*100}
"""

    # Exemple sans group_variables (produit cartésien complet)
    input_variables_full = {
        "H_X": [10, 100],
        "r0": [0.17000, 0.1800],
        "r1": [0.64706, 0.6500],
        "r2": [0.09091, 0.1000],
    }
    f.CompileInput(input_file="Pumet2.pij", input_variables=input_variables_full, use_dirs=True)

    # Exemple avec group_variables (r0, r1, r2 liés)
    input_variables_grouped = {
        "H_X": [10, 100],
        "r0": [0.17000, 0.1800],
        "r1": [0.64706, 0.6500],
        "r2": [0.09091, 0.1000],
    }
    f.CompileInput(input_file="Pumet2.pij",
                   input_variables=input_variables_grouped,
                   group_variables=["r0", "r1", "r2"],
                   use_dirs=True)
