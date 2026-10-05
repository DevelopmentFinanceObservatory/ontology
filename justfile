# Mirrors CI: ruff check, format check, ty, pytest.
check:
    uv run ruff check .
    uv run ruff format --check .
    uv run ty check src/dfo_ontology
    uv run pytest

# Autofix lint and format.
fmt:
    uv run ruff check --fix .
    uv run ruff format .

# Compile the bench to MCF.
compile:
    uv run dfo-ontology compile
