#title: Random Sampling Algorithm
#author: Test
#type: sampling
#options: nvalues=10;seed=42

import random

class Randomsampling:
    """Random sampling algorithm for design of experiments"""

    def __init__(self, **options):
        self.nvalues = int(options.get('nvalues', 10))
        seed = options.get('seed', None)
        if seed is not None:
            random.seed(int(seed))

    def get_initial_design(self, input_vars, output_vars):
        samples = []
        for i in range(self.nvalues):
            sample = {}
            for var_name, (min_val, max_val) in input_vars.items():
                sample[var_name] = random.uniform(min_val, max_val)
            samples.append(sample)
        return samples

    def get_next_design(self, previous_input_vars, previous_output_values):
        return []  # One-shot algorithm

    def get_analysis(self, input_vars, output_values):
        valid_results = [(inp, out) for inp, out in zip(input_vars, output_values)
                        if out is not None]

        if not valid_results:
            return {'text': 'No valid results', 'data': {'samples': len(input_vars), 'valid_samples': 0}}

        best_input, best_output = min(valid_results, key=lambda x: x[1])
        worst_input, worst_output = max(valid_results, key=lambda x: x[1])
        valid_outputs = [out for out in output_values if out is not None]
        mean_output = sum(valid_outputs) / len(valid_outputs)

        result_text = f"""Random Sampling Results:
  Total samples: {len(input_vars)}
  Valid samples: {len(valid_results)}
  Best output: {best_output:.6g}
  Best input: {best_input}
  Worst output: {worst_output:.6g}
  Mean output: {mean_output:.6g}
"""

        return {
            'text': result_text,
            'data': {
                'samples': len(input_vars),
                'valid_samples': len(valid_results),
                'best_output': best_output,
                'best_input': best_input,
                'worst_output': worst_output,
                'mean_output': mean_output,
            }
        }
