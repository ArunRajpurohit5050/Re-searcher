import os
import json
import arxiv
import wikipedia
import internetarchive
import yfinance as yf
from ddgs import DDGS
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from openai import OpenAI
from tavily import TavilyClient
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from supabase import create_client, Client
from firecrawl import FirecrawlApp, V1ScrapeOptions
from pymed import PubMed
from github import Github, Auth


# load main app ---
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
supa_admin_key = os.environ.get("supa_admin_key")
# auth part ---
supabase_admin = create_client(supabase_url, supa_admin_key)
supabase: Client = create_client(supabase_url, supabase_key)
security = HTTPBearer()

def verify_supa(credentials: HTTPAuthorizationCredentials = Depends(security) ):
    token = credentials.credentials
    try:
        user_claims  = supabase.auth.get_claims(token)
        return user_claims
    except Exception as e:
        print("jwt token error", e)

#all client load ---
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

xiv_client = arxiv.Client(
      page_size= 10,
      delay_seconds= 3.0,
      num_retries= 3
)

wikipedia.set_user_agent("RE-search/v1 (larry.reddit.reads@gmail.com)")

pubmed = PubMed(tool="RE-search", email="larry.reddit.reads@gmail.com")

github_key = os.environ.get("git_key")
auth = Auth.Token(github_key)

gt = Github(auth= auth)

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

@app.get("/config")
def get_key():
     return{
          "url": os.environ.get("SUPABASE_URL"),
          "key": os.environ.get("SUPABASE_ANON_KEY")
     }
    

