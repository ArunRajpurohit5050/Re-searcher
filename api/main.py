import requests
import json
from ddgs import DDGS
from fastapi import FastAPI
from openai import OpenAI
from tavily import TavilyClient
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key= "ai_key"
)

tavily_client = TavilyClient(api_key="tavily_key")


@app.get("/")
def index():
    return{"name":"how are you"}
@app.get("/get")
def get_res(q:str):
    with DDGS() as ddgs:
        search_got = list(ddgs.text(q,max_results=5))
        ans = [item["body"] for item in search_got]
    return{"query": q,
           "response": ans,
           }

@app.get("/search")
def open_search(q:str):
    selected_model = "llama-3.3-70b-versatile"

    response = client.chat.completions.create(
        model= selected_model,
        messages=[
            {
                "role" : "system",
                "content": "provide a consise response under 100 tokens"
            },
            {
                "role": "user",
                "content": q
            }
        ],
        max_tokens=100,
        temperature=0.5
    )
    return{"response": response.choices[0].message.content}

@app.get("/choose")
def opt_search(criteria:str):
    option1 = "java"
    option2 = "python"
    selecte_model = "llama-3.3-70b-versatile"

    respons = client.chat.completions.create(
        model= selecte_model,
        messages= [
            {
                "role": "system",
                "content": (
                    "You are a strict routing system for web search.\n"
                    "Option 1: DuckDuckGo (Best for standard facts, news, simple questions, programming syntax).\n"
                    "Option 2: Tavily (Best ONLY for complex research, deep technical dives, multi-part synthesis).\n"
                    "Analyze the user query and pick the best option.\n"
                    "You MUST respond with exactly the single character '1' or '2'.\n"
                    "Do not include any extra text, punctuation, or explanations."
                )
            },
            {
                "role": "user",
                "content": criteria
            }
            
        ],
        max_tokens= 10,
        temperature= 0.1
    )
    result = respons.choices[0].message.content.strip()
    ddgs_taivly_resp = client.chat.completions.create(
            model= selecte_model,
            messages=[
                {
                    "role": "system" ,
                    "content": (
                        "You are an expert Search Query Optimizer for an AI research agent.\n"
                        "You will receive a raw user query and a choice selection:\n"
                        "- Choice '1' = DuckDuckGo (Standard Keyword Search Engine)\n"
                        "- Choice '2' = Tavily (AI Semantic Search Engine)\n\n"
                        "REWRITING RULES:\n"
                        "1. IF CHOICE IS '1' (DuckDuckGo):\n"
                        "   - Remove conversational filler ('how to', 'can you', 'what is').\n"
                        "   - Keep 3 to 6 core keywords, technical terms, or library names.\n\n"
                        "2. IF CHOICE IS '2' (Tavily):\n"
                        "   - Rewrite into a clean, context-rich natural language query for semantic RAG search.\n"
                        "   - Target length 8 to 15 words.\n\n"
                        "OUTPUT FORMAT (Strict JSON only):\n"
                        '{"selected_engine": "DuckDuckGo" or "Tavily", "optimized_query": "rewritten query"}'
                    )
                },
                {
                    "role": "user",
                    "content": f"Choice: {result}\nRaw Query: {criteria}"
                }
            ]
        )
    raw_json = ddgs_taivly_resp.choices[0].message.content.strip()
    prcess = json.loads(raw_json)
    final_prompt = prcess.get("optimized_query",criteria)

    if result == "1":
        engine_used = "duckduckgo"
        with DDGS() as ddgs:
            respond = list(ddgs.text(final_prompt,max_results=5))
            search_result = [item["body"] for item in respond]

        
    elif result == "2":
        engine_used = "tavily"
        tavily_resp = tavily_client.search(query=final_prompt, max_results=5)
        search_result = [item["content"] for item in tavily_resp["results"]]
        
    else:
        print("error")
    final_result = "\n---\n".join(search_result)
    final_ai = client.chat.completions.create(
        model= selecte_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful research assistant. Your task is to look at the provided search data, "
                    "make sense of it, eliminate duplicates, resolve contradictions logically, and deliver a "
                    "single, cohesive, well-structured answer to the user's original query."
                )
            },
            {
                "role": "user",
                "content": (
                    f"original user request:{criteria}\n"
                    f"search prompt used:{final_prompt}\n"
                    f"search engine used:{engine_used}\n"
                    f"raw search context:{final_result}\n"
                    f"please provide your final response now:"
                )
            }
        ],
        temperature=0.3
    )
    final_answer = final_ai.choices[0].message.content.strip()

    return{
        "engine used": engine_used,
        "prompt": final_prompt,
        "search result":search_result,
        "agent response": final_answer
    }
