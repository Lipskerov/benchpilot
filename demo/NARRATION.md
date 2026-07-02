# BenchPilot demo — voice-over script (matches benchpilot-demo.mp4, 2:09)

Read at a natural, confident pace. Timestamps are approximate cue points — watch the
video and start each line when the matching caption/section appears. ~19 lines, ~2 min.

| # | ~Time | Line |
|---|-------|------|
| 1 | 0:00 | What if you could skip the twenty-plus hours of reading, planning and assigning — and jump straight from a scientific idea to real work at the bench? |
| 2 | 0:08 | Because today, every project starts the same way: buried in papers and trials before a single experiment even begins. |
| 3 | 0:14 | So let's just ask — in plain language — and let BenchPilot read the whole field for us. |
| 4 | 0:19 | In seconds it pulls a grounded answer from real PubMed papers and clinical trials, and surfaces the actual molecular targets. |
| 5 | 0:24 | Every paper opens to its full abstract; every trial, to its phase, sponsor and outcomes. |
| 6 | 0:33 | Pick a target, and it proposes competing hypotheses — each one in plain English, and each one testable. |
| 7 | 0:40 | You get a clear prediction, and the exact result that would prove it wrong. |
| 8 | 0:47 | Choose one, and BenchPilot designs the experiments to answer it — on a timeline, with some running in parallel. |
| 9 | 0:53 | Western blots, imaging, dose-response — already scoped with the right cell lines, test groups and reagents. |
| 10 | 0:59 | Now one click turns that plan into a real project. Fedor leads, and the whole team is staffed automatically. |
| 11 | 1:12 | You see everyone's workload at a glance… |
| 12 | 1:16 | …and the AI even suggests who should run each task, based on expertise and current load. |
| 13 | 1:22 | Reassign or move work, and the board updates live. |
| 14 | 1:26 | Every experiment is tracked on a board, with a roadmap of what's coming next. |
| 15 | 1:33 | Open the Western blot — the design, the cell lines, and the real result, right there. |
| 16 | 1:40 | And the confocal imaging, sitting right next to the protocol. |
| 17 | 1:47 | Need a reagent? It's all searchable — with concentration and live stock. |
| 18 | 1:56 | And before you run anything, BenchPilot checks your inventory and tells you exactly what to order. |
| 19 | 2:03 | From a single question to a staffed, scheduled project — in minutes, not weeks. This is BenchPilot, built with IBM Bob. |

---

## How to add the voice-over

**If you record it yourself:** record while watching the video (QuickTime → File → New Audio
Recording, or Audacity). Save as `demo/voiceover.m4a` (or .wav) and I'll mux it:
```
ffmpeg -i demo/benchpilot-demo.mp4 -i demo/voiceover.m4a -map 0:v -map 1:a \
  -c:v copy -c:a aac -shortest demo/benchpilot-demo-vo.mp4
```

**Auto (open TTS):** I can generate `voiceover.wav` locally with Kokoro or Piper from the
lines above, then mux the same way. For tight sync I'll re-run the recorder so it logs the
exact cue time of each line, generate one clip per line, and place each at its timestamp.
