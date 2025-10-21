
#title: Estimate mean with given confidence interval range using Monte Carlo
#author: Yann Richet
#type: sampling
#options: batch_sample_size=10;max_iterations=100;confidence=0.9;target_confidence_range=1.0;seed=42
#require: numpy;scipy;matplotlib

class MonteCarlo_Uniform:
    """Monte Carlo sampling algorithm with adaptive stopping based on confidence interval"""

    def __init__(self, **options):
        """Initialize with algorithm options"""
        self.options = {}
        self.options["batch_sample_size"] = int(options.get("batch_sample_size", 10))
        self.options["max_iterations"] = int(options.get("max_iterations", 100))
        self.options["confidence"] = float(options.get("confidence", 0.9))
        self.options["target_confidence_range"] = float(options.get("target_confidence_range", 1.0))

        self.n_samples = 0
        self.variables = {}

        import numpy as np
        np.random.seed(int(options.get("seed", 42)))

    def get_initial_design(self, input_variables, output_variables):
        """
        Generate initial design

        Args:
            input_variables: Dict[str, Tuple[float, float]] - {var: (min, max)}
            output_variables: List[str] - output variable names
        """
        for v, bounds in input_variables.items():
            # Bounds are already parsed as tuples (min, max)
            if isinstance(bounds, tuple) and len(bounds) == 2:
                self.variables[v] = bounds
            else:
                raise ValueError(
                    f"Input variable {v} must have (min, max) tuple bounds for MonteCarlo_Uniform sampling"
                )
        return self._generate_samples(self.options["batch_sample_size"])
  
    def get_next_design(self, X, Y):
        """
        Generate next design based on convergence criteria

        Args:
            X: List[Dict[str, float]] - previous inputs
            Y: List[float] - previous outputs (may contain None)

        Returns:
            List[Dict[str, float]] - next points, or [] if finished
        """
        # Check max iterations
        if self.n_samples >= self.options["max_iterations"] * self.options["batch_sample_size"]:
            return []

        # Filter out None values
        import numpy as np
        from scipy import stats
        Y_valid = [y for y in Y if y is not None]

        if len(Y_valid) < 2:
            return self._generate_samples(self.options["batch_sample_size"])

        Y_array = np.array(Y_valid)
        mean = np.mean(Y_array)
        conf_int = stats.t.interval(
            self.options["confidence"],
            len(Y_array) - 1,
            loc=mean,
            scale=stats.sem(Y_array)
        )
        conf_range = conf_int[1] - conf_int[0]

        # Stop if confidence interval is narrow enough
        if conf_range <= self.options["target_confidence_range"]:
            return []

        # Generate more samples
        return self._generate_samples(self.options["batch_sample_size"])
      
    def _generate_samples(self, n):
        import numpy as np
        samples = []
        for _ in range(n):
            sample = {}
            for v,(min_val,max_val) in self.variables.items():
                sample[v] = np.random.uniform(min_val, max_val)
            samples.append(sample)
        self.n_samples += n
        return samples
  
    def get_analysis(self, X, Y):
        """
        Display results with statistics and histogram

        Args:
            X: List[Dict[str, float]] - all evaluated inputs
            Y: List[float] - all outputs (may contain None)

        Returns:
            Dict with 'text', 'data', and optionally 'html' keys
        """
        import numpy as np
        from scipy import stats

        display_dict = {"text": "", "data": {}}

        # Filter out None values
        Y_valid = [y for y in Y if y is not None]

        if len(Y_valid) < 2:
            display_dict["text"] = "Not enough valid results to display statistics"
            display_dict["data"] = {"valid_samples": len(Y_valid)}
            return display_dict

        Y_array = np.array(Y_valid)
        mean = np.mean(Y_array)
        std = np.std(Y_array)
        conf_int = stats.t.interval(
            self.options["confidence"],
            len(Y_array) - 1,
            loc=mean,
            scale=stats.sem(Y_array)
        )

        # Store data
        display_dict["data"] = {
            "mean": float(mean),
            "std": float(std),
            "confidence_interval": [float(conf_int[0]), float(conf_int[1])],
            "n_samples": len(Y_valid),
            "min": float(np.min(Y_array)),
            "max": float(np.max(Y_array))
        }

        # Create text summary
        display_dict["text"] = f"""Monte Carlo Sampling Results:
  Valid samples: {len(Y_valid)}
  Mean: {mean:.6f}
  Std: {std:.6f}
  {self.options['confidence']*100:.0f}% confidence interval: [{conf_int[0]:.6f}, {conf_int[1]:.6f}]
  Range: [{np.min(Y_array):.6f}, {np.max(Y_array):.6f}]
"""

        # Try to create HTML with histogram
        try:
            import matplotlib
            matplotlib.use('Agg')  # Non-interactive backend
            import matplotlib.pyplot as plt
            import base64
            from io import BytesIO

            plt.figure(figsize=(8, 6))
            plt.hist(Y_array, bins=20, density=True, alpha=0.6, color='g', edgecolor='black')
            plt.title("Output Distribution")
            plt.xlabel("Output Value")
            plt.ylabel("Density")
            plt.grid(alpha=0.3)

            # Add mean line
            plt.axvline(mean, color='r', linestyle='--', linewidth=2, label=f'Mean: {mean:.3f}')
            plt.legend()

            # Convert to base64
            buffered = BytesIO()
            plt.savefig(buffered, format="png", dpi=100, bbox_inches='tight')
            plt.close()
            img_str = base64.b64encode(buffered.getvalue()).decode()

            html_output = f"""<div>
  <p><strong>Estimated mean:</strong> {mean:.6f}</p>
  <p><strong>{self.options['confidence']*100:.0f}% confidence interval:</strong> [{conf_int[0]:.6f}, {conf_int[1]:.6f}]</p>
  <img src="data:image/png;base64,{img_str}" alt="Histogram" style="max-width:800px;"/>
</div>"""
            display_dict["html"] = html_output
        except Exception as e:
            # If plotting fails, just skip it
            pass

        return display_dict

    def get_analysis_tmp(self, X, Y):
        """
        Display intermediate results at each iteration

        Args:
            X: List[Dict[str, float]] - all evaluated inputs so far
            Y: List[float] - all outputs so far (may contain None)

        Returns:
            Dict with 'text' and 'data' keys
        """
        import numpy as np
        from scipy import stats

        # Filter out None values
        Y_valid = [y for y in Y if y is not None]

        if len(Y_valid) < 2:
            return {
                'text': f"  Progress: {len(Y_valid)} valid sample(s) collected",
                'data': {'valid_samples': len(Y_valid)}
            }

        Y_array = np.array(Y_valid)
        mean = np.mean(Y_array)
        std = np.std(Y_array)
        conf_int = stats.t.interval(
            self.options["confidence"],
            len(Y_array) - 1,
            loc=mean,
            scale=stats.sem(Y_array)
        )
        conf_range = conf_int[1] - conf_int[0]

        return {
            'text': f"  Progress: {len(Y_valid)} samples, "
                   f"mean={mean:.6f}, "
                   f"{self.options['confidence']*100:.0f}% CI range={conf_range:.6f}",
            'data': {
                'n_samples': len(Y_valid),
                'mean': float(mean),
                'std': float(std),
                'confidence_range': float(conf_range)
            }
        }

