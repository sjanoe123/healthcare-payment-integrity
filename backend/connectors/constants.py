"""Shared constants for connector configuration."""

# Secret fields by connector type - used for:
# 1. Encrypting/storing credentials when connector is created/updated
# 2. Masking sensitive values when returning connector config to client
# 3. Injecting decrypted secrets before connector operations
CONNECTOR_SECRET_FIELDS: dict[str, list[str]] = {
    "database": ["password"],
    "api": ["api_key", "oauth_client_secret", "bearer_token"],
    "file": [
        "aws_access_key",
        "aws_secret_key",
        "password",  # SFTP password
        "private_key",  # SFTP private key
        "account_key",  # Azure Blob Storage
        "sas_token",  # Azure SAS token
        "azure_connection_string",  # Azure full connection string
    ],
}
