# Use prod/ env/.env for production settings
from navconfig import config, BASE_DIR

print("Current Environment:", config.ENV)
print('PRODUCTION:', config.PRODUCTION)
print("OKTA_CLIENT_ID:", config.get('OKTA_CLIENT_ID'))
