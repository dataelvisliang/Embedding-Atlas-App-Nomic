# Embedding Atlas - TripAdvisor Reviews Visualization

A monorepo containing multiple deployment options for visualizing TripAdvisor hotel reviews using Apple's Embedding Atlas.

## Project Structure

```
├── streamlit/          # Python Streamlit app with LLM chat
├── static-demo/        # Static HTML export for GitHub Pages
├── vercel-app/         # Next.js app for Vercel deployment
└── README.md
```

## Deployment Options

### 1. Streamlit Cloud (Full Features)
Interactive app with LLM-powered chat to analyze selected reviews.

```bash
cd streamlit
pip install -r requirements.txt
streamlit run 3_visualize_atlas_with_llm_deploy.py
```

**Deploy:** Push to GitHub and connect to [Streamlit Cloud](https://streamlit.io/cloud)

### 2. GitHub Pages (Static)
Lightweight static visualization without server requirements.

**Deploy:** Enable GitHub Pages in repo settings, set source to `/static-demo` folder.

### 3. Vercel (Next.js)
Modern React-based app with server-side capabilities.

```bash
cd vercel-app
npm install
npm run dev
```

**Deploy:** Push to GitHub and import to [Vercel](https://vercel.com)

## Features

- Interactive 2D embedding visualization
- Cluster exploration with automatic labeling
- Search and filter reviews
- LLM chat analysis (Streamlit version only)

## Tech Stack

- **Visualization:** [Apple Embedding Atlas](https://apple.github.io/embedding-atlas/)
- **Embeddings:** Nomic Embed V1.5
- **Frameworks:** Streamlit, Next.js
- **LLM:** OpenRouter API (free models)

## Data Pipeline

1. `1_generate_embeddings_*.py` - Generate embeddings from review text
2. `2_reduce_dimensions.py` - UMAP projection to 2D
3. `3_visualize_atlas*.py` - Interactive visualization

## License

MIT
