import os
import sys
import feedparser
import requests
from groq import Groq

# ---------------------------------------------------------
# CONFIGURATION & ENVIRONMENT INJECTION
# ---------------------------------------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# High-signal AI news feed
RSS_URL = "https://techcrunch.com/category/artificial-intelligence/feed/"

# Early validation to fail fast if orchestration variables are missing
if not all([GROQ_API_KEY, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
    print("Critical Error: Missing required environment variables.", file=sys.stderr)
    sys.exit(1)

# Initialize the Groq inference engine client
client = Groq(api_key=GROQ_API_KEY)

def fetch_and_aggregate_news() -> str:
    """Parses the upstream RSS feed and extracts top entries."""
    print("Fetching raw data from RSS feed...")
    feed = feedparser.parse(RSS_URL)
    
    if not feed.entries:
        print("Warning: No entries found in the RSS feed.")
        return ""
        
    # Restrict processing to top 3 articles to conserve token context window
    target_entries = feed.entries[:3]
    
    extracted_payload = ""
    for entry in target_entries:
        title = entry.get("title", "No Title Available")
        link = entry.get("link", "#")
        summary = entry.get("summary", "No summary text provided.")
        
        extracted_payload += f"Title: {title}\nLink: {link}\nContext: {summary}\n\n"
        
    return extracted_payload

def generate_ai_summary(raw_news_payload: str) -> str:
    """Invokes the Llama 3.3 model to synthesize the raw news items."""
    if not raw_news_payload:
        return "🤖 No new AI updates were identified in the source feeds today."

    print("Invoking Groq API for text synthesis...")
    
    system_instruction = (
        "You are an elite software architect tracking artificial intelligence industry developments. "
        "Your task is to convert raw RSS article payloads into an executive daily briefing."
    )
    
    # Updated prompt: explicitly forbidding <ul> and <li>, using standard text bullets
    user_prompt = (
        f"Analyze the following raw news items and compile a clean, punchy HTML daily report "
        f"optimized for Telegram mobile viewing.\n\n"
        f"CRITICAL FORMATTING RULES:\n"
        f"1. Use standard text dashes (-) or bullets (•) for list items. Do NOT use <ul> or <li> tags.\n"
        f"2. Use <b>text</b> for bold headers or key terms.\n"
        f"3. Wrap links inline using exactly this syntax: <a href=\"LINK\">Headline text</a>\n"
        f"4. Do not use any markdown notation (like asterisks or backticks). Return ONLY valid Telegram HTML.\n\n"
        f"Raw news data:\n{raw_news_payload}"
    )

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=1024
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Inference error encountered: {e}", file=sys.stderr)
        sys.exit(1)

def dispatch_telegram_payload(content: str):
    """Executes a POST request to deliver the summary to Telegram."""
    print("Dispatching finalized brief to Telegram...")
    endpoint = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": content,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
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
