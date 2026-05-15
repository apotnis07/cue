from metaflow import FlowSpec, step, Parameter
import yt_dlp
import subprocess
import json
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
        self.next(self.extract_frames)

    @step
    def extract_frames(self):
        """Extract frames at 1fps and score visual activity with CLIP"""
        import os
        import shutil
        import torch
        from PIL import Image
        from transformers import CLIPProcessor, CLIPModel

        frames_dir = "frames"
        shutil.rmtree(frames_dir, ignore_errors=True)
        os.makedirs(frames_dir)

        subprocess.run([
            "ffmpeg", "-y", "-i", self.video_path,
            "-vf", "fps=1", "-q:v", "2",
            f"{frames_dir}/frame_%06d.jpg"
        ], check=True, capture_output=True)

        frame_files = sorted(os.listdir(frames_dir))
        print(f"Extracted {len(frame_files)} frames, scoring with CLIP...")

        device = "mps" if torch.backends.mps.is_available() else "cpu"
        clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(device)
        clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        clip_model.eval()

        positive_prompts = [
            "hands actively demonstrating a technique",
            "person performing a physical action",
            "close-up of hands doing something",
            "active demonstration in progress",
            "showing how to do something with hands",
        ]
        negative_prompts = [
            "person talking to camera",
            "presenter speaking without demonstrating",
            "talking head with no action",
        ]
        all_prompts = positive_prompts + negative_prompts
        n_pos = len(positive_prompts)

        import torch.nn.functional as F

        text_inputs = clip_processor(text=all_prompts, return_tensors="pt", padding=True)
        text_inputs = {k: v.to(device) for k, v in text_inputs.items()}
        with torch.no_grad():
            text_out = clip_model.text_model(**text_inputs)
            text_features = clip_model.text_projection(text_out.pooler_output)
            text_features = F.normalize(text_features, dim=-1)

        BATCH = 32
        visual_scores = {}
        logit_scale = clip_model.logit_scale.exp()

        with torch.no_grad():
            for b in range(0, len(frame_files), BATCH):
                batch_fnames = frame_files[b:b + BATCH]
                batch_imgs = [
                    Image.open(os.path.join(frames_dir, f)).convert("RGB")
                    for f in batch_fnames
                ]
                img_inputs = clip_processor(images=batch_imgs, return_tensors="pt")
                img_inputs = {k: v.to(device) for k, v in img_inputs.items()}

                img_out = clip_model.vision_model(**img_inputs)
                image_features = clip_model.visual_projection(img_out.pooler_output)
                image_features = F.normalize(image_features, dim=-1)

                sim = (image_features @ text_features.T) * logit_scale
                probs = sim.softmax(dim=1)
                pos_scores = probs[:, :n_pos].sum(dim=1).cpu().tolist()

                for i, score in enumerate(pos_scores):
                    visual_scores[float(b + i)] = score

        shutil.rmtree(frames_dir)
        self.visual_scores = visual_scores
        print(f"Visual scores computed for {len(visual_scores)} frames")
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
        """Detect key moments using universal semantic anchors + CLIP visual validation"""
        from sentence_transformers import SentenceTransformer, util

        model = SentenceTransformer("all-MiniLM-L6-v2", device="mps")

        ANCHORS = [
            # Tutorial-framing register
            "Now I am going to show you how to do this",
            "Watch as I demonstrate this step right here",
            "This is the technique you need to apply",
            "Pay close attention to what I am doing now",
            "Here is the next step in the process",
            "Let me demonstrate this important action",
            "This is how you perform this correctly",
            "Follow along carefully as I do this",
            "This is the key action at this moment",
            "Now we move on to this step",
            "I will now perform this action",
            "Here is what you need to do at this point",
            # Direct-action register
            "I am doing this action right now",
            "I am placing this here right now",
            "I am applying this step directly now",
            "putting this in right now",
            "I am performing this step right now",
            "I am pressing here at this moment",
            "doing this specific thing at this moment",
            "this is going in right now",
        ]

        print("Encoding anchors...")
        anchor_embeddings = model.encode(ANCHORS, convert_to_tensor=True)

        print(f"Encoding {len(self.segments)} segments...")
        texts = [seg["text"] for seg in self.segments]
        segment_embeddings = model.encode(texts, convert_to_tensor=True, batch_size=64)

        AUDIO_THRESHOLD = 0.30
        AUDIO_STRONG = 0.50
        VISUAL_THRESHOLD = 0.25

        moments = []
        for seg, seg_emb in zip(self.segments, segment_embeddings):
            if len(seg["text"].split()) < 6:
                continue

            scores = util.cos_sim(seg_emb, anchor_embeddings)[0]
            audio_score = float(scores.max())

            if audio_score < AUDIO_THRESHOLD:
                continue

            t = seg["start"]
            window_visual = max(
                (self.visual_scores.get(float(ts), 0.0)
                 for ts in range(max(0, int(t) - 3), int(t) + 4)),
                default=0.0
            )

            if audio_score >= AUDIO_STRONG or window_visual >= VISUAL_THRESHOLD:
                moments.append({
                    "start": seg["start"],
                    "end": seg["end"],
                    "text": seg["text"],
                    "timestamp_display": self._format_timestamp(seg["start"]),
                    "_score": audio_score,
                    "_emb": seg_emb.cpu().numpy(),
                })

        self.moments = self._deduplicate_content_aware(moments)
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
            print(f"[{m['timestamp_display']}]  {m['text']}", flush=True)

    def _format_timestamp(self, seconds: float) -> str:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}:{secs:02d}"

    def _deduplicate_content_aware(self, moments: list, min_gap: float = 2.0, sim_threshold: float = 0.85) -> list:
        import torch
        from sentence_transformers import util as st_util
        if not moments:
            return []
        deduped = [moments[0]]
        for new in moments[1:]:
            conflict_idx = None
            for j, kept in enumerate(deduped):
                if abs(new["start"] - kept["start"]) < min_gap:
                    sim = float(st_util.cos_sim(
                        torch.tensor(new["_emb"]),
                        torch.tensor(kept["_emb"])
                    )[0][0])
                    if sim > sim_threshold:
                        conflict_idx = j
                        break
            if conflict_idx is None:
                deduped.append(new)
            elif new["_score"] > deduped[conflict_idx]["_score"]:
                deduped[conflict_idx] = new
        for m in deduped:
            m.pop("_score", None)
            m.pop("_emb", None)
        return deduped

if __name__ == "__main__":
    CuePipeline()