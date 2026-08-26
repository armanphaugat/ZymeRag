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

WEB_SEARCH_PROMPT = """System: You are a Precise Technical Assistant.
            Core Instruction: Answer ONLY using the provided Context. Do not use external knowledge.
            Rules:
            1. Context Check:
            -If answer exists in Context → Provide it with relevant citations.
            -If answer NOT in Context → Reply: "I don't have this information online either" (In user's language)
            2. No Hallucinations:
            - Never fabricate facts, examples, or details not in Context.
            - If uncertain, say so explicitly.
            3. Language Handling:
            - Detect user's question language automatically.
            - Respond in the SAME language as the question.
            - If user specifies a different language (e.g., "answer in Spanish"), use that language instead.
            - Maintain clarity: always prioritize user's language preference over context language.

            4. Citation & References:
            - Quote or reference specific sections from Context when possible.
            - Format: "According to [source], ..."
 
            5. Tone & Style:
            - Be concise, professional, and direct.
            - Avoid unnecessary elaboration.
            - Use bullet points only if context already uses them.
Context: {context}
User Question: {question}
Sources: {sources}
Response:"""


class WebSearchFallback:
    """
    Fallback Web Search component for RAG pipeline.
    Uses Tavily and Exa search APIs (with highlights) to retrieve external web context,
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
            temperature=0,
            api_key=key
        )

    def search_tavily(self, question: str, max_results: int = 5) -> Tuple[str, List[str]]:
        """
        Execute search using Tavily API and return (context_text, sources_urls).
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
            content = r.get("content", "")
            if content:
                context.append(content)
            url = r.get("url", "")
            if url:
                sources.append(url)

        return "\n\n".join(context), sources

    def search_exa(self, question: str, num_results: int = 5) -> Tuple[str, List[str]]:
        """
        Execute search using Exa API with highlights enabled and return (context_text, sources_urls).
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
            num_results=num_results,
            contents={"highlights": True}
        )
        if not response.results:
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

    def synthesize_answer(self, question: str, context: str, sources: List[str]) -> str:
        """
        Synthesize answer from web search context using ChatGroq and WEB_SEARCH_PROMPT.
        """
        llm = self.get_llm()
        prompt = ChatPromptTemplate.from_template(WEB_SEARCH_PROMPT)
        chain = prompt | llm | StrOutputParser()
        sources_str = "\n".join(f"- {url}" for url in sources) if sources else "None"
        
        answer = chain.invoke({
            "context": context,
            "sources": sources_str,
            "question": question
        })
        return f"Web Search Result (not from knowledge base):\n\n{answer}"

    def web_search_fallback(self, question: str) -> Optional[str]:
        """
        Attempts web search via Tavily first, then Exa if Tavily fails, and synthesizes the final response.
        """
        tavily_key = self.tavily_api_key or os.getenv("TAVILY_API_KEY")
        exa_key = self.exa_api_key or os.getenv("EXA_API_KEY")

        if tavily_key:
            try:
                context, sources = self.search_tavily(question)
                print(f"Web search succeeded via Tavily for: {question[:60]}")
                return self.synthesize_answer(question, context, sources)
            except Exception as e:
                print(f"Tavily search failed: {e}")

        if exa_key:
            try:
                context, sources = self.search_exa(question)
                print(f"Web search succeeded via Exa AI for: {question[:60]}")
                return self.synthesize_answer(question, context, sources)
            except Exception as e:
                print(f"Exa AI search failed: {e}")

        if not tavily_key and not exa_key:
            print("No web search API keys configured (TAVILY_API_KEY / EXA_API_KEY)")
        else:
            print("All web search providers failed")

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
    ) -> Dict[str, Any]:
        """
        Evaluates KB chunks. If insufficient, triggers web_search_fallback to retrieve and synthesize answer.
        """
        if self.is_kb_sufficient(kb_chunks, threshold=threshold):
            return {
                "source": "kb",
                "is_fallback": False,
                "chunks": kb_chunks,
                "answer": None
            }

        print(f"[WebSearchFallback] KB results insufficient or empty. Triggering web search fallback...")
        synthesized_answer = await asyncio.to_thread(self.web_search_fallback, query)
        
        return {
            "source": "web_fallback",
            "is_fallback": True,
            "chunks": [],
            "answer": synthesized_answer
        }


# Standalone function maintaining exact compatibility with old implementation
def web_search_fallback(question: str) -> Optional[str]:
    fallback_instance = WebSearchFallback()
    return fallback_instance.web_search_fallback(question)
