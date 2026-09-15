import json
import re
from typing import Sequence

from google import genai
from pydantic import BaseModel, Field
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

# Common financial phrases and SEC 10-K terms to preserve as multi-word units
KNOWN_FINANCIAL_PHRASES: tuple[str, ...] = (
    "total net sales",
    "net sales",
    "operating income",
    "operating margin",
    "operating expenses",
    "gross margin",
    "gross profit",
    "cash flow",
    "free cash flow",
    "data center",
    "customer concentration",
    "demand drivers",
    "cloud capacity constraints",
    "cloud capacity",
    "ai infrastructure",
    "traffic acquisition costs",
    "advertising revenue",
    "revenue streams",
    "capital expenditures",
    "research and development",
    "product category",
    "balance sheet",
    "statements of operations",
    "segment income",
    "aws segment",
)

# Comprehensive standard English stop words (based on NLTK corpus) plus conversational prompt fillers
STOP_WORDS: frozenset[str] = frozenset({
    # Standard English grammatical stop words (NLTK)
    "a", "about", "above", "after", "again", "against", "ain", "all", "am", "an", "and",
    "any", "are", "aren", "arent", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "cannot", "cant", "could", "couldn",
    "couldnt", "d", "did", "didn", "didnt", "do", "does", "doesn", "doesnt", "doing",
    "don", "dont", "down", "during", "each", "few", "for", "from", "further", "had",
    "hadn", "hadnt", "has", "hasn", "hasnt", "have", "haven", "havent", "having", "he",
    "her", "here", "hers", "herself", "him", "himself", "his", "how", "i", "if", "in",
    "into", "is", "isn", "isnt", "it", "its", "itself", "just", "ll", "m", "ma", "me",
    "mightn", "mightnt", "more", "most", "mustn", "mustnt", "my", "myself", "needn",
    "neednt", "no", "nor", "not", "now", "o", "of", "off", "on", "once", "only", "or",
    "other", "our", "ours", "ourselves", "out", "over", "own", "re", "s", "same", "shan",
    "shant", "she", "shes", "should", "shouldn", "shouldnt", "so", "some", "such", "t",
    "than", "that", "thatll", "the", "their", "theirs", "them", "themselves", "then",
    "there", "these", "they", "this", "those", "through", "to", "too", "under", "until",
    "up", "ve", "very", "was", "wasn", "wasnt", "we", "were", "weren", "werent", "what",
    "when", "where", "which", "while", "who", "whom", "why", "will", "with", "won",
    "wont", "would", "wouldn", "wouldnt", "y", "you", "youd", "youll", "your", "youre",
    "yours", "yourself", "yourselves", "youve",

    # Conversational & research query fillers
    "also", "analyze", "breakdown", "changed", "clarify", "compare", "describe",
    "described", "describing", "detail", "details", "discuss", "explain", "explained",
    "find", "give", "given", "identify", "indicate", "information", "know", "like",
    "list", "look", "many", "mean", "mention", "mentioned", "much", "outline",
    "perform", "performed", "performing", "please", "primary", "provide", "provided",
    "regarding", "related", "report", "reported", "say", "see", "show", "showed",
    "showing", "state", "stated", "summarize", "summary", "tell", "told", "understand",
    "way", "well", "whether",
})


class ExtractedKeywords(BaseModel):
    terms: list[str] = Field(
        description=(
            "3 to 5 high-impact keyword search terms or phrases specifically tailored for "
            "finding relevant SEC 10-K filing sections (e.g., metric names, line items, product segments)."
        )
    )


