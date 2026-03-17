"""Judge agents for the debate system."""

import json
from typing import Dict, List, Any
from src.utils.api_client import APIClient
from src.utils.utils import load_prompt, format_prompt

class JudgeSingle:
    """Single judge that evaluates the debate."""
    
    def __init__(self, api_client: APIClient):
        """Initialize judge."""
        self.api_client = api_client
        self.name = "Judge"
        self.verdict = None
    
    def evaluate(self, question: str, debater_a_position: str, debater_b_position: str,
                 debate_transcript: str) -> Dict[str, Any]:
        """
        Evaluate the debate and render a verdict.
        
        Args:
            question: Original debate question
            debater_a_position: Debater A's position
            debater_b_position: Debater B's position
            debate_transcript: Full transcript of the debate
            
        Returns:
            Judge's verdict as dictionary
        """
        prompt_template = load_prompt("judge_single")
        
        prompt = format_prompt(
            prompt_template,
            question=question,
            debater_a_answer=debater_a_position,
            debater_b_answer=debater_b_position,
            debate_transcript=debate_transcript
        )
        
        response = self.api_client.call(prompt)
        
        # Parse verdict
        verdict = self._parse_verdict(response)
        self.verdict = verdict
        
        return verdict
    
    def _parse_verdict(self, response: str) -> Dict[str, Any]:
        """Parse judge's verdict from response."""
        verdict = {
            'response': response,
            'judge': self.name,
            'winner': None,
            'confidence': None,  # Now numeric 1-5
            'scores': {'debater_a': None, 'debater_b': None}
        }
        
        # Extract winner
        if "Debater A" in response and "Winner: Debater A" in response:
            verdict['winner'] = 'Debater A'
        elif "Debater B" in response and "Winner: Debater B" in response:
            verdict['winner'] = 'Debater B'
        elif "Debater A" in response[:1000]:
            verdict['winner'] = 'Debater A'
        elif "Debater B" in response[:1000]:
            verdict['winner'] = 'Debater B'
        
        # FIXED: Extract numeric confidence (1-5)
        for conf_level in range(5, 0, -1):
            if f"Confidence: {conf_level}" in response or f"Confidence Score: {conf_level}" in response or f"confidence: {conf_level}" in response:
                verdict['confidence'] = conf_level
                break
        
        # Fallback: try to extract confidence as "Confidence: X" pattern
        if verdict['confidence'] is None:
            import re
            match = re.search(r'Confidence[:\s]+(\d)', response)
            if match:
                conf_val = int(match.group(1))
                if 1 <= conf_val <= 5:
                    verdict['confidence'] = conf_val
        
        # Try to extract scores
        try:
            if "Score:" in response:
                score_part = response.split("Score:")[-1].split("\n")[0]
                parts = score_part.split(",")
                for part in parts:
                    if "A:" in part:
                        verdict['scores']['debater_a'] = float(part.split(":")[1].strip())
                    elif "B:" in part:
                        verdict['scores']['debater_b'] = float(part.split(":")[1].strip())
        except:
            pass
        
        return verdict

class JuryMember:
    """Individual jury member in the judge panel."""
    
    def __init__(self, api_client: APIClient, member_id: int):
        """Initialize jury member."""
        self.api_client = api_client
        self.member_id = member_id
        self.name = f"Jury Member {member_id}"
        self.verdict = None
    
    def evaluate(self, question: str, debater_a_position: str, debater_b_position: str,
                 debate_transcript: str) -> Dict[str, Any]:
        """
        Independently evaluate the debate.
        
        Args:
            question: Original debate question
            debater_a_position: Debater A's position
            debater_b_position: Debater B's position
            debate_transcript: Full transcript of the debate
            
        Returns:
            Jury member's verdict
        """
        prompt_template = load_prompt("jury_member")
        
        prompt = format_prompt(
            prompt_template,
            question=question,
            debater_a_answer=debater_a_position,
            debater_b_answer=debater_b_position,
            debate_transcript=debate_transcript,
            jury_member_id=self.member_id
        )
        
        response = self.api_client.call(prompt)
        verdict = self._parse_verdict(response)
        self.verdict = verdict
        
        return verdict
    
    def _parse_verdict(self, response: str) -> Dict[str, Any]:
        """Parse jury member's verdict from response."""
        verdict = {
            'member_id': self.member_id,
            'response': response,
            'winner': None,
            'confidence': None,  # Now numeric 1-5
            'scores': {'debater_a': None, 'debater_b': None}
        }
        
        # Extract winner
        if "Debater A" in response and ("Winner: Debater A" in response or "Debater A wins" in response.lower()):
            verdict['winner'] = 'Debater A'
        elif "Debater B" in response and ("Winner: Debater B" in response or "Debater B wins" in response.lower()):
            verdict['winner'] = 'Debater B'
        
        # FIXED: Extract numeric confidence (1-5)
        for conf_level in range(5, 0, -1):
            if f"Confidence: {conf_level}" in response or f"Confidence: [{conf_level}" in response:
                verdict['confidence'] = conf_level
                break
        
        # Fallback: try to extract confidence as "Confidence: X" pattern
        if verdict['confidence'] is None:
            import re
            match = re.search(r'Confidence[:\s]+(\d)', response)
            if match:
                conf_val = int(match.group(1))
                if 1 <= conf_val <= 5:
                    verdict['confidence'] = conf_val
        
        # Try to extract scores
        try:
            if "Score:" in response:
                score_part = response.split("Score:")[-1].split("\n")[0]
                parts = score_part.split(",")
                for part in parts:
                    if "A:" in part:
                        verdict['scores']['debater_a'] = float(part.split(":")[1].strip())
                    elif "B:" in part:
                        verdict['scores']['debater_b'] = float(part.split(":")[1].strip())
        except:
            pass
        
        return verdict

