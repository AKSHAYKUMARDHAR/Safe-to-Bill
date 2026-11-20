FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY safe_to_bill/ safe_to_bill/
COPY api/ api/
COPY prompts/ prompts/
COPY data/ data/
# Train the ML baseline at build time so the image is self-contained.
RUN python -m safe_to_bill.generator && python -m safe_to_bill.ml_baseline

# Run as a non-root user; GEMINI_API_KEY is passed at runtime, never baked into the image.
RUN useradd --create-home app && mkdir -p logs && chown -R app /app
USER app
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
