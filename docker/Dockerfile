#FROM python:3.10.14-slim
FROM --platform=$TARGETPLATFORM python:3.9.19-alpine
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

USER root
RUN mkdir -p /usr/kindleear /data
WORKDIR /usr/kindleear
COPY ./config.py ./tools/update_req.py ./docker/gunicorn.conf.py ./main.py ./
COPY ./tools/mp3cat/*mp3cat /usr/local/bin/

#RUN python update_req.py docker[all]
RUN python update_req.py docker && \
    pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    chmod +x /usr/local/bin/*mp3cat

COPY ./application/ ./application/

EXPOSE 8000

CMD ["/usr/local/bin/gunicorn", "-c", "/usr/kindleear/gunicorn.conf.py", "main:app"]
