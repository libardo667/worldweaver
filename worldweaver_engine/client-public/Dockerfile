FROM node:20-alpine

WORKDIR /app/client-public

COPY client-public/package*.json ./
RUN npm ci

COPY client-public/ ./

EXPOSE 5174

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5174"]
