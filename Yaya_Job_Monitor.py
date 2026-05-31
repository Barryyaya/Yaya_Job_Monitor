#!/usr/bin/env python3
"""
Reddit Game Jobs Monitor
Scrapes game dev job/collaboration posts from multiple subreddits
Stores results in Notion and sends summary via Telegram
"""

import praw
import os
import json
from datetime import datetime, timedelta

# Config
SUBREDDITS = ['gamejobs', 'INAT', 'gamedev', 'leveldesign', 'EnvironmentArt']
KEYWORDS = [
    'looking for', 'hiring', 'recruiting', 'job',
    'game designer', 'level designer', 'environment artist',
    'qa', 'quality assurance', 'project manager', 'pm',
    'need artist', 'need programmer', 'need sound',
    'collaboration', 'team up', 'partner'
]
DAYS_BACK = 7
NOTION_TOKEN = open(os.path.expanduser('~/.config/notion/api_key')).read().strip()
NOTION_DATABASE_ID = 'personal data' //Put your database ID

def load_config():
    config_path = os.path.expanduser('~/.config/reddit-crawler/config.json')
    with open(config_path) as f:
        return json.load(f)

def create_reddit_instance():
    """Create Reddit instance with cookie-based auth for better access"""
    config = load_config()
    reddit = praw.Reddit(
        client_id="",
        client_secret="",
        user_agent="[App Name]/1.0 (game jobs scraper)", //Put your user agent app name in [App Name]
        username=config['username'],
        password=config['password']
    )
    return reddit

def search_posts(reddit):
    """Search subreddits for relevant job/collaboration posts"""
    results = []
    cutoff_date = datetime.utcnow() - timedelta(days=DAYS_BACK)
    
    for subreddit_name in SUBREDDITS:
        subreddit = reddit.subreddit(subreddit_name)
        
        # Search by hot + new, filtered by keywords
        for post in subreddit.hot(limit=100):
            post_date = datetime.fromtimestamp(post.created_utc)
            
            if post_date < cutoff_date:
                continue
            
            # Check title and body for keywords
            title_lower = post.title.lower()
            body_lower = post.selftext.lower() if hasattr(post, 'selftext') else ''
            
            matched = any(kw in title_lower or kw in body_lower for kw in KEYWORDS)
            
            if matched or any(kw in title_lower for kw in ['looking for', 'hiring', 'recruiting']):
                results.append({
                    'title': post.title,
                    'url': post.url,
                    'subreddit': subreddit_name,
                    'author': str(post.author),
                    'score': post.score,
                    'created': post_date.isoformat(),
                    'flair': post.link_flair_text or '',
                    'body_preview': post.selftext[:500] if hasattr(post, 'selftext') else ''
                })
        
        # Also check new posts
        for post in subreddit.new(limit=50):
            post_date = datetime.fromtimestamp(post.created_utc)
            
            if post_date < cutoff_date:
                continue
            
            title_lower = post.title.lower()
            
            if any(kw in title_lower for kw in KEYWORDS):
                # Avoid duplicates from hot
                if not any(r['url'] == post.url for r in results):
                    results.append({
                        'title': post.title,
                        'url': post.url,
                        'subreddit': subreddit_name,
                        'author': str(post.author),
                        'score': post.score,
                        'created': post_date.isoformat(),
                        'flair': post.link_flair_text or '',
                        'body_preview': post.selftext[:500] if hasattr(post, 'selftext') else ''
                    })
    
    return results

def format_telegram_message(posts):
    """Format results for Telegram summary"""
    if not posts:
        return "🎮 本週 Reddit 遊戲職缺/合作文章：0 篇\n\n沒有找到符合條件的徵才或合作文。"
    
    msg = f"🎮 **本週 Reddit 遊戲職缺/合作文** ({len(posts)} 篇)\n\n"
    
    for i, post in enumerate(posts[:10], 1):
        msg += f"**{i}.** [{post['title']}]({post['url']})\n"
        msg += f"📍 r/{post['subreddit']} · 👍 {post['score']}\n\n"
    
    if len(posts) > 10:
        msg += f"...還有 {len(posts) - 10} 篇更多，見 Notion。"
    
    return msg

def save_to_notion(posts):
    """Save posts to Notion database"""
    import requests
    
    headers = {
        'Authorization': f'Bearer {NOTION_TOKEN}',
        'Notion-Version': '2025-09-03',
        'Content-Type': 'application/json'
    }
    
    for post in posts:
        data = {
            'parent': {'database_id': NOTION_DATABASE_ID},
            'properties': {
                'Title': {'title': [{'text': {'content': post['title'][:200]}}]},
                'Subreddit': {'select': {'name': post['subreddit']}},
                'Author': {'rich_text': [{'text': {'content': post['author']}}]},
                'Score': {'number': post['score']},
                'Posted Date': {'date': {'start': post['created'][:10]}},
                'URL': {'url': post['url']},
                'Flair': {'select': {'name': post['flair']} if post['flair'] else None},
            },
            'children': [{
                'object': 'block',
                'type': 'paragraph',
                'paragraph': {'rich_text': [{'text': {'content': post['body_preview'][:2000]}}]}
            }]
        }
        
        try:
            r = requests.post('https://api.notion.com/v1/pages', headers=headers, json=data)
            if r.status_code not in [200, 201]:
                print(f"Failed to save: {post['title'][:30]} - {r.status_code}")
        except Exception as e:
            print(f"Error saving to Notion: {e}")

def main():
    print(f"[{datetime.now().isoformat()}] Starting Reddit job crawl...")
    
    try:
        reddit = create_reddit_instance()
        posts = search_posts(reddit)
        print(f"Found {len(posts)} relevant posts")
        
        if posts:
            save_to_notion(posts)
        
        msg = format_telegram_message(posts)
        print(msg)
        
    except Exception as e:
        print(f"Crawl failed: {e}")

if __name__ == '__main__':
    main()
