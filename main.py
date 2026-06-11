import os
import sys
import feedparser
import requests
from groq import Groq

# --- CORE FIX: Bypass Reddit's RSS Bot Blockers ---
feedparser.USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 AI-News-Agent/1.0"

# ---------------------------------------------------------
# CONFIGURATION & ENVIRONMENT INJECTION
# ---------------------------------------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not all([GROQ_API_KEY, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
    print("Critical Error: Missing required environment variables.", file=sys.stderr)
    sys.exit(1)

client = Groq(api_key=GROQ_API_KEY)

# ---------------------------------------------------------
# CATEGORIZED FEED DICTIONARY
# ---------------------------------------------------------
RSS_FEEDS = {
    "Enterprise Integration & .NET": [
        "https://devblogs.microsoft.com/semantic-kernel/feed/",
        "https://devblogs.microsoft.com/dotnet/category/ai/feed/"
    ],
    "Local Inference & Edge AI": [
        "https://github.com/ollama/ollama/releases.atom",
        "https://www.reddit.com/r/LocalLLaMA/.rss"
    ],
    "Architecture & Standards": [
        "https://github.com/modelcontextprotocol/modelcontextprotocol/releases.atom",
        "https://blog.bytebytego.com/feed"
    ],
    "Vector & RAG Engineering": [
        "https://www.pinecone.io/blog/rss.xml",
        "https://weaviate.io/blog/rss.xml"
    ]
}

def fetch_and_aggregate_news() -> str:
    """Iterates through the categorized dictionary and extracts top entries."""
    print("Fetching raw data from categorized RSS feeds...")
    extracted_payload = ""
    
    for category, urls in RSS_FEEDS.items():
        extracted_payload += f"=== {category} ===\n"
        
        for url in urls:
            try:
                feed = feedparser.parse(url)
                # Take ONLY the top 2 recent items per feed to avoid token bloat
                target_entries = feed.entries[:2]
                
                for entry in target_entries:
                    title = entry.get("title", "No Title Available")
                    link = entry.get("link", "#")
                    # Safely grab the summary and chop it to 500 chars so we don't send Groq 10 pages of HTML
                    summary = entry.get("summary", entry.get("description", ""))[:500] 
                    
                    extracted_payload += f"Title: {title}\nLink: {link}\nContext: {summary}...\n\n"
            except Exception as e:
                print(f"Failed to parse {url}: {e}", file=sys.stderr)
                
        extracted_payload += "\n"
        
    return extracted_payload

def generate_ai_summary(raw_news_payload: str) -> str:
    """Invokes the Llama 3.3 model to synthesize the multi-category payload."""
    if not raw_news_payload.strip():
        return "🤖 No new AI updates were identified in the source feeds today."

    print("Invoking Groq API for categorized text synthesis...")
    
    system_instruction = (
        "You are an elite software architect tracking artificial intelligence industry developments. "
        "Your task is to convert raw RSS article payloads into an executive daily briefing grouped by technical categories."
    )
    
    user_prompt = (
        f"Analyze the following raw categorized news items and compile a clean, punchy HTML daily report "
        f"optimized for Telegram mobile viewing.\n\n"
        f"CRITICAL FORMATTING RULES:\n"
        f"1. Use standard text dashes (-) or bullets (•) for list items. Do NOT use <ul> or <li> tags.\n"
        f"2. Use <b>text</b> for bold category headers and key terms.\n"
        f"3. Group the news strictly under the categories provided in the raw data.\n"
        f"4. Wrap links inline using exactly this syntax: <a href=\"LINK\">Headline text</a>\n"
        f"5. Write 1 or 2 high-signal bullet points summarizing the most important items per category. Skip trivial updates.\n"
        f"6. Do not use any markdown notation (like asterisks or backticks). Return ONLY valid Telegram HTML.\n\n"
        f"Raw news data:\n{raw_news_payload}"
    )

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3, # Low temperature keeps it analytical and strictly formatted
            max_tokens=2048   # Increased token limit to accommodate the larger multi-section report
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Inference error encountered: {e}", file=sys.stderr)
        sys.exit(1)

def dispatch_telegram_payload(content: str):
    """Executes a POST request to deliver the summary to Telegram."""
    print("Dispatching finalized categorized brief to Telegram...")
    endpoint = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": content,
        "parse_mode": "HTML",
        # Set to True! 8 links will generate 8 massive preview cards otherwise.
        "disable_web_page_preview": True 
    }
    
    try:
        response = requests.post(endpoint, json=payload, timeout=15)
        if response.status_code == 200:
            print("Orchestration pipeline executed successfully. Notification sent.")
        else:
            print(f"Telegram Delivery Failure ({response.status_code}): {response.text}", file=sys.stderr)
    except requests.exceptions.RequestException as e:
        print(f"Network exception during delivery: {e}", file=sys.stderr)

if __name__ == "__main__":
    raw_data = fetch_and_aggregate_news()
    executive_brief = generate_ai_summary(raw_data)
    dispatch_telegram_payload(executive_brief)
