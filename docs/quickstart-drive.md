= Start Using NavConfig with Google Drive =

== Preamble ==

Users can use Google Drive to storing Environment variables, as a text environment file.

== QuickStart ==

For start using Google Drive for saving secrets, you need to configure Google OAuth2 authentication, Drive API requires OAuth2.0 for authentication, this module uses pyDrive for connection.


== Pre-requisites ==

1. Go to *[Google APIs Console](https://console.developers.google.com/iam-admin/projects)* and make your own project.
2. Go to "API and Services", click on "Library"
3. Search for ‘Google Drive API’, select the entry, and click ‘Enable’.
4. Select ‘Credentials’ from the left menu, click ‘Create Credentials’, select ‘OAuth client ID’.
5. Now, the product name and consent screen need to be set -> click ‘Configure consent screen’ and follow the instructions.
6. Finish configure the Application:
  a. Configure the Application, select "Application Type" to be Web Application
  b. Enter an appropiate Name for the application
  c. put in ‘Authorized JavaScript origins’: http://localhost:8090
  d. put in ‘Authorized redirect URIs’. the same URL: http://localhost:8090/
  e. Click on "SAVE"

7. Once you finished of configuring the Application, Click on ‘Download JSON’ on the right side of Client ID to download the secret.json file.
8. rename file to "client_secrets.json" and put in the root of the working directory.

When you're ready to use Google Drive, let's move out to use it.

== Using Config via Google Drive ==

1. Upload a File to Google Drive
2. Click on 'Get Link', in the link (something like this https://drive.google.com/file/d/{ID}/view?usp=sharing) the number after **/d/** is the **File ID**
3. Put the ID of the file in a environment variable, called:

`os.environ['NAVCONFIG_DRIVE_ID']`

before to invoking NavConfig.

4. Put the other two expected environment variables before invoking NavConfig:

`os.environ['NAVCONFIG_ENV'] = 'drive'
os.environ['NAVCONFIG_DRIVE_CLIENT'] = 'credentials.txt'`

Note: the last file (credentials.txt) creates a File for saving the credentials and reuse for next authentications.

5. And that's it!, when you try to load NavConfig:

`from navconfig import config, BASE_DIR, DEBUG`

NavConfig will try to use Google Drive as Source of Environment Variables.
