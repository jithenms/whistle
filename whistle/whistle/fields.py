import base64

import boto3
import redis
from django.conf import settings
from django.core import checks
from django.db import models

from whistle import utils


class EncryptedField(models.CharField):
    def __init__(self, key_id, cache_expiry=2592000, *args, **kwargs):
        kwargs.setdefault("editable", True)
        self.key_id = key_id
        self.cache_expiry = cache_expiry
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

    @property
    def _redis_client(self):
        return redis.from_url(settings.REDIS_CACHE_URL)

    def get_db_prep_value(self, value, connection, prepared=False):
        if isinstance(value, str) and value:
            response = self._kms_client.encrypt(
                KeyId=self.key_id, Plaintext=value.encode()
            )
            return super().get_db_prep_value(
                base64.b64encode(response["CiphertextBlob"]).decode(),
                connection,
                prepared,
            )
        return super().get_db_prep_value(value, connection, prepared)

    def from_db_value(self, value, expression, connection):
        if value:
            cipher_hash = utils.perform_hash(value)
            cache = self._redis_client.get(f"whistle:{cipher_hash}")
            if cache:
                return cache.decode()
            else:
                response = self._kms_client.decrypt(
                    CiphertextBlob=base64.b64decode(value.encode())
                )
                data = response["Plaintext"].decode()
                self._redis_client.set(
                    f"whistle:{cipher_hash}", data, ex=self.cache_expiry
                )
                return data
        return value

    def to_python(self, value):
        return value
