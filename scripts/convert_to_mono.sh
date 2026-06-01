#!/usr/bin/env bash
set -euo pipefail

set -a
[ -f .env ] && source .env
set +a

dir="${LOCAL_BREAK_SAMPLE_DIRECTORY:-}"
if [ -z "$dir" ]; then
	echo "LOCAL_BREAK_SAMPLE_DIRECTORY is not set; add it to .env (see .env.example)" >&2
	exit 1
fi

if [ ! -d "$dir" ]; then
	echo "directory does not exist: $dir" >&2
	exit 1
fi

command -v ffmpeg >/dev/null || { echo "ffmpeg not found in PATH" >&2; exit 1; }
command -v ffprobe >/dev/null || { echo "ffprobe not found in PATH" >&2; exit 1; }

converted=0
skipped=0

while IFS= read -r -d '' f; do
	ch=$(ffprobe -v error -select_streams a:0 -show_entries stream=channels -of csv=p=0 "$f")
	if [ "$ch" -le 1 ] 2>/dev/null; then
		echo "skip (already mono): $(basename "$f")"
		skipped=$((skipped + 1))
		continue
	fi

	out="$dir/$(basename "${f%.*}").wav"
	echo "converting $ch ch -> mono: $(basename "$f")"
	ffmpeg_args=(-hide_banner -loglevel error -y -i "$f" \
		-af "pan=mono|c0=0.5*c0+0.5*c1" -ac 1 -ar 44100 -acodec pcm_s16le)

	if [ "$f" = "$out" ]; then
		tmp=$(mktemp "$dir/.convert-to-mono.XXXXXX.wav")
		ffmpeg "${ffmpeg_args[@]}" "$tmp"
		mv "$tmp" "$out"
	else
		ffmpeg "${ffmpeg_args[@]}" "$out"
	fi

	converted=$((converted + 1))
done < <(find "$dir" -maxdepth 1 -type f \( \
	-iname "*.wav" -o -iname "*.mp3" -o -iname "*.aiff" -o \
	-iname "*.aif" -o -iname "*.flac" -o -iname "*.m4a" -o \
	-iname "*.aac" -o -iname "*.ogg" \
\) -print0)

echo "done ($converted converted, $skipped already mono)"