class JuryPanel:
    """Panel of jury members that deliberates together."""
    
    def __init__(self, api_client: APIClient, jury_size: int = 3):
        """Initialize jury panel."""
        self.api_client = api_client
        self.jury_size = jury_size
        self.members = [JuryMember(api_client, i+1) for i in range(jury_size)]
        self.verdicts = []
        self.consensus = None
    
    def evaluate(self, question: str, debater_a_position: str, debater_b_position: str,
                 debate_transcript: str) -> Dict[str, Any]:
        """
        Run independent evaluations by all jury members.
        
        Args:
            question: Original debate question
            debater_a_position: Debater A's position
            debater_b_position: Debater B's position
            debate_transcript: Full transcript of the debate
            
        Returns:
            Dictionary containing all jury verdicts
        """
        print(f"\n[JURY EVALUATION] {self.jury_size} jury members evaluating debate...")
        
        self.verdicts = []
        for member in self.members:
            print(f"  Member {member.member_id} evaluating...")
            verdict = member.evaluate(question, debater_a_position, debater_b_position, debate_transcript)
            self.verdicts.append(verdict)
        
        return {
            'jury_verdicts': self.verdicts,
            'jury_size': self.jury_size
        }
    
    def deliberate(self, question: str, debater_a_position: str, debater_b_position: str,
                   debate_transcript: str) -> Dict[str, Any]:
        """
        Deliberate to reach consensus on verdict.
        
        Args:
            question: Original debate question
            debater_a_position: Debater A's position
            debater_b_position: Debater B's position
            debate_transcript: Full transcript of the debate
            
        Returns:
            Consensus verdict from jury panel
        """
        print("\n[JURY DELIBERATION] Jury members deliberating...")
        
        # Format verdicts for deliberation
        verdicts_text = ""
        for verdict in self.verdicts:
            verdicts_text += f"\nMember {verdict['member_id']}: Winner = {verdict['winner']}, Confidence = {verdict['confidence']}"
        
        prompt_template = load_prompt("jury_deliberation")
        
        prompt = format_prompt(
            prompt_template,
            question=question,
            debater_a_answer=debater_a_position,
            debater_b_answer=debater_b_position,
            debate_transcript=debate_transcript,
            jury_verdicts=verdicts_text
        )
        
        response = self.api_client.call(prompt)
        self.consensus = self._parse_consensus(response)
        
        return {
            'consensus_response': response,
            'consensus_verdict': self.consensus,
            'individual_verdicts': self.verdicts
        }
    
    def _parse_consensus(self, response: str) -> Dict[str, Any]:
        """Parse consensus verdict from deliberation response."""
        consensus = {
            'response': response,
            'winner': None,
            'confidence': None,  # Now numeric 1-5
            'scores': {'debater_a': None, 'debater_b': None}
        }
        
        # Extract winner
        if "Winner: Debater A" in response:
            consensus['winner'] = 'Debater A'
        elif "Winner: Debater B" in response:
            consensus['winner'] = 'Debater B'
        
        # FIXED: Extract numeric confidence (1-5)
        for conf_level in range(5, 0, -1):
            if f"Confidence: {conf_level}" in response or f"Confidence: [{conf_level}" in response:
                consensus['confidence'] = conf_level
                break
        
        # Fallback: try to extract confidence as "Confidence: X" pattern
        if consensus['confidence'] is None:
            import re
            match = re.search(r'Confidence[:\s]+(\d)', response)
            if match:
                conf_val = int(match.group(1))
                if 1 <= conf_val <= 5:
                    consensus['confidence'] = conf_val
        
        # Try to extract scores
        try:
            if "Final Scores:" in response:
                score_part = response.split("Final Scores:")[-1].split("\n")[0]
                parts = score_part.split(",")
                for part in parts:
                    if "A:" in part:
                        consensus['scores']['debater_a'] = float(part.split(":")[1].strip())
                    elif "B:" in part:
                        consensus['scores']['debater_b'] = float(part.split(":")[1].strip())
        except:
            pass
        
        return consensus
    
    def get_consensus_winner(self) -> str:
        """Get the consensus winner (majority vote if no deliberation consensus)."""
        if self.consensus and self.consensus['winner']:
            return self.consensus['winner']
        
        # Fallback to majority vote
        a_votes = sum(1 for v in self.verdicts if v['winner'] == 'Debater A')
        b_votes = sum(1 for v in self.verdicts if v['winner'] == 'Debater B')
        
        if a_votes > b_votes:
            return 'Debater A'
        elif b_votes > a_votes:
            return 'Debater B'
        else:
            return 'Tie'
