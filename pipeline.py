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
            "hands adding an ingredient to a bowl or pan",
            "person measuring or pouring a cooking ingredient",
            "hands chopping, slicing, or dicing food",
            "close-up of a specific cooking action happening now",
            "active food preparation step in progress",
        ]
        negative_prompts = [
            "chef talking about the recipe without touching food",
            "overview shot of the kitchen or finished dish",
            "food resting or cooking unattended",
            "presenter speaking to camera",
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
        """Detect key cooking moments using category anchors + regex gate + CLIP visual validation"""
        import re
        from sentence_transformers import SentenceTransformer, util

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


        ACTION_INDICATORS = re.compile(
            r"\b(adding|pour(ing)?|sprinkle|mix(ing)?|fold(ing)?|bake|baking|cook(ing)?|stir(ring)?|"
            r"whisk(ing)?|reduc(e|ing)|combining?|incorporating?|slic(e|ing)|chop(ping)?|dic(e|ing)|"
            r"mince|grat(e|ing)|knead(ing)?|spread(ing)?|drizzle|season(ing)?|coat(ing)?|"
            r"brush(ing)?|transfer(ring)?)\b",
            re.IGNORECASE
        )

        print("Encoding anchors...")
        anchor_embeddings = {
            category: model.encode(anchors, convert_to_tensor=True)
            for category, anchors in ANCHORS.items()
        }

        print(f"Encoding {len(self.segments)} segments...")
        texts = [seg["text"] for seg in self.segments]
        segment_embeddings = model.encode(texts, convert_to_tensor=True, batch_size=64)

        THRESHOLD = 0.40
        VISUAL_PERCENTILE = 0.65  # top 20% most visually active frames

        all_visual_scores = sorted(self.visual_scores.values())
        cutoff_idx = int(len(all_visual_scores) * VISUAL_PERCENTILE)
        visual_threshold = all_visual_scores[cutoff_idx] if all_visual_scores else 1.0
        print(f"Dynamic visual threshold (p{int(VISUAL_PERCENTILE*100)}): {visual_threshold:.3f}")

        moments = []
        count_v = 0
        count_t = 0
        for seg, seg_emb in zip(self.segments, segment_embeddings):
            if len(seg["text"].split()) < 3:
                continue

            matched_types = []
            best_score = 0.0
            for category, cat_embeddings in anchor_embeddings.items():
                scores = util.cos_sim(seg_emb, cat_embeddings)[0]
                max_score = float(scores.max())
                if max_score >= THRESHOLD:
                    matched_types.append(category)
                    best_score = max(best_score, max_score)

            t = seg["start"]
            window_scores = [
                self.visual_scores.get(float(ts), 0.0)
                for ts in range(max(0, int(t) - 3), int(t) + 4)
            ]
            window_visual = sum(window_scores) / len(window_scores) if window_scores else 0.0

            text_gate = bool(matched_types and ACTION_INDICATORS.search(seg["text"]))
            visual_gate = bool(matched_types and window_visual >= visual_threshold)

            if text_gate:
                count_t += 1

            if visual_gate:
                count_v += 1

            if not (text_gate or visual_gate):
                continue

            moments.append({
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["text"],
                "timestamp_display": self._format_timestamp(seg["start"]),
                "types": matched_types,
                "_score": best_score,
                "_emb": seg_emb.cpu().numpy(),
            })

        self.moments = self._deduplicate_content_aware(moments)
        print(f"Detected {len(self.moments)} moments")
        print(f"Detected {count_t} text moments and {count_v} visual moments")

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
            types = ", ".join(m.get("types", []))
            print(f"[{m['timestamp_display']}] ({types})  {m['text']}", flush=True)

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