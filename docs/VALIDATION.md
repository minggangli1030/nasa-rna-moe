# Validation

Updated November 6, 2026 after source reorganization.

- `python -m pytest -q research/spaceflight/tests research/specialization/tests`: **47 passed** in an isolated environment with a fresh SciPy wheel.
- The 31 retained Python implementation/test files passed syntax checks; the portable training launcher passed shell syntax checks.
- Local Markdown links resolve; common token, private-key, personal-machine-path, email, and IP checks passed.
- Selected implementations have one canonical copy; superseded source variants and compatibility symlinks are omitted from the current portfolio tree.

Expanding the suite exposed an import-time console-output side effect in the original shared trainer. Console configuration now occurs only at execution and reconfigures streams without replacing/closing their descriptors. This allowed captured test runs to exit normally without changing model training mathematics.

An initial GitHub check lacked Matplotlib; the workflow now declares all test dependencies and installs CPU PyTorch for offline checks. The numerical attention helper emits four upstream PyTorch AMP deprecation warnings. No CUDA training, multi-node experiment, full archived suite, or scientific-metric reproduction was performed.
