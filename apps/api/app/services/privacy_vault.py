from __future__ import annotations

import base64
import json
import os
from datetime import UTC, datetime
from typing import Any


class VaultEncryptionUnavailable(RuntimeError):
    pass


class PrivacyVaultService:
    """Privacy-safe vault export helpers.

    Plain vault exports are redacted JSON. Encrypted vault exports use the optional
    `cryptography` package and a passphrase-derived Fernet key.
    """

    format_version = "self-learning-vision.vault.v1"

    def wrap_plain_export(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "format": self.format_version,
            "encrypted": False,
            "created_at": datetime.now(UTC).isoformat(),
            "payload": payload,
        }

    def encrypt_export(self, payload: dict[str, Any], passphrase: str) -> dict[str, Any]:
        fernet, salt = self._fernet_from_passphrase(passphrase)
        wrapped = self.wrap_plain_export(payload)
        ciphertext = fernet.encrypt(json.dumps(wrapped).encode("utf-8")).decode("utf-8")
        return {
            "format": self.format_version,
            "encrypted": True,
            "created_at": datetime.now(UTC).isoformat(),
            "kdf": "PBKDF2HMAC-SHA256",
            "iterations": 390000,
            "salt": base64.urlsafe_b64encode(salt).decode("utf-8"),
            "ciphertext": ciphertext,
        }

    def decrypt_export(self, vault: dict[str, Any], passphrase: str) -> dict[str, Any]:
        salt_value = vault.get("salt")
        ciphertext = vault.get("ciphertext")
        if not isinstance(salt_value, str) or not isinstance(ciphertext, str):
            raise ValueError("Encrypted vault payload is missing salt or ciphertext")
        try:
            salt = base64.urlsafe_b64decode(salt_value.encode("utf-8"))
        except Exception as exc:
            raise ValueError("Encrypted vault salt is invalid") from exc
        fernet, _ = self._fernet_from_passphrase(passphrase, salt=salt)
        try:
            plaintext = fernet.decrypt(ciphertext.encode("utf-8"))
            payload = json.loads(plaintext.decode("utf-8"))
        except Exception as exc:
            raise ValueError("Could not decrypt vault payload") from exc
        if not isinstance(payload, dict) or payload.get("format") != self.format_version:
            raise ValueError("Vault format is not supported")
        return payload

    def _fernet_from_passphrase(self, passphrase: str, *, salt: bytes | None = None):
        if len(passphrase) < 8:
            raise ValueError("Vault passphrase must be at least 8 characters")
        try:
            from cryptography.fernet import Fernet
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        except Exception as exc:
            raise VaultEncryptionUnavailable(
                "Encrypted vault export requires optional dependency: cryptography"
            ) from exc

        salt = salt or os.urandom(16)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=390000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))
        return Fernet(key), salt
