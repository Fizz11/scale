ARG IMAGE=centos:7
FROM $IMAGE

MAINTAINER Scale Developers "https://github.com/ngageoint/scale"

## By default install epel-release, if our base image already includes this we can set to 0
ARG EPEL_INSTALL=1

RUN if [ "$EPEL_INSTALL" -eq 1 ]; then yum install -y epel-release; fi \
	&& yum -y groupinstall 'Development Tools' \
	&& yum install -y python-devel python-pip nodejs \
	&& yum install -y openssl-devel libffi-devel gdal geos \
	&& yum clean all
RUN pip install -U pip wheel

