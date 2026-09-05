import os
import logging
import feedparser
from newsapi import NewsApiClient
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

logger = logging.getLogger(__name__)

class SentimentAnalyzer:
    def __init__(self):
        self.newsapi_key = os.getenv("NEWS_API_KEY")
        if self.newsapi_key:
            self.newsapi = NewsApiClient(api_key=self.newsapi_key)
        else:
            self.newsapi = None

        self.vader = SentimentIntensityAnalyzer()
        self.use_finbert = False
        
        # Initialize FinBERT
        try:
            from transformers import pipeline
            # Suppress excessive huggingface hardware warnings
            os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3" 
            
            logger.info("Loading FinBERT NLP model. This may take a moment if not cached...")
            self.finbert = pipeline(
                "text-classification", 
                model="ProsusAI/finbert", 
                device=-1  # Force CPU inference
            )
            self.use_finbert = True
            logger.info("✅ FinBERT successfully loaded.")
        except ImportError:
            logger.warning("⚠️ 'transformers' or 'torch' not found. Falling back to VADER.")
        except Exception as e:
            logger.warning(f"⚠️ Could not load FinBERT ({e}). Falling back to VADER.")

    def fetch_news_headlines(self, company_name: str, market: str = "US") -> list:
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
                logger.error(f"NewsAPI error: {e}")
        
        # Fallback: Google News RSS
        try:
            safe_name = company_name.replace(" ", "+")
            rss_url = f"https://news.google.com/rss/search?q={safe_name}+stock&hl=en-IN"
            feed = feedparser.parse(rss_url)
            headlines += [entry.title for entry in feed.entries[:10]]
        except Exception as e:
            logger.error(f"RSS fetch error: {e}")

        # Deduplicate and limit to top 15
        return list(dict.fromkeys(headlines))[:15]

    def analyze_sentiment(self, headlines: list) -> dict:
        """Compute aggregate sentiment score using FinBERT or VADER fallback."""
        if not headlines:
            return {"score": 0.0, "label": "NEUTRAL", "count": 0}

        scores = []
        
        if self.use_finbert:
            try:
                # Batch processing for efficiency
                results = self.finbert(headlines)
                for res in results:
                    label = res['label']
                    conf = res['score']
                    
                    if label == 'positive':
                        scores.append(conf)
                    elif label == 'negative':
                        scores.append(-conf)
                    else:
                        scores.append(0.0)
            except Exception as e:
                logger.error(f"❌ FinBERT inference failed: {e}. Falling back to VADER.")
                self._run_vader(headlines, scores)
        else:
            self._run_vader(headlines, scores)

        avg_score = sum(scores) / len(scores) if scores else 0.0
        
        # Adjust thresholds slightly for FinBERT's higher confidence ranges
        threshold = 0.15 if self.use_finbert else 0.05
        label = "POSITIVE" if avg_score > threshold else "NEGATIVE" if avg_score < -threshold else "NEUTRAL"

        return {
            "score": round(avg_score, 3),
            "label": label,
            "count": len(headlines),
            "headlines_sample": headlines[:3]
        }

    def _run_vader(self, headlines: list, scores: list):
        """Standard VADER fallback logic."""
        for headline in headlines:
            vs = self.vader.polarity_scores(headline)
            scores.append(vs['compound'])

    def get_stock_sentiment(self, ticker: str, company_name: str, market: str = "US") -> dict:
        # Skip sentiment for broad ETFs
        etf_keywords = ['GOLD', 'SILV', 'BEES', 'ETF', 'MON100', 'VOO', 'SCHD', 'USD']
        if any(kw in ticker.upper() for kw in etf_keywords):
            return {
                "score": 0.0, 
                "label": "NEUTRAL", 
                "count": 0, 
                "headlines_sample": ["ETF - No news sentiment required."]
            }
            
        headlines = self.fetch_news_headlines(company_name, market)
        return self.analyze_sentiment(headlines)