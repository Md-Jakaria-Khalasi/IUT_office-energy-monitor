# Frontend Dockerfile (project root: frontend/)
# Two-stage build:
#   1) flutter build web with API_BASE_URL / WS_URL baked in
#   2) nginx:alpine serving the SPA build with SPA-friendly routing
FROM ghcr.io/cirruslabs/flutter:3.35.4 AS builder

WORKDIR /app

# Cache pub deps separately
COPY pubspec.yaml ./
COPY pubspec.lock* ./
RUN flutter pub get

# Now copy the rest of the source and build
COPY . .
ARG API_BASE_URL=http://127.0.0.1:8001
ARG WS_URL=ws://127.0.0.1:8001/ws
ENV API_BASE_URL=${API_BASE_URL}
ENV WS_URL=${WS_URL}

RUN flutter build web --release \
    --dart-define=API_BASE_URL=${API_BASE_URL} \
    --dart-define=WS_URL=${WS_URL}

# Runtime stage — static nginx
FROM nginx:1.27-alpine
COPY --from=builder /app/build/web /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
