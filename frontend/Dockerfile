# --- build ---------------------------------------------------------------
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
# same-origin API calls; nginx proxies /api -> backend
ENV VITE_API_BASE=/api
RUN npm run build

# --- serve --------------------------------------------------------------
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=5 \
    CMD wget -qO- http://localhost/ >/dev/null 2>&1 || exit 1
