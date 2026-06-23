"""Generate an RSA-2048 key pair for JWT RS256 signing.

Run once during setup. Copy the printed PEM strings into your .env file under
RSA_PRIVATE_KEY and RSA_PUBLIC_KEY (escape newlines as \\n if storing inline).
"""

from __future__ import annotations

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def main() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    print("# Add the following lines to your backend/.env file:")
    print()
    print("RSA_PRIVATE_KEY=\"" + private_pem.replace("\n", "\\n") + "\"")
    print("RSA_PUBLIC_KEY=\"" + public_pem.replace("\n", "\\n") + "\"")


if __name__ == "__main__":
    main()
