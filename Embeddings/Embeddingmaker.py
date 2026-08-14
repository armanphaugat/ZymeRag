from sentence_transformers import SentenceTransformer
class Embedder:

    def __init__(self, model_name="Qwen/Qwen3-Embedding-0.6B"):
        self.model = SentenceTransformer(model_name)

    def embed_documents(self, chunks):
        return self.model.encode(
            chunks,
            normalize_embeddings=True,
            show_progress_bar=True
        ).astype("float32")

    def embed_query(self, query):
        return self.model.encode(
            query,
            normalize_embeddings=True
        ).astype("float32")