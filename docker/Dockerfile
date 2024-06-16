#step 1
FROM --platform=$TARGETPLATFORM python:3.9.19-alpine AS builder
ARG TARGETPLATFORM
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

USER root
RUN mkdir -p /usr/kindleear
WORKDIR /usr/kindleear
COPY ./config.py ./tools/update_req.py ./
COPY ./tools/mp3cat/*mp3cat /usr/kindleear/tools/
RUN if [ "$TARGETPLATFORM" = "linux/arm64" ]; then \
        rm -f /usr/kindleear/tools/mp3cat; \
        mv /usr/kindleear/tools/arm64_mp3cat /usr/kindleear/tools/mp3cat; \
    fi
RUN python update_req.py docker $TARGETPLATFORM

#step 2
FROM --platform=$TARGETPLATFORM python:3.9.19-alpine
ARG TARGETPLATFORM
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

USER root
RUN mkdir -p /usr/kindleear /data
WORKDIR /usr/kindleear
COPY --from=builder /usr/kindleear/config.py /usr/kindleear/requirements.txt ./
COPY --from=builder /usr/kindleear/tools/mp3cat /usr/local/bin/mp3cat
COPY ./docker/gunicorn.conf.py ./main.py ./

#apk add libstdc++ && \
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    chmod +x /usr/local/bin/mp3cat

COPY ./application/ ./application/

EXPOSE 8000

CMD ["/usr/local/bin/gunicorn", "-c", "/usr/kindleear/gunicorn.conf.py", "main:app"]
