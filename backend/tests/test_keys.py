import re

from auth.keys import load_or_generate_keypair


def test_generates_keypair_on_first_call(tmp_path):
    priv_path = tmp_path / "keys" / "jwt_private.pem"
    pub_path = tmp_path / "keys" / "jwt_public.pem"
    private_pem, public_pem, kid = load_or_generate_keypair(priv_path, pub_path)
    assert "BEGIN PRIVATE KEY" in private_pem
    assert "BEGIN PUBLIC KEY" in public_pem
    assert re.fullmatch(r"[0-9a-f]{16}", kid)
    assert priv_path.exists()
    assert pub_path.exists()


def test_loads_existing_keypair_on_second_call(tmp_path):
    priv_path = tmp_path / "keys" / "jwt_private.pem"
    pub_path = tmp_path / "keys" / "jwt_public.pem"
    first_private, first_public, first_kid = load_or_generate_keypair(priv_path, pub_path)
    second_private, second_public, second_kid = load_or_generate_keypair(priv_path, pub_path)
    assert first_private == second_private
    assert first_public == second_public
    assert first_kid == second_kid


def test_private_key_file_is_owner_only(tmp_path):
    priv_path = tmp_path / "keys" / "jwt_private.pem"
    pub_path = tmp_path / "keys" / "jwt_public.pem"
    load_or_generate_keypair(priv_path, pub_path)
    mode = priv_path.stat().st_mode & 0o777
    assert mode == 0o600
