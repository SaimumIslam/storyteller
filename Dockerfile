FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-ben poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md LICENSE config.yaml rules.yaml rules-en.yaml rules-islamic.yaml .env.example ./
COPY styles/ styles/
COPY src/ src/
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu .

# Mount your library here: books/, data/ (index), output/ and optionally .env
ENV STORYTELLER_HOME=/library
VOLUME /library

ENTRYPOINT ["storyteller"]
CMD ["--help"]
