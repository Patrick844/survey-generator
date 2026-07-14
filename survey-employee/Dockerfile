# Stage 1 — build the React app
FROM node:20-alpine AS builder

WORKDIR /app

# Backend URL baked into the bundle (browser calls it directly). Overridden at
# build time via --build-arg VITE_API_BASE=... (wired through docker-compose).
ARG VITE_API_BASE=http://localhost:8000
ENV VITE_API_BASE=$VITE_API_BASE

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# Stage 2 — serve the static build with nginx
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
