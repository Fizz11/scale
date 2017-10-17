ARG BUILD_IMAGE=geoint/scale-build

### Run build of UI and docs
FROM $BUILD_IMAGE as scale-build

# build arg to set the version qualifier. This should be blank for a
# release build. Otherwise it is typically a build number or git hash.
# if present, the qualifier will be '.${BUILDNUM}
ARG BUILDNUM=''

COPY pip/.cache /root/.cache
COPY . /tmp/scale
COPY scale/__init__.py.template /tmp/scale/scale/__init__.py
COPY pip/*.txt /tmp/

# By default build the docs
ARG BUILD_DOCS=1

# Apply build number
RUN if [[ ${BUILDNUM}x != x ]]; then sed -i "s/___BUILDNUM___/+${BUILDNUM}/" /tmp/scale/scale/__init__.py; fi \
 # Build documentation
 && if [ $BUILD_DOCS -eq 1 ]; then pip install -r /tmp/requirements.txt; make -C /tmp/scale/docs code_docs html; fi 
