from openai import OpenAI
from typing import Sequence, List

class OpenAICompatibleEmbeddingModel:
    """
    OpenAI-compatible embeddings wrapper.
    Works with OpenAI and OpenAI-compatible servers implementing /v1/embeddings.

    Example model: "qwen3-embedding:8b"
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str = "qwen3-embedding:8b",
        timeout: float | None = 60.0,
    ) -> None:
        self._client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
        self._model = model

    def embed_batch(self, texts: Sequence[str]) -> List[List[float]]:
        texts_list = list(texts)
        if not texts_list:
            return []

        res = self._client.embeddings.create(
            model=self._model,
            input=texts_list,
        )

        data = list(res.data)
        try:
            data.sort(key=lambda d: d.index)
        except Exception:
            pass

        return [list(d.embedding) for d in data]