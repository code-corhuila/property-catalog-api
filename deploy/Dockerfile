FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir . && rm -rf src build
COPY apps ./apps
USER 10001
EXPOSE 3002
CMD ["python", "-m", "apps.api"]
