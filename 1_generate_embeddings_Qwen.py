# 1_generate_embeddings_Qwen.py
import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
import gc
import torch

print("="*60)
print("Step 1: Generate Embeddings (Qwen 3 via Sentence Transformers)")
print("="*60)

# Configuration
BATCH_SIZE = 8  # Reduced for 4B model - adjust based on GPU memory
MODEL_NAME = "Qwen/Qwen3-Embedding-4B"  # 512d embeddings (4B model)

# Setup device
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"\nUsing device: {device}")

# Load model
print(f"\nLoading model: {MODEL_NAME}")
print("Using memory-optimized settings for 4B model...")

# Load with float16 to save memory
model = SentenceTransformer(
    MODEL_NAME, 
    device=device,
    truncate_dim=512,
    model_kwargs={
        "torch_dtype": torch.float16,  # Use half precision
    }
)
print(f"✅ Model loaded")
print(f"   Embedding dimension: 512 (MRL truncated)")
print(f"   L2 normalization: Enabled")
print(f"   Precision: float16 (memory optimized)")

# Load data
print("\n[1/2] Loading TripAdvisor reviews...")
df = pd.read_csv('tripadvisor_hotel_reviews.csv')

# Clean data
df = df.dropna(subset=['description']).copy()
df = df[df['description'].str.strip() != ''].copy()
df = df.reset_index(drop=True)

total_reviews = len(df)
print(f"✅ Loaded {total_reviews:,} reviews")

# Generate embeddings
print(f"\n[2/2] Generating 512-dimensional embeddings...")
texts = df['description'].tolist()

# Optional: Add clustering instruction for 1-5% improvement
# For clustering, you can either:
# 1. Use no prompt (default) - simple and effective
# 2. Add a custom instruction - may improve performance by 1-5%
USE_CLUSTERING_INSTRUCTION = True  # Set to True to enable

if USE_CLUSTERING_INSTRUCTION:
    print("Using custom clustering instruction...")
    # Prepend task instruction to each text
    instruction = "Encode the texts for semantic clustering and grouping by themes\nQuery:"
    texts_with_instruction = [f"{instruction}{text}" for text in texts]
    
    print(f"Processing in batches of {BATCH_SIZE}...")
    embeddings = model.encode(
        texts_with_instruction,
        batch_size=BATCH_SIZE,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,  # L2 normalization enabled
        device=device,
    )
else:
    print("Using default encoding (no instruction)...")
    print(f"Processing in batches of {BATCH_SIZE}...")
    embeddings = model.encode(
        texts,
        batch_size=BATCH_SIZE,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,  # L2 normalization enabled
        device=device,
    )

# Convert to float32 to save space
embeddings = embeddings.astype(np.float32)

print(f"\n✅ Embeddings generated!")
print(f"   Shape: {embeddings.shape}")
print(f"   Dimension: {embeddings.shape[1]}d")
print(f"   Memory: {embeddings.nbytes / 1024 / 1024:.2f} MB")

# Save with static file names
print("\nSaving embeddings...")
np.save('embeddings.npy', embeddings)
df.to_csv('reviews_clean.csv', index=False)

print("\n" + "="*60)
print("✅ Step 1 Complete!")
print("="*60)
print(f"Saved files:")
print(f"  - embeddings.npy ({embeddings.shape[1]}d)")
print(f"  - reviews_clean.csv")
print(f"\n🚀 Next: python 2_reduce_dimensions.py")

# Cleanup
del model, embeddings
if torch.cuda.is_available():
    torch.cuda.empty_cache()
gc.collect()