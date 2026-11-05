"""
Few-shot prompt builder for baseline LLM evaluation.

Supplies 2 in-context exemplars (1 grounded answer showing JSON citation,
1 adversarial refusal showing empty bullets) to provide a strong, fair
baseline for untuned models without PEFT adapter weights.
"""

from __future__ import annotations

import json
from training.generate_dataset import SYSTEM_PROMPT, format_excerpts

EXEMPLAR_1_USER = (
    "Question: How does the pointer adjustment work?\n\n"
    "Lecture Excerpts:\n"
    "[1] (18m50s-19m24s) the low was pointed here and the high was pointed here. "
    "The new array to sort according to the algorithm is divided from the midpoint.\n\n"
    "[2] (28m36s-29m08s) you get the corresponding index in the hash array."
)
EXEMPLAR_1_ASST = json.dumps(
    {"bullets": [{"text": "The low was pointed here and the high was pointed here.", "sources": [1]}]},
    ensure_ascii=False,
)

EXEMPLAR_2_USER = (
    "Question: how to configure spring boot security jwt filter chain\n\n"
    "Lecture Excerpts:\n"
    "[1] (10m12s-10m45s) we calculate the mid element and compare with key.\n\n"
    "[2] (11m00s-11m30s) if the key is smaller we search the left sub-array."
)
EXEMPLAR_2_ASST = json.dumps({"bullets": []}, ensure_ascii=False)


def build_fewshot_messages(question: str, excerpts: list[dict]) -> list[dict]:
    """Builds chat messages with 2 multi-turn demonstrations."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": EXEMPLAR_1_USER},
        {"role": "assistant", "content": EXEMPLAR_1_ASST},
        {"role": "user", "content": EXEMPLAR_2_USER},
        {"role": "assistant", "content": EXEMPLAR_2_ASST},
        {
            "role": "user",
            "content": f"Question: {question}\n\nLecture Excerpts:\n{format_excerpts(excerpts)}",
        },
    ]
