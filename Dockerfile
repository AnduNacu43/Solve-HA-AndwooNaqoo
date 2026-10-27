# Hype Arena run image: stdlib only, no pip, no model at run time.
# data/ carries the lexicon, templates and B's baked files (data/baked/).
# tests/c/stubs/ is the fallback arena.generate.deps uses for any A/B module
# that fails to import; with every module merged it is never loaded.
FROM python:3.12-slim

# user 10001 has no home and only /tmp and /output are writable
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp

WORKDIR /app
COPY arena/ arena/
COPY data/ data/
COPY tests/c/stubs/ tests/c/stubs/
# COPY keeps the checkout's file modes; a file only its owner can read would
# be unreadable to user 10001, so make everything readable (dirs searchable)
RUN python -m compileall -q arena tests/c/stubs && chmod -R a+rX /app

ENTRYPOINT ["python", "-m", "arena"]
USER 10001
