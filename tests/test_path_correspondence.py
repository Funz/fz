#!/usr/bin/env python3
"""
Test that path field corresponds exactly with variable values and outputs
"""
import os
import tempfile
from pathlib import Path
from fz import fzr, fzo


def test_path_pressure_correspondence():
    """Verify path and pressure values match exactly between fzr and fzo"""

    with tempfile.TemporaryDirectory() as temp_dir:
        original_cwd = os.getcwd()

        try:
            os.chdir(temp_dir)

            # Create input.txt with variables
            with open("input.txt", "w") as f:
                f.write("# Perfect Gas Calculation Input\n")
                f.write("Temperature_Celsius = $(T_celsius)\n")
                f.write("Volume_Liters = $(V_L)\n")
                f.write("Amount_Moles = $(n_mol)\n")

            # Create simple calculator script
            with open("calc.py", "w") as f:
                f.write("#!/usr/bin/env python3\n")
                f.write("import re\n")
                f.write("with open('input.txt') as f:\n")
                f.write("    content = f.read()\n")
                f.write(r"T_celsius = float(re.search(r'Temperature_Celsius = ([\d.]+)', content).group(1))" + "\n")
                f.write(r"V_L = float(re.search(r'Volume_Liters = ([\d.]+)', content).group(1))" + "\n")
                f.write(r"n_mol = float(re.search(r'Amount_Moles = ([\d.]+)', content).group(1))" + "\n")
                f.write("R = 0.08314\n")
                f.write("T_kelvin = T_celsius + 273.15\n")
                f.write("pressure = n_mol * R * T_kelvin / V_L\n")
                f.write("with open('output.txt', 'w') as out:\n")
                f.write("    out.write(f'pressure = {pressure:.4f} bar\\n')\n")

            os.chmod("calc.py", 0o755)

            # Run fzr
            fzr_result = fzr(
                "input.txt",
                {
                    "varprefix": "$",
                    "delim": "()",
                    "commentline": "#",
                    "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
                },
                {
                    "T_celsius": [20, 25, 30],
                    "V_L": [1.0, 1.5],
                    "n_mol": [0.5, 1.0]
                },
                engine="python",
                calculators=["python calc.py"],
                resultsdir="results"
            )

            # Run fzo
            fzo_result = fzo(
                "results",
                {
                    "varprefix": "$",
                    "delim": "()",
                    "commentline": "#",
                    "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
                }
            )

            print("\n=== Checking fzr/fzo correspondence ===")
            print(f"Total cases: {len(fzr_result['path'])}")

            # Check each case
            all_match = True
            for i in range(len(fzr_result['path'])):
                fzr_path = fzr_result['path'][i]
                fzr_T = fzr_result['T_celsius'][i] if hasattr(fzr_result['T_celsius'], '__getitem__') else fzr_result['T_celsius'].iloc[i]
                fzr_V = fzr_result['V_L'][i] if hasattr(fzr_result['V_L'], '__getitem__') else fzr_result['V_L'].iloc[i]
                fzr_n = fzr_result['n_mol'][i] if hasattr(fzr_result['n_mol'], '__getitem__') else fzr_result['n_mol'].iloc[i]
                fzr_p = fzr_result['pressure'][i] if hasattr(fzr_result['pressure'], '__getitem__') else fzr_result['pressure'].iloc[i]

                fzo_path = fzo_result['path'][i] if hasattr(fzo_result['path'], '__getitem__') else fzo_result['path'].iloc[i]
                fzo_T = fzo_result['T_celsius'][i] if hasattr(fzo_result['T_celsius'], '__getitem__') else fzo_result['T_celsius'].iloc[i]
                fzo_V = fzo_result['V_L'][i] if hasattr(fzo_result['V_L'], '__getitem__') else fzo_result['V_L'].iloc[i]
                fzo_n = fzo_result['n_mol'][i] if hasattr(fzo_result['n_mol'], '__getitem__') else fzo_result['n_mol'].iloc[i]
                fzo_p = fzo_result['pressure'][i] if hasattr(fzo_result['pressure'], '__getitem__') else fzo_result['pressure'].iloc[i]

                # Check path matches
                if fzr_path != fzo_path:
                    print(f"❌ Case {i}: Path mismatch - fzr: {fzr_path}, fzo: {fzo_path}")
                    all_match = False

                # Check variables match
                if fzr_T != fzo_T or fzr_V != fzo_V or fzr_n != fzo_n:
                    print(f"❌ Case {i}: Variable mismatch - fzr: T={fzr_T}, V={fzr_V}, n={fzr_n}, fzo: T={fzo_T}, V={fzo_V}, n={fzo_n}")
                    all_match = False

                # Check pressure matches
                if abs(float(fzr_p) - float(fzo_p)) > 0.001:
                    print(f"❌ Case {i}: Pressure mismatch - fzr: {fzr_p}, fzo: {fzo_p}")
                    all_match = False

                # Verify path name matches variable values
                expected_path = f"T_celsius={fzr_T},V_L={fzr_V},n_mol={fzr_n}"
                if fzr_path != expected_path:
                    print(f"⚠️  Case {i}: Path '{fzr_path}' doesn't match expected '{expected_path}'")

                print(f"✅ Case {i}: path={fzr_path}, T={fzr_T}, V={fzr_V}, n={fzr_n}, pressure={fzr_p}")

            assert all_match, "Some cases had mismatches between fzr and fzo"
            print("\n✅ All path and pressure values correspond exactly between fzr and fzo!")

        finally:
            os.chdir(original_cwd)


if __name__ == "__main__":
    test_path_pressure_correspondence()
