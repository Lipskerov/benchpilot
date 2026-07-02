#!/bin/bash
# Records the BenchPilot demo and converts it to mp4.
# Prereqs: app running on http://localhost:8600 ; Playwright + chromium installed.
set -e
cd "$(dirname "$0")"
node record.js
webm=$(ls -t video/*.webm | head -1)
ffmpeg -y -i "$webm" -c:v libx264 -pix_fmt yuv420p -movflags +faststart -r 30 ../benchpilot-demo.mp4
echo "✓ wrote demo/benchpilot-demo.mp4"
