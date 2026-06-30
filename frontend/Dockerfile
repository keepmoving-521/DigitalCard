FROM node:22-alpine AS build

ARG APP_WORKSPACE
ARG OUTPUT_DIR
ARG VITE_API_BASE_URL=http://localhost:8000/api/v1
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

WORKDIR /app
COPY package.json ./
COPY frontend/admin/package.json ./frontend/admin/package.json
COPY frontend/h5/package.json ./frontend/h5/package.json
RUN npm install
COPY frontend ./frontend
RUN npm run build -w $APP_WORKSPACE && cp -r $OUTPUT_DIR /output

FROM nginx:1.27-alpine AS runtime
COPY deploy/nginx/spa.conf /etc/nginx/conf.d/default.conf
COPY --from=build /output /usr/share/nginx/html
EXPOSE 80
