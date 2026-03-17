"""Debater agents for the debate system."""

from typing import Dict, List, Optional, Tuple
from src.utils.api_client import APIClient
from src.utils.utils import load_prompt, format_prompt, create_debate_context

class DebaterBase:
    """Base class for debater agents."""
    
    def __init__(self, api_client: APIClient, debater_name: str):
        """Initialize debater."""
        self.api_client = api_client
        self.name = debater_name
        self.argument_history = []
        self.position = None
    
    def _extract_answer_from_response(self, response: str) -> str:
        """Extract answer from response text."""
        # Simple extraction - look for common answer patterns
        response_lower = response.lower()
        
        if "yes" in response_lower and "no" in response_lower:
            # Look for explicit answer statement
            if "answer:" in response_lower:
                parts = response.split("ANSWER:")[-1].strip()
                return "Yes" if "yes" in parts.lower() else "No"
            return "Yes" if response_lower.find("yes") < response_lower.find("no") else "No"
        elif "yes" in response_lower:
            return "Yes"
        elif "no" in response_lower:
            return "No"
        
        return "Unknown"

class DebaterA(DebaterBase):
    """Debater A (Proponent) - argues in favor of answer."""
    
    def __init__(self, api_client: APIClient):
        """Initialize Debater A."""
        super().__init__(api_client, "Debater A (Proponent)")
    
    def initial_argument(self, question: str, ground_truth: Optional[str] = None) -> Tuple[str, str]:
        """
        Generate initial argument for Debater A.
        
        Args:
            question: The debate question
            ground_truth: Optional ground truth answer
            
        Returns:
            Tuple of (position/answer, full argument)
        """
        # FIXED: First, debater independently decides their position
        position_prompt = f"""You are preparing for a debate on the following question:

QUESTION: {question}

Before seeing the other debater's position, analyze this question carefully and decide:
Do you believe the answer is YES or NO?

Respond with ONLY:
POSITION: [YES or NO]
REASONING: [2-3 sentences explaining why]"""
        
        position_response = self.api_client.call(position_prompt)
        position = self._extract_answer_from_response(position_response)
        
        # If extraction failed, default to Yes for Debater A
        if position == "Unknown":
            position = "Yes"
        
        # Now generate the full argument with the decided position
        prompt_template = load_prompt("debater_a")
        prompt = format_prompt(
            prompt_template,
            question=question,
            your_answer=position,
            debate_context=create_debate_context(1)
        )
        
        response = self.api_client.call(prompt)
        self.position = position
        self.argument_history.append({
            'round': 1,
            'position': position,
            'argument': response
        })
        
        return position, response
    
    def rebut(self, question: str, opponent_position: str, 
              opponent_argument: str, round_num: int) -> str:
        """
        Generate rebuttal to Debater B's argument.
        
        Args:
            question: The debate question
            opponent_position: Debater B's position
            opponent_argument: Debater B's argument
            round_num: Current round number
            
        Returns:
            Rebuttal argument
        """
        prompt_template = load_prompt("debater_a")
        
        previous_args = [
            {'round': arg['round'], 'debater': self.name, 'argument': arg['argument']}
            for arg in self.argument_history
        ]
        
        context = create_debate_context(round_num, previous_args)
        context += f"\n\n**Debater B's Latest Argument:**\n{opponent_argument}"
        
        prompt = format_prompt(
            prompt_template,
            question=question,
            your_answer=self.position,
            debate_context=context
        )
        
        response = self.api_client.call(prompt)
        self.argument_history.append({
            'round': round_num,
            'position': self.position,
            'argument': response
        })
        
        return response

class DebaterB(DebaterBase):
    """Debater B (Opponent) - argues against Debater A's answer."""
    
    def __init__(self, api_client: APIClient):
        """Initialize Debater B."""
        super().__init__(api_client, "Debater B (Opponent)")
    
    def initial_argument(self, question: str, ground_truth: Optional[str] = None) -> Tuple[str, str]:
        """
        Generate initial argument for Debater B.
        
        Args:
            question: The debate question
            ground_truth: Optional ground truth answer
            
        Returns:
            Tuple of (position/answer, full argument)
        """
        # FIXED: Debater B independently decides their position WITHOUT knowing Debater A's position
        position_prompt = f"""You are preparing for a debate on the following question:

QUESTION: {question}

Before seeing the other debater's position, analyze this question carefully and decide:
Do you believe the answer is YES or NO?

Respond with ONLY:
POSITION: [YES or NO]
REASONING: [2-3 sentences explaining why]"""
        
        position_response = self.api_client.call(position_prompt)
        position = self._extract_answer_from_response(position_response)
        
        # If extraction failed, default to No for Debater B (opposite perspective)
        if position == "Unknown":
            position = "No"
        
        # Now generate the full argument with the decided position
        prompt_template = load_prompt("debater_b")
        prompt = format_prompt(
            prompt_template,
            question=question,
            opponent_answer="Unknown",  # Don't mention opponent position yet
            your_answer=position,
            debate_context=create_debate_context(1)
        )
        
        response = self.api_client.call(prompt)
        self.position = position
        self.argument_history.append({
            'round': 1,
            'position': position,
            'argument': response
        })
        
        return position, response
    
    def rebut(self, question: str, opponent_position: str,
              opponent_argument: str, round_num: int) -> str:
        """
        Generate rebuttal to Debater A's argument.
        
        Args:
            question: The debate question
            opponent_position: Debater A's position
            opponent_argument: Debater A's argument
            round_num: Current round number
            
        Returns:
            Rebuttal argument
        """
        prompt_template = load_prompt("debater_b")
        
        previous_args = [
            {'round': arg['round'], 'debater': self.name, 'argument': arg['argument']}
            for arg in self.argument_history
        ]
        
        context = create_debate_context(round_num, previous_args)
        context += f"\n\n**Debater A's Latest Argument:**\n{opponent_argument}"
        
        prompt = format_prompt(
            prompt_template,
            question=question,
            opponent_answer=opponent_position,
            your_answer=self.position,
            debate_context=context
        )
        
        response = self.api_client.call(prompt)
        self.argument_history.append({
            'round': round_num,
            'position': self.position,
            'argument': response
        })
        
        return response
    
    def check_convergence(self, debater_a_position: str) -> bool:
        """Check if Debater B agrees with Debater A."""
        return self.position == debater_a_position
