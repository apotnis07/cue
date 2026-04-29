import yt_dlp
import subprocess
import mlx_whisper
from pathlib import Path
import json

VIDEO_URL = "https://www.youtube.com/watch?v=BSsv6sBD6ow"
AUDIO_PATH = "test_audio.wav"
VIDEO_PATH = "test_video.mp4"

def download_video(url: str, output_path: str):
    print("Downloading video...")
    ydl_opts = {
        "format": "best[ext=mp4]",
        "outtmpl": output_path,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    print(f"Downloaded to {output_path}")


def extract_audio(video_path: str, audio_path: str):
    print("Extracting audio...")
    subprocess.run([
        "ffmpeg", "-y",
        "-i", video_path,
        "-ar", "16000",
        "-ac", "1",
        "-c:a", "pcm_s16le",
        audio_path
    ], check=True, capture_output=True)
    print(f"Audio extracted to {audio_path}")


def transcribe(audio_path: str):
    print("Transcribing...")
    result = mlx_whisper.transcribe(
        audio_path,
        path_or_hf_repo="mlx-community/whisper-medium-mlx",
    )

    print(f"\nDetected language: {result['language']}")
    print("=" * 60)
    

    results = []
    for segment in result["segments"]:
        timestamp = f"[{segment['start']:.1f}s → {segment['end']:.1f}s]"
        print(f"{timestamp}  {segment['text'].strip()}")
        results.append({
            "start": segment["start"],
            "end": segment["end"],
            "text": segment["text"].strip()
        })

    with open("segments.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nSegments saved to segments.json")
    
    return results        


if __name__ == "__main__":
    if not Path(VIDEO_PATH).exists():
        download_video(VIDEO_URL, VIDEO_PATH)
    
    if not Path(AUDIO_PATH).exists():
        extract_audio(VIDEO_PATH, AUDIO_PATH)
    
    segments = transcribe(AUDIO_PATH)
    print(f"\nTotal segments: {len(segments)}")

    
