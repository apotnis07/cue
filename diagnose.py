from sentence_transformers import SentenceTransformer, util

model = SentenceTransformer("all-MiniLM-L6-v2", device="mps")

ANCHORS = {
    "action": [
        "I am doing this specific thing right now",
        "now performing this step",
        "watch me do this",
        "here is how to do this",
        "do this right now",
        "I will show you how",
    ],
    "transition": [
        "moving to the next step",
        "now we move on",
        "the next thing to do",
        "once that is done",
        "after that",
    ],
    "key_information": [
        "this specific detail is important",
        "remember this number or quantity",
        "this is the critical part",
        "make sure you do this",
        "this is important to know",
    ],
}

# mix of known true positives and known false positives from the output
TEST_SEGMENTS = [
    # cooking true positives
    ("TP-cook", "I'm adding three tablespoons of butter"),
    ("TP-cook", "Now pour in the cream slowly"),
    ("TP-cook", "We're gonna boil these for about five minutes"),
    # guitar true positives  
    ("TP-guitar", "Now I'm going to show you the G chord"),
    ("TP-guitar", "Watch my fingers here on the fret"),
    ("TP-guitar", "Let's move to the next chord progression"),
    ("TP-guitar", "I'm playing this part slowly so you can follow"),
    # false positives from both domains
    ("FP", "Hey welcome back to my channel"),
    ("FP", "That cheesecake is so light and creamy"),
    ("FP", "In the next video we'll cover fingerpicking"),
    ("FP", "Let me tell you about my grandmother"),
    ("FP", "This song was written in 1975"),
]

anchor_embeddings = {
    cat: model.encode(anchors, convert_to_tensor=True)
    for cat, anchors in ANCHORS.items()
}

print(f"{'LABEL':<5} {'MAX':>6}  {'BEST_CAT':<12}  TEXT")
print("-" * 70)
for label, text in TEST_SEGMENTS:
    seg_emb = model.encode(text, convert_to_tensor=True)
    best_score = 0
    best_cat = ""
    for cat, cat_emb in anchor_embeddings.items():
        score = float(util.cos_sim(seg_emb, cat_emb)[0].max())
        if score > best_score:
            best_score = score
            best_cat = cat
    marker = "✓" if label == "TP" else "✗"
    print(f"{marker:<5} {best_score:>6.3f}  {best_cat:<12}  {text[:60]}")