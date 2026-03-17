"""Anthropic API client wrapper with retry logic and rate limiting."""

import time
import json
from typing import Optional
from anthropic import Anthropic

class APIClient:
    """Wrapper around Anthropic API with retry logic and rate limiting."""
    
    def __init__(self, config: dict):
        """Initialize API client with configuration."""
        self.client = Anthropic()
        self.config = config
        self.model = config['model']['name']
        self.temperature = config['model']['temperature']
        self.max_tokens = config['model']['max_tokens']
        self.retry_attempts = config['api']['retry_attempts']
        self.timeout = config['api']['timeout_seconds']
        self.rate_limit_delay = config['api']['rate_limit_delay']
        self.call_count = 0
        
    def call(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Make API call with retry logic.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system context
            
        Returns:
            Model response text
        """
        for attempt in range(self.retry_attempts):
            try:
                # Rate limiting
                time.sleep(self.rate_limit_delay)
                
                # Prepare messages
                messages = [{"role": "user", "content": prompt}]
                
                # Make API call
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    system=system_prompt,
                    messages=messages
                )
                
                self.call_count += 1
                return response.content[0].text
                
            except Exception as e:
                if attempt < self.retry_attempts - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    print(f"API call failed (attempt {attempt + 1}). Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise Exception(f"API call failed after {self.retry_attempts} attempts: {str(e)}")
        
    def get_call_count(self) -> int:
        """Return total API calls made."""
        return self.call_count
