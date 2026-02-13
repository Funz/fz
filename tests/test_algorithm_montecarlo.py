#title: Estimate mean with given confidence interval range using Monte Carlo
#author: Yann Richet
#type: sampling
#options: batch_sample_size=10;max_iterations=100;confidence=0.9;target_confidence_range=1.0;seed=42
#require: numpy;scipy;matplotlib;base64

class MonteCarlo_Uniform:

    options = {}
    samples = []
    n_samples = 0
    variables = {}

    def __init__(self, **options):
        # parse (numeric) options
        self.options["batch_sample_size"] = int(options.get("batch_sample_size", 10))
        self.options["max_iterations"] = int(options.get("max_iterations", 100))
        self.options["confidence"] = float(options.get("confidence", 0.9))
        self.options["target_confidence_range"] = float(options.get("target_confidence_range", 1.0))

        import numpy as np
        from scipy import stats
        np.random.seed(int(options.get("seed", 42)))

    def get_initial_design(self, input_variables, output_variables):
        for v, bounds in input_variables.items():
            # bounds is already a tuple (min, max) from parse_input_vars
            if isinstance(bounds, tuple) and len(bounds) == 2:
                min_val, max_val = bounds
            else:
                # Fallback: parse bounds string if needed : [min;max]
                bounds_str = str(bounds).strip("[]").split(";")
                if len(bounds_str) != 2:
                    raise Exception(f"Input variable {v} must be defined with min and max values for MonteCarlo_Uniform sampling")
                min_val = float(bounds_str[0])
                max_val = float(bounds_str[1])
            self.variables[v] = (min_val, max_val)
        return self._generate_samples(self.options["batch_sample_size"])

    def get_next_design(self, X, Y):
        # check max iterations
        if self.n_samples >= self.options["max_iterations"] * self.options["batch_sample_size"]:
            return []
        # check confidence interval: compute empirical confidence interval (using kernel density) on Y, compare with target_confidence_range
        import numpy as np
        from scipy import stats
        Y_array = np.array([y for y in Y if y is not None])
        if len(Y_array) < 2:
            return self._generate_samples(self.options["batch_sample_size"])
        kde = stats.gaussian_kde(Y_array)
        mean = np.mean(Y_array)
        conf_int = stats.t.interval(self.options["confidence"], len(Y_array)-1, loc=mean, scale=stats.sem(Y_array))
        conf_range = conf_int[1] - conf_int[0]
        if conf_range <= self.options["target_confidence_range"]:
            return []
        # else generate new samples
        return self._generate_samples(self.options["batch_sample_size"])

    def _generate_samples(self, n):
        import numpy as np
        samples = []
        for _ in range(n):
            sample = {}
            for v, (min_val, max_val) in self.variables.items():
                sample[v] = np.random.uniform(min_val, max_val)
            samples.append(sample)
        self.n_samples += n
        return samples

    def get_analysis(self, X, Y):
        analysis_dict = {"text": "", "data": {}}
        html_output = ""
        import numpy as np
        from scipy import stats
        Y_array = np.array([y for y in Y if y is not None])
        if len(Y_array) < 2:
            analysis_dict["text"] = "Not enough valid results to analysis statistics"
            return analysis_dict
        mean = np.mean(Y_array)
        conf_int = stats.t.interval(self.options["confidence"], len(Y_array)-1, loc=mean, scale=stats.sem(Y_array))
        html_output += f"<p>Estimated mean: {mean}</p>"
        html_output += f"<p>{self.options['confidence']*100}% confidence interval: [{conf_int[0]}, {conf_int[1]}]</p>"

        # Store data
        analysis_dict["data"]["mean"] = mean
        analysis_dict["data"]["confidence_interval"] = conf_int
        analysis_dict["data"]["n_samples"] = len(Y_array)

        # Text output
        analysis_dict["text"] = (
            f"Estimated mean: {mean:.6f}\n"
            f"{self.options['confidence']*100}% confidence interval: [{conf_int[0]:.6f}, {conf_int[1]:.6f}]\n"
            f"Number of valid samples: {len(Y_array)}"
        )

        # Try to plot histogram if matplotlib is available
        try:
            import matplotlib.pyplot as plt
            import base64
            from io import BytesIO

            plt.figure()
            plt.hist(Y_array, bins=20, density=True, alpha=0.6, color='g')
            plt.title("Output Y histogram")
            plt.xlabel("Y")
            plt.ylabel("Density")
            plt.grid()

            # base64 in html
            buffered = BytesIO()
            plt.savefig(buffered, format="png")
            plt.close()
            img_str = base64.b64encode(buffered.getvalue()).decode()
            html_output += f'<img src="data:image/png;base64,{img_str}" alt="Histogram"/>'
            analysis_dict["html"] = html_output
        except Exception as e:
            # If plotting fails, just skip it
            pass

        return analysis_dict
