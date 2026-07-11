# Stage 1: build the V-Taper Log SPA
FROM node:22-alpine AS webbuild
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm ci --no-audit --no-fund 2>/dev/null || npm install --no-audit --no-fund
COPY web/ ./
RUN npm run build

# Stage 2: the API/worker image — FastAPI serves the built SPA from web/dist
FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
COPY --from=webbuild /web/dist ./web/dist
ENV PYTHONUNBUFFERED=1
