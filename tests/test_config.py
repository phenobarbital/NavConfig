import os

# set configuration for navconfig
os.environ['NAVCONFIG_ENV'] = 'drive'
with open('file_env', 'r') as f:
    file_id = f.read().replace('\n', '')
os.environ['NAVCONFIG_DRIVE_CLIENT'] = 'credentials.txt'
os.environ['NAVCONFIG_DRIVE_ID'] = file_id

from navconfig import config, BASE_DIR, DEBUG
from navconfig.conf import adwh_url, DEBUG, dwh_url, CACHE_URL

print(config)
print('base dir is: ', BASE_DIR)
print('debug is: ', DEBUG)
print('cache is: ', CACHE_URL)
