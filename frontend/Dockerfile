FROM node:20-bookworm-slim AS build
WORKDIR /app

ARG VITE_API_URL=/api
ARG VITE_ANALYTICS_ENABLED=false
ARG VITE_POSTHOG_KEY=
ARG VITE_POSTHOG_HOST=https://app.posthog.com
ARG VITE_SENTRY_DSN=
ARG VITE_SENTRY_TRACES_SAMPLE_RATE=0.05

ENV VITE_API_URL=$VITE_API_URL \
    VITE_ANALYTICS_ENABLED=$VITE_ANALYTICS_ENABLED \
    VITE_POSTHOG_KEY=$VITE_POSTHOG_KEY \
    VITE_POSTHOG_HOST=$VITE_POSTHOG_HOST \
    VITE_SENTRY_DSN=$VITE_SENTRY_DSN \
    VITE_SENTRY_TRACES_SAMPLE_RATE=$VITE_SENTRY_TRACES_SAMPLE_RATE

COPY package.json package-lock.json* ./

RUN npm cache clean --force
RUN npm ci --legacy-peer-deps || npm install --legacy-peer-deps --include=dev

COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]