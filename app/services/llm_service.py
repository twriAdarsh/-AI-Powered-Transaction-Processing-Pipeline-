"""
Gemini LLM integration.
Handles merchant categorization and spending narrative generation.
"""
import json
import time
import logging
from typing import List, Dict, Any, Optional
import google.generativeai as genai

from app.config import get_settings
from app.utils.constants import (
    VALID_CATEGORIES,
    LLM_RETRY_MAX_ATTEMPTS,
    LLM_RETRY_BACKOFF_FACTOR,
    LLM_INITIAL_BACKOFF_SECONDS,
)

logger = logging.getLogger(__name__)


class LLMService:
    """Handles LLM interactions with Gemini API"""
    
    def __init__(self):
        """Initialize Gemini API"""
        settings = get_settings()
        
        if not settings.GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY not set — add it to .env to enable LLM features")
        
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = settings.GEMINI_MODEL
    
    @staticmethod
    def _retry_with_backoff(func, *args, **kwargs):
        """
        Execute function with exponential backoff retry logic
        
        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: If all retries fail
        """
        last_exception = None
        backoff = LLM_INITIAL_BACKOFF_SECONDS
        
        for attempt in range(LLM_RETRY_MAX_ATTEMPTS):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                logger.warning(
                    f"Attempt {attempt + 1}/{LLM_RETRY_MAX_ATTEMPTS} failed: {str(e)}"
                )
                
                if attempt < LLM_RETRY_MAX_ATTEMPTS - 1:
                    time.sleep(backoff)
                    backoff *= LLM_RETRY_BACKOFF_FACTOR
        
        raise last_exception
    
    def categorize_batch(self, merchants: List[str]) -> Dict[str, str]:
        """
        Categorize a batch of merchants using LLM
        
        Args:
            merchants: List of merchant names to categorize
            
        Returns:
            Dict mapping merchant to category
        """
        if not merchants:
            return {}
        
        # Create prompt for batch categorization
        prompt = self._create_categorization_prompt(merchants)
        
        def _call_api():
            model = genai.GenerativeModel(self.model)
            response = model.generate_content(prompt)
            return response.text
        
        try:
            response_text = self._retry_with_backoff(_call_api)
            categorizations = self._parse_categorization_response(response_text, merchants)
            return categorizations
        except Exception as e:
            logger.error(f"Categorization failed after retries: {str(e)}")
            return {}
    
    def generate_summary(
        self,
        total_spend_inr: float,
        total_spend_usd: float,
        top_merchants: List[Dict[str, Any]],
        anomaly_count: int,
        category_breakdown: Dict[str, float],
    ) -> Dict[str, Any]:
        """
        Generate narrative summary using LLM
        
        Args:
            total_spend_inr: Total spend in INR
            total_spend_usd: Total spend in USD
            top_merchants: List of top merchants with spending
            anomaly_count: Number of flagged anomalies
            category_breakdown: Spending by category
            
        Returns:
            Dict with narrative, risk_level, and top_merchants
        """
        # Create prompt for summary generation
        prompt = self._create_summary_prompt(
            total_spend_inr,
            total_spend_usd,
            top_merchants,
            anomaly_count,
            category_breakdown,
        )
        
        def _call_api():
            model = genai.GenerativeModel(self.model)
            response = model.generate_content(prompt)
            return response.text
        
        try:
            response_text = self._retry_with_backoff(_call_api)
            summary = self._parse_summary_response(response_text, top_merchants)
            return summary
        except Exception as e:
            logger.error(f"Summary generation failed after retries: {str(e)}")
            # Return default summary on failure
            return {
                "narrative": "Unable to generate narrative due to API failure.",
                "risk_level": "medium",
                "top_merchants": top_merchants,
            }
    
    @staticmethod
    def _create_categorization_prompt(merchants: List[str]) -> str:
        """Create prompt for merchant categorization"""
        merchants_str = "\n".join([f"{i+1}. {m}" for i, m in enumerate(merchants)])
        
        categories = ", ".join(VALID_CATEGORIES)
        
        prompt = f"""You are a transaction categorizer. Categorize the following merchants into one of these categories:
{categories}

Merchants to categorize:
{merchants_str}

Respond ONLY with a JSON object mapping each merchant to a category. Example:
{{"Starbucks": "Food", "Target": "Shopping"}}

Use exact merchant names as keys and valid categories as values."""
        
        return prompt
    
    @staticmethod
    def _create_summary_prompt(
        total_spend_inr: float,
        total_spend_usd: float,
        top_merchants: List[Dict[str, Any]],
        anomaly_count: int,
        category_breakdown: Dict[str, float],
    ) -> str:
        """Create prompt for summary generation"""
        
        top_merchants_str = "\n".join(
            [f"{m['merchant']}: ${m['total']:.2f}" for m in top_merchants[:5]]
        )
        
        category_str = "\n".join(
            [f"{cat}: ${amount:.2f}" for cat, amount in category_breakdown.items()]
        )
        
        prompt = f"""Analyze the following transaction summary and provide insights:

Total Spend:
- INR: {total_spend_inr:.2f}
- USD: {total_spend_usd:.2f}

Top Merchants:
{top_merchants_str}

Category Breakdown:
{category_str}

Flagged Anomalies: {anomaly_count}

Provide a JSON response with:
1. "narrative": A 2-3 sentence summary of spending patterns (string)
2. "risk_level": One of "low", "medium", or "high" based on anomaly count and spending patterns (string)

Example response:
{{"narrative": "User primarily spends on shopping and food with consistent monthly patterns.", "risk_level": "low"}}"""
        
        return prompt
    
    @staticmethod
    def _parse_categorization_response(response_text: str, merchants: List[str]) -> Dict[str, str]:
        """Parse categorization response from LLM"""
        try:
            # Try to extract JSON from response
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            
            if json_start == -1 or json_end == 0:
                logger.warning("No JSON found in categorization response")
                return {}
            
            json_str = response_text[json_start:json_end]
            categorizations = json.loads(json_str)
            
            # Validate and clean
            result = {}
            for merchant in merchants:
                cat = categorizations.get(merchant, "Other")
                # Ensure category is valid
                if cat not in VALID_CATEGORIES:
                    cat = "Other"
                result[merchant] = cat
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse categorization JSON: {str(e)}")
            return {}
    
    @staticmethod
    def _parse_summary_response(
        response_text: str, top_merchants: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Parse summary response from LLM"""
        try:
            # Try to extract JSON from response
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            
            if json_start == -1 or json_end == 0:
                logger.warning("No JSON found in summary response")
                return {
                    "narrative": "Transaction summary generated.",
                    "risk_level": "medium",
                    "top_merchants": top_merchants,
                }
            
            json_str = response_text[json_start:json_end]
            summary = json.loads(json_str)
            
            # Validate and set defaults
            narrative = summary.get("narrative", "Transaction summary generated.")
            risk_level = summary.get("risk_level", "medium")
            
            if risk_level not in {"low", "medium", "high"}:
                risk_level = "medium"
            
            return {
                "narrative": narrative,
                "risk_level": risk_level,
                "top_merchants": top_merchants,
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse summary JSON: {str(e)}")
            return {
                "narrative": "Transaction summary generated.",
                "risk_level": "medium",
                "top_merchants": top_merchants,
            }
