"""
Encryption utilities for Local Clip Studio.

API keys and other sensitive data are encrypted at rest using
Fernet symmetric encryption (AES-256-GCM). The encryption key is
derived from a machine-specific identifier to bind encrypted data
to the hardware it was created on.

Never log or expose encryption keys.
"""

from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from backend.config.defaults import DEFAULT_STORAGE_PATH

# ─── Constants ────────────────────────────────────────────────────────────
KEY_FILE_NAME = "key.der"
KEY_ENV_VAR = "LOCALCLIP_ENCRYPTION_KEY"


def _get_machine_id() -> str:
    """
    Derive a machine-specific identifier for key binding.

    Uses /etc/machine-id on Linux, or falls back to a hash of
    hostname + os-specific paths. This means the encryption key
    is tied to the machine — copying the config to another machine
    will not work without the encryption key.
    """
    # Try Linux machine-id
    machine_id_paths = [
        Path("/etc/machine-id"),
        Path("/var/lib/dbus/machine-id"),
    ]

    for path in machine_id_paths:
        if path.exists():
            try:
                return path.read_text().strip()
            except OSError:
                continue

    # Fallback: hash of hostname + home directory
    import socket

    hostname = socket.gethostname()
    home = str(Path.home())
    return hashlib.sha256(f"{hostname}:{home}".encode()).hexdigest()[:32]


def _derive_key(machine_id: str | None = None) -> bytes:
    """
    Derive a 32-byte Fernet key from machine identity.

    The key is deterministic for a given machine but different
    across machines. If LOCALCLIP_ENCRYPTION_KEY env var is set,
    it takes precedence over machine-derived key.
    """
    env_key = os.environ.get(KEY_ENV_VAR)
    if env_key:
        # User-provided key (must be 44-character base64-encoded 32 bytes)
        try:
            return base64.urlsafe_b64decode(env_key.encode())
        except (ValueError, base64.binascii.Error):
            raise ValueError(
                f"Environment variable {KEY_ENV_VAR} must be a valid "
                f"44-character base64-encoded Fernet key"
            )

    if machine_id is None:
        machine_id = _get_machine_id()

    # Hash machine ID to 32 bytes
    key_bytes = hashlib.sha256(machine_id.encode()).digest()
    return key_bytes


def _get_fernet(key_path: Path | None = None) -> Fernet:
    """
    Get or create a Fernet instance.

    The encryption key is stored in the config directory on first use
    and reused thereafter. If the key file doesn't exist, it's created
    from the machine-derived key.
    """
    if key_path is None:
        config_dir = DEFAULT_STORAGE_PATH / "config"
        key_path = config_dir / KEY_FILE_NAME

    if key_path.exists():
        key_data = key_path.read_bytes()
    else:
        # Create deterministic key from machine identity
        key_data = _derive_key()
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_bytes(key_data)
        # Restrict permissions
        key_path.chmod(0o600)

    # Fernet expects a 32-byte url-safe base64-encoded key
    encoded_key = base64.urlsafe_b64encode(key_data)
    return Fernet(encoded_key)


def encrypt_value(plaintext: str, key_path: Path | None = None) -> str:
    """
    Encrypt a string value (e.g., API key) for storage.

    Args:
        plaintext: The value to encrypt.
        key_path: Optional custom path to the encryption key file.

    Returns:
        Encrypted token as a base64-encoded string prefixed with 'enc:'.
    """
    if not plaintext:
        return ""

    fernet = _get_fernet(key_path)
    encrypted = fernet.encrypt(plaintext.encode("utf-8"))
    return "enc:" + encrypted.decode("utf-8")


def decrypt_value(encrypted_token: str, key_path: Path | None = None) -> str:
    """
    Decrypt a previously encrypted value.

    Args:
        encrypted_token: The encrypted token (must start with 'enc:').
        key_path: Optional custom path to the encryption key file.

    Returns:
        Decrypted plaintext string.

    Raises:
        ValueError: If the token cannot be decrypted (wrong machine or
                    corrupted data).
    """
    if not encrypted_token:
        return ""

    if not encrypted_token.startswith("enc:"):
        return encrypted_token  # Not encrypted, return as-is

    try:
        fernet = _get_fernet(key_path)
        token = encrypted_token[4:]  # Strip 'enc:' prefix
        decrypted = fernet.decrypt(token.encode("utf-8"))
        return decrypted.decode("utf-8")
    except (InvalidToken, ValueError, IndexError) as exc:
        raise ValueError(
            "Failed to decrypt API key. The key may have been "
            "encrypted on a different machine, or the key file "
            "has been corrupted."
        ) from exc


def rotate_key(old_key_path: Path, new_key_path: Path, encrypted_values: list[str]) -> list[str]:
    """
    Re-encrypt values with a new key (key rotation).

    Args:
        old_key_path: Path to the current encryption key.
        new_key_path: Path where the new key will be stored.
        encrypted_values: List of encrypted tokens to re-encrypt.

    Returns:
        List of re-encrypted tokens using the new key.
    """
    # Decrypt all values with old key
    decrypted = [decrypt_value(val, old_key_path) for val in encrypted_values]

    # Generate new key
    new_config_dir = new_key_path.parent
    new_config_dir.mkdir(parents=True, exist_ok=True)
    new_key_data = _derive_key(os.urandom(32).hex())  # Use random seed for new key
    new_key_path.write_bytes(new_key_data)
    new_key_path.chmod(0o600)

    # Re-encrypt with new key
    re_encrypted = [encrypt_value(val, new_key_path) for val in decrypted]
    return re_encrypted
