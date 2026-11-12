# SE code-model test

A fixed set of 38 small coding tasks with automatic tests, for comparing local models in the SE's code slot (Grey, 2026-11-04). 30 are in Python and 8 in TypeScript; 29 ask for new code from a description and 9 ask for a bug fix. The first ten Python tasks are the original pilot.

```
python -I scripts\model_bench\check_answer_keys.py
python -I scripts\model_bench\bench.py --allow-unsafe-local-execution 3 fast qwen3:14b qwen2.5-coder:14b
python -I scripts\model_bench\analyze.py fast
```

- `check_answer_keys.py` is a trusted-only verifier: it runs the fixed repository reference solutions and buggy fixtures, not model replies or user-supplied code. Review changed fixtures before running it. Every reference must pass and every buggy input must fail, so a miss is the model's and not the test's.
- `bench.py --allow-unsafe-local-execution <runs per task> <fast|think> <model> ...` calls each model through ZAE's own helper. Without the explicit flag it exits before loading a model, creating result files or executing answers. `fast` is non-thinking mode, the way the SE calls its models (temperature 0.3, 8,192-token context); `think` is Qwen3's thinking mode. Each model is loaded first, so loading time is not counted. Earlier timing observations are workload-dependent; measure each model on the current workstation.
- `analyze.py [fast|think]` prints the tables: pass rate by model and kind of task, per-task results, failure reasons, a paired comparison (resampling the tasks), the pilot against the new tasks, tasks solved at least once, and timing.
- Results are written to `data/model_bench/bench_<mode>.json` (the private data folder, not committed).

**Execution is disabled by default.** The explicit flag acknowledges unsafe local execution; it does not create a sandbox. Python runs in a same-account subprocess with `-I` and a 10-second limit. TypeScript is compiled with the app's own compiler (`desktop/node_modules`) and evaluated using Node `vm`. Neither mechanism, the temporary directory, nor regex filtering prevents filesystem, network or process access. Run model-generated answers only inside a separately provisioned, disposable OS-isolated environment without private files or credentials. This tool does not provision that isolation. Do not connect it to autonomous execution as a security boundary.

The filters reject some obvious system/network constructs as a convenience, not a security guarantee. A run passes only if every assertion passes. Both checker APIs default to blocked execution, and the TypeScript child requires the explicit flag even when invoked directly. The trusted answer-key verifier deliberately opts in only for reviewed fixed repository fixtures.

Safety-gate tests do not invoke models or execute candidate answers:

```
python -I scripts\model_bench\execution_gate_test.py
```

Needs Ollama running with the models pulled. The first results (qwen2.5-coder:14b, qwen3:14b and qwen3.5:9b, 2026-11-04) are in `docs/architecture/CLAUDE_NOTES_2026-11-02.md`.
