ARG BUILD_IMAGE=geoint/scale-build

### Run build of UI and docs
FROM $BUILD_IMAGE as scale-build

COPY . /tmp/ui

RUN cd /tmp/ui \
 && tar xf node_modules.tar.gz \
 && tar xf bower_components.tar.gz \
 && npm install \
 && node node_modules/gulp/bin/gulp.js dist
