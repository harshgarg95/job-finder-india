"""Skills taxonomy + normalization — our lightweight version of LinkedIn's
Skills Graph, the one transferable lesson from how LinkedIn matches.

For a candidate who only mirrors their resume into LinkedIn, LinkedIn's edge over
us is NOT extra/verified data — it's that it stores skills as normalized,
taxonomy-mapped tags (so "GenAI" == "generative AI") and computes adjacency
(LangChain ~ LangGraph). This module gives us the same two things:

  - normalize(): map a raw skill string to a canonical skill (handles wording),
  - extract(): pull the candidate's canonical skills from resume text ONCE
    (our "structured profile" — parity with LinkedIn's parsed profile),
  - match(): met / partial / missing for a required skill, where a sibling skill
    in the same group earns `partial` (LinkedIn's skill-expansion idea).

Deliberately small and editable (a few dozen skills around AI delivery / PM /
India), not a 40k graph — enough to make the qualifications-match consistent and
cheap. The LLM remains the judge; this just feeds it a clean, normalized view.
"""

from __future__ import annotations

import re

# canonical skill -> {aliases, group}. Group members are "adjacent" (partial).
TAXONOMY: dict[str, dict] = {
    # ── GenAI / LLM application building (Harsh's actual hands-on area) ──────
    "rag": {"aliases": ["retrieval augmented generation", "retrieval-augmented generation",
                        "retrieval augmented", "rag pipeline"], "group": "llm-apps"},
    "vector database": {"aliases": ["vector db", "faiss", "chromadb", "astradb", "pinecone",
                                    "pgvector", "weaviate"], "group": "llm-apps"},
    "embeddings": {"aliases": ["embedding", "semantic search"], "group": "llm-apps"},
    "prompt engineering": {"aliases": ["prompting", "prompt design"], "group": "llm-apps"},
    "langchain": {"aliases": ["lcel", "langgraph", "llamaindex", "llama index", "semantic kernel",
                              "crewai", "autogen"], "group": "genai-frameworks"},
    "ai agents": {"aliases": ["agent", "react agent", "agentic", "multi-agent", "nl-to-sql",
                              "tool calling"], "group": "genai-frameworks"},
    "llm": {"aliases": ["large language model", "claude", "openai", "gpt", "groq", "mistral",
                        "llama", "gemini", "ollama", "huggingface", "hugging face"], "group": "genai-frameworks"},
    "genai": {"aliases": ["generative ai", "gen ai", "generative a.i."], "group": "genai-frameworks"},
    # ── Hands-on ML / DS (the group Harsh mostly LACKS → adjacency matters) ──
    "machine learning": {"aliases": ["ml", "scikit-learn", "sklearn", "ml pipeline"], "group": "ml-ds"},
    "deep learning": {"aliases": ["neural network", "transformers", "pytorch", "tensorflow",
                                  "fine-tuning", "fine tuning"], "group": "ml-ds"},
    "nlp": {"aliases": ["natural language processing"], "group": "ml-ds"},
    "data science": {"aliases": ["data scientist", "statistical modeling", "statistical modelling"],
                     "group": "ml-ds"},
    "mlops": {"aliases": ["llmops", "model monitoring", "model deployment"], "group": "ml-ds"},
    # ── Software engineering (adjacent but distinct from delivery/PM) ────────
    "python": {"aliases": ["flask", "fastapi", "uvicorn", "streamlit"], "group": "languages"},
    "sql": {"aliases": ["nosql", "postgres", "mysql"], "group": "languages"},
    "java": {"aliases": ["spring", "spring boot", ".net", "c++", "golang", "scala"], "group": "languages"},
    "software development": {"aliases": ["software engineering", "coding", "programming",
                                        "microservices", "rest api", "api integration"], "group": "swe"},
    "devops": {"aliases": ["ci/cd", "docker", "kubernetes", "jenkins", "gitlab ci",
                           "terraform", "sdlc"], "group": "swe"},
    "cloud": {"aliases": ["aws", "azure", "gcp", "google cloud", "vercel", "render"], "group": "cloud"},
    # ── Delivery / program / product management (Harsh's core function) ──────
    "program management": {"aliases": ["programme management", "program manager",
                                       "delivery management", "delivery manager"], "group": "delivery"},
    "project management": {"aliases": ["project manager", "phase-gate", "phase gate",
                                       "milestone tracking", "ms project", "gantt"], "group": "delivery"},
    "stakeholder management": {"aliases": ["stakeholder", "client management", "cross-functional"],
                               "group": "delivery"},
    "change management": {"aliases": ["adoption", "enablement", "rollout"], "group": "delivery"},
    "agile": {"aliases": ["scrum", "kanban", "sprint"], "group": "agile"},
    "safe": {"aliases": ["scaled agile", "safe delivery"], "group": "agile"},
    "product management": {"aliases": ["product manager", "prd", "roadmap", "product strategy",
                                       "discovery"], "group": "product"},
    "requirements gathering": {"aliases": ["requirements", "scoping", "business analysis",
                                           "business analyst"], "group": "product"},
    "vendor management": {"aliases": ["procurement", "vendor coordination"], "group": "delivery"},
    "stakeholder communication": {"aliases": ["presentation", "facilitation"], "group": "delivery"},
}

# precompute alias -> canonical and canonical -> group
_ALIAS = {}
for canon, meta in TAXONOMY.items():
    _ALIAS[canon] = canon
    for a in meta.get("aliases", []):
        _ALIAS[a] = canon
_GROUP = {c: m.get("group", c) for c, m in TAXONOMY.items()}


def normalize(skill: str) -> str | None:
    """Map a raw skill phrase to its canonical skill, or None if unknown."""
    s = (skill or "").strip().lower()
    if not s:
        return None
    if s in _ALIAS:
        return _ALIAS[s]
    # substring contains (longest alias first so 'langgraph' beats 'lang')
    for alias in sorted(_ALIAS, key=len, reverse=True):
        if re.search(r"\b" + re.escape(alias) + r"\b", s):
            return _ALIAS[alias]
    return None


def extract(text: str) -> list[str]:
    """Canonical skills present in resume text — our 'structured profile'."""
    t = (text or "").lower()
    found = []
    for alias, canon in _ALIAS.items():
        if re.search(r"\b" + re.escape(alias) + r"\b", t) and canon not in found:
            found.append(canon)
    return sorted(found)


def match(required_skill: str, candidate_skills: list[str]) -> str:
    """met | partial | missing for a required skill vs the candidate's canonical
    skills. A sibling in the same group → partial (LinkedIn's skill expansion)."""
    canon = normalize(required_skill)
    if canon is None:
        return "unknown"            # not a taxonomy skill — leave to the LLM
    cand = set(candidate_skills)
    if canon in cand:
        return "met"
    grp = _GROUP.get(canon)
    if grp and any(_GROUP.get(c) == grp for c in cand):
        return "partial"
    return "missing"
