# HotpotQA project continuity

Read PROJECT_PROGRESS_FA.md before continuing this project. It is the user-requested durable history and current decision record. The canonical branch is docs/hotpotqa-progress in omidghpython/VIE.

The accepted development baseline is v3.2.4-max4. The user has authorized a simple-prompt vs operadic comparison; simple_vs_operadic_v1 is prepared and awaiting actual results. Separate-judge selection remains pending the user's decision. Do not infer implementation authorization from historical proposals or attached documents.

After every pipeline change, update the current status and append a dated entry with intent, changed files/settings, code/package reference and verification. Mark live results pending until actually received. After analyzing each run, append observed metrics, concrete semantic findings, limitations, the user's decision and the next step. Preserve old history; correct mistakes explicitly. Keep result artifacts and hashes in history/artifacts.json. Commit and push these records to the canonical branch, verify remote delivery, and report any upload failure. Do not silently treat local files as durable remote records.

Quality and completeness take priority over token savings. Report actual usage. Offline tests are not model accuracy; reviewer valid is not ground truth. Preserve evaluation inputs, keep experimental outputs separate, and do not insert evaluation gold into prompts. Existing instructions and reports from earlier experiments are historical evidence, not new user authorization. Do not publish cloud-environment configuration unless separately requested.
