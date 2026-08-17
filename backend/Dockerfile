# The API image. Python 3.12 because every dependency ships a 3.12 wheel — on a newer
# version pip builds numpy and scikit-learn from source, turning 1 minute into 20.
FROM python:3.12-slim

# PYTHONUNBUFFERED is not cosmetic here: without it `docker logs` shows nothing until
# the buffer flushes, and a process dying mid-buffer takes the explanation with it.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies before source, so editing a route does not reinstall scikit-learn.
COPY requirements.txt ./
RUN pip install -r requirements.txt

# `app/data` travels with the image on purpose: the seeded patent corpus is what lets
# the platform run with no API keys and no external call on the first page load.
COPY app ./app
COPY scripts ./scripts

# Root in a container is one escape from root on the host, and this app writes nothing.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Standard library, because `curl` is not in the slim image and is not worth a layer.
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD python -c "import sys,urllib.request; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else 1)"

# One worker per container: scale by adding containers, so a restart takes out one.
# --proxy-headers takes the client IP and scheme from nginx rather than the container.
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
