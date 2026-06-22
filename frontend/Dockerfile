FROM node:22-alpine AS build
WORKDIR /app/frontend
ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
COPY frontend/package*.json ./
RUN npm ci
COPY frontend .
RUN npm run build

FROM node:22-alpine
WORKDIR /app/frontend
RUN npm install -g serve
COPY --from=build /app/frontend/dist ./dist
EXPOSE 5173
CMD ["serve", "-s", "dist", "-l", "5173"]
