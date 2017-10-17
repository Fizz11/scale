ARG BUILD_IMAGE=geoint/scale-build

### Compile any non-binary packages into wheels
### Context should be scale/pip
FROM $BUILD_IMAGE as scale-packages
COPY *.txt /tmp/
RUN pip install -r /tmp/requirements.txt \
    && pip install -r /tmp/production.txt
