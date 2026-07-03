# Build stage — Flutter Web requires the full Flutter SDK
FROM ghcr.io/cirruslabs/flutter:3.22.0 AS build

WORKDIR /app
COPY frontend/web /app

ARG API_BASE_URL=http://localhost:8000
ARG WS_URL=ws://localhost:8000/ws
ENV API_BASE_URL=${API_BASE_URL}
ENV WS_URL=${WS_URL}

RUN flutter pub get \
 && flutter build web --release \
    --dart-define=API_BASE_URL=${API_BASE_URL} \
    --dart-define=WS_URL=${WS_URL}

# Runtime stage — static nginx
FROM nginx:1.27-alpine
COPY --from=build /app/build/web /usr/share/nginx/html
COPY frontend/web/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD wget -qO- http://localhost/ >/dev/null || exit 1