import json
import math
import re
import urllib.request
from abc import ABC, abstractmethod

from .chatbot import ChatBot


class SemanticSimilarityModel(ABC):
    @abstractmethod
    async def calculate_similarity(self, ground_truth: str, user_answer: str) -> float:
        pass


def cosine_similarity(a: list, b: list) -> float:
    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)


class SimilarityBasedModel(SemanticSimilarityModel):
    pass


class ModelBasedModel(SemanticSimilarityModel):
    pass


class TraditionalSimilarityModel(SemanticSimilarityModel):
    def _get_tokens(self, text: str) -> list:
        return re.sub(r"\W+", " ", text.lower()).strip().split()

    def _get_ngrams(self, tokens: list, n: int) -> set:
        if not tokens:
            return set()
        if len(tokens) < n:
            return set(tokens)
        return set(tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1))

    def _jaccard_similarity(self, set1: set, set2: set) -> float:
        if not set1 and not set2:
            return 1.0
        if not set1 or not set2:
            return 0.0
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        return float(intersection / union)

    async def calculate_similarity(self, ground_truth: str, user_answer: str) -> float:
        gt_tokens = self._get_tokens(ground_truth)
        ans_tokens = self._get_tokens(user_answer)

        if not gt_tokens and not ans_tokens:
            return 1.0
        if not gt_tokens or not ans_tokens:
            return 0.0

        max_len = max(len(gt_tokens), len(ans_tokens))
        max_n = min(10, max_len)

        total_score = 0.0
        for n in range(1, max_n + 1):
            gt_ngrams = self._get_ngrams(gt_tokens, n)
            ans_ngrams = self._get_ngrams(ans_tokens, n)
            total_score += self._jaccard_similarity(gt_ngrams, ans_ngrams)

        return total_score / max_n


class CosineSimilarityModel(SimilarityBasedModel):
    def __init__(self, provider: str, api_key: str):
        self.provider = provider
        self.api_key = api_key

    class EmbeddingEngine(ABC):
        """
        Provider-specific embeddings engine.

        Note:
            We keep engines separate because providers have different endpoints, auth headers,
            request/response shapes, and model IDs.
        """

        @abstractmethod
        def embed_texts(self, texts: list[str]) -> list[list[float]]:
            """Return one embedding vector per input text (same order)."""

    class GeminiEmbeddingEngine(EmbeddingEngine):
        """
        Gemini Embeddings engine (Gemini API).

        Uses REST `batchEmbedContents` with the Gemini Embedding 2 model and a task type optimized
        for semantic similarity.
        """

        def __init__(self, api_key: str):
            self.api_key = api_key

        def embed_texts(self, texts: list[str]) -> list[list[float]]:
            if not texts:
                return []

            try:
                endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-2:batchEmbedContents"

                requests = []
                for t in texts:
                    requests.append(
                        {
                            "model": "models/gemini-embedding-2",
                            "taskType": "SEMANTIC_SIMILARITY",
                            "content": {"parts": [{"text": t}]},
                        }
                    )

                data = json.dumps({"requests": requests}).encode("utf-8")
                req = urllib.request.Request(endpoint, data=data, method="POST")
                req.add_header("x-goog-api-key", self.api_key)
                req.add_header("Content-Type", "application/json")

                with urllib.request.urlopen(req) as response:
                    res_data = json.loads(response.read().decode())

                embeddings = res_data.get("embeddings") or []
                vectors: list[list[float]] = []
                for emb in embeddings:
                    if isinstance(emb, dict):
                        if "values" in emb and isinstance(emb["values"], list):
                            vectors.append(emb["values"])
                        elif "embedding" in emb and isinstance(emb["embedding"], list):
                            vectors.append(emb["embedding"])
                        else:
                            vectors.append([])
                    else:
                        vectors.append([])

                if len(vectors) != len(texts):
                    raise ValueError("Gemini embedding response count mismatch.")
                return vectors
            except Exception as e:
                print(f"GeminiEmbeddingEngine Error: {e}")
                raise

    class OpenAIEmbeddingEngine(EmbeddingEngine):
        """OpenAI embeddings engine (POST https://api.openai.com/v1/embeddings)."""

        def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
            self.api_key = api_key
            self.model = model

        def embed_texts(self, texts: list[str]) -> list[list[float]]:
            try:
                endpoint = "https://api.openai.com/v1/embeddings"
                data = json.dumps({"input": texts, "model": self.model}).encode("utf-8")
                req = urllib.request.Request(endpoint, data=data, method="POST")
                req.add_header("Authorization", f"Bearer {self.api_key}")
                req.add_header("Content-Type", "application/json")

                with urllib.request.urlopen(req) as response:
                    res_data = json.loads(response.read().decode())

                return [item.get("embedding", []) for item in (res_data.get("data") or [])]
            except Exception as e:
                print(f"OpenAIEmbeddingEngine Error: {e}")
                raise

    class OpenRouterEmbeddingEngine(EmbeddingEngine):
        """OpenRouter embeddings engine (POST https://openrouter.ai/api/v1/embeddings)."""

        def __init__(self, api_key: str, model: str = "openai/text-embedding-3-small"):
            self.api_key = api_key
            self.model = model

        def embed_texts(self, texts: list[str]) -> list[list[float]]:
            try:
                endpoint = "https://openrouter.ai/api/v1/embeddings"
                data = json.dumps({"input": texts, "model": self.model}).encode("utf-8")
                req = urllib.request.Request(endpoint, data=data, method="POST")
                req.add_header("Authorization", f"Bearer {self.api_key}")
                req.add_header("Content-Type", "application/json")

                with urllib.request.urlopen(req) as response:
                    res_data = json.loads(response.read().decode())

                return [item.get("embedding", []) for item in (res_data.get("data") or [])]
            except Exception as e:
                print(f"OpenRouterEmbeddingEngine Error: {e}")
                raise

    def _get_engine(self) -> "CosineSimilarityModel.EmbeddingEngine":
        if self.provider == "gemini":
            return self.GeminiEmbeddingEngine(self.api_key)
        if self.provider == "openai":
            return self.OpenAIEmbeddingEngine(self.api_key)
        if self.provider == "openrouter":
            return self.OpenRouterEmbeddingEngine(self.api_key)
        raise ValueError(f"Provider '{self.provider}' is not supported for similarity embedding.")

    def _get_embeddings(self, text1: str, text2: str) -> tuple:
        engine = self._get_engine()
        vectors = engine.embed_texts([text1, text2])
        if len(vectors) != 2:
            raise ValueError("Embedding engine did not return 2 vectors.")
        return vectors[0], vectors[1]

    async def calculate_similarity(self, ground_truth: str, user_answer: str) -> float:
        try:
            emb1, emb2 = self._get_embeddings(ground_truth, user_answer)
            return cosine_similarity(emb1, emb2)
        except Exception as e:
            print(f"CosineSimilarityModel calculate error: {e}. Falling back to Traditional.")
            fallback = TraditionalSimilarityModel()
            return await fallback.calculate_similarity(ground_truth, user_answer)


