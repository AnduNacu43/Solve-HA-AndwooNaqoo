# Hype Arena run image: stdlib only, no pip, no model at run time.
# data/ carries the lexicon, templates and B's baked files (data/baked/).
# tests/c/stubs/ is the fallback arena.generate.deps uses for any A/B module
# that fails to import; with every module merged it is never loaded.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY arena/ arena/
COPY data/ data/
COPY tests/c/stubs/ tests/c/stubs/
RUN python -m compileall -q arena tests/c/stubs

ENTRYPOINT ["python", "-m", "arena"]
USER 10001
