
#title: Estimate mean with given confidence interval range using Monte Carlo
#author: Yann Richet
#type: sampling
#options: batch_sample_size=10;max_iterations=100;confidence=0.9;target_confidence_range=1.0;seed=42
#require: base64enc

# Constructor for MonteCarlo_Uniform S3 class
MonteCarlo_Uniform <- function(...) {
  # Get options from ... arguments
  opts <- list(...)

  # Create object with initial state
  # Use an environment for mutable state (idiomatic S3 pattern)
  state <- new.env(parent = emptyenv())
  state$n_samples <- 0
  state$variables <- list()

  obj <- list(
    options = list(
      batch_sample_size = as.integer(
        ifelse(is.null(opts$batch_sample_size), 10, opts$batch_sample_size)
      ),
      max_iterations = as.integer(
        ifelse(is.null(opts$max_iterations), 100, opts$max_iterations)
      ),
      confidence = as.numeric(
        ifelse(is.null(opts$confidence), 0.9, opts$confidence)
      ),
      target_confidence_range = as.numeric(
        ifelse(is.null(opts$target_confidence_range), 1.0, opts$target_confidence_range)
      )
    ),
    state = state  # Environment for mutable state
  )

  # Set random seed
  seed <- ifelse(is.null(opts$seed), 42, opts$seed)
  set.seed(as.integer(seed))

  # Set S3 class
  class(obj) <- "MonteCarlo_Uniform"

  return(obj)
}

# Generic function definitions (if not already defined)
if (!exists("get_initial_design")) {
  get_initial_design <- function(obj, ...) UseMethod("get_initial_design")
}

if (!exists("get_next_design")) {
  get_next_design <- function(obj, ...) UseMethod("get_next_design")
}

if (!exists("get_analysis")) {
  get_analysis <- function(obj, ...) UseMethod("get_analysis")
}

if (!exists("get_analysis_tmp")) {
  get_analysis_tmp <- function(obj, ...) UseMethod("get_analysis_tmp")
}

# Method: get_initial_design
get_initial_design.MonteCarlo_Uniform <- function(obj, input_variables, output_variables) {
  # Store variable bounds in mutable state
  # input_variables is a named list: list(var1 = c(min, max), var2 = c(min, max))
  for (v in names(input_variables)) {
    bounds <- input_variables[[v]]
    if (!is.numeric(bounds) || length(bounds) != 2) {
      stop(paste("Input variable", v, "must have c(min, max) bounds for MonteCarlo_Uniform sampling"))
    }
    obj$state$variables[[v]] <- bounds
  }

  return(generate_samples(obj, obj$options$batch_sample_size))
}

# Method: get_next_design
get_next_design.MonteCarlo_Uniform <- function(obj, X, Y) {
  # Check max iterations
  if (obj$state$n_samples >= obj$options$max_iterations * obj$options$batch_sample_size) {
    return(list())  # Empty list signals finished
  }

  # Filter out NULL/NA values
  Y_valid <- Y[!sapply(Y, is.null) & !is.na(Y)]
  Y_valid <- unlist(Y_valid)

  if (length(Y_valid) < 2) {
    return(generate_samples(obj, obj$options$batch_sample_size))
  }

  # Calculate confidence interval
  mean_y <- mean(Y_valid)
  n <- length(Y_valid)
  se <- sd(Y_valid) / sqrt(n)

  # t-distribution confidence interval
  alpha <- 1 - obj$options$confidence
  t_critical <- qt(1 - alpha/2, df = n - 1)
  conf_int_lower <- mean_y - t_critical * se
  conf_int_upper <- mean_y + t_critical * se
  conf_range <- conf_int_upper - conf_int_lower

  # Stop if confidence interval is narrow enough
  if (conf_range <= obj$options$target_confidence_range) {
    return(list())  # Finished
  }

  # Generate more samples
  return(generate_samples(obj, obj$options$batch_sample_size))
}

