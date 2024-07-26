import base64

import boto3
from django.core import checks
from django.db import models


class EncryptedField(models.TextField):
    def __init__(self, key_id, *args, **kwargs):
        kwargs.setdefault("editable", True)
        self.key_id = key_id
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs["key_id"] = self.key_id
        return name, path, args, kwargs

    def check(self, **kwargs):
        extra_checks = list()
        if self.key_id is None:
            extra_checks.append(
                checks.Error(
                    "EncryptedField must define a key_id.",
                    obj=self,
                )
            )

        return [
            *super().check(**kwargs),
            *extra_checks,
        ]

    @property
    def _kms_client(self):
        return boto3.client("kms", region_name="us-east-1")

    def get_db_prep_value(self, value, connection, prepared=False):
        if isinstance(value, str):
            response = self._kms_client.encrypt(KeyId=self.key_id, Plaintext=value)
            return super().get_db_prep_value(
                base64.b64encode(response["CiphertextBlob"]).decode(),
                connection,
                prepared,
            )
        return super().get_db_prep_value(value, connection, prepared)

    def from_db_value(self, value, expression, connection):
        if value:
            response = self._kms_client.decrypt(
                CiphertextBlob=base64.b64decode(value.encode())
            )
            return response["Plaintext"].decode()
        return value

    def to_python(self, value):
        return value
