/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
  readonly VITE_OLLAMA_BASE_URL?: string;
  readonly VITE_OLLAMA_EMBEDDING_MODEL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
