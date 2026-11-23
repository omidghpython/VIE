# HotpotQA / VIE

Current experimental release: **Evidence Planning v0.3.1 — retrieval frontier fix**. Accepted decomposition baseline: **v3.2.4-max4**.

- [Download v0.3.1 ZIP](HotpotQA_Evidence_Planning_v0.3.1_Frontier_Fix.zip)
- [Persian update and run guide](HotpotQA_v0.3.1_Frontier_Fix_FA.txt)
- [Browsable v0.3.1 source](experiments/evidence_planning_v0_3_1)
- [Persian current status](PROJECT_PROGRESS_FA.md)
- [Analysis of the actual v0.3 debug traces](https://github.com/omidghpython/VIE/blob/docs/hotpotqa-progress/history/reports/rag-debug-analysis-2026-11-24.md)
- [Open research reminder: full-loop dependency control](OPEN_RESEARCH_TASKS_FA.md)
- [Complete durable project history](https://github.com/omidghpython/VIE/blob/docs/hotpotqa-progress/PROJECT_PROGRESS_FA.md)

The patch gives other ready unresolved branches a retrieval turn before repeatedly targeting one branch, and checks the budget before recording another retrieve decision. **93 offline tests passed. No new live result for the patch is available yet.** Prompts, frozen trees, evidence gates, model and budgets remain unchanged. Model evidence errors and the unsupported negative prerequisite in the observed comparison question remain open.

The original v0.3 has six real trial records from two development questions (24 model calls, 8 retrieval calls, 12,602 tokens), reproduced exactly from saved traces. This is not a complete benchmark. New runs use `results/rag_development_v031`; keep old results and reuse the installed venv/model cache. Final15 remains unused for model inference. Recovery and the cancelled console redesign are not part of this release.

Previous release: [original v0.3 ZIP](HotpotQA_Evidence_Planning_v0.3_Three_Method_RAG.zip), [v0.3 guide](HotpotQA_v0.3_Guide_FA.txt), [v0.2 audit / v0.3 changes](HotpotQA_v0.2_Audit_v0.3_Changes_FA.txt), [v0.3 source](experiments/evidence_planning_v0_3_0). Earlier releases remain historical records; no decomposition baseline promotion is claimed.
