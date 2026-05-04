from metaflow import FlowSpec, step, Parameter
import yt_dlp
import subprocess
import json
import re
from pathlib import Path
import mlx_whisper
import time


class CuePipeline(FlowSpec):

    video_url = Parameter("video_url",
        help="YouTube URL to process",
        required=True
    )

    @step
    def start(self):
        """Validate input and set up working directory"""
        self.run_id = str(int(time.time()))
        self.video_path = f"video_{self.run_id}.mp4"
        self.audio_path = f"audio_{self.run_id}.wav"

        print(f"Starting pipeline for: {self.video_url}")
        print(f"Run ID: {self.run_id}")
        self.next(self.download)

    @step
    def download(self):
        """Download video from YouTube"""
        print(f"Downloading: {self.video_url}")
        ydl_opts = {
            "format": "best[ext=mp4]",
            "outtmpl": self.video_path,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(self.video_url, download=True)
            self.video_title = info.get("title", "Unknown")
            self.video_duration = info.get("duration", 0)

        print(f"Downloaded: {self.video_title} ({self.video_duration}s)")
        self.next(self.extract_audio)

    @step
    def extract_audio(self):
        """Extract and normalize audio for Whisper"""
        print("Extracting audio...")
        subprocess.run([
            "ffmpeg", "-y",
            "-i", self.video_path,
            "-ar", "16000",
            "-ac", "1",
            "-c:a", "pcm_s16le",
            self.audio_path
        ], check=True, capture_output=True)
        print(f"Audio extracted to {self.audio_path}")
        self.next(self.transcribe)

    @step 
    def transcribe(self):
        """Transcribe audio using MLX Whisper"""
        print("Transcribing audio...")
        result = mlx_whisper.transcribe(
            self.audio_path,
            path_or_hf_repo="mlx-community/whisper-medium-mlx",
        )
        self.segments = [
            {
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["text"].strip()
            }
            for seg in result["segments"]
        ]
        print(f"Transcribed {len(self.segments)} segments")
        self.next(self.detect_moments)

    @step
    def detect_moments(self):
        """Detect key moments from transcript"""
        INGREDIENT_PATTERNS = [
            r"i'?m adding", r"we'?re adding", r"adding in",
            r"add(ing)? (in |the |your )?",
            r"pour(ing)? (in|over|into)",
            r"sprinkle", r"dash of", r"garnish (with)?",
            r"top(ping|ped) with",
            r"throw(ing)? in", r"toss(ing)? in",
            r"it'?s time for",
            r"now (we'?re|i'?m) (adding|pouring|throwing|putting)",
        ]
        MEASUREMENT_PATTERNS = [
            r"\d+\s*(grams?|g\b|cups?|tablespoons?|tbsp|teaspoons?|tsp|ounces?|oz|pounds?|lb|ml|liters?)",
            r"(a |one |two |three |four )?(pinch|dash|handful|splash|drizzle) of",
            r"(quarter|half|third) (cup|teaspoon|tablespoon)",
        ]
        TECHNIQUE_PATTERNS = [
            r"(turn|reduce|increase|set|keep).{0,15}(heat|temperature|oven|stove)",
            r"(bake|cook|fry|simmer|boil|roast|grill|steam).{0,10}for.{0,10}(minute|hour|second)",
            r"(fold|mix|stir|whisk|beat|blend).{0,15}(until|gently|carefully|slowly)",
            r"(until|once|when).{0,20}(golden|brown|soft|thick|set|bubble|boil|done|ready)",
            r"(remove|take).{0,10}(from|off).{0,10}(heat|oven|pan|stove)",
            r"(let|allow).{0,10}(rest|cool|sit|chill|set)",
        ]
        TIMING_PATTERNS = [
            r"\d+\s*to\s*\d+\s*(minutes?|hours?|seconds?)",
            r"(for\s*)?\d+\s*(minutes?|hours?|seconds?)",
            r"\d+\s*(degrees?|fahrenheit|celsius|°F|°C)",
            r"(medium|low|high|medium.low|medium.high)\s*heat",
        ]

        pattern_groups = {
            "ingredient": re.compile("|".join(INGREDIENT_PATTERNS), re.IGNORECASE),
            "measurement": re.compile("|".join(MEASUREMENT_PATTERNS), re.IGNORECASE),
            "technique": re.compile("|".join(TECHNIQUE_PATTERNS), re.IGNORECASE),
            "timing": re.compile("|".join(TIMING_PATTERNS), re.IGNORECASE),
        }

        moments = []
        for segment in self.segments:
            text = segment["text"]

            matched_types = []

            for category, pattern in pattern_groups.items():
                if pattern.search(text):
                    matched_types.append(category)

            if matched_types:
                moments.append({
                    "start": segment["start"],
                    "end": segment["end"],
                    "text": text,
                    "timestamp_display": self._format_timestamp(segment["start"]),
                    "types": matched_types
                })

        self.moments = self._deduplicate(moments, min_gap=4.0)
        print(f"Detected {len(self.moments)} moments")
        self.next(self.end)

    @step
    def end(self):
        """Summarize and save results"""
        self.transcript = []
        for segment in self.segments:
            self.transcript.append({
                "start": segment["start"],
                "end": segment["end"],
                "text": segment["text"],
                "timestamp_display": self._format_timestamp(segment["start"]),
            })
        results = {
            "url": self.video_url,
            "title": self.video_title,
            "duration": self.video_duration,
            "moments": self.moments,
            "total_moments": len(self.moments),
            "transcript": self.transcript,
        }

        output_path = f"results_{self.run_id}.json"
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)

        print(f"\n{'='*60}")
        print(f"Title:    {self.video_title}")
        print(f"Duration: {self.video_duration}s")
        print(f"Moments:  {len(self.moments)}")
        print(f"Saved to: {output_path}")
        print(f"{'='*60}\n")

        for m in self.moments:
            types = ", ".join(m["types"])
            print(f"[{m['timestamp_display']}] ({types})  {m['text']}", flush=True)

    def _format_timestamp(self, seconds: float) -> str:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}:{secs:02d}"

    def _deduplicate(self, moments: list, min_gap: float) -> list:
        if not moments:
            return []
        deduped = [moments[0]]
        for m in moments[1:]:
            if m["start"] - deduped[-1]["start"] >= min_gap:
                deduped.append(m)
        return deduped

if __name__ == "__main__":
    CuePipeline()