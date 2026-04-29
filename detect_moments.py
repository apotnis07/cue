import re
import json

INGREDIENT_PATTERNS = [
    r"i'?m adding",
    r"we'?re adding",
    r"adding in",
    r"add(ing)? (in |the |your )?",
    r"i want \d",
    r"pour(ing)? in",
    r"sprinkle",
    r"dash of",
    r"garnish (with)?",
    r"throw(ing)? in",
    r"toss(ing)? in",
    r"it'?s time for",
    r"now (we'?re|i'?m) (adding|pouring|throwing|putting)",
]

MEASUREMENT_PATTERNS = [
    r"\d+\s*(grams?|g\b|cups?|tablespoons?|tbsp|teaspoons?|tsp|ounces?|oz|pounds?|lbs?|mils?|ml|liters?)",
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
    r"\d+\s*(degrees?|°|fahrenheit|celsius|F\b|C\b)",
    r"(medium|low|high|medium.low|medium.high)\s*heat",
]


COMBINED_INGREDIENT_PATTERN = re.compile(
    "|".join(INGREDIENT_PATTERNS),
    re.IGNORECASE
)

COMBINED_TECHNIQUE_PATTERN = re.compile(
    "|".join(TECHNIQUE_PATTERNS),
    re.IGNORECASE
)

COMBINED_TIMING_PATTERN = re.compile(
    "|".join(TIMING_PATTERNS),
    re.IGNORECASE
)

COMBINED_MEASUREMENT_PATTERN = re.compile(
    "|".join(MEASUREMENT_PATTERNS),
    re.IGNORECASE
)

def detect_moments(segments: list[dict]) -> list[dict]:
    moments = []
    pattern_groups = {
        "ingredient": COMBINED_INGREDIENT_PATTERN,
        "technique": COMBINED_TECHNIQUE_PATTERN,
        "timing": COMBINED_TIMING_PATTERN,
        "measurement": COMBINED_MEASUREMENT_PATTERN,
    }

    for segment in segments:
        text = segment["text"]
        matched_types = []

        for category, pattern in pattern_groups.items():
            if pattern.search(text):
                matched_types.append(category)


        if matched_types:
            moments.append({
                "start": segment["start"],
                "end": segment["end"],
                "text": segment["text"],
                "timestamp_display": format_timestamp(segment["start"]),
                "types": matched_types
            })

    return moments


def format_timestamp(seconds: float) -> str:
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}:{secs:02d}"


def deduplicate_moments(moments: list[dict], min_gap: float = 8.0) -> list[dict]:
    """Remove moments that are too close together — 
    same action often spans multiple segments"""
    if not moments:
        return []
    
    deduped = [moments[0]]
    for moment in moments[1:]:
        if moment["start"] - deduped[-1]["start"] >= min_gap:
            deduped.append(moment)

    return deduped

if __name__ == "__main__":
    # Load segments saved from transcribe.py
    with open("segments.json") as f:
        segments = json.load(f)
    
    moments = detect_moments(segments)
    moments = deduplicate_moments(moments)
    
    print(f"Found {len(moments)} moments:\n")
    for m in moments:
        print(f"[{m['timestamp_display']}]  {m['text']}")
