
import os
import requests
from dotenv import load_dotenv
load_dotenv()

GROQ_API_URL = os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions")
MODEL_NAME = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")


def generate_response(prompt: str) -> str:
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise RuntimeError("GROQ_API_KEY environment variable is not configured.")

    response = requests.post(
        GROQ_API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL_NAME,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "stream": False,
        },
        timeout=120,
    )

    response.raise_for_status()

    result = response.json()
    answer = result["choices"][0]["message"]["content"]

    if not answer:
        raise RuntimeError("Groq returned an empty response.")

    return answer.strip()


if __name__ == "__main__":
    prompt = "Explain Apache Kafka in three simple sentences."
    print(generate_response(prompt))
