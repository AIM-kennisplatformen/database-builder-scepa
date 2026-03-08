from unittest.mock import Mock, patch

from scepa_app.document_parsing.embedding.openai_embedding_model import OpenAICompatibleEmbeddingModel


class FakeEmbedding:
    def __init__(self, index, embedding):
        self.index = index
        self.embedding = embedding


class FakeResponse:
    def __init__(self, data):
        self.data = data


def test_embed_batch_returns_empty_for_empty_input():
    model = OpenAICompatibleEmbeddingModel(
        base_url="http://test",
        api_key="key",
    )

    assert model.embed_batch([]) == []


@patch("scepa_app.document_parsing.embedding.openai_embedding_model.OpenAI")
def test_embed_batch_calls_openai_client(mock_openai):
    mock_client = Mock()
    mock_openai.return_value = mock_client

    mock_client.embeddings.create.return_value = FakeResponse(
        [
            FakeEmbedding(0, [0.1, 0.2]),
            FakeEmbedding(1, [0.3, 0.4]),
        ]
    )

    model = OpenAICompatibleEmbeddingModel(
        base_url="http://test",
        api_key="key",
        model="test-model",
    )

    result = model.embed_batch(["a", "b"])

    mock_client.embeddings.create.assert_called_once_with(
        model="test-model",
        input=["a", "b"],
    )

    assert result == [[0.1, 0.2], [0.3, 0.4]]


@patch("scepa_app.document_parsing.embedding.openai_embedding_model.OpenAI")
def test_embed_batch_sorts_by_index(mock_openai):
    mock_client = Mock()
    mock_openai.return_value = mock_client

    mock_client.embeddings.create.return_value = FakeResponse(
        [
            FakeEmbedding(1, [0.3, 0.4]),
            FakeEmbedding(0, [0.1, 0.2]),
        ]
    )

    model = OpenAICompatibleEmbeddingModel(
        base_url="http://test",
        api_key="key",
    )

    result = model.embed_batch(["a", "b"])

    assert result == [
        [0.1, 0.2],
        [0.3, 0.4],
    ]


@patch("scepa_app.document_parsing.embedding.openai_embedding_model.OpenAI")
def test_embed_batch_handles_missing_index(mock_openai):
    mock_client = Mock()
    mock_openai.return_value = mock_client

    # objects without index attribute -> sort fails but code continues
    obj1 = Mock(embedding=[1.0])
    obj2 = Mock(embedding=[2.0])

    mock_client.embeddings.create.return_value = FakeResponse([obj1, obj2])

    model = OpenAICompatibleEmbeddingModel(
        base_url="http://test",
        api_key="key",
    )

    result = model.embed_batch(["a", "b"])

    assert result == [[1.0], [2.0]]