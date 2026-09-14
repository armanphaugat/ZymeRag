import os
import asyncio
from typing import List, Dict, Any, Tuple, Optional
from dotenv import load_dotenv

load_dotenv(override=True)

try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None

try:
    from exa_py import Exa
except ImportError:
    Exa = None

try:
    from langchain_groq import ChatGroq
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser
except ImportError:
    ChatGroq = None
    ChatPromptTemplate = None
    StrOutputParser = None

WEB_SEARCH_PROMPT = """You are a Precise Technical Assistant for ZymeRag.
Core Instruction: Synthesize a helpful, accurate, and concise answer ONLY using the provided Web Context below.

Rules:
1. Context Check:
   - If the answer exists in the Context → Provide a detailed, accurate response citing the web sources.
   - If the answer is NOT in the Context → State clearly: "I could not find sufficient information from web search for this query."
2. Anti-Hallucination:
   - Do NOT invent or assume facts not grounded in the provided Context.
3. Language:
   - Automatically detect and respond in the same language as the user question.

Context:
{context}

Sources:
{sources}

User Question: {question}

Response:"""


class WebSearchFallback:
    """
    Fallback Web Search component for ZymeRag RAG pipeline.
    Uses Tavily and Exa search APIs to retrieve external web context,
    and synthesizes answers using ChatGroq (llama-3.3-70b-versatile) when local KB is insufficient.
    """

    def __init__(
        self,
        tavily_api_key: Optional[str] = None,
        exa_api_key: Optional[str] = None,
        groq_api_key: Optional[str] = None,
        llm_model: str = "llama-3.3-70b-versatile",
    ):
        self.tavily_api_key = tavily_api_key or os.getenv("TAVILY_API_KEY")
        self.exa_api_key = exa_api_key or os.getenv("EXA_API_KEY")
        self.groq_api_key = groq_api_key or os.getenv("GROQ_API_KEY")
        self.llm_model = llm_model

    def get_llm(self, api_key: Optional[str] = None):
        """
        Instantiate ChatGroq model using active Groq API Key.
        """
        if ChatGroq is None:
            raise ImportError("langchain_groq is not installed.")

        key = api_key or self.groq_api_key or os.getenv("GROQ_API_KEY")
        if not key:
            raise ValueError("GROQ_API_KEY is not set in environment or initialization.")

        return ChatGroq(
            model=self.llm_model,
            temperature=0.1,
            api_key=key
        )

    def search_tavily(self, question: str, max_results: int = 5) -> Tuple[str, List[str]]:
        """
        Execute synchronous Tavily search and return (context_text, list_of_source_urls).
        """
        key = self.tavily_api_key or os.getenv("TAVILY_API_KEY")
        if not key:
            raise ValueError("TAVILY_API_KEY is not configured")
        if TavilyClient is None:
            raise ImportError("tavily python package is not installed")

        client = TavilyClient(api_key=key)
        response = client.search(question, max_results=max_results)
        results = response.get("results", [])
        if not results:
            raise ValueError("Tavily returned no results")

        context = []
        sources = []
        for r in results:
            content = r.get("content", "").strip()
            if content:
                context.append(content)
            url = r.get("url", "").strip()
            if url:
                sources.append(url)

        return "\n\n".join(context), sources

    def search_exa(self, question: str, max_results: int = 5) -> Tuple[str, List[str]]:
        """
        Execute synchronous Exa search with highlights and return (context_text, list_of_source_urls).
        """
        key = self.exa_api_key or os.getenv("EXA_API_KEY")
        if not key:
            raise ValueError("EXA_API_KEY is not configured")
        if Exa is None:
            raise ImportError("exa_py python package is not installed")

        client = Exa(api_key=key)
        response = client.search(
            question,
            type="auto",
            num_results=max_results,
            contents={"highlights": True}
        )
        if not getattr(response, "results", None):
            raise ValueError("Exa returned no results")

        context = []
        sources = []
        for r in response.results:
            if getattr(r, "highlights", None):
                context.append("\n".join(r.highlights))
            elif getattr(r, "text", None):
                context.append(r.text)
            url = getattr(r, "url", "")
            if url:
                sources.append(url)

        return "\n\n".join(context), sources

    async def async_search_tavily(self, question: str, max_results: int = 5) -> Tuple[str, List[str]]:
        """Non-blocking async wrapper for Tavily search."""
        return await asyncio.to_thread(self.search_tavily, question, max_results)

    async def async_search_exa(self, question: str, max_results: int = 5) -> Tuple[str, List[str]]:
        """Non-blocking async wrapper for Exa search."""
        return await asyncio.to_thread(self.search_exa, question, max_results)

    async def synthesize_answer_async(self, question: str, context: str, sources: List[str]) -> str:
        """
        Synthesize answer asynchronously using ChatGroq ainvoke.
        """
        if not context.strip():
            return "No web context found to synthesize an answer."

        llm = self.get_llm()
        prompt = ChatPromptTemplate.from_template(WEB_SEARCH_PROMPT)
        chain = prompt | llm | StrOutputParser()
        sources_str = "\n".join(f"- {url}" for url in sources) if sources else "None"

        answer = await chain.ainvoke({
            "context": context,
            "sources": sources_str,
            "question": question
        })
        return f"Web Search Result (Fallback):\n\n{answer}"

    def synthesize_answer(self, question: str, context: str, sources: List[str]) -> str:
        """
        Synchronous fallback for answer synthesis.
        """
        if not context.strip():
            return "No web context found to synthesize an answer."

        llm = self.get_llm()
        prompt = ChatPromptTemplate.from_template(WEB_SEARCH_PROMPT)
        chain = prompt | llm | StrOutputParser()
        sources_str = "\n".join(f"- {url}" for url in sources) if sources else "None"

        answer = chain.invoke({
            "context": context,
            "sources": sources_str,
            "question": question
        })
        return f"Web Search Result (Fallback):\n\n{answer}"

    async def web_search_fallback_async(
        self,
        question: str,
        provider: str = "both",
        max_results: int = 5
    ) -> Optional[str]:
        """
        Async web search fallback executing search and synthesis non-blockingly.
        """
        tavily_key = self.tavily_api_key or os.getenv("TAVILY_API_KEY")
        exa_key = self.exa_api_key or os.getenv("EXA_API_KEY")

        # Provider strategy: Tavily
        if provider in ("tavily", "both") and tavily_key:
            try:
                context, sources = await self.async_search_tavily(question, max_results=max_results)
                print(f"[WebSearchFallback] Tavily search succeeded for: '{question[:50]}'")
                return await self.synthesize_answer_async(question, context, sources)
            except Exception as e:
                print(f"[WebSearchFallback] Tavily search failed: {e}")

        # Provider strategy: Exa
        if provider in ("exa", "both") and exa_key:
            try:
                context, sources = await self.async_search_exa(question, max_results=max_results)
                print(f"[WebSearchFallback] Exa AI search succeeded for: '{question[:50]}'")
                return await self.synthesize_answer_async(question, context, sources)
            except Exception as e:
                print(f"[WebSearchFallback] Exa AI search failed: {e}")

        if not tavily_key and not exa_key:
            print("[WebSearchFallback] No web search API keys configured (TAVILY_API_KEY / EXA_API_KEY)")
        else:
            print("[WebSearchFallback] All requested web search providers failed")

        return None

    def web_search_fallback(self, question: str) -> Optional[str]:
        """
        Synchronous web search fallback.
        """
        tavily_key = self.tavily_api_key or os.getenv("TAVILY_API_KEY")
        exa_key = self.exa_api_key or os.getenv("EXA_API_KEY")

        if tavily_key:
            try:
                context, sources = self.search_tavily(question)
                return self.synthesize_answer(question, context, sources)
            except Exception as e:
                print(f"[WebSearchFallback] Tavily search failed: {e}")

        if exa_key:
            try:
                context, sources = self.search_exa(question)
                return self.synthesize_answer(question, context, sources)
            except Exception as e:
                print(f"[WebSearchFallback] Exa AI search failed: {e}")

        return None

    def is_kb_sufficient(self, kb_chunks: List[Any], threshold: float = 0.5) -> bool:
        """
        Determines if retrieved KB chunks are sufficient to answer the query.
        Returns False if chunks are empty or top score fails threshold.
        """
        if not kb_chunks:
            return False

        valid_scores = []
        for chunk in kb_chunks:
            if isinstance(chunk, (list, tuple)) and len(chunk) >= 2:
                score = chunk[1]
                if isinstance(score, (int, float)):
                    valid_scores.append(score)

        if not valid_scores:
            return True

        best_score = max(valid_scores)
        return best_score >= threshold

    async def evaluate_and_fallback(
        self,
        query: str,
        kb_chunks: List[Any],
        threshold: float = 0.5,
        provider: str = "both",
        max_results: int = 5,
    ) -> Dict[str, Any]:
        """
        Evaluates KB chunks. If insufficient, triggers async web search fallback.
        """
        if self.is_kb_sufficient(kb_chunks, threshold=threshold):
            return {
                "source": "kb",
                "is_fallback": False,
                "chunks": kb_chunks,
                "answer": None
            }

        print(f"[WebSearchFallback] KB results insufficient or empty. Triggering web search fallback...")
        synthesized_answer = await self.web_search_fallback_async(
            question=query,
            provider=provider,
            max_results=max_results
        )

        return {
            "source": "web_fallback",
            "is_fallback": True,
            "chunks": [],
            "answer": synthesized_answer
        }


# Standalone backward-compatible function
def web_search_fallback(question: str) -> Optional[str]:
    fallback_instance = WebSearchFallback()
    return fallback_instance.web_search_fallback(question)
