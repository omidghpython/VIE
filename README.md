# HotpotQA / VIE

Current experimental release: **Evidence Planning v0.3.2 — full development run and failure continuation**. Accepted decomposition baseline: **v3.2.4-max4**.

- [Download v0.3.2 ZIP](HotpotQA_Evidence_Planning_v0.3.2_Full_Development.zip)
- [Persian update and full-run guide](HotpotQA_v0.3.2_Full_Development_FA.txt)
- [Browsable v0.3.2 source](experiments/evidence_planning_v0_3_2)
- [Persian current status](PROJECT_PROGRESS_FA.md)
- [Analysis of the actual v0.3 debug traces](https://github.com/omidghpython/VIE/blob/docs/hotpotqa-progress/history/reports/rag-debug-analysis-2026-11-24.md)
- [Open research reminder: full-loop dependency control](OPEN_RESEARCH_TASKS_FA.md)
- [Complete durable project history](https://github.com/omidghpython/VIE/blob/docs/hotpotqa-progress/PROJECT_PROGRESS_FA.md)

The development launcher now runs **all 40 development questions / 120 method records**. Method errors, budget exhaustion, abstentions and invalid plans remain recorded; per-question retriever setup exceptions are now recorded and isolated so later questions continue. Persisted successes and failures are skipped on resume. Storage/identity failures and process interruption remain stopping conditions. **98 offline tests passed**, including a synthetic full 40-question run with mixed failures. No live result for v0.3.2 is available yet. Algorithms, prompts, trees, evidence gates and per-trial budgets remain unchanged.

The original v0.3 has six real trial records from two development questions (24 model calls, 8 retrieval calls, 12,602 tokens), reproduced exactly from saved traces. This is not a complete benchmark. New runs use `results/rag_development_v032`; keep old results and reuse the installed venv/model cache. Final15 remains unused for model inference. Recovery and the cancelled console redesign are not part of this release.

Previous release: [original v0.3 ZIP](HotpotQA_Evidence_Planning_v0.3_Three_Method_RAG.zip), [v0.3 guide](HotpotQA_v0.3_Guide_FA.txt), [v0.2 audit / v0.3 changes](HotpotQA_v0.2_Audit_v0.3_Changes_FA.txt), [v0.3 source](experiments/evidence_planning_v0_3_0). Earlier releases remain historical records; no decomposition baseline promotion is claimed.

Previous frontier correction: [v0.3.1 ZIP](HotpotQA_Evidence_Planning_v0.3.1_Frontier_Fix.zip), [guide](HotpotQA_v0.3.1_Frontier_Fix_FA.txt).
