# 1_generate_embeddings.py
import pandas as pd
from nomic import embed
import numpy as np
from tqdm import tqdm
import gc

print("="*60)
print("Step 1: Generate Embeddings")
print("="*60)

# Configuration
BATCH_SIZE = 2000
EMBEDDING_DIM = 512

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
print(f"\n[2/2] Generating {EMBEDDING_DIM}-dimensional embeddings...")
texts = df['description'].tolist()
all_embeddings = []

n_batches = (total_reviews + BATCH_SIZE - 1) // BATCH_SIZE
print(f"Processing {n_batches} batches...")

for i in tqdm(range(0, total_reviews, BATCH_SIZE), desc="Embedding batches"):
    batch_texts = texts[i:i+BATCH_SIZE]
    
    try:
        output = embed.text(
            texts=batch_texts,
            model='nomic-embed-text-v1.5',
            task_type='clustering',
            inference_mode='local',
            device='cuda',
            dimensionality=EMBEDDING_DIM
        )
        
        batch_embeddings = np.array(output['embeddings'], dtype=np.float32)
        all_embeddings.append(batch_embeddings)
        del output
        
    except Exception as e:
        print(f"\n⚠️ GPU error: {e}")
        print("Falling back to CPU...")
        
        output = embed.text(
            texts=batch_texts,
            model='nomic-embed-text-v1.5',
            task_type='clustering',
            inference_mode='local',
            device='cpu',
            dimensionality=EMBEDDING_DIM
        )
        
        batch_embeddings = np.array(output['embeddings'], dtype=np.float32)
        all_embeddings.append(batch_embeddings)
        del output
    
    if (i // BATCH_SIZE) % 10 == 0:
        gc.collect()

# Combine all embeddings
print("\nCombining embeddings...")
embeddings = np.vstack(all_embeddings)

print(f"\n✅ Embeddings generated!")
print(f"   Shape: {embeddings.shape}")
print(f"   Memory: {embeddings.nbytes / 1024 / 1024:.2f} MB")

# Save with static file names
print("\nSaving embeddings...")
np.save('embeddings.npy', embeddings)
df.to_csv('reviews_clean.csv', index=False)

print("\n" + "="*60)
print("✅ Step 1 Complete!")
print("="*60)
print(f"Saved files:")
print(f"  - embeddings.npy")
print(f"  - reviews_clean.csv")
print(f"\n🚀 Next: python 2_reduce_dimensions.py")