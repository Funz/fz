#!/usr/bin/env python3
"""
Test perfect gas calculation with fzr - Fixed version
"""
import os
from pathlib import Path
from fz import fzr

def test_perfect_gas():
    """Test perfect gas calculation with proper setup"""

    # Use temp directory from conftest fixture
    temp_dir = Path.cwd()
    print(f"Testing in: {temp_dir}")

    # Create input.txt with variables
    with open("input.txt", "w") as f:
        f.write("# Perfect Gas Calculation Input\n")
        f.write("Temperature_Celsius = $(T_celsius)\n")
        f.write("Volume_Liters = $(V_L)\n")
        f.write("Amount_Moles = $(n_mol)\n")
        f.write("Gas_Constant_R = 0.08314  # L⋅bar/(mol⋅K)\n")

    # Create the calculator script
    with open("PerfectGazPressure.sh", "w") as f:
        f.write("#!/bin/bash\n")
        f.write("# Perfect Gas Pressure Calculator\n")
        f.write("echo 'Calculating perfect gas pressure...'\n")
        f.write("\n")
        f.write("# Read variables from input.txt\n")
        f.write("T_CELSIUS=$(grep 'Temperature_Celsius =' input.txt | cut -d'=' -f2 | tr -d ' ')\n")
        f.write("V_L=$(grep 'Volume_Liters =' input.txt | cut -d'=' -f2 | tr -d ' ')\n")
        f.write("N_MOL=$(grep 'Amount_Moles =' input.txt | cut -d'=' -f2 | tr -d ' ')\n")
        f.write("R=0.08314\n")
        f.write("\n")
        f.write("# Convert temperature to Kelvin\n")
        f.write("T_KELVIN=$(python3 -c \"print($T_CELSIUS + 273.15)\")\n")
        f.write("\n")
        f.write("# Calculate pressure using ideal gas law: P = nRT/V\n")
        f.write("if [ \"$N_MOL\" != \"0\" ] && [ \"$V_L\" != \"0\" ]; then\n")
        f.write("    PRESSURE=$(python3 -c \"print(round($N_MOL * $R * $T_KELVIN / $V_L, 4))\")\n")
        f.write("    echo \"pressure = $PRESSURE bar\" > output.txt\n")
        f.write("    echo \"Calculated pressure: $PRESSURE bar\"\n")
        f.write("else\n")
        f.write("    echo \"pressure = 0.0 bar\" > output.txt\n")
        f.write("    echo \"Warning: Zero moles or volume, pressure set to 0\"\n")
        f.write("fi\n")
        f.write("\n")
        f.write("echo \"Calculation completed\"\n")

    # Make script executable
    os.chmod("PerfectGazPressure.sh", 0o755)

    print("Created test files:")
    print("- input.txt")
    print("- PerfectGazPressure.sh")

    # Fixed fzr call
    print("\n🚀 Running fzr with fixed configuration...")
    result = fzr(
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
                    "n_mol": [1.0, 0.5]  # Fixed: Use 0.5 instead of 0 to avoid division by zero
                },
                
                calculators=["sh://bash ./PerfectGazPressure.sh"],  # Fixed: Single calculator, proper path
                results_dir="results"
            )

    print("\n📊 Results:")
            print(f"Cases executed: {len(result['T_celsius'])}")
            print(f"Statuses: {set(result['status'])}")
            print(f"Sample pressures: {result['pressure'][:5]}...")  # Show first 5 results

    # Verify results
    success_count = sum(1 for status in result['status'] if status == 'done')
    total_count = len(result['status'])

    print(f"\n✅ Success: {success_count}/{total_count} cases completed successfully")

    if success_count == total_count:
        print("🎉 All test cases passed!")
        return True
    else:
        print("⚠️  Some test cases failed")
        return False

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_perfect_gas()