# Method: get_analysis
get_analysis.MonteCarlo_Uniform <- function(obj, X, Y) {
  analysis_dict <- list(text = "", data = list())

  # Filter out NULL/NA values
  Y_valid <- Y[!sapply(Y, is.null) & !is.na(Y)]
  Y_valid <- unlist(Y_valid)

  if (length(Y_valid) < 2) {
    analysis_dict$text <- "Not enough valid results to analyze statistics"
    analysis_dict$data <- list(valid_samples = length(Y_valid))
    return(analysis_dict)
  }

  # Calculate statistics
  mean_y <- mean(Y_valid)
  std_y <- sd(Y_valid)
  n <- length(Y_valid)
  se <- std_y / sqrt(n)

  # t-distribution confidence interval
  alpha <- 1 - obj$options$confidence
  t_critical <- qt(1 - alpha/2, df = n - 1)
  conf_int_lower <- mean_y - t_critical * se
  conf_int_upper <- mean_y + t_critical * se

  # Store data
  analysis_dict$data <- list(
    mean = mean_y,
    std = std_y,
    confidence_interval = c(conf_int_lower, conf_int_upper),
    n_samples = length(Y_valid),
    min = min(Y_valid),
    max = max(Y_valid)
  )

  # Create text summary
  analysis_dict$text <- sprintf(
"Monte Carlo Sampling Results:
  Valid samples: %d
  Mean: %.6f
  Std: %.6f
  %.0f%% confidence interval: [%.6f, %.6f]
  Range: [%.6f, %.6f]
",
    length(Y_valid),
    mean_y,
    std_y,
    obj$options$confidence * 100,
    conf_int_lower,
    conf_int_upper,
    min(Y_valid),
    max(Y_valid)
  )

  # Try to create HTML with histogram
  tryCatch({
    # Create histogram plot
    png_file <- tempfile(fileext = ".png")
    png(png_file, width = 800, height = 600)

    hist(Y_valid, breaks = 20, freq = FALSE,
         col = rgb(0, 1, 0, 0.6),
         border = "black",
         main = "Output Distribution",
         xlab = "Output Value",
         ylab = "Density")
    grid(col = rgb(0, 0, 0, 0.3))

    # Add mean line
    abline(v = mean_y, col = "red", lwd = 2, lty = 2)
    legend("topright",
           legend = sprintf("Mean: %.3f", mean_y),
           col = "red", lty = 2, lwd = 2)

    dev.off()

    # Convert to base64
    if (requireNamespace("base64enc", quietly = TRUE)) {
      img_base64 <- base64enc::base64encode(png_file)

      html_output <- sprintf(
'<div>
  <p><strong>Estimated mean:</strong> %.6f</p>
  <p><strong>%.0f%% confidence interval:</strong> [%.6f, %.6f]</p>
  <img src="data:image/png;base64,%s" alt="Histogram" style="max-width:800px;"/>
</div>',
        mean_y,
        obj$options$confidence * 100,
        conf_int_lower,
        conf_int_upper,
        img_base64
      )
      analysis_dict$html <- html_output
    }

    # Clean up temp file
    unlink(png_file)
  }, error = function(e) {
    # If plotting fails, just skip it
  })

  return(analysis_dict)
}

# Method: get_analysis_tmp
get_analysis_tmp.MonteCarlo_Uniform <- function(obj, X, Y) {
  # Filter out NULL/NA values
  Y_valid <- Y[!sapply(Y, is.null) & !is.na(Y)]
  Y_valid <- unlist(Y_valid)

  if (length(Y_valid) < 2) {
    return(list(
      text = sprintf("  Progress: %d valid sample(s) collected", length(Y_valid)),
      data = list(valid_samples = length(Y_valid))
    ))
  }

  # Calculate statistics
  mean_y <- mean(Y_valid)
  std_y <- sd(Y_valid)
  n <- length(Y_valid)
  se <- std_y / sqrt(n)

  # t-distribution confidence interval
  alpha <- 1 - obj$options$confidence
  t_critical <- qt(1 - alpha/2, df = n - 1)
  conf_int_lower <- mean_y - t_critical * se
  conf_int_upper <- mean_y + t_critical * se
  conf_range <- conf_int_upper - conf_int_lower

  return(list(
    text = sprintf(
      "  Progress: %d samples, mean=%.6f, %.0f%% CI range=%.6f",
      length(Y_valid),
      mean_y,
      obj$options$confidence * 100,
      conf_range
    ),
    data = list(
      n_samples = length(Y_valid),
      mean = mean_y,
      std = std_y,
      confidence_range = conf_range
    )
  ))
}

# Helper function: generate_samples (not a method, internal use only)
generate_samples <- function(obj, n) {
  samples <- list()

  for (i in 1:n) {
    sample <- list()
    for (v in names(obj$state$variables)) {
      bounds <- obj$state$variables[[v]]
      sample[[v]] <- runif(1, min = bounds[1], max = bounds[2])
    }
    samples[[i]] <- sample
  }

  # Update n_samples in state environment (mutable)
  obj$state$n_samples <- obj$state$n_samples + n

  return(samples)
}