# main ai search part ---
@app.get("/choose")
def opt_search(criteria:str,mode: str= "norm",user: dict = Depends(verify_supa)):
    print(mode)
    engine_api = "none"
    engine_used = "multiple"
    if mode=="norm":
    # api selection ---
        selecte_model = "openai/gpt-oss-120b"
        choose_model = "openai/gpt-oss-20b"
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
                        "Option 3 (Firecrawl): Best for DEEP TECHNICAL or FULL-DOCUMENT research. Trigger this if the query contains a specific URL, asks for deep implementation guides, complex technical documentation, or full-page extraction and if there is a link for a youtube video do not use firecrawl instead use duckduckgo (e.g., 'how semantic search vector embeddings are implemented', 'read this github repo').\n\n"
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

    # other api selection part ---
        if result == 1:
            engine_api = "duckduckgo"
        elif result == 2:
            engine_api = "tavily"
        elif result == 3:
            engine_api = "firecrawl"
        else:
            engine_api = "no info"
        other_api = client.chat.completions.create(
            model= selecte_model,
            response_format={"type":"json_object"},
            messages=[
                {
                        "role" :"system",
                        "content":(
                            "You are an expert Multi-Source Library Router and Search Query Optimizer for an AI research agent.\n"
                                "Your job is to analyze the raw user query, decide which specialized databases should be queried, "
                                "and generate custom, high-precision search queries for each active database.\n\n"

                                "LIBRARY SELECTION & QUERY REWRITING RULES:\n"
                                "1. **arxiv**:\n"
                                "   - Set 'use': true for AI, computer science, physics, mathematics, or academic research.\n"
                                "   - Query format: 3 to 6 technical terms or academic keywords (e.g., 'attention mechanism transformer').\n"
                                "2. **wikipedia**:\n"
                                "   - Set 'use': true for general encyclopedia facts, history, geography, or biographies.\n"
                                "   - Query format: Clean core concept name without filler (e.g., 'Quantum computing').\n"
                                "3. **pubmed**:\n"
                                "   - Set 'use': true for medical, biological, clinical, or healthcare research.\n"
                                "   - Query format: Medical terms, disease names, or drug keywords (e.g., 'CRISPR cas9 gene editing').\n"
                                "4. **internet_archive**:\n"
                                "   - Set 'use': true for historical texts, vintage books, old media, or archival documents.\n"
                                "   - Query format: Archival title, author, or historical event keywords.\n\n"
                                "5. **finance**:\n"
                                "   - Set 'finance_use': true for stock market data, company overviews, stock price history, or financial news.\n"
                                "   - Query format: The exact stock ticker symbol (e.g., 'AAPL', 'TSLA', 'NVDA').\n\n"
                                "6. **github**:\n"
                                "   - Set 'github_use': true for finding open-source code, GitHub repositories, software libraries, or developer tools.\n"
                                "   - Query format: Repository name, programming language, or tech stack keywords.\n"
                                


                                "GENERAL RULES:\n"
                                "- Strip all conversational filler ('can you search for', 'what is', 'do deep research').\n"
                                "- If a library is NOT relevant, set 'use': false and 'query': null.\n\n"

                                "OUTPUT FORMAT (Strict JSON only):\n"
                                "{\n"
                                '  "arxiv_use": true or false, "arxiv_query": "rewritten query or null",\n'
                                '  "wiki_use": true or false, "wiki_query": "rewritten query or null",\n'
                                '  "pub_use": true or false, "pub_query": "rewritten query or null",\n'
                                '  "internet_use": true or false, "internet_query": "rewritten query or null"\n'
                                '  "fin_use": true or false, "fin_query": "rewritten ticker or null",\n'
                                '  "github_use": true or false, "github_query": "rewritten query or null"\n'
                                "}\n"
                        )
                },
                {
                        "role": "user",
                        "content":(
                            f"raw user query:{criteria}\n"
                            f"choice made for search engine:{engine_api}\n"
                        )
                }
            ] 
        )
        raw_api = other_api.choices[0].message.content.strip()
        json_api = json.loads(raw_api)
    #api t/f
        arxiv_t = json_api.get("arxiv_use")
        wiki = json_api.get("wiki_use")
        pub = json_api.get("pub_use")
        internet = json_api.get("internet_use")
        fin = json_api.get("fin_use")
        git = json_api.get("github_use")
        print("ar",arxiv_t)
        print("wi",wiki)
        print("pu",pub)
        print("in",internet)
        print("fi",fin)
        print("gi",git)
    #api query
        arxiv_q = json_api.get("arxiv_query")
        wiki_q = json_api.get("wiki_query")
        pub_q = json_api.get("pub_query")
        internet_q = json_api.get("internet_query")
        fin_q = json_api.get("fin_query")
        git_q = json_api.get("github_query")
        print("query")
        print (arxiv_q)
        print(wiki_q)
        print(pub_q)
        print(internet_q)
        print(fin_q)
        print(git_q)

        all_info = []
    # arxiv
        if arxiv_t == True:
            xiv_search = arxiv.Search(
                    query = arxiv_q,
                    max_results = 3 ,
                    sort_by = arxiv.SortCriterion.SubmittedDate
                )
            answer = xiv_client.results(xiv_search)
            arxiv_res = [res.summary for res in answer]
            all_info.extend(arxiv_res)
    #wikipedia
        if wiki == True:
            try:
                search = wikipedia.search(wiki_q)
                match = search[0]
                wiki_res = wikipedia.summary(match)
                all_info.append(wiki_res)
            except Exception as e:
                wiki_res = "there was an error in getting wiki"
                all_info.append(wiki_res)
    #pubmed
        if pub == True:
            result = pubmed.query(f"{pub_q} AND English[lang] AND medline[sb]", max_results=3)
            pub_res = [res.abstract for res in result]
            all_info.extend(pub_res)
    #internet archive
        if internet == True:
            result_i = internetarchive.search_items(internet_q, fields=["title","description"],params={'rows':1000})
            inter_res = [p.get("description","no description") for  p in result_i]
            all_info.extend(inter_res)
    #yfinance
        if fin == True:
            fina = []
            ticker = yf.Ticker(fin_q)
            inf = ticker.info
            his = ticker.history(period="1mo", interval = "1h").reset_index()
            news = ticker.news
            ans_his = json.loads(his.to_json(orient="records", date_format="iso"))
            fina.append(json.dumps(inf, indent=2))
            fina.append(json.dumps(news, indent=2))
            fina.append(json.dumps(ans_his, indent=2))
            fin_res = "\n\n--- info type break ---\n\n".join(fina)
            all_info.append(fin_res)
    #github
        if git == True:
            rep = gt.search_repositories(query=git_q, sort="stars",order="desc")
            git_res = [
                f"name : {r.full_name}\nstars:{r.stargazers_count}\ndesc:{r.description}\nurl:{r.html_url}"
                for r in rep
            ]
            all_info.extend(git_res)
        if not all_info:
            no_api = "no api selected"
            print(no_api)
            all_info.append(no_api)
        ans = "\n\n--- source break ---\n\n".join(all_info)
        print("got info")
    # query generator part ---
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

    # api search part ---
        try:
            search_result =[]
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
    # final answer generating part ---
        deep_scrape = 2
        chances = 2
        while chances >= 1:
            try:
                selecte_model_gem = "gemini-3.6-flash"
                final_ai = gemini_client.chat.completions.create(
                model= selecte_model_gem,
                response_format= {"type":"json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": (
                                    "You are a helpful research assistant. Your task is to look at the provided search data, "
                                    "make sense of it, eliminate duplicates, resolve contradictions logically, and deliver a "
                                    "single, cohesive, well-structured answer to the user's original query."
                                    "also read the other api answer which are arxiv, wikipedia, pubmed, internet archive use their information to gain more info and use this info in the final answer making"
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
                                            f"other api context:{ans}\n"
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
        print ("extracted user")
        supabase_admin.table("search_logs").insert({
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
    if mode=="max":
         selected_model = "openai/gpt-oss-120b"
         ai_prom = client.chat.completions.create(
              model= selected_model,
              response_format= {"type": "json_object"},
              messages=[
                   {
                        "role": "system",
                        "content":(
                             "You are an expert Search Query Optimizer for an AI research agent.\n"
                             "REWRITING RULES:\n"
                             "1. STRIP ALL CONVERSATIONAL FILLER (e.g., 'can you find', 'detailed report on').\n\n"
                             "2. DuckDuckGo:\n"
                             "   - Convert to 3 to 6 highly specific keywords.\n"
                             "   - Use operators like site: or filetype: if applicable.\n"
                             "   - Example Output: 'FastAPI CORS middleware implementation'\n\n"
                             "3. Tavily:\n"
                             "   - Rewrite into a clean, context-rich natural language query (8-15 words).\n"
                             "   - Make the intent explicit.\n"
                             "   - Example Output: 'Recent developments and market performance of NVIDIA in 2026'\n\n"
                             "4. Firecrawl:\n"
                             "   - If a URL is present, preserve the URL exactly as is.\n"
                             "   - If no URL, rewrite into a targeted query for deep technical documentation or full-page extraction.\n"
                             "   - Example Output: 'semantic search implementation best practices vector embeddings'\n\n"
                             "OUTPUT FORMAT (Strict JSON only):\n"
                             "{\n"
                             '"duckduckgo_query": "rewritten query",\n'
                             '"tavily_query": "rewritten query",\n'
                             '"firecrawl_query": "rewritten query",\n'
                             "}\n"
                             
                        )
                   },
                   {
                        "role": "user",
                        "content": (
                             f"raw_query: {criteria}\n"
                        )
                   }
              ]
              
         )

         json_max = ai_prom.choices[0].message.content.strip()
         load_max = json.loads(json_max)
         duck_q = load_max.get("duckduckgo_query")
         tavily_q = load_max.get("tavily_query")
         fire_q = load_max.get("firecrawl_query")
         print(duck_q)
         print(tavily_q)
         print(fire_q)
         final_ans =[]
         try:
              with DDGS() as ddgs:
                respond = list(ddgs.text(duck_q,max_results=5))
                ddgs_res = [item["body"] for item in respond]
         except Exception as e :
              ddgs_res="error in ddgs"
         tavily_resp = tavily_client.search(query=tavily_q, max_results=5)
         tav_res = [item["content"] for item in tavily_resp.get("results",[])]
         fire_search = fire_client.search(
                                                             query = fire_q,
                                                             limit=5,
                                                             scrape_options = {
                                                                 "formats":["markdown"],
                                                                 "onlyMainContent": True
                                                             }
                                                         )
         fire_res = [res.markdown for res in fire_search.web if getattr(res, "markdown", None)is not None]
         final_ans.extend(ddgs_res)
         final_ans.extend(tav_res)
         final_ans.extend(fire_res)
         fin_answer= "\n\n--- source break ---\n\n".join(final_ans)

         other_api = client.chat.completions.create(
                        model= selected_model,
                        response_format={"type":"json_object"},
                        messages=[
                            {
                                    "role" :"system",
                                    "content":(
                                        "You are an expert Multi-Source Library Router and Search Query Optimizer for an AI research agent.\n"
                                            "Your job is to analyze the raw user query, decide which specialized databases should be queried, "
                                            "and generate custom, high-precision search queries for each active database.\n\n"

                                            "LIBRARY SELECTION & QUERY REWRITING RULES:\n"
                                            "1. **arxiv**:\n"
                                            "   - Set 'use': true for AI, computer science, physics, mathematics, or academic research.\n"
                                            "   - Query format: 3 to 6 technical terms or academic keywords (e.g., 'attention mechanism transformer').\n"
                                            "2. **wikipedia**:\n"
                                            "   - Set 'use': true for general encyclopedia facts, history, geography, or biographies.\n"
                                            "   - Query format: Clean core concept name without filler (e.g., 'Quantum computing').\n"
                                            "3. **pubmed**:\n"
                                            "   - Set 'use': true for medical, biological, clinical, or healthcare research.\n"
                                            "   - Query format: Medical terms, disease names, or drug keywords (e.g., 'CRISPR cas9 gene editing').\n"
                                            "4. **internet_archive**:\n"
                                            "   - Set 'use': true for historical texts, vintage books, old media, or archival documents.\n"
                                            "   - Query format: Archival title, author, or historical event keywords.\n\n"
                                            "5. **finance**:\n"
                                            "   - Set 'finance_use': true for stock market data, company overviews, stock price history, or financial news.\n"
                                            "   - Query format: The exact stock ticker symbol (e.g., 'AAPL', 'TSLA', 'NVDA').\n\n"
                                            "6. **github**:\n"
                                            "   - Set 'github_use': true for finding open-source code, GitHub repositories, software libraries, or developer tools.\n"
                                            "   - Query format: Repository name, programming language, or tech stack keywords.\n"
                                            


                                            "GENERAL RULES:\n"
                                            "- Strip all conversational filler ('can you search for', 'what is', 'do deep research').\n"
                                            "- If a library is NOT relevant, set 'use': false and 'query': null.\n\n"

                                            "OUTPUT FORMAT (Strict JSON only):\n"
                                            "{\n"
                                            '  "arxiv_use": true or false, "arxiv_query": "rewritten query or null",\n'
                                            '  "wiki_use": true or false, "wiki_query": "rewritten query or null",\n'
                                            '  "pub_use": true or false, "pub_query": "rewritten query or null",\n'
                                            '  "internet_use": true or false, "internet_query": "rewritten query or null"\n'
                                            '  "fin_use": true or false, "fin_query": "rewritten ticker or null",\n'
                                            '  "github_use": true or false, "github_query": "rewritten query or null"\n'
                                            "}\n"
                                    )
                            },
                            {
                                    "role": "user",
                                    "content":(
                                        f"raw user query:{criteria}\n"
                                        f"choice made for search engine:{engine_api}\n"
                                    )
                            }
                        ] 
                    )
         try:
                    raw_api = other_api.choices[0].message.content.strip()
                    json_api = json.loads(raw_api)
                #api t/f
                    arxiv_t = json_api.get("arxiv_use")
                    wiki = json_api.get("wiki_use")
                    pub = json_api.get("pub_use")
                    internet = json_api.get("internet_use")
                    fin = json_api.get("fin_use")
                    git = json_api.get("github_use")
                    print("ar",arxiv_t)
                    print("wi",wiki)
                    print("pu",pub)
                    print("in",internet)
                    print("fi",fin)
                    print("gi",git)
                #api query
                    arxiv_q = json_api.get("arxiv_query")
                    wiki_q = json_api.get("wiki_query")
                    pub_q = json_api.get("pub_query")
                    internet_q = json_api.get("internet_query")
                    fin_q = json_api.get("fin_query")
                    git_q = json_api.get("github_query")
                    print("query")
                    print (arxiv_q)
                    print(wiki_q)
                    print(pub_q)
                    print(internet_q)
                    print(fin_q)
                    print(git_q)

                    all_info = []
                # arxiv
                    if arxiv_t == True:
                        xiv_search = arxiv.Search(
                                query = arxiv_q,
                                max_results = 3 ,
                                sort_by = arxiv.SortCriterion.SubmittedDate
                            )
                        answer = xiv_client.results(xiv_search)
                        arxiv_res = [res.summary for res in answer]
                        all_info.extend(arxiv_res)
                #wikipedia
                    if wiki == True:
                        try:
                            search = wikipedia.search(wiki_q)
                            match = search[0]
                            wiki_res = wikipedia.summary(match)
                            all_info.append(wiki_res)
                        except Exception as e:
                            wiki_res = "there was an error in getting wiki"
                            all_info.append(wiki_res)
                #pubmed
                    if pub == True:
                        result = pubmed.query(f"{pub_q} AND English[lang] AND medline[sb]", max_results=3)
                        pub_res = [res.abstract for res in result]
                        all_info.extend(pub_res)
                #internet archive
                    if internet == True:
                        result_i = internetarchive.search_items(internet_q, fields=["title","description"],params={'rows':1000})
                        inter_res = [p.get("description","no description") for  p in result_i]
                        all_info.extend(inter_res)
                #yfinance
                    if fin == True:
                        fina = []
                        ticker = yf.Ticker(fin_q)
                        inf = ticker.info
                        his = ticker.history(period="1mo", interval = "1h").reset_index()
                        news = ticker.news
                        ans_his = json.loads(his.to_json(orient="records", date_format="iso"))
                        fina.append(json.dumps(inf, indent=2))
                        fina.append(json.dumps(news, indent=2))
                        fina.append(json.dumps(ans_his, indent=2))
                        fin_res = "\n\n--- info type break ---\n\n".join(fina)
                        all_info.append(fin_res)
                #github
                    if git == True:
                        rep = gt.search_repositories(query=git_q, sort="stars",order="desc")
                        git_res = [
                            f"name : {r.full_name}\nstars:{r.stargazers_count}\ndesc:{r.description}\nurl:{r.html_url}"
                            for r in rep
                        ]
                        all_info.extend(git_res)
                    if not all_info:
                        no_api = "no api selected"
                        print(no_api)
                        all_info.append(no_api)
                    ans = "\n\n--- source break ---\n\n".join(all_info)
                    print("got ans")
         except Exception as e:
              print("there was an error")
              ans = "no api info"
         selecte_model_gem = "gemini-3.6-flash"
         final_anser = gemini_client.chat.completions.create(
              model = selecte_model_gem,
              messages=[
                   {
                        "role":"system",
                        "content":(
                             "You are a helpful research assistant. Your task is to look at the provided search data, "
                             "make sense of it, eliminate duplicates, resolve contradictions logically, and deliver a "
                             "single, cohesive, well-structured answer to the user's original query."
                             "and also include most of the info and give the user the most amount of info,"
                             "also read the other api answer which are arxiv, wikipedia, pubmed, internet archive use their information to gain more info and use this info in the final answer making"
                             "Analyze the user query, search for relevant web data using your search tool, and evaluate if the retrieved info is complete, accurate, and sufficient.\n\n"
                             "if the result is duckduckgo was timeout or blocked do not make status to need_deep_scrape ,let it be complete"
                             "You MUST respond strictly in the following JSON format:\n"
                             "{\n"
                             '  "answer": "Your comprehensive answer based on search data"\n'
                             "}\n"

                        )
                   },
                   {
                        "role":"user",
                        "content":(
                             f"raw query: {criteria}\n"
                             f"scrapped info:{fin_answer}\n"
                             f"other libraries and api info: {ans}\n"
                        )
                   }
              ]
         )
         ai_don = final_anser.choices[0].message.content.strip()
         json_ai = json.loads(ai_don)   
         final_answer = json_ai.get("answer")
         print("hi", ans)   
         return{
              "agent response": final_answer
         }  
