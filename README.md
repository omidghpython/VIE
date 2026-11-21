# HotpotQA / VIE

Current research release: **Evidence Planning v0.3.0**. Accepted decomposition baseline: **v3.2.4-max4**.

- [Persian current status and continuation instructions](PROJECT_PROGRESS_FA.md)
- [Open research reminder: full-loop dependency control](OPEN_RESEARCH_TASKS_FA.md)
- [Download v0.3 ZIP](HotpotQA_Evidence_Planning_v0.3_Three_Method_RAG.zip)
- [Persian run guide](HotpotQA_v0.3_Guide_FA.txt)
- [Complete Windows recovery ZIP (fresh environment)](HotpotQA_v0.3_Recovery_Windows_v1.zip)
- [Persian recovery guide](HotpotQA_Recovery_Windows_v1_FA.txt)
- [Recovery installer source and software checks](tools/hotpotqa_environment_recovery_v1)
- [Audit of v0.2 and changes in v0.3](HotpotQA_v0.2_Audit_v0.3_Changes_FA.txt)
- [Browsable v0.3 source](experiments/evidence_planning_v0_3_0)
- [Complete durable project history](https://github.com/omidghpython/VIE/blob/docs/hotpotqa-progress/PROJECT_PROGRESS_FA.md)

The release implements three-method RAG, actual local retrieval and an active dependency stopping gate. **88 offline tests passed; live Qwen/BGE results and independent semantic evaluation remain pending.** Software tests are not accuracy results. The 15 final questions remain unused for model inference in the delivered record.

The full-loop dependency ablation is an open research task, not a completed result. Earlier downloads remain available in this repository. The unchanged v0.3 archive retains its original build-time notes; the user authorized ongoing GitHub recording on 2026-11-21.

For a wiped Windows GPU environment, extract the recovery ZIP and run `restore_environment_windows.bat`. It installs the recorded CUDA PyTorch build, runtime libraries and pinned model caches in a separate environment. Python 64-bit and a working NVIDIA driver are prerequisites. The installer passed 11 mocked software tests in source and extracted delivery; real Windows/CUDA installation remains to be checked on the target machine. All 95 original v0.3 package files remain byte-identical.
