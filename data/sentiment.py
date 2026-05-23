from newsapi import NewsApiClient
import feedparser
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import os

class SentimentAnalyzer:
    def __init__(self):
        self.vader = SentimentIntensityAnalyzer()
        self.newsapi_key = os.getenv("NEWS_API_KEY")
        if self.newsapi_key:
            self.newsapi = NewsApiClient(api_key=self.newsapi_key)

    def fetch_news_headlines(self, company_name: str, market: str = "US") -> list:
        """Fetch news headlines for a given company."""
        headlines = []
        if market == "US" and self.newsapi_key:
            try:
                articles = self.newsapi.get_everything(
                    q=company_name,
                    language='en',
                    sort_by='publishedAt',
                    page_size=10
                )
                headlines = [a['title'] for a in articles.get('articles', [])]
            except Exception as e:
                print(f"NewsAPI error: {e}")
        
        # Fallback: Google News RSS
        try:
            rss_url = f"https://news.google.com/rss/search?q={company_name}+stock&hl=en-IN"
            feed = feedparser.parse(rss_url)
            headlines += [entry.title for entry in feed.entries[:10]]
        except Exception:
            pass

        return headlines[:15]

    def analyze_sentiment(self, headlines: list) -> dict:
        """Compute aggregate sentiment score."""
        if not headlines:
            return {"score": 0.0, "label": "NEUTRAL", "count": 0}

        scores = []
        for headline in headlines:
            vs = self.vader.polarity_scores(headline)
            scores.append(vs['compound'])

        avg_score = sum(scores) / len(scores)
        label = "POSITIVE" if avg_score > 0.05 else "NEGATIVE" if avg_score < -0.05 else "NEUTRAL"

        return {
            "score": round(avg_score, 3),
            "label": label,
            "count": len(headlines),
            "headlines_sample": headlines[:3]
        }

    def get_stock_sentiment(self, ticker: str, company_name: str, market: str = "US") -> dict:
        headlines = self.fetch_news_headlines(company_name, market)
        return self.analyze_sentiment(headlines)