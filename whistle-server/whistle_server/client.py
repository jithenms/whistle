import json

import google
from google.oauth2 import service_account
from pyapns_client import APNSClient
from pyfcm import FCMNotification
from pyfcm.errors import InvalidDataError


class CustomAPNSClient(APNSClient):
    def _get_auth_key(auth_key):
        return auth_key


class CustomFCMNotification(FCMNotification):
    def _get_access_token(self):
        # get OAuth 2.0 access token
        try:
            if self.service_account_file:
                credentials = service_account.Credentials.from_service_account_info(
                    json.loads(self.service_account_file, strict=False),
                    scopes=["https://www.googleapis.com/auth/firebase.messaging"],
                )
            else:
                credentials = self.credentials
            request = google.auth.transport.requests.Request()
            credentials.refresh(request)
            return credentials.token
        except Exception as e:
            raise InvalidDataError(e)
