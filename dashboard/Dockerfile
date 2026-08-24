FROM node:20-alpine AS builder

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install

ARG ROUTER_URL=http://router:8080
ARG MIND_URL=http://mind:8081
ARG AGENTS_URL=http://agents:8082
ARG SENTINEL_URL=http://sentinel:8083

ENV ROUTER_URL=$ROUTER_URL
ENV MIND_URL=$MIND_URL
ENV AGENTS_URL=$AGENTS_URL
ENV SENTINEL_URL=$SENTINEL_URL

COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
