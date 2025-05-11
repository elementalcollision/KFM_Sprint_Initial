## KFM Verifier CLI (`kfm-verifier`)

The KFM Verifier CLI is a tool designed to automate the verification checklist for end-to-end (E2E) test runs. It analyzes various aspects of a test run based on inputs like commit and branch information, and can use a configuration file for more detailed control.

### Usage

The CLI is invoked as `python src/cli/kfm_verifier_cli.py [options]`.

```bash
python src/cli/kfm_verifier_cli.py --commit <commit_sha> --branch <branch_name> --report-output <path_to_report.json> [other_options]
```

### Arguments

**Required Arguments:**

*   `--commit SHA`
    *   The full commit SHA of the code version being verified.
    *   Example: `--commit a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0`
*   `--branch BRANCH_NAME`
    *   The name of the branch associated with the commit being verified.
    *   Example: `--branch feature/my-new-feature`
*   `--report-output REPORT_FILEPATH`
    *   The file path where the structured verification report (in JSON format) will be saved.
    *   The directory will be created if it doesn't exist.
    *   Example: `--report-output E2E_run_123/verification_report.json`

**Optional Arguments:**

*   `--config CONFIG_FILEPATH`
    *   Path to a YAML configuration file for the verifier. This file can define specific thresholds, checks to enable/disable, or other parameters for the verification engine.
    *   Example: `--config .verifier/prod_config.yaml`
*   `--verification-level {basic,standard,detailed}`
    *   Specifies the depth and breadth of verification checks to perform.
    *   Choices:
        *   `basic`: Performs only essential, high-level checks.
        *   `standard`: Performs a comprehensive set of standard checks. (Default)
        *   `detailed`: Performs all standard checks plus more in-depth, potentially time-consuming analyses.
    *   Default: `standard`
    *   Example: `--verification-level detailed`
*   `--junit-report JUNIT_FILEPATH`
    *   File path where an optional JUnit XML formatted report will be saved. This is useful for integration with CI/CD systems that can display JUnit test results.
    *   The directory will be created if it doesn't exist.
    *   Example: `--junit-report E2E_run_123/junit_results.xml`
*   `--version`
    *   Show the program's version number and exit.
*   `-h, --help`
    *   Show the help message and exit.

### Exit Codes

The CLI will exit with one of the following codes:

*   `0`: Success. Verification completed, and all critical checks passed (or no issues warranting a failure were found according to the verification level and configuration).
*   `1`: Verification Issues. Verification completed, but one or more checks resulted in warnings or non-critical failures. The generated reports should be reviewed.
*   `2`: CLI Error. An error occurred within the CLI tool itself, such as an issue with the (mock) core verification engine or invalid internal state.
*   `3`: Reporting Error. An error occurred while trying to write one of the output report files (JSON or JUnit XML).

### Example Invocations

1.  **Minimal required execution:**
    ```bash
    python src/cli/kfm_verifier_cli.py --commit <sha> --branch main --report-output report.json
    ```

2.  **Detailed verification with a config file and JUnit output:**
    ```bash
    python src/cli/kfm_verifier_cli.py \
        --commit <sha> \
        --branch feature/new-feature \
        --report-output logs/run_X/verification_report.json \
        --config .verifier-config/detailed.yaml \
        --verification-level detailed \
        --junit-report logs/run_X/junit_report.xml
    ``` 