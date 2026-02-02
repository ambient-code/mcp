#!/bin/bash
# Bulk recording script for advanced MCP-ACP demos
# Requires: asciinema, agg, ffmpeg, IBM Plex Mono font

set -e

DEMOS=(
  "demo-5-session-template"
  "demo-6-crash-recovery"
  "demo-7-metrics-export"
)

echo "MCP-ACP Advanced Demo Recorder"
echo "=============================="
echo

for demo in "${DEMOS[@]}"; do
  echo "📹 Recording: $demo"
  asciinema rec "${demo}.cast" --cols 108 --rows 35 -c "./${demo}.sh" --overwrite
  echo "  ✓ .cast file created"

  echo "🎨 Converting to GIF..."
  agg "${demo}.cast" "${demo}.gif"
  echo "  ✓ .gif file created"

  echo "🎬 Converting to MP4..."
  ffmpeg -i "${demo}.gif" \
    -vf "fps=10,scale=1080:-1:flags=lanczos,format=yuv420p" \
    -c:v libx264 -preset slow -crf 23 \
    -y "${demo}.mp4" 2>&1 | tail -3
  echo "  ✓ .mp4 file created"

  echo "✅ $demo complete"
  echo
done

echo "================================"
echo "All advanced demos recorded!"
echo
echo "Files created:"
ls -lh demo-{5,6,7}*.{cast,gif,mp4} 2>/dev/null | awk '{print "  " $9, "(" $5 ")"}'
