FROM node:22-alpine AS build

WORKDIR /app

ARG VITE_API_BASE=http://localhost:8000
ARG VITE_OLLAMA_BASE_URL=http://ollama:11434
ARG VITE_OLLAMA_EMBEDDING_MODEL=nomic-embed-text
ENV VITE_API_BASE=$VITE_API_BASE
ENV VITE_OLLAMA_BASE_URL=$VITE_OLLAMA_BASE_URL
ENV VITE_OLLAMA_EMBEDDING_MODEL=$VITE_OLLAMA_EMBEDDING_MODEL

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
