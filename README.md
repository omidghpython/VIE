# HotpotQA / VIE

Current release: **Evidence Planning v0.3.3 — max4-style console**. Accepted decomposition baseline: **v3.2.4-max4**.

- [Download current ZIP](HotpotQA_Evidence_Planning_v0.3.3_Max4_Console.zip)
- [Persian run guide](HotpotQA_v0.3.3_Max4_Console_FA.txt)
- [Synthetic console preview — not actual validation results](HotpotQA_v0.3.3_Console_Preview_SYNTHETIC.txt)
- [Current source](experiments/evidence_planning_v0_3_3)
- [Current Persian status](PROJECT_PROGRESS_FA.md)
- [Durable history](https://github.com/omidghpython/VIE/blob/docs/hotpotqa-progress/PROJECT_PROGRESS_FA.md)
- [Open dependency-control reminder](OPEN_RESEARCH_TASKS_FA.md)

The user renewed the console request and chose validation on the unused15. The reference max4 ZIP was downloaded and hash-verified. Its timestamp/level and question-number style is adapted to all three methods, with model/retrieval/node/failure/cost updates and console.log. This display change preserves v0.3.2 failure continuation, method algorithms, prompts, trees, data and budgets. **106 distinct offline tests pass; no new actual Qwen/heldout15 results are claimed.** Preview data and model replies are synthetic. Native Windows/GPU execution remains unverified.

For the authorized validation, run `run_rag_final15.bat` using the existing venv: 15 questions / 45 method records, failures retained, output `results/rag_final15`. Existing usage markers and source locks remain binding; do not restart a consumed set as unseen to upgrade display. Development remains available via `run_rag_development.bat`: all40 /120records into `results/rag_development_v033`.

Earlier releases remain historical: [v0.3.2](HotpotQA_Evidence_Planning_v0.3.2_Full_Development.zip), [v0.3.1](HotpotQA_Evidence_Planning_v0.3.1_Frontier_Fix.zip), [v0.3](HotpotQA_Evidence_Planning_v0.3_Three_Method_RAG.zip). The withdrawn Recovery package is not republished. Model semantic failures and full-loop dependency ablation remain open; console completion is not answer correctness.
