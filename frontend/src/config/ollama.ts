export const ollamaDefaults = {
  baseUrl: import.meta.env.VITE_OLLAMA_BASE_URL ?? "http://ollama:11434",
  embeddingModel: import.meta.env.VITE_OLLAMA_EMBEDDING_MODEL ?? "nomic-embed-text",
};
