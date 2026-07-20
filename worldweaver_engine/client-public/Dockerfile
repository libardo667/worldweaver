FROM node:20-alpine AS build

WORKDIR /app/client-public

COPY client-public/package*.json ./
RUN npm ci

COPY client-public/ ./
RUN npm run build

FROM node:20-alpine AS runtime

WORKDIR /app/client-public

ENV NODE_ENV=production

COPY client-public/server.mjs ./server.mjs
COPY --from=build /app/client-public/dist ./dist

EXPOSE 5174

CMD ["node", "server.mjs"]
