from metaflow import FlowSpec, step, Parameter
import yt_dlp
import subprocess
import json
import re
from pathlib import Path
import mlx_whisper
import time
from sentence_transformers import SentenceTransformer, util


class CuePipeline(FlowSpec):

    video_url = Parameter("video_url",
        help="YouTube URL to process",
        required=True
    )

    @step
    def start(self):
        """Validate input and set up working directory"""
        self.run_id = str(int(time.time()))
        # self.video_path = f"video_{self.run_id}.mp4"
        # self.audio_path = f"audio_{self.run_id}.wav"

        self.video_path = f"video.mp4"
        self.audio_path = f"audio.wav"

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
            "noplaylist": True,
            "overwrites": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(self.video_url, download=True)
            self.video_title = info.get("title", "Unknown")
            self.video_duration = info.get("duration", 0)

        print(f"Downloaded: {self.video_title} ({self.video_duration}s)")
        # self.video_title = "Test Video"
        # self.video_duration = 0
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
        """Detect key moments using semantic similarity"""
        model = SentenceTransformer("all-MiniLM-L6-v2", device="mps")

        ANCHORS = {
        "ingredient": [
            "I am adding an ingredient right now",
            "pouring this into the pan now",
            "putting this ingredient into the bowl",
            "I'm mixing in this ingredient",
            "adding this to the recipe now",
            "use exactly this amount of ingredient",
            "measure out this quantity right now",
            "you need this many grams or cups",
        ],
        "technique": [
            "do this specific action right now",
            "perform this step at this moment",
            "this is how you do this technique",
            "apply this method right now",
        ],
        "timing": [
            "cook this for exactly this many minutes",
            "set the temperature to this number",
            "wait this long before the next step",
            "it is ready when this happens",
        ],
        }

        print("Encoding anchors...")
        anchor_embeddings = {
            category: model.encode(anchors, convert_to_tensor=True)
            for category, anchors in ANCHORS.items()
        }

        print(f"Encoding {len(self.segments)} segments...")
        texts = [seg["text"] for seg in self.segments]
        segment_embeddings = model.encode(texts, convert_to_tensor=True, batch_size=64)

        THRESHOLD = 0.35

        moments = []
        ACTION_INDICATORS = re.compile(
    r"\b(i'?m|i am|we'?re|we are|i'?ll|let'?s|go ahead|now|we'?re gonna|i'?m gonna|going to|adding|pour|sprinkle|mix|fold|bake|cook|stir|whisk|reduce|set|turn)\b",
    re.IGNORECASE
)
        for seg, seg_emg in zip(self.segments, segment_embeddings):

            if len(seg["text"].split()) < 6:
                continue
            matched_types = []
            for category, cat_embeddings in anchor_embeddings.items():
                scores = util.cos_sim(seg_emg, cat_embeddings)[0]
                max_score = float(scores.max())
                if max_score >= THRESHOLD:
                    matched_types.append(category)

            if matched_types:
                if ACTION_INDICATORS.search(seg["text"]):
                    moments.append({
                        "start": seg["start"],
                        "end": seg["end"],
                        "text": seg["text"],
                        "timestamp_display": self._format_timestamp(seg["start"]),
                        "types": matched_types,
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