import os
import json
from ddgs import DDGS
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from openai import OpenAI
from tavily import TavilyClient
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from supabase import create_client, Client
from firecrawl import FirecrawlApp, V1ScrapeOptions


load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "http://127.0.0.1:3000",
        "http://localhost:5500",
        "http://127.0.0.1:5500"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_ANON_KEY")

supabase: Client = create_client(supabase_url, supabase_key)
security = HTTPBearer()

def verify_supa(credentials: HTTPAuthorizationCredentials = Depends(security) ):
    token = credentials.credentials
    try:
        user_claims  = supabase.auth.get_claims(token)
        return user_claims
    except Exception as e:
        print("jwt token error", e)
client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key= os.environ.get("ai_key")
)

gemini_client = OpenAI(
    base_url= "https://generativelanguage.googleapis.com/v1beta/openai/",
    api_key= os.environ.get("gemini_key")
)

tavily_client = TavilyClient(api_key=os.environ.get("tavily_key"))

fire_client = FirecrawlApp(api_key=os.environ.get("fire_key"))


@app.get("/")
def index():
    return{"name":"how are you"}
@app.get("/logs")
def get_logs(user = Depends(verify_supa)):
    user_id = None
    if isinstance(user,dict):
        user_id = user.get("claims", {}).get("sub") or user.get("id") or user.get("sub") or user.get("user")
    response = supabase.table("search_logs").select("*").eq("user_id",user_id).order("created_at",desc=True).execute()
    return {"logs": response.data}
@app.get("/get")
def get_res(q:str):
    fire = fire_client.search(
                    query = q,
                    limit=5,
                    scrape_options = {
                        "formats":["markdown"],
                        "onlyMainContent": True
                    }
                )
    ans = [res.markdown for res in fire.web if getattr(res, "markdown", None)is not None]
    return{"query": q,
               "response": ans,
               }

