# Gates, structured evidence, and portability

Python 3.9+ is required, with no third-party dependencies. Use `scripts/gate.sh` on Bash, `scripts/gate.ps1` on PowerShell, or `python scripts/gate.py` on any supported platform. Native argv gates need no shell; legacy shell strings need Bash (Git Bash on Windows; the WSL `System32\bash.exe` launcher is skipped in favor of Git's Bash when available). Missing required tools are `MISSING_TOOL`; explicitly optional missing tools are `SKIP` and remain unverified. A timeout is `TIMEOUT`, not a test failure. The default per-gate timeout is 600 seconds; use `--timeout` or per-gate JSON values.

Discovery recurses into nested projects, omits dependency/build caches, honors ancestor package-manager pins and lockfiles, and keeps each project working directory. .NET commands explicitly target discovered solution/project files. Projects referenced by a selected solution are not duplicated. A structured `dotnet test` gate is attached only to test projects (`Microsoft.NET.Test.Sdk`, `IsTestProject`, or `MSTest.Sdk`) or solutions containing one; application-only projects get a build gate. Path-like argv commands such as `./scripts/check` resolve against the gate's `cwd`. Select components with repeated `--project path/to/project` arguments. Monorepos with orchestration scripts should use an explicit configuration to avoid duplicate workspace runs.

Configuration precedence is selected `--project` targets, `.quality-pass/gates.json`, `.quality-pass/gates`, then discovery. Legacy `gates` has one Bash command per line; blank lines and full-line comments are ignored, while quoting and inline comments are handled by Bash.

Example portable JSON configuration:

```json
{
  "gates": [
    {
      "id": "api-tests",
      "cwd": "services/api",
      "command": ["pytest", "-q", "--junitxml={report}"],
      "kind": "test",
      "timeout": 300,
      "report": {"format": "junit", "path": "{report}"}
    },
    {
      "id": "web-tests",
      "cwd": "web",
      "command": ["npm", "test", "--", "--json", "--outputFile={report}"],
      "kind": "test",
      "report": {"format": "jest", "path": "{report}"}
    }
  ]
}
```

Use Jest flags only when the project's runner supports them. Supported report formats are JUnit XML, .NET TRX, Jest JSON, and Go `test -json`. `{report}` and `{report_dir}` are unique to this gate run; `{log}` is its captured output, and `{python}` is the interpreter running the gate. Shell commands must quote path placeholders when paths may contain spaces. Native argv avoids that quoting requirement. Reports must reside under the selected repository and must have been produced by the current command. Malformed, missing, duplicate-identity, or stale reports cannot establish equivalence. Structured test gates with zero tests are `NO_TESTS`.

## Baselines

`--baseline` saves `.quality-pass/baseline.json` and a human-readable `baseline.txt`. The JSON includes HEAD, source fingerprint, complete gate configuration/hash, test counts, identities, failure-detail hashes, and log paths. Each invocation saves a unique `logs/<run>/results.json` and `latest.json`. Old text-only baselines remain readable but report **failure equivalence unknown**.

Comparison requires unchanged gate configuration. New/changed failure identities or assertion details are regressions. Fewer executed tests are a regression even if the test command turns green. An unchanged red gate is only equivalent when both current and baseline reports identify failures and their details with a normal test-failure exit code. Otherwise report **failure equivalence unknown**. Do not infer identity from matching command names, exit codes, or red status. Counts include total, passed, failed, and skipped; reports that do not expose a category cannot prove it ran.

The runner continues to exit 1 for failing required gates, including identified pre-existing failures. It never turns an existing red into a passing check. Exit 2 means invalid configuration/no gates, and 130 means interrupted. Optional skips do not turn the entire environment into a fully verified workflow. New regressions, missing tools, timeouts, or unknown equivalence block a claim of no worse than baseline.

Existing baselines are not silently replaced. Use `--baseline --replace-baseline` only after explicitly reviewing why the baseline/configuration or intentional test-count reduction changed. Preserve the previous run result and explain the change in the report. Never refresh a baseline to conceal a regression.
