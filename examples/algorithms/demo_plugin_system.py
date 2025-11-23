#!/usr/bin/env python3
"""
Demonstration of the algorithm plugin system

This script demonstrates:
1. Creating an algorithm plugin in .fz/algorithms/
2. Loading the algorithm by name (not path)
3. Using the plugin with fzd
"""

import sys
from pathlib import Path
import tempfile
import shutil

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def demo_plugin_system():
    """Demonstrate the algorithm plugin system"""

    print("=" * 70)
    print("Algorithm Plugin System Demo")
    print("=" * 70)

    # Create temporary directory for demo
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        print(f"\nWorking in: {tmpdir}\n")

        # Step 1: Create .fz/algorithms/ directory
        print("Step 1: Creating .fz/algorithms/ directory")
        algo_dir = tmpdir / ".fz" / "algorithms"
        algo_dir.mkdir(parents=True)
        print(f"  ✓ Created: {algo_dir}\n")

        # Step 2: Create a simple algorithm plugin
        print("Step 2: Creating algorithm plugin 'quicksampler.py'")
        plugin_file = algo_dir / "quicksampler.py"
        plugin_file.write_text("""
class QuickSampler:
    '''Simple random sampler with fixed number of samples'''

    def __init__(self, **options):
        self.n_samples = options.get("n_samples", 5)
        self.iteration = 0

    def get_initial_design(self, input_vars, output_vars):
        import random
        random.seed(42)

        samples = []
        for _ in range(self.n_samples):
            sample = {}
            for var, (min_val, max_val) in input_vars.items():
                sample[var] = random.uniform(min_val, max_val)
            samples.append(sample)

        return samples

    def get_next_design(self, X, Y):
        # One-shot sampling - return empty list (finished)
        return []

    def get_analysis(self, X, Y):
        valid_Y = [y for y in Y if y is not None]
        if not valid_Y:
            return {"text": "No valid results", "data": {}}

        mean_val = sum(valid_Y) / len(valid_Y)
        min_val = min(valid_Y)
        max_val = max(valid_Y)

        return {
            "text": f"Sampled {len(valid_Y)} points\\nMean: {mean_val:.2f}\\nRange: [{min_val:.2f}, {max_val:.2f}]",
            "data": {
                "mean": mean_val,
                "min": min_val,
                "max": max_val,
                "n_samples": len(valid_Y)
            }
        }
""")
        print(f"  ✓ Created: {plugin_file.name}\n")

        # Step 3: Load algorithm by name (plugin mode)
        print("Step 3: Loading algorithm by name 'quicksampler'")
        print("  Note: No .py extension, no path - just the name!")

        import os
        os.chdir(tmpdir)  # Change to tmpdir so .fz/algorithms/ is found

        from fz.algorithms import load_algorithm

        algo = load_algorithm("quicksampler", n_samples=3)
        print(f"  ✓ Loaded algorithm: {type(algo).__name__}\n")

        # Step 4: Test the algorithm
        print("Step 4: Testing the algorithm")
        input_vars = {"x": (0.0, 10.0), "y": (-5.0, 5.0)}
        output_vars = ["result"]

        design = algo.get_initial_design(input_vars, output_vars)
        print(f"  ✓ Generated {len(design)} samples:")
        for i, point in enumerate(design):
            print(f"    Sample {i+1}: x={point['x']:.2f}, y={point['y']:.2f}")

        # Simulate outputs
        outputs = [point['x']**2 + point['y']**2 for point in design]
        print(f"\n  ✓ Simulated outputs (x² + y²):")
        for i, val in enumerate(outputs):
            print(f"    Output {i+1}: {val:.2f}")

        # Get analysis
        analysis = algo.get_analysis(design, outputs)
        print(f"\n  ✓ Analysis:")
        for line in analysis['text'].split('\n'):
            print(f"    {line}")

        print("\n" + "=" * 70)
        print("✓ Plugin System Demo Complete!")
        print("=" * 70)

        print("\nKey Takeaways:")
        print("  • Algorithms stored in .fz/algorithms/")
        print("  • Load by name: load_algorithm('quicksampler')")
        print("  • Project-level: .fz/algorithms/ (current directory)")
        print("  • Global: ~/.fz/algorithms/ (user home)")
        print("  • Priority: Project-level overrides global")
        print("  • Works with both .py and .R files")
        print()


def demo_comparison():
    """Show side-by-side comparison of plugin vs direct path"""

    print("\n" + "=" * 70)
    print("Plugin vs Direct Path Comparison")
    print("=" * 70)

    print("\n📁 Plugin Mode (Recommended):")
    print("  • Place file: .fz/algorithms/myalgo.py")
    print("  • Load: load_algorithm('myalgo')")
    print("  • Benefits: Organized, shareable, clean code")
    print()

    print("📄 Direct Path Mode (Still works):")
    print("  • Place file: anywhere/myalgo.py")
    print("  • Load: load_algorithm('anywhere/myalgo.py')")
    print("  • Benefits: Backward compatible, explicit")
    print()

    print("🎯 Use plugin mode for:")
    print("  • Team projects (commit .fz/algorithms/ to git)")
    print("  • Personal library (~/.fz/algorithms/)")
    print("  • Clean, maintainable code")
    print()

    print("🎯 Use direct path for:")
    print("  • Quick experiments")
    print("  • External algorithms")
    print("  • Legacy code")
    print()


if __name__ == "__main__":
    demo_plugin_system()
    demo_comparison()