def extract_terms_heuristic(
    query: str, min_terms: int = 3, max_terms: int = 5
) -> list[str]:
    """
    Rule-based fallback keyword extraction.
    Identifies financial multi-word phrases, quoted text, entity names, fiscal years,
    and high-signal nouns, stripping conversational and stop-word noise.
    Always returns between `min_terms` and `max_terms` (or as many as available).
    """
    cleaned_query = query.strip()
    extracted: list[str] = []
    seen: set[str] = set()

    def add_term(term: str) -> None:
        norm = term.strip().lower()
        if norm and norm not in seen and norm not in STOP_WORDS and len(norm) > 1:
            seen.add(norm)
            extracted.append(term.strip())

    # 1. Quoted phrases from user query
    for quoted in re.findall(r'["\']([^"\']+)["\']', cleaned_query):
        add_term(quoted)

    # 2. Known financial phrases (case-insensitive match against original query)
    lower_query = cleaned_query.lower()
    for phrase in KNOWN_FINANCIAL_PHRASES:
        if phrase in lower_query:
            # Preserve original casing if possible
            start_idx = lower_query.find(phrase)
            add_term(cleaned_query[start_idx : start_idx + len(phrase)])

    # 3. Fiscal year patterns (e.g., "fiscal 2024", "FY2024", "2024")
    for fy in re.findall(r"\b(?:fiscal\s+\d{4}|FY\d{2,4}|\b20\d{2}\b)\b", cleaned_query, flags=re.IGNORECASE):
        add_term(fy)

    # 4. Known companies / product lines / capitalized entities
    # Tokenize words, removing punctuation
    raw_tokens = re.findall(r"[A-Za-z0-9\-\']+", cleaned_query)
    for token in raw_tokens:
        clean_token = token.strip("'-")
        lower_token = clean_token.lower()
        if lower_token in STOP_WORDS or len(clean_token) < 2:
            continue
        # Avoid adding redundant single words already covered in extracted phrases
        if any(lower_token in s for s in seen):
            continue
        add_term(clean_token)

    # If we have more than max_terms, trim
    if len(extracted) > max_terms:
        extracted = extracted[:max_terms]

    # If we have fewer than min_terms, add any remaining non-stop words
    if len(extracted) < min_terms:
        for token in raw_tokens:
            clean_token = token.strip("'-")
            lower_token = clean_token.lower()
            if lower_token not in seen and len(clean_token) > 2:
                add_term(clean_token)
            if len(extracted) >= min_terms:
                break

    return extracted[:max_terms]


def extract_keyword_terms(
    query: str,
    use_llm: bool = False,
    min_terms: int = 3,
    max_terms: int = 5,
) -> list[str]:
    """
    Extract 3 to 5 high-impact keyword search terms from a natural language user query.
    
    Uses Gemini structured output (gemini-3.6-flash) when enabled and available,
    with an automatic fallback to an intelligent financial heuristic extractor
    if the API is rate-limited, times out, or unavailable.
    """
    if not query or not query.strip():
        return []

    if use_llm and settings.gemini_api_key:
        try:
            client = genai.Client(api_key=settings.gemini_api_key)
            prompt = (
                "You are an expert financial search analyzer for SEC 10-K filings.\n"
                "Given the user query, extract exactly 3 to 5 concise, high-signal keyword search terms or short phrases.\n"
                "Focus on:\n"
                "- Exact financial line items, metrics, and accounting terms (e.g., 'net sales', 'operating income', 'traffic acquisition costs')\n"
                "- Key business segments, products, or units (e.g., 'iPhone', 'AWS', 'Data Center', 'Azure')\n"
                "- Company names, tickers, and fiscal years (e.g., 'Apple', 'fiscal 2024')\n"
                "Do NOT include conversational verbs, questions, or generic words (e.g., 'what was', 'how did', 'describe', 'perform').\n\n"
                f"User Query: {query.strip()}"
            )
            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": ExtractedKeywords,
                },
            )

            if response.text:
                data = json.loads(response.text)
                terms = [t.strip() for t in data.get("terms", []) if t and t.strip()]
                if len(terms) >= min_terms:
                    return terms[:max_terms]
                elif terms:
                    # Pad up to min_terms using heuristic
                    heuristic_pad = extract_terms_heuristic(query, min_terms=min_terms, max_terms=max_terms)
                    for ht in heuristic_pad:
                        if ht.lower() not in [t.lower() for t in terms]:
                            terms.append(ht)
                        if len(terms) >= min_terms:
                            break
                    return terms[:max_terms]

        except Exception as exc:
            logger.warning(
                "LLM keyword extraction encountered an error; falling back to heuristic extractor",
                error=str(exc),
            )

    # Heuristic fallback
    return extract_terms_heuristic(query, min_terms=min_terms, max_terms=max_terms)


def format_terms_for_fts(terms: Sequence[str]) -> str:
    """
    Format a sequence of keyword terms into a PostgreSQL websearch_to_tsquery compatible string.
    
    - Multi-word phrases are wrapped in double quotes for exact word adjacency ('phrase' <-> 'match').
    - Individual terms are joined with 'OR' so chunks matching any or multiple terms match,
      and PostgreSQL's ts_rank ranks chunks higher if they contain more of the matched terms.
    """
    formatted_parts: list[str] = []
    for term in terms:
        clean = term.strip().strip('"').strip("'")
        if not clean:
            continue
        if " " in clean:
            formatted_parts.append(f'"{clean}"')
        else:
            formatted_parts.append(clean)

    return " OR ".join(formatted_parts) if formatted_parts else ""
