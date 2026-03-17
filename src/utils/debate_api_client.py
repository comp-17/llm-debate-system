"""
LLM API Client for Debate Pipeline
Supports multiple LLM providers
"""

import os
import anthropic
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class DebateAPIClient:
    """Unified API client for LLM calls"""
    
    def __init__(self, model: str = "claude-3-5-sonnet-20241022", provider: str = "anthropic"):
        """
        Initialize API client
        
        Args:
            model: Model name/ID
            provider: "anthropic" (default)
        """
        self.model = model
        self.provider = provider
        
        if provider == "anthropic":
            self.client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        else:
            raise ValueError(f"Provider {provider} not supported")
    
    def call(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7
    ) -> str:
        """
        Make LLM API call
        
        Args:
            prompt: Prompt text
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            
        Returns:
            Generated text response
        """
        try:
            if self.provider == "anthropic":
                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                return message.content[0].text
        except Exception as e:
            logger.error(f"API call failed: {e}")
            raise
    
    def call_with_system(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7
    ) -> str:
        """Call with system prompt"""
        try:
            if self.provider == "anthropic":
                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": user_prompt}
                    ]
                )
                return message.content[0].text
        except Exception as e:
            logger.error(f"API call failed: {e}")
            raise
