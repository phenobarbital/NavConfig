import os
import logging
from navconfig.loaders.base import BaseLoader
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.CRITICAL)


class driveLoader(BaseLoader):
    drive = None
    file_id = None

    def __init__(self, **kwargs):
        self.file_id = os.getenv('NAVCONFIG_DRIVE_ID')
        client = os.getenv('NAVCONFIG_DRIVE_CLIENT')
        if self.file_id and client:
            gauth = GoogleAuth()
            gauth.LoadCredentialsFile(client)
            if gauth.credentials is None:
                # Authenticate if they're not there
                gauth.LocalWebserverAuth() # Creates local webserver and auto handles authentication.
                # Save the current credentials to a file
            elif gauth.access_token_expired:
                gauth.Refresh()
            else:
                gauth.Authorize()
            gauth.SaveCredentialsFile(client)
            print("Google Auth Success")
            self.drive = GoogleDrive(gauth)
        else:
            raise Exception('Config Google Drive Error: you need to provide **NAVCONFIG_DRIVE_CLIENT** for client configuration')

    def load_enviroment(self):
        try:
            env = self.drive.CreateFile({'id': self.file_id})
            content = env.GetContentString()
            if content:
                self.load_from_string(content)
        except Exception as err:
            raise Exception('Error loading Environment: {}'.format(err))

    def save_enviroment(self, path:str=None):
        try:
            env = self.drive.CreateFile({'id': self.file_id})
            content = env.GetContentString()
            if content:
                with open(path, 'w+') as f:
                    f.write(content)
        except Exception as err:
            raise Exception('Error Saving Environment: {}'.format(err))
