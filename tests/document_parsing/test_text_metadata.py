from scepa_app.document_parsing.text_metadata import Acknowledgement, TextMetadata


def test_text_metadata_defaults():
    meta = TextMetadata()

    assert meta.authors is None
    assert meta.keywords is None
    assert meta.acknowledgements == []
    assert meta.source == {}


def test_text_metadata_accepts_lists():
    meta = TextMetadata(
        authors=["Alice"],
        acknowledgements=[Acknowledgement(name="Org", type="organization", relation="support")],
        keywords=["tag"],
    )

    assert meta.authors == ["Alice"]
    assert meta.acknowledgements[0].name == "Org"
    assert meta.keywords == ["tag"]