class PromptBasedSimilarityModel(ModelBasedModel):
    DEFAULT_MODELS = {
        "gemini": "gemini-2.5-flash",
        "openai": "gpt-4o-mini",
        "openrouter": "google/gemini-2.5-pro",
    }

    def __init__(self, provider: str, api_key: str, model_name: str = None):
        self.provider = provider
        self.api_key = api_key
        self.model_name = model_name or self.DEFAULT_MODELS.get(provider, "")

    async def calculate_similarity(self, ground_truth: str, user_answer: str) -> float:
        prompt = f"""You are an expert evaluator. Compare the user's answer with the ground truth and determine their semantic similarity.
Output ONLY a float number between 0.0 and 1.0 representing the score (1.0 means exactly the same meaning). Do not output any other text.

Ground truth: {ground_truth}
User's answer: {user_answer}"""
        try:
            chatbot = ChatBot(self.provider, self.api_key, self.model_name, system_prompt="", temperature=0.1)
            response, _ = await chatbot.async_send_message([{"role": "user", "content": prompt}])

            import re
            # Loại bỏ phần reasoning (thẻ <think>) nếu có
            cleaned_response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL).strip()
            
            # Tìm một số thập phân từ 0.0 đến 1.0 trong câu trả lời
            match = re.search(r'\b(0\.\d+|1\.0|0|1)\b', cleaned_response)
            if match:
                score = float(match.group(1))
            else:
                # Ép kiểu fallback nếu không regex được
                score = float(cleaned_response)
                
            return max(0.0, min(1.0, score))
        except Exception as e:
            print(f"PromptBasedSimilarityModel calculate error: {e}. Falling back to Traditional.")
            fallback = TraditionalSimilarityModel()
            return await fallback.calculate_similarity(ground_truth, user_answer)




class AIModelFactory:
    @staticmethod
    def create(eval_mode: str, provider: str, api_key: str, model_name: str = None) -> SemanticSimilarityModel:
        if eval_mode == "similarity":
            return CosineSimilarityModel(provider, api_key)
        if eval_mode == "model":
            return PromptBasedSimilarityModel(provider, api_key, model_name)
        raise ValueError(f"AI Model unsupported for eval_mode: '{eval_mode}'")
