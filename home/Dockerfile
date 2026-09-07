# Production Dockerfile for devify-home
FROM node:18-alpine AS builder

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build VitePress site
RUN npm run docs:build

# Production stage - nginx
FROM nginx:alpine

# Remove default nginx index.html
RUN rm -f /usr/share/nginx/html/index.html

# Copy built files from builder
COPY --from=builder /app/docs/.vitepress/dist /usr/share/nginx/html

# Copy custom nginx configuration for SPA routing
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
