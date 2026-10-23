from pydantic import BaseModel, field_validator


class VaultEncryptRequest(BaseModel):
    vault_password_id: int
    plaintext: str
    var_name: str | None = None

    @field_validator("var_name")
    @classmethod
    def _blank_to_none(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None


class VaultEncryptResponse(BaseModel):
    vault_text: str
    yaml_block: str
    # Ansible's JSON form, for a run's extra vars or a host's vars (a `"name": ...` member
    # with a variable name)
    json_value: str


class VaultDecryptRequest(BaseModel):
    vault_password_id: int
    ciphertext: str


class VaultDecryptResponse(BaseModel):
    plaintext: str
