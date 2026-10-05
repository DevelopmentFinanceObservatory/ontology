"""Tests for config.py."""

import pytest

from dfo_ontology import config


def test_every_bench_is_named() -> None:
    """The table holds exactly the benches the CLI offers."""
    assert sorted(config.BENCHES) == ["dev", "prod", "testing"]


@pytest.mark.parametrize("bench", ["prod", "testing", "dev"])
def test_shared_settings_are_identical_across_benches(bench: str) -> None:
    """Only the URL varies: every other setting is the same on every bench."""
    cfg = config.Config(bench=bench)
    assert cfg.id_property == "P1"
    assert cfg.dcid_property == "P2"
    assert cfg.prefix == config.PREFIX
    assert cfg.namespaces == (config.ITEM_NAMESPACE, config.PROPERTY_NAMESPACE)
    assert cfg.batch_size == config.BATCH_SIZE


def test_site_is_the_browsable_instance() -> None:
    """site is the URL a person opens, with no API path on it."""
    assert config.Config(bench="prod").site == config.BENCHES["prod"]
    assert config.API_PATH not in config.Config(bench="prod").site


def test_url_appends_the_api_endpoint_to_the_site() -> None:
    """url is the site plus api.php, so the two can't drift apart."""
    cfg = config.Config(bench="testing")
    assert cfg.url == f"{cfg.site}{config.API_PATH}"
    assert cfg.url == "https://dfo-testing-2.wikibase.cloud/w/api.php"


def test_dev_url_appends_the_api_endpoint_to_the_site() -> None:
    """The dev bench resolves like the others."""
    assert config.Config(bench="dev").url == "https://dfo-dev.wikibase.cloud/w/api.php"


def test_provenance_names_bench_and_site() -> None:
    """The line both artifacts carry names the bench and links the instance."""
    cfg = config.Config(bench="testing")
    assert cfg.provenance == "bench: testing (https://dfo-testing-2.wikibase.cloud)"


def test_bench_is_required() -> None:
    """There is no default bench: a Config must say which instance it reads."""
    with pytest.raises(TypeError):
        config.Config()  # ty: ignore[missing-argument]


def test_unknown_bench_fails_on_use() -> None:
    """A bench outside the table has no URL; the CLI's choices= prevents it earlier."""
    with pytest.raises(KeyError):
        _ = config.Config(bench="nope").url
