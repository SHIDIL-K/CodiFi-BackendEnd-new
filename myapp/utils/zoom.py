# myapp/utils/zoom.py
import base64, requests
from django.conf import settings

def get_zoom_access_token():
    """
    Server-to-Server OAuth: exchange Client ID + Secret for a short-lived token.
    """
    url = f"https://zoom.us/oauth/token?grant_type=account_credentials&account_id={settings.ZOOM_ACCOUNT_ID}"
    auth = (settings.ZOOM_CLIENT_ID, settings.ZOOM_CLIENT_SECRET)
    response = requests.post(url, auth=auth)
    response.raise_for_status()
    return response.json()["access_token"]
