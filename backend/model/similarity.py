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

    def _get_embeddings(self, text1: str, text2: str) -> tuple:
        if self.provider == "gemini":
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            embeddings = genai.embed_content(
                model="models/text-embedding-004",
                content=[text1, text2],
            )
            return embeddings["embedding"][0], embeddings["embedding"][1]

        if self.provider in ["openai", "openrouter"]:
            endpoint = "https://api.openai.com/v1/embeddings" if self.provider == "openai" else "https://openrouter.ai/api/v1/embeddings"
            model_name = "text-embedding-3-small" if self.provider == "openai" else "openai/text-embedding-3-small"

            data = json.dumps({"input": [text1, text2], "model": model_name}).encode("utf-8")
            req = urllib.request.Request(endpoint, data=data, method="POST")
            req.add_header("Authorization", f"Bearer {self.api_key}")
            req.add_header("Content-Type", "application/json")

            with urllib.request.urlopen(req) as response:
                res_data = json.loads(response.read().decode())
                return res_data["data"][0]["embedding"], res_data["data"][1]["embedding"]

        raise ValueError(f"Provider '{self.provider}' is not supported for similarity embedding.")

    async def calculate_similarity(self, ground_truth: str, user_answer: str) -> float:
        emb1, emb2 = self._get_embeddings(ground_truth, user_answer)
        return cosine_similarity(emb1, emb2)


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
            print(self.provider, self.api_key)
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
            print(f"Error parsing similarity score: {e}")
            return 0.0



class AIModelFactory:
    @staticmethod
    def create(eval_mode: str, provider: str, api_key: str, model_name: str = None) -> SemanticSimilarityModel:
        if eval_mode == "similarity":
            return CosineSimilarityModel(provider, api_key)
        if eval_mode == "model":
            return PromptBasedSimilarityModel(provider, api_key, model_name)
        raise ValueError(f"AI Model unsupported for eval_mode: '{eval_mode}'")
