# The web image: build the bundle, then serve it from nginx. Two stages so the ~300 MB
# Node toolchain and its vulnerabilities stay out of the image that serves finished files.
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
# `npm ci`, not install: exact locked versions, and it fails if the lockfile and
# package.json disagree — so the image cannot quietly build against untested versions.
RUN npm ci

COPY . .
RUN npm run build


FROM nginx:1.27-alpine AS runtime

# Replaces the default server block rather than adding to it, so no second server on 80.
COPY nginx.conf /etc/nginx/conf.d/default.conf
# Fails the build on a bad config. Nothing else checks this file — a syntax error would
# otherwise surface as a container that starts and then fails its healthcheck.
RUN nginx -t
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --spider --quiet http://127.0.0.1/ || exit 1
