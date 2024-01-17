import hvac
import logging

# Authenticate with your Vault token
token = 'hvs.wpQEXwLqo6p9QRDWKEWkvNEO'
# Initialize the client
client = hvac.Client(url='http://localhost:8200', token=token)
if client.is_authenticated():
    logging.debug("Hashicorp Vault Connected")


# Define the path where your secret is stored
# For KV v1 secrets engine
# secret_path = 'secret/navigator/dev'

# For KV v1 secrets engine
secret_path = 'dev'

# Read the secret
# read_response = client.secrets.kv.v1.read_secret(
#     path=secret_path,
#     mount_point='navconfig',
# )

# Read the secret
secret_path = 'dev'
read_response = client.secrets.kv.v2.read_secret_version(
    path=secret_path,
    mount_point='navconfig'
)

# # Extract the value of 'CONFIG_FILE' from the secret
config_file = read_response['data']['data']['CONFIG_FILE']

print('CONFIG_FILE:', config_file)
