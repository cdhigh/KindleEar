#step 1
FROM --platform=$TARGETPLATFORM python:3.9.19-alpine AS builder
ARG TARGETPLATFORM
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

USER root
RUN mkdir -p /usr/kindleear /data
WORKDIR /usr/kindleear
COPY ./application/ ./application/
COPY ./docker/ ./docker/
COPY ./tools/ ./tools/
COPY ./main.py ./config.py ./
RUN python /usr/kindleear/tools/update_req.py docker $TARGETPLATFORM

#update recipes
RUN apk add --no-cache git && \
    git clone --depth 1 https://github.com/kovidgoyal/calibre && \
    rm -f /usr/kindleear/application/recipes/builtin_recipes.* && \
    mv -f /usr/kindleear/calibre/recipes/*.recipe /usr/kindleear/application/recipes/ && \
    pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    python /usr/kindleear/tools/archive_builtin_recipes.py -q && \
    rm -f /usr/kindleear/application/recipes/*.recipe

#choose mp3cat by arch
RUN if [ "$TARGETPLATFORM" = "linux/arm64" ]; then \
        rm -f /usr/kindleear/tools/mp3cat/mp3cat; \
        mv /usr/kindleear/tools/mp3cat/arm64_mp3cat /usr/kindleear/tools/mp3cat/mp3cat; \
    fi

#step 2
FROM --platform=$TARGETPLATFORM python:3.9.19-alpine
ARG TARGETPLATFORM
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

USER root
RUN mkdir -p /usr/kindleear /data
WORKDIR /usr/kindleear
COPY --from=builder /usr/kindleear/config.py /usr/kindleear/requirements.txt ./
COPY --from=builder /usr/kindleear/tools/mp3cat/mp3cat /usr/local/bin/mp3cat
COPY ./docker/run_docker.sh /usr/local/bin/run_docker.sh
COPY ./docker/gunicorn.conf.py ./main.py ./

#apk add libstdc++ && \
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    chmod +x /usr/local/bin/mp3cat /usr/local/bin/run_docker.sh

COPY ./application/ ./application/
COPY --from=builder /usr/kindleear/application/recipes/builtin_recipes.* ./application/recipes/

EXPOSE 8000

CMD ["/usr/local/bin/run_docker.sh"]
