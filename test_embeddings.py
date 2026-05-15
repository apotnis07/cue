import time
from sentence_transformers import SentenceTransformer, util

model = SentenceTransformer("all-MiniLM-L6-v2", device="mps")

anchors = [
    "adding an ingredient to the dish",
    "pouring something into the pan",
    "playing the next chord progression",
    "showing how to play a chord on the guitar",
    "demonstrating a guitar technique"
]

test_segments = [
    "I'm adding three tablespoons of butter",
    "The weather looks nice today",
    "Now pour in the cream slowly",
    "Let me tell you about my grandmother",
    "Now play the E chord"
]


start = time.time()
anchor_embeddings = model.encode(anchors, convert_to_tensor=True)
segment_embeddings = model.encode(test_segments, convert_to_tensor=True)
print(f"Embedding time: {time.time() - start:.3f}s\n")

for seg, seg_emb in zip(test_segments, segment_embeddings):
    scores = util.cos_sim(seg_emb, anchor_embeddings)[0]
    max_score = float(scores.max())
    print(f"{max_score:.3f}  {seg}")
