"""
Encrypted Keystore Manager
AES-256-GCM encrypted wallet storage, ported from xrpl-cli-ng.

Replaces plaintext seeds in config/test_wallets.py with encrypted keystore files.
Each wallet is stored as a JSON file with:
  - AES-256-GCM encryption
  - PBKDF2 key derivation (600K iterations, SHA-256)
  - Random salt and IV per file
  - Optional human-readable alias
"""

import json
import os
import logging
from pathlib import Path
from typing import Optional, Dict, List
from hashlib import pbkdf2_hmac
from secrets import token_bytes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from xrpl.wallet import Wallet
from xrpl.core.keypairs import derive_keypair

logger = logging.getLogger(__name__)

DEFAULT_KEYSTORE_DIR = os.path.join(os.path.expanduser("~"), ".xrpl", "keystore")
PBKDF2_ITERATIONS = 600_000
KEY_LENGTH = 32
SALT_LENGTH = 32
IV_LENGTH = 12


class KeystoreFile:
    """Represents an encrypted keystore file."""

    def __init__(self, address: str, ciphertext: bytes, salt: bytes, iv: bytes,
                 tag: bytes, key_type: str = "ed25519", label: Optional[str] = None):
        self.address = address
        self.ciphertext = ciphertext
        self.salt = salt
        self.iv = iv
        self.tag = tag
        self.key_type = key_type
        self.label = label

    def to_dict(self) -> dict:
        return {
            "version": 1,
            "address": self.address,
            "label": self.label,
            "keyType": self.key_type,
            "kdf": "pbkdf2",
            "kdfparams": {
                "iterations": PBKDF2_ITERATIONS,
                "keylen": KEY_LENGTH,
                "digest": "sha256",
                "salt": self.salt.hex(),
            },
            "cipher": "aes-256-gcm",
            "cipherparams": {
                "iv": self.iv.hex(),
                "tag": self.tag.hex(),
            },
            "ciphertext": self.ciphertext.hex(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "KeystoreFile":
        return cls(
            address=data["address"],
            ciphertext=bytes.fromhex(data["ciphertext"]),
            salt=bytes.fromhex(data["kdfparams"]["salt"]),
            iv=bytes.fromhex(data["cipherparams"]["iv"]),
            tag=bytes.fromhex(data["cipherparams"]["tag"]),
            key_type=data.get("keyType", "ed25519"),
            label=data.get("label"),
        )


def _derive_key(password: str, salt: bytes) -> bytes:
    return pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS, dklen=KEY_LENGTH)


def encrypt_seed(seed: str, password: str, address: str,
                 key_type: str = "ed25519", label: Optional[str] = None) -> KeystoreFile:
    """Encrypt a wallet seed with a password."""
    salt = token_bytes(SALT_LENGTH)
    iv = token_bytes(IV_LENGTH)
    key = _derive_key(password, salt)

    aesgcm = AESGCM(key)
    ct_with_tag = aesgcm.encrypt(iv, seed.encode(), None)
    ciphertext = ct_with_tag[:-16]
    tag = ct_with_tag[-16:]

    return KeystoreFile(
        address=address, ciphertext=ciphertext, salt=salt, iv=iv,
        tag=tag, key_type=key_type, label=label,
    )


def decrypt_seed(ks: KeystoreFile, password: str) -> str:
    """Decrypt a wallet seed from a keystore file."""
    key = _derive_key(password, ks.salt)
    aesgcm = AESGCM(key)
    ct_with_tag = ks.ciphertext + ks.tag
    plaintext = aesgcm.decrypt(ks.iv, ct_with_tag, None)
    return plaintext.decode()


class KeystoreManager:
    """Manages encrypted wallet keystores on disk."""

    def __init__(self, keystore_dir: Optional[str] = None):
        self.keystore_dir = keystore_dir or os.getenv("XRPL_KEYSTORE", DEFAULT_KEYSTORE_DIR)
        os.makedirs(self.keystore_dir, exist_ok=True)

    def _filepath(self, address: str) -> str:
        return os.path.join(self.keystore_dir, f"{address}.json")

    def save_wallet(self, seed: str, password: str,
                    label: Optional[str] = None) -> Dict:
        """Encrypt and save a wallet seed to the keystore."""
        wallet = Wallet.from_seed(seed)
        ks = encrypt_seed(seed, password, wallet.address, label=label)

        filepath = self._filepath(wallet.address)
        with open(filepath, "w") as f:
            json.dump(ks.to_dict(), f, indent=2)

        logger.info(f"Wallet saved: {wallet.address} ({label or 'no label'})")
        return {
            "address": wallet.address,
            "label": label,
            "path": filepath,
        }

    def load_wallet(self, address: str, password: str) -> Wallet:
        """Load and decrypt a wallet from the keystore."""
        filepath = self._filepath(address)
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Keystore not found for {address}")

        with open(filepath) as f:
            data = json.load(f)

        ks = KeystoreFile.from_dict(data)
        seed = decrypt_seed(ks, password)
        return Wallet.from_seed(seed)

    def list_wallets(self) -> List[Dict]:
        """List all wallets in the keystore."""
        wallets = []
        for f in Path(self.keystore_dir).glob("r*.json"):
            try:
                with open(f) as fp:
                    data = json.load(fp)
                wallets.append({
                    "address": data.get("address", f.stem),
                    "label": data.get("label"),
                    "keyType": data.get("keyType", "unknown"),
                })
            except Exception:
                continue
        return wallets

    def remove_wallet(self, address: str) -> bool:
        """Remove a wallet from the keystore."""
        filepath = self._filepath(address)
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False

    def has_wallet(self, address: str) -> bool:
        """Check if a wallet exists in the keystore."""
        return os.path.exists(self._filepath(address))

    def import_from_config(self, password: str) -> List[Dict]:
        """Import existing plaintext seeds from config/test_wallets.py into encrypted keystore."""
        results = []
        try:
            from config.test_wallets import SPOT_TRADER_WALLET, FLASH_LOAN_WALLET
            for name, cfg in [("spot_trader", SPOT_TRADER_WALLET), ("flash_loan", FLASH_LOAN_WALLET)]:
                seed = cfg["seed"]
                result = self.save_wallet(seed, password, label=name)
                results.append(result)
        except ImportError:
            logger.warning("config/test_wallets.py not found")

        try:
            issuer_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "testnet_issuer.json")
            if os.path.exists(issuer_path):
                with open(issuer_path) as f:
                    cfg = json.load(f)
                if "seed" in cfg:
                    result = self.save_wallet(cfg["seed"], password, label="issuer")
                    results.append(result)
        except Exception as e:
            logger.warning(f"Could not import issuer: {e}")

        return results