@app.get("/search")
def open_search(q:str, user: dict = Depends(verify_supa)):
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
def opt_search(criteria:str, user: dict = Depends(verify_supa)):

    selecte_model = "llama-3.3-70b-versatile"
    choose_model = "llama-3.1-8b-instant"
    respons = client.chat.completions.create(
        model= choose_model,
        messages= [
            {
                "role": "system",
                "content": (
                    "You are the core routing engine for an AI research agent.\n\n"
                    "CRITICAL RULE - IGNORE META-FILLER:\n"
                    "Ignore phrases like 'do a deep research', 'tell me about', or 'give me details'. Judge the complexity of the actual core topic.\n\n"
                    "ROUTING RULES:\n"
                    "Option 1 (DuckDuckGo): Best for simple facts, specific error codes, quick definitions, basic math, or simple programming syntax (e.g., 'python append list', 'HTTP 404 meaning').\n"
                    "Option 2 (Tavily): Best for broad multi-source research, market analysis, news synthesis, or comparing multiple products (e.g., 'AI trends in healthcare 2026', 'competitors to Notion').\n"
                    "Option 3 (Firecrawl): Best for DEEP TECHNICAL or FULL-DOCUMENT research. Trigger this if the query contains a specific URL, asks for deep implementation guides, complex technical documentation, or full-page extraction (e.g., 'how semantic search vector embeddings are implemented', 'read this github repo').\n\n"
                    "You MUST respond with exactly the single character '1', '2', or '3'."
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
                        "You will receive a raw user query and the selected search engine choice:\n"
                        "- Choice '1' = DuckDuckGo (Keyword Search)\n"
                        "- Choice '2' = Tavily (Semantic RAG Search)\n"
                        "- Choice '3' = Firecrawl (Deep Document/Documentation Search)\n\n"
                        "REWRITING RULES:\n"
                        "1. STRIP ALL CONVERSATIONAL FILLER (e.g., 'can you find', 'detailed report on').\n\n"
                        "2. IF CHOICE IS '1' (DuckDuckGo):\n"
                        "   - Convert to 3 to 6 highly specific keywords.\n"
                        "   - Use operators like site: or filetype: if applicable.\n"
                        "   - Example Output: 'FastAPI CORS middleware implementation'\n\n"
                        "3. IF CHOICE IS '2' (Tavily):\n"
                        "   - Rewrite into a clean, context-rich natural language query (8-15 words).\n"
                        "   - Make the intent explicit.\n"
                        "   - Example Output: 'Recent developments and market performance of NVIDIA in 2026'\n\n"
                        "4. IF CHOICE IS '3' (Firecrawl):\n"
                        "   - If a URL is present, preserve the URL exactly as is.\n"
                        "   - If no URL, rewrite into a targeted query for deep technical documentation or full-page extraction.\n"
                        "   - Example Output: 'semantic search implementation best practices vector embeddings'\n\n"
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

    
    try:
        if result == "1":
            engine_used = "duckduckgo"
            try:
                with DDGS() as ddgs:
                    respond = list(ddgs.text(final_prompt,max_results=5))
                search_result = [item["body"] for item in respond]
            except Exception as e:
                    print(f"duckduckgo error : {e}")
                    search_result = ["duckduckgo was timeout or blocked, please try again"]      
        elif result == "2":
                engine_used = "tavily"
                tavily_resp = tavily_client.search(query=final_prompt, max_results=5)
                search_result = [item["content"] for item in tavily_resp.get("results",[])]

        elif result == "3":
                engine_used = "firecrawl"
                fire_search = fire_client.search(
                                                query = final_prompt,
                                                limit=5,
                                                scrape_options = {
                                                    "formats":["markdown"],
                                                    "onlyMainContent": True
                                                }
                                            )
                search_result = [res.markdown for res in fire_search.web if getattr(res, "markdown", None)is not None]
    except Exception as e:
            print(e)
            engine_used = "duckduckgo"
            try:
                            with DDGS() as ddgs:
                                respond = list(ddgs.text(final_prompt,max_results=5))
                            search_result = [item["body"] for item in respond]
            except Exception as e:
                                print(f"duckduckgo error : {e}")
                                search_result = ["duckduckgo was timeout or blocked, please try again"]      
            print("there was an error search engine changed to duckducgo")
    final_result = "\n---\n".join(search_result)
    deep_scrape = 2
    chances = 2
    while chances >= 1:
        try:
            selecte_model_gem = "llama-3.3-70b-versatile"
            final_ai = client.chat.completions.create(
            model= selecte_model_gem,
            response_format= {"type":"json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                                "You are a helpful research assistant. Your task is to look at the provided search data, "
                                "make sense of it, eliminate duplicates, resolve contradictions logically, and deliver a "
                                "single, cohesive, well-structured answer to the user's original query."
                                "do not put extra symbols such as *"
                                "Analyze the user query, search for relevant web data using your search tool, and evaluate if the retrieved info is complete, accurate, and sufficient.\n\n"
                                "if the result is duckduckgo was timeout or blocked do not make status to need_deep_scrape ,let it be complete"
                                "You MUST respond strictly in the following JSON format:\n"
                                "{\n"
                                    '  "status": "COMPLETE" or "NEED_DEEP_SCRAPE",\n'
                                    '  "reason": "Why the data is sufficient or insufficient",\n'
                                    '  "target_url": "Specific URL that needs deep scraping (leave null if status is COMPLETE)",\n'
                                    '  "answer": "Your comprehensive answer based on search data (leave null if NEED_DEEP_SCRAPE)"\n'
                                    "}"
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
            raw_answer = final_ai.choices[0].message.content.strip()

            json_ans = json.loads(raw_answer)
            statu = json_ans.get("status")
            final_answer = json_ans.get("answer")

        except Exception as e:
              print("error", e)
              final_answer = "there was an issue in generating the answer"
              break

        if statu == "COMPLETE":
            print("got the answer")
            break
        elif statu == "NEED_DEEP_SCRAPE":
            print("fire")
            if deep_scrape == 1:
                final_answer = json_ans.get("reason") or "duckduckgo was timeout or blocked, please try again"
                chances = chances -1
                break
            else:    
                    engine_used = "duckduckgo"
                    try:
                        with DDGS() as ddgs:
                            respond = list(ddgs.text(final_prompt,max_results=5))
                        search_result = [item["body"] for item in respond]
                    except Exception as e:
                        print(f"duckduckgo error : {e}")
                        search_result = ["duckduckgo was timeout or blocked, please try again"]     
                    chances = chances-1
                    deep_scrape = deep_scrape - 1
            final_result = "\n---\n".join(search_result)
    user_id = None
    if isinstance(user, dict):
        user_id = user.get("claims", {}).get("sub") or user.get("sub") or user.get("user")
    else:
        user_id = getattr(user, "id", None)
    print (f"debug: extracted user -> {user_id}")
    supabase.table("search_logs").insert({
        "user_id": user_id,
        "raw_query": criteria,
        "engine_used": engine_used,
        "prompt": final_prompt,
        "agent_response": final_answer,
        "search_result": search_result
    }).execute()

    return{
        "engine used": engine_used,
        "prompt": final_prompt,
        "search result":search_result,
        "agent response": final_answer
    }

