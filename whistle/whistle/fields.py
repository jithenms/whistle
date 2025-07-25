import base64

import aws_encryption_sdk
from django.core import checks
from django.db import models

from whistle import settings

kms_client = aws_encryption_sdk.EncryptionSDKClient()

kms_cache = aws_encryption_sdk.LocalCryptoMaterialsCache(settings.KMS_CACHE_CAPACITY)


class EncryptedFieldTypeChoices(models.TextChoices):
    PERSONAL_DATA = "PERSONAL_DATA", "PERSONAL_DATA"
    API_CREDENTIALS = "API_CREDENTIALS", "API_CREDENTIALS"


field_arns = {
    EncryptedFieldTypeChoices.PERSONAL_DATA: settings.KMS_PERSONAL_DATA_KEY_ARN,
    EncryptedFieldTypeChoices.API_CREDENTIALS: settings.KMS_API_CREDENTIALS_KEY_ARN,
}


class EncryptedField(models.CharField):
    def __init__(
        self, field_type, cache_expiry=settings.KMS_CACHE_EXPIRY, *args, **kwargs
    ):
        kwargs.setdefault("editable", True)
        self.field_type = field_type
        self.key_id = field_arns[self.field_type]
        self.kms_key_provider = aws_encryption_sdk.StrictAwsKmsMasterKeyProvider(
            key_ids=[self.key_id]
        )
        self.cache_expiry = cache_expiry
        self.cache_cmm = aws_encryption_sdk.CachingCryptoMaterialsManager(
            master_key_provider=self.kms_key_provider,
            cache=kms_cache,
            max_age=self.cache_expiry,
        )
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs["field_type"] = self.field_type
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

    def get_db_prep_value(self, value, connection, prepared=False):
        if isinstance(value, str) and value:
            cipher_text, encryptor_header = kms_client.encrypt(
                source=value.encode(),
                materials_manager=self.cache_cmm,
            )
            return super().get_db_prep_value(
                base64.b64encode(cipher_text).decode(),
                connection,
                prepared,
            )
        return super().get_db_prep_value(value, connection, prepared)

    def from_db_value(self, value, expression, connection):
        if value:
            decrypted_plaintext, decryptor_header = kms_client.decrypt(
                source=base64.b64decode(value.encode()),
                materials_manager=self.cache_cmm,
            )
            data = decrypted_plaintext.decode()
            return data
        return value

    def to_python(self, value):
        return value
