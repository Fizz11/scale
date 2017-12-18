import sys
import urllib
import zipfile
import tarfile

TEMP_ZIP_FILE_LOCATION = "/tmp/tempfile.zip"
CONFIGJSON_FILE_NAME = "/usr/lib/python2.7/site-packages/botocore/data/endpoints.json"


def designate_endpoints(tar_zip_url, certs_endpoints_url):
    print("in designate_endpoints")
    if tar_zip_url and certs_endpoints_url:  # check existance of CERTS_ENDPOINTS_URL and CERTS_TAR_ZIP
        tar_zip_split = tar_zip_url.split(".")
        if tar_zip_split[-1] == "zip":  # zip file
            urllib.urlretrieve(certs_endpoints_url, CONFIGJSON_FILE_NAME)
            urllib.urlretrieve(tar_zip_url, TEMP_ZIP_FILE_LOCATION)
            zipped_certs = zipfile.ZipFile(TEMP_ZIP_FILE_LOCATION)
            zipped_certs.extractall("/etc/pki/ca-trust/source/anchors")

            # unzip
            # move to /etc/pki/ca-trust/source/anchors
        elif tar_zip_split[-1] == "gz" or tar_zip_split[-1] == "bz2":  # tar file
            urllib.urlretrieve(certs_endpoints_url, CONFIGJSON_FILE_NAME)
            urllib.urlretrieve(tar_zip_url, TEMP_ZIP_FILE_LOCATION)
            tar = tarfile.open(TEMP_ZIP_FILE_LOCATION)
            tar.extractall("/etc/pki/ca-trust/source/anchors")
            # untar
            # move to /etc/pki/ca-trust/source/anchors
        else:
            x = 4
            #TODO 
            # bad file name
            # throw warning?
            #??????????????
            # do nothing?????

print("yo we in \n")
designate_endpoints(sys.argv[0], sys.argv[1])
print("we done")
