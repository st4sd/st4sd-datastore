ARG base_image=quay.io/st4sd/official-base/st4sd-runtime-core:latest

FROM $base_image

COPY requirements.txt /tmp/st4sd-datastore/requirements.txt

RUN  apt-get update -y && \
     apt-get install -y nginx && \
     pip install --upgrade pip setuptools && \
     rm -rf /var/lib/apt/lists/* && \
     pip install -r /tmp/st4sd-datastore/requirements.txt

COPY st4sd_datastore /tmp/st4sd-datastore/st4sd_datastore
COPY drivers /tmp/st4sd-datastore/drivers
COPY setup.py /tmp/st4sd-datastore/setup.py

RUN  pip install /tmp/st4sd-datastore/ && \
     rm -rf /tmp/st4sd-datastore

COPY scripts/* /scripts/
COPY configurations/* /configurations/

ENV PYTHONPATH=$PYTHONPATH:/venvs/st4sd-runtime-core/bin/

RUN mkdir -p /etc/nginx/conf.d/ /var/log/nginx/ /var/lib/nginx /gunicorn && \
    chmod -R 777  /etc/nginx/conf.d/ /var/log/nginx/ /var/lib/nginx /gunicorn && \
    chgrp -R 0 /etc/nginx /var/log/nginx /var/lib/nginx /gunicorn && \
    chmod -R g=u /etc/nginx /var/log/nginx /var/lib/nginx /gunicorn && \
    cp /configurations/nginx.conf /etc/nginx/nginx.conf
