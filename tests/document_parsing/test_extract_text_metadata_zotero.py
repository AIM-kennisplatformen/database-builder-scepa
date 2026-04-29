from scepa_app.document_parsing.extract_text_metadata_zotero import ZoteroMetadataExtractor


def test_extract_keywords_maps_prefixed_tags():
    extractor = ZoteroMetadataExtractor()

    data = {
        "tags": [
            {"tag": "strategy: roadmap"},
            {"tag": "target: teachers"},
            {"tag": "practice: workshop"},
            {"tag": "report"},
            {"tag": "unmapped"},
        ]
    }

    keywords = extractor._extract_keywords(data)

    assert keywords["strategic_overview"] == ["roadmap"]
    assert keywords["target_groups"] == ["teachers"]
    assert keywords["best_practices"] == ["workshop"]
    assert keywords["literature_type"] == "report"
    assert keywords["keywords"] == ["unmapped"]


def test_is_institution_name_uses_domain_hints():
    extractor = ZoteroMetadataExtractor()

    assert extractor._is_institution_name("University of Example")
    assert not extractor._is_institution_name("Alice Smith")
