# PokerKit Holdem - Frontend Dockerfile
# Multi-stage build with nginx for production

# =============================================================================
# Stage 1: Dependencies
# =============================================================================
FROM node:20-alpine as deps

WORKDIR /app

# Install dependencies only when needed
COPY package.json pnpm-lock.yaml* ./

# Install pnpm and dependencies
RUN corepack enable pnpm && \
    pnpm install --frozen-lockfile


# =============================================================================
# Stage 2: Builder
# =============================================================================
FROM node:20-alpine as builder

WORKDIR /app

# Copy dependencies from deps stage
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Build arguments for environment
ARG VITE_API_URL=/api
ARG VITE_WS_URL=/ws

ENV VITE_API_URL=$VITE_API_URL
ENV VITE_WS_URL=$VITE_WS_URL

# Build the application
RUN corepack enable pnpm && \
    pnpm run build


# =============================================================================
# Stage 3: Production with Nginx
# =============================================================================
FROM nginx:1.25-alpine as production

# Copy custom nginx config
COPY nginx.conf /etc/nginx/nginx.conf

# Copy built assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Add non-root user
RUN adduser -D -g '' appuser && \
    chown -R appuser:appuser /usr/share/nginx/html && \
    chown -R appuser:appuser /var/cache/nginx && \
    chown -R appuser:appuser /var/log/nginx && \
    touch /var/run/nginx.pid && \
    chown -R appuser:appuser /var/run/nginx.pid

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost/health || exit 1

# Run nginx
CMD ["nginx", "-g", "daemon off;"]


# =============================================================================
# Stage 4: Development (optional)
# =============================================================================
FROM node:20-alpine as development

WORKDIR /app

# Copy dependencies
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Install pnpm
RUN corepack enable pnpm

EXPOSE 5173

CMD ["pnpm", "run", "dev", "--host", "0.0.0.0"]
