#step 1
#FROM python:3.10.14-slim AS req_builder
FROM python:3.9.19-alpine AS req_builder
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /usr/site/
COPY ./config.py .
COPY ./tools/update_req.py .
RUN python update_req.py docker

#step 2
#FROM python:3.10.14-slim
FROM python:3.9.19-alpine
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

USER root
RUN mkdir -p /usr/site /data
WORKDIR /usr/site
RUN pip install --upgrade pip
COPY --from=req_builder /usr/site/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./docker/gunicorn.conf.py .
COPY ./main.py .
COPY --from=req_builder /usr/site/config.py .
COPY ./application/ ./application/

EXPOSE 8000

CMD ["/usr/local/bin/gunicorn", "-c", "/usr/site/gunicorn.conf.py", "main:app"]
