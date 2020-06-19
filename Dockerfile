FROM python:3.7-alpine
MAINTAINER Adam Wong <bh.wong@gmail.com>

# install required packages
RUN apk add --update tini && \
    apk add --no-cache tzdata && \
    pip install --upgrade pip && \
    pip install gunicorn && \
    pip install falcon && \
    pip install mysql-connector && \
    pip install influxdb && \
    pip install orionsdk && \
    pip install sqlparse

# copy the app folder for execution
COPY ./app /app

# Set the startup working directory
WORKDIR /app

# Define port for exposure
EXPOSE 80

# Define entry point and startup command
ENTRYPOINT ["/sbin/tini", "--"]
CMD ["gunicorn", "-w 6", "-b :80", "-t 300", "main:app"]
