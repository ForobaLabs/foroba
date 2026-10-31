"""The image must ship every package the gateway imports (a bare `COPY *.py` drops sub-packages)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_dockerfile_copies_every_subpackage():
    docker = (ROOT / "Dockerfile").read_text()
    pkgs = [p.name for p in ROOT.iterdir() if (p / "__init__.py").is_file() and p.name != "tests"]
    assert {"masking", "providers"} <= set(pkgs)
    for pkg in pkgs:
        assert f"COPY {pkg} ./{pkg}" in docker, f"Dockerfile does not copy package {pkg}/"


def test_dockerfile_port_matches_expose_and_cmd():
    docker = (ROOT / "Dockerfile").read_text()
    assert "EXPOSE 8095" in docker and '"--port", "8095"' in docker
