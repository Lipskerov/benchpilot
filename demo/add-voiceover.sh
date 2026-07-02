#!/bin/bash
# Muxes your recorded narration onto the demo video (loudness-normalised, keeps subtitles).
set -e
cd "$(dirname "$0")"
vo=$(ls voiceover.* 2>/dev/null | head -1)
[ -z "$vo" ] && { echo "Put your recording at demo/voiceover.m4a (or .wav/.mp3) first."; exit 1; }
echo "Using audio: $vo"
ffmpeg -y -i benchpilot-demo.mp4 -i "$vo" \
  -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 192k \
  -af "loudnorm=I=-16:TP=-1.5:LRA=11" -movflags +faststart \
  benchpilot-demo-vo.mp4
echo "✓ wrote demo/benchpilot-demo-vo.mp4"
