# SecureNet SOC — React Frontend Dockerfile
# Two-stage: Node build → Nginx static serving

FROM node:20-alpine AS build

WORKDIR /app

# Install dependencies
COPY soc-frontend/package.json soc-frontend/package-lock.json ./
RUN npm ci --production=false

# Build the production bundle
COPY soc-frontend/ .
RUN npm run build

# --- Production stage ---
FROM nginx:1.25-alpine

# Copy built static files
COPY --from=build /app/dist /usr/share/nginx/html

# Copy nginx config (handles SPA routing + API proxy)
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
    CMD wget -qO- http://127.0.0.1/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
