from scepa_app.util.metadata_util import extract_zotero_metadata


def test_extract_zotero_metadata_maps_fields():
    zotero_content = type(
        "ZoteroContent",
        (),
        {
            "content": {
                "title": "Paper",
                "creators": [{"creatorType": "author", "firstName": "Alice", "lastName": "Smith"}],
                "abstractNote": "Summary",
                "publisher": "Example Org",
                "tags": [{"tag": "tag1"}],
            }
        },
    )()

    meta = extract_zotero_metadata(zotero_content)

    assert meta["title"] == "Paper"
    assert meta["authors"] == ["Smith, Alice"]
    assert meta["summary"] == "Summary"
    assert meta["keywords"] == ["tag1"]
    assert meta["publishing_institute"] == {"name": "Example Org"}


def test_extract_zotero_metadata_reads_creators_and_tags():
    zotero_content = type(
        "ZoteroContent",
        (),
        {
            "content": {
                "title": "Example",
                "creators": [
                    {"creatorType": "author", "firstName": "Alice", "lastName": "Smith"},
                    {"creatorType": "editor", "name": "Example Institute"},
                ],
                "abstractNote": "Summary",
                "publisher": "Example Org",
                "tags": [{"tag": "strategy: roadmap"}, {"tag": "unmapped"}],
            }
        },
    )()

    meta = extract_zotero_metadata(zotero_content)

    assert meta["authors"] == ["Smith, Alice"]
    assert meta["keywords"] == ["strategy: roadmap", "unmapped"]
