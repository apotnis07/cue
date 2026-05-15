import json
import subprocess
import sys
from pathlib import Path

TOLERANCE = 10  # seconds

def parse_timestamp(display):
    parts = display.split(":")
    return int(parts[0]) * 60 + int(parts[1])

def load_ground_truth(path):
    with open(path) as f:
        return json.load(f)

def load_results(path):
    with open(path) as f:
        return json.load(f)

def evaluate(detected_moments, ground_truth_moments):
    gt_matched = set()
    true_positives = 0

    for detected in detected_moments:
        det_seconds = parse_timestamp(detected["timestamp_display"])
        for i, gt in enumerate(ground_truth_moments):
            if i in gt_matched:
                continue
            gt_seconds = parse_timestamp(gt["timestamp_display"])
            if abs(det_seconds - gt_seconds) <= TOLERANCE:
                true_positives += 1
                gt_matched.add(i)
                break

    total_detected = len(detected_moments)
    total_gt = len(ground_truth_moments)

    precision = true_positives / total_detected if total_detected > 0 else 0
    recall = true_positives / total_gt if total_gt > 0 else 0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) > 0 else 0)

    return {
        "true_positives": true_positives,
        "total_detected": total_detected,
        "total_ground_truth": total_gt,
        "false_positives": total_detected - true_positives,
        "false_negatives": total_gt - true_positives,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
    }

def print_results(version, metrics):
    print(f"\n{'='*50}")
    print(f"  {version}")
    print(f"{'='*50}")
    print(f"  Detected:        {metrics['total_detected']}")
    print(f"  True Positives:  {metrics['true_positives']}")
    print(f"  False Positives: {metrics['false_positives']}")
    print(f"  False Negatives: {metrics['false_negatives']}")
    print(f"  Precision:       {metrics['precision']:.1%}")
    print(f"  Recall:          {metrics['recall']:.1%}")
    print(f"  F1:              {metrics['f1']:.3f}")

def run_pipeline(pipeline_file, video_url):
    """Run a pipeline and return the results file path"""
    print(f"\nRunning {pipeline_file}...")
    result = subprocess.run(
        [sys.executable, "-u", pipeline_file, "run",
         "--video_url", video_url],
        capture_output=False,
        text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"{pipeline_file} failed")

    # find the most recent results file
    results_files = sorted(Path(".").glob("results_*.json"),
                          key=lambda p: p.stat().st_mtime,
                          reverse=True)
    if not results_files:
        raise RuntimeError("No results file found")
    return results_files[0]

def find_misses(detected_moments, ground_truth_moments, tolerance=10):
    gt_matched = set()
    for detected in detected_moments:
        det_seconds = parse_timestamp(detected["timestamp_display"])
        for i, gt in enumerate(ground_truth_moments):
            if i in gt_matched:
                continue
            gt_seconds = parse_timestamp(gt["timestamp_display"])
            if abs(det_seconds - gt_seconds) <= tolerance:
                gt_matched.add(i)
                break
    
    misses = [gt for i, gt in enumerate(ground_truth_moments) 
              if i not in gt_matched]
    return misses

if __name__ == "__main__":
    gt_data = load_ground_truth("eval/cheesecake_ground_truth.json")
    ground_truth = gt_data["ground_truth"]
    video_url = gt_data["video_url"]

    print(f"Evaluating on: {gt_data['video_title']}")
    print(f"Ground truth moments: {len(ground_truth)}")

    # run both pipelines
    v1_results_path = run_pipeline("pipeline_v1.py", video_url)
    v2_results_path = run_pipeline("pipeline.py", video_url)

    # score both
    v1_results = load_results(v1_results_path)
    v2_results = load_results(v2_results_path)

    v1_metrics = evaluate(v1_results["moments"], ground_truth)
    v2_metrics = evaluate(v2_results["moments"], ground_truth)

    print_results("V1 — Regex", v1_metrics)
    print_results("V2 — Semantic + Action", v2_metrics)

    # comparison
    print(f"\n{'='*50}")
    print("  COMPARISON")
    print(f"{'='*50}")
    recall_delta = v2_metrics["recall"] - v1_metrics["recall"]
    precision_delta = v2_metrics["precision"] - v1_metrics["precision"]
    f1_delta = v2_metrics["f1"] - v1_metrics["f1"]
    print(f"  Recall:    {'+' if recall_delta >= 0 else ''}{recall_delta:.1%}")
    print(f"  Precision: {'+' if precision_delta >= 0 else ''}{precision_delta:.1%}")
    print(f"  F1:        {'+' if f1_delta >= 0 else ''}{f1_delta:.3f}")

    v1_misses = find_misses(v1_results["moments"], ground_truth)
    v2_misses = find_misses(v2_results["moments"], ground_truth)

    both_miss = [gt for gt in v2_misses 
                if any(gt["timestamp_display"] == m["timestamp_display"] 
                        for m in v1_misses)]

    print("\n--- V1 misses ---")
    for m in v1_misses:
        print(f"  [{m['timestamp_display']}] {m['label']}")

    print("\n--- V2 misses ---")
    for m in v2_misses:
        print(f"  [{m['timestamp_display']}] {m['label']}")

    print("\n--- Both miss ---")
    for m in both_miss:
        print(f"  [{m['timestamp_display']}] {m['label']}")