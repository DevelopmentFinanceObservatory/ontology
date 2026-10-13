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

# Compile a bench to MCF, e.g. `just compile prod` or `just compile dev --check`.
compile bench *flags:
    uv run dfo-ontology compile --bench {{bench}} {{flags}}
