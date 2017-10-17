### Final Scale image
ARG IMAGE=geoint/scale-base
FROM $IMAGE
MAINTAINER Scale Developers "https://github.com/ngageoint/scale"

LABEL \
    VERSION="5.1.1-snapshot" \
    RUN="docker run -d geoint/scale scale_scheduler" \
    SOURCE="https://github.com/ngageoint/scale" \
    DESCRIPTION="Processing framework for containerized algorithms" \
    CLASSIFICATION="UNCLASSIFIED"

EXPOSE 80

# recognized environment variables
# CONFIG_URI
# DCOS_OAUTH_TOKEN authentication for Marathon deployments when DCOS OAuth is enabled
# DCOS_PACKAGE_FRAMEWORK_NAME used to inject a configurable framework name allowing for multiple scale frameworks per cluster
# DCOS_PASS authentication for Marathon deployments when using DCOS enterprise
# DCOS_SERVICE_ACCOUNT a DCOS account name with read/update/create/delete access to the secrets store
# DCOS_USER authentication for Marathon deployments when using DCOS enterprise
# DEPLOY_WEBSERVER to start the web server container
# ENABLE_BOOTSTRAP true to initialize database and bootstrap supporting containers, should only be set on scheduler in DCOS
# ENABLE_WEBSERVER true to start the RESTful API server, should only be set on webserver app
# LOGSTASH_DOCKER_IMAGE the name of the Docker image for logstash
# MARATHON_APP_DOCKER_IMAGE used in Marathon to autodetect Scale docker image
# MESOS_MASTER_URL
# NPM_URL
# PYPI_URL
# SCALE_DB_HOST
# SCALE_DB_NAME
# SCALE_DB_PASS
# SCALE_DB_PORT
# SCALE_DB_USER
# SCALE_DEBUG
# SCALE_DOCKER_IMAGE used for explicit override of docker image used, not needed in Marathon
# SCALE_ELASTICSEARCH_URLS
# SCALE_LOGGING_ADDRESS
# SCALE_WEBSERVER_CPU
# SCALE_WEBSERVER_MEMORY
# SCALE_ZK_URL
# SECRETS_SSL_WARNINGS false to silence SSL warnings from secrets transactions, true (defualt) to raise them.
# SECRETS_TOKEN used for authenticating Scale against Vault or DCOS Secrets Store
# SECRETS_URL used for linking Scale to a secrets storage service (works with Vault and DCOS Secrets Store)

# Default location for the GOSU binary to be retrieved from.
# This should be changed on disconnected networks to point to the directory with the tarballs.
ARG GOSU_URL=https://github.com/tianon/gosu/releases/download/1.9/gosu-amd64

# install required packages for scale execution
COPY scale /opt/scale
COPY dist/ui /opt/scale/ui
COPY dist/__init__.py /opt/scale/scale/__init__.py
COPY scale/pip/.cache /root/.cache

COPY scale/pip/production.txt /tmp/
COPY dockerfiles/framework/scale/mesos-0.25.0-py2.7-linux-x86_64.egg /tmp/
COPY dockerfiles/framework/scale/*shim.sh /tmp/

# setup the scale user and sudo so mounts, etc. work properly
RUN ls -lha /root/.cache && useradd --uid 7498 -M -d /opt/scale scale
#COPY dockerfiles/framework/scale/scale.sudoers /etc/sudoers.d/scale

# Shim in any environment specific configuration from script
RUN sh /tmp/env-shim.sh \
 && pip install -r /tmp/production.txt \
 && easy_install /tmp/*.egg \
 && curl -o /usr/bin/gosu -fsSL ${GOSU_URL} \
 && chmod +sx /usr/bin/gosu 

# Apply Apache configuration and enable CORS in Apache
RUN sed -i 's^User apache^User scale^g' /etc/httpd/conf/httpd.conf \
 # Patch access logs to show originating IP instead of reverse proxy.
 && sed -i 's!LogFormat "%h!LogFormat "%{X-Forwarded-For}i %h!g' /etc/httpd/conf/httpd.conf \
 && sed -ri \
		-e 's!^(\s*CustomLog)\s+\S+!\1 /proc/self/fd/1!g' \
		-e 's!^(\s*ErrorLog)\s+\S+!\1 /proc/self/fd/2!g' \
		/etc/httpd/conf/httpd.conf \
 && echo 'Header set Access-Control-Allow-Origin "*"' > /etc/httpd/conf.d/cors.conf 

# install the source code and config files
COPY dockerfiles/framework/scale/entryPoint.sh /opt/scale/
COPY dockerfiles/framework/scale/*.py /opt/scale/
COPY dockerfiles/framework/scale/app-templates/* /opt/scale/app-templates/
COPY dockerfiles/framework/scale/scale.conf /etc/httpd/conf.d/scale.conf
COPY scale/scale/local_settings_docker.py /opt/scale/scale/local_settings.py
COPY dockerfiles/framework/scale/country_data.json.bz2 /opt/scale/

WORKDIR /opt/scale

# setup ownership and permissions. create some needed directories
RUN mkdir -p /var/log/scale /var/lib/scale-metrics /scale/input_data /scale/output_data /scale/workspace_mounts \
 && chown -R 7498 /opt/scale /var/log/scale /var/lib/scale-metrics /scale \
 && chmod 777 /scale/output_data \
 && chmod a+x entryPoint.sh
# Issues with DC/OS, so run as root for now..shouldn't be a huge security concern
#USER 7498

# finish the build
RUN python manage.py collectstatic --noinput --settings=

ENTRYPOINT ["./entryPoint.sh"]
