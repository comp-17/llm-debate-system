"""
Enhanced Multi-Agent Judge Panel with deliberation, disagreement analysis, and consensus quality metrics.
Inspired by VERDICT (Kalra et al., 2025) and Wang et al. (2023) self-consistency principles.
"""

import json
import re
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import statistics

from src.utils.api_client import APIClient
from src.utils.utils import load_prompt, format_prompt


class JuryMode(Enum):
    """Jury decision-making modes."""
    INDEPENDENT = "independent"  # No deliberation
    MAJORITY_VOTE = "majority_vote"  # Simple majority voting
    DELIBERATION = "deliberation"  # Interactive deliberation rounds
    WEIGHTED = "weighted"  # Confidence-weighted voting


@dataclass
class JuryVerdictData:
    """Data class for jury member verdict."""
    member_id: int
    winner: Optional[str]
    confidence: Optional[int]  # 1-5 scale
    reasoning: str
    scores: Dict[str, float]
    reasoning_quality_score: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class DisagreementMetrics:
    """Metrics for analyzing jury panel disagreement."""
    unanimous: bool  # All judges agree
    disagreement_level: float  # 0 = unanimous, 1 = maximum disagreement
    confidence_variance: float  # Variance in confidence scores
    winner_split: Dict[str, int]  # Count by winner {A: n, B: n, Tie: n}
    confidence_by_winner: Dict[str, List[int]]  # Confidence distribution per winner
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class DeliberationOutcome:
    """Tracks deliberation improvement."""
    round_number: int
    pre_deliberation_agreement: float  # % of jury agreeing before round
    post_deliberation_agreement: float  # % of jury agreeing after round
    changed_verdicts: int  # Number of members who changed their verdict
    consensus_confidence_change: float  # Change in average confidence
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class EnhancedJuryMember:
    """Individual jury member with enhanced reasoning tracking."""
    
    def __init__(self, api_client: APIClient, member_id: int, use_chain_of_thought: bool = True):
        """
        Initialize jury member.
        
        Args:
            api_client: API client for LLM calls
            member_id: Unique member identifier
            use_chain_of_thought: Whether to use CoT in reasoning (Wang et al., 2023)
        """
        self.api_client = api_client
        self.member_id = member_id
        self.name = f"Jury Member {member_id}"
        self.use_chain_of_thought = use_chain_of_thought
        self.verdict: Optional[JuryVerdictData] = None
        self.deliberation_history: List[JuryVerdictData] = []
    
    def evaluate(self, question: str, debater_a_position: str, debater_b_position: str,
                 debate_transcript: str, round_num: int = 1, 
                 other_verdicts: Optional[List[JuryVerdictData]] = None) -> JuryVerdictData:
        """
        Evaluate the debate with optional awareness of other jury members' verdicts.
        
        Args:
            question: Original debate question
            debater_a_position: Debater A's position/answer
            debater_b_position: Debater B's position/answer
            debate_transcript: Full transcript of the debate
            round_num: Deliberation round number (for multi-round deliberation)
            other_verdicts: Other jury members' verdicts (for deliberation rounds)
            
        Returns:
            JuryVerdictData with complete verdict information
        """
        # Select appropriate prompt template
        if round_num == 1:
            prompt_template = load_prompt("jury_member")
        else:
            prompt_template = load_prompt("jury_deliberation_round")
        
        # Format other verdicts for context (if available)
        other_verdicts_text = ""
        if other_verdicts:
            for v in other_verdicts:
                other_verdicts_text += (
                    f"\nMember {v.member_id}: {v.winner} "
                    f"(Confidence: {v.confidence}/5)"
                )
        
        # Build prompt with optional CoT instruction
        cot_instruction = (
            "Please think through this step-by-step, examining the key arguments, "
            "evidence quality, and reasoning coherence from both debaters.\n"
            if self.use_chain_of_thought else ""
        )
        
        prompt = format_prompt(
            prompt_template,
            question=question,
            debater_a_answer=debater_a_position,
            debater_b_answer=debater_b_position,
            debate_transcript=debate_transcript,
            jury_member_id=self.member_id,
            round_number=round_num,
            cot_instruction=cot_instruction,
            other_verdicts=other_verdicts_text,
            deliberation_context=self._build_deliberation_context(round_num, other_verdicts)
        )
        
        response = self.api_client.call(prompt)
        verdict = self._parse_verdict(response)
        
        # Store verdict history for deliberation tracking
        if round_num > 1:
            self.deliberation_history.append(verdict)
        
        self.verdict = verdict
        return verdict
    
    def _build_deliberation_context(self, round_num: int, 
                                   other_verdicts: Optional[List[JuryVerdictData]]) -> str:
        """Build context text for deliberation rounds."""
        if round_num == 1 or not other_verdicts:
            return ""
        
        context = f"\n[Deliberation Round {round_num}] "
        context += "Other jury members' initial positions:\n"
        
        for v in other_verdicts:
            context += f"  - Member {v.member_id}: {v.winner} (Confidence: {v.confidence}/5)\n"
        
        context += "\nPlease reconsider the evidence in light of your colleagues' perspectives. "
        context += "You may change your verdict if convinced by stronger evidence."
        
        return context
    
    def _parse_verdict(self, response: str) -> JuryVerdictData:
        """
        Parse jury member's verdict from LLM response.
        
        Returns:
            JuryVerdictData object with parsed information
        """
        winner = self._extract_winner(response)
        confidence = self._extract_confidence(response)
        scores = self._extract_scores(response)
        reasoning_quality = self._score_reasoning_quality(response)
        
        return JuryVerdictData(
            member_id=self.member_id,
            winner=winner,
            confidence=confidence,
            reasoning=response,
            scores=scores,
            reasoning_quality_score=reasoning_quality
        )
    
    def _extract_winner(self, response: str) -> Optional[str]:
        """Extract winner from response."""
        patterns = [
            r"Winner:\s*(Debater [AB])",
            r"(Debater [AB])\s+wins",
            r"chooses?\s+(Debater [AB])",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                return match.group(1)
        
        # Fallback: first mention
        if "Debater A" in response[:1000]:
            return "Debater A"
        elif "Debater B" in response[:1000]:
            return "Debater B"
        
        return None
    
    def _extract_confidence(self, response: str) -> Optional[int]:
        """Extract numeric confidence (1-5 scale)."""
        patterns = [
            r"Confidence:\s*(\d)",
            r"Confidence\s*Score:\s*(\d)",
            r"confidence:\s*(\d)",
            r"\[(\d)\s*/\s*5\]",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, response)
            if match:
                conf = int(match.group(1))
                if 1 <= conf <= 5:
                    return conf
        
        return None
    
    def _extract_scores(self, response: str) -> Dict[str, float]:
        """Extract debater scores from response."""
        scores = {"debater_a": None, "debater_b": None}
        
        try:
            patterns = [
                r"Score[s]?:.*?A:\s*([\d.]+).*?B:\s*([\d.]+)",
                r"Debater A:\s*([\d.]+).*?Debater B:\s*([\d.]+)",
            ]
            
            for pattern in patterns:
                match = re.search(pattern, response)
                if match:
                    scores["debater_a"] = float(match.group(1))
                    scores["debater_b"] = float(match.group(2))
                    break
        except (ValueError, IndexError):
            pass
        
        return scores
    
    def _score_reasoning_quality(self, response: str) -> float:
        """
        Score the quality of the reasoning (0-1 scale).
        Inspired by VERDICT's hierarchical reasoning verification.
        """
        quality = 0.0
        
        # Presence of structured reasoning
        quality += 0.2 if self._has_step_by_step_reasoning(response) else 0
        
        # Specific evidence citations
        quality += 0.2 if self._references_debate_content(response) else 0
        
        # Acknowledges counterarguments
        quality += 0.2 if self._acknowledges_both_positions(response) else 0
        
        # Clear justification
        quality += 0.2 if self._has_clear_justification(response) else 0
        
        # Appropriate confidence calibration
        quality += 0.2 if self._confidence_matches_reasoning(response) else 0
        
        return min(quality, 1.0)
    
    def _has_step_by_step_reasoning(self, response: str) -> bool:
        """Check if response shows structured reasoning."""
        keywords = ["first", "second", "additionally", "therefore", "because", "however", "in conclusion"]
        return sum(1 for kw in keywords if kw.lower() in response.lower()) >= 2
    
    def _references_debate_content(self, response: str) -> bool:
        """Check if response references specific debate content."""
        return response.count("Debater") >= 3 and len(response) > 300
    
    def _acknowledges_both_positions(self, response: str) -> bool:
        """Check if response discusses both debater positions."""
        return "Debater A" in response and "Debater B" in response
    
    def _has_clear_justification(self, response: str) -> bool:
        """Check for clear justification of verdict."""
        keywords = ["stronger", "better", "more convincing", "more logical", "more supported"]
        return any(kw in response.lower() for kw in keywords)
    
    def _confidence_matches_reasoning(self, response: str) -> bool:
        """Check if confidence level seems calibrated to reasoning quality."""
        has_caveats = any(word in response.lower() for word in ["however", "though", "nevertheless", "somewhat"])
        has_confidence = "confidence" in response.lower()
        
        # If has strong caveats, shouldn't have very high confidence
        return not (has_caveats and "5" in response and has_confidence)


class EnhancedJuryPanel:
    """
    Advanced jury panel with deliberation, disagreement analysis, and consensus quality tracking.
    Implements patterns from VERDICT (Kalra et al., 2025), Wang et al. (2023), and Kenton et al. (2024).
    """
    
    def __init__(self, api_client: APIClient, jury_size: int = 3, 
                 mode: JuryMode = JuryMode.DELIBERATION,
                 max_deliberation_rounds: int = 2,
                 use_chain_of_thought: bool = True):
        """
        Initialize enhanced jury panel.
        
        Args:
            api_client: API client for LLM calls
            jury_size: Number of jury members (3-5 recommended)
            mode: Decision-making mode
            max_deliberation_rounds: Maximum deliberation rounds
            use_chain_of_thought: Use CoT in jury reasoning
        """
        self.api_client = api_client
        self.jury_size = jury_size
        self.mode = mode
        self.max_deliberation_rounds = max_deliberation_rounds
        self.use_chain_of_thought = use_chain_of_thought
        
        # Initialize jury members
        self.members = [
            EnhancedJuryMember(api_client, i + 1, use_chain_of_thought)
            for i in range(jury_size)
        ]
        
        # Results tracking
        self.initial_verdicts: List[JuryVerdictData] = []
        self.final_verdicts: List[JuryVerdictData] = []
        self.deliberation_outcomes: List[DeliberationOutcome] = []
        self.final_consensus: Optional[Dict[str, Any]] = None
        self.disagreement_metrics: Optional[DisagreementMetrics] = None
    
    def evaluate(self, question: str, debater_a_position: str, debater_b_position: str,
                 debate_transcript: str, question_difficulty: Optional[float] = None) -> Dict[str, Any]:
        """
        Run full jury evaluation with optional deliberation.
        
        Args:
            question: Original debate question
            debater_a_position: Debater A's position
            debater_b_position: Debater B's position
            debate_transcript: Full debate transcript
            question_difficulty: Optional difficulty score (0-1) for analysis
            
        Returns:
            Dictionary with all jury results and metrics
        """
        print(f"\n[JURY PANEL] {self.jury_size} members evaluating debate")
        print(f"  Mode: {self.mode.value}")
        
        # Phase 1: Independent evaluation
        self._run_independent_evaluation(
            question, debater_a_position, debater_b_position, debate_transcript
        )
        
        # Phase 2: Deliberation (if applicable)
        if self.mode == JuryMode.DELIBERATION:
            self._run_deliberation(
                question, debater_a_position, debater_b_position, debate_transcript
            )
        
        # Phase 3: Consensus decision
        self._determine_consensus()
        
        # Phase 4: Metrics and analysis
        self._compute_metrics(question_difficulty)
        
        return self._build_result_dict()
    
    def _run_independent_evaluation(self, question: str, debater_a_position: str,
                                   debater_b_position: str, debate_transcript: str) -> None:
        """Phase 1: All jury members independently evaluate."""
        print("\n[PHASE 1] Independent Evaluation")
        
        for member in self.members:
            print(f"  {member.name} evaluating...")
            verdict = member.evaluate(
                question, debater_a_position, debater_b_position, debate_transcript
            )
            self.initial_verdicts.append(verdict)
        
        # Store initial verdicts as final (will be updated if deliberation happens)
        self.final_verdicts = [v for v in self.initial_verdicts]
    
    def _run_deliberation(self, question: str, debater_a_position: str,
                         debater_b_position: str, debate_transcript: str) -> None:
        """Phase 2: Multi-round deliberation with agreement tracking."""
        print("\n[PHASE 2] Deliberation")
        
        for round_num in range(1, self.max_deliberation_rounds + 1):
            print(f"  Deliberation Round {round_num}...")
            
            # Record pre-deliberation agreement
            pre_agreement = self._compute_agreement_rate(self.final_verdicts)
            
            # All members reconsider with awareness of others' verdicts
            round_verdicts = []
            for member in self.members:
                # Get other members' current verdicts
                other_verdicts = [
                    v for v in self.final_verdicts
                    if v.member_id != member.member_id
                ]
                
                # Evaluate in deliberation round
                verdict = member.evaluate(
                    question, debater_a_position, debater_b_position, debate_transcript,
                    round_num=round_num + 1,
                    other_verdicts=other_verdicts
                )
                round_verdicts.append(verdict)
            
            # Track changes
            changed = sum(
                1 for old, new in zip(self.final_verdicts, round_verdicts)
                if old.winner != new.winner
            )
            
            # Update final verdicts
            self.final_verdicts = round_verdicts
            
            # Record outcome
            post_agreement = self._compute_agreement_rate(self.final_verdicts)
            avg_confidence_before = statistics.mean(
                [v.confidence for v in self._get_round_verdicts(round_num - 1) if v.confidence]
            ) if round_num > 1 else 0
            avg_confidence_after = statistics.mean(
                [v.confidence for v in self.final_verdicts if v.confidence]
            )
            
            outcome = DeliberationOutcome(
                round_number=round_num,
                pre_deliberation_agreement=pre_agreement,
                post_deliberation_agreement=post_agreement,
                changed_verdicts=changed,
                consensus_confidence_change=avg_confidence_after - avg_confidence_before
            )
            self.deliberation_outcomes.append(outcome)
            
            print(f"    Changed: {changed}/{self.jury_size} | "
                  f"Agreement: {pre_agreement:.1%} → {post_agreement:.1%}")
            
            # Early stopping if consensus reached
            if post_agreement >= 0.8:  # 80% agreement threshold
                print(f"    → Strong consensus reached, stopping deliberation")
                break
    
    def _determine_consensus(self) -> None:
        """Phase 3: Determine final consensus verdict."""
        print("\n[PHASE 3] Consensus Decision")
        
        mode_action = {
            JuryMode.INDEPENDENT: self._consensus_independent,
            JuryMode.MAJORITY_VOTE: self._consensus_majority_vote,
            JuryMode.DELIBERATION: self._consensus_deliberation,
            JuryMode.WEIGHTED: self._consensus_weighted,
        }
        
        self.final_consensus = mode_action[self.mode]()
    
    def _consensus_independent(self) -> Dict[str, Any]:
        """Consensus for independent mode: first verdict."""
        verdict = self.final_verdicts[0]
        return {
            "winner": verdict.winner,
            "confidence": verdict.confidence,
            "method": "first_judgment",
            "reasoning": "Independent judgment (no consensus computed)"
        }
    
    def _consensus_majority_vote(self) -> Dict[str, Any]:
        """Consensus via majority voting."""
        winners = [v.winner for v in self.final_verdicts if v.winner]
        
        from collections import Counter
        vote_counts = Counter(winners)
        majority_winner = vote_counts.most_common(1)[0][0]
        
        # Average confidence for winning side
        winner_confidences = [
            v.confidence for v in self.final_verdicts
            if v.winner == majority_winner and v.confidence
        ]
        avg_confidence = statistics.mean(winner_confidences) if winner_confidences else None
        
        return {
            "winner": majority_winner,
            "confidence": avg_confidence,
            "method": "majority_vote",
            "vote_breakdown": dict(vote_counts),
            "reasoning": f"{len(winner_confidences)}/{self.jury_size} jurors chose {majority_winner}"
        }
    
    def _consensus_deliberation(self) -> Dict[str, Any]:
        """Consensus after deliberation."""
        # Use weighted approach after deliberation
        return self._consensus_weighted()
    
    def _consensus_weighted(self) -> Dict[str, Any]:
        """Consensus via confidence-weighted voting."""
        # Weight votes by member's reasoning quality and confidence
        total_weight_a = 0.0
        total_weight_b = 0.0
        
        for verdict in self.final_verdicts:
            if not verdict.confidence:
                weight = 1.0
            else:
                # Quality-adjusted weight
                quality_factor = verdict.reasoning_quality_score or 0.5
                weight = (verdict.confidence / 5.0) * (0.5 + 0.5 * quality_factor)
            
            if verdict.winner == "Debater A":
                total_weight_a += weight
            elif verdict.winner == "Debater B":
                total_weight_b += weight
        
        majority_winner = "Debater A" if total_weight_a > total_weight_b else "Debater B"
        
        # Confidence as average of members who voted for winner
        winner_confidences = [
            v.confidence for v in self.final_verdicts
            if v.winner == majority_winner and v.confidence
        ]
        avg_confidence = statistics.mean(winner_confidences) if winner_confidences else 3.0
        
        return {
            "winner": majority_winner,
            "confidence": avg_confidence,
            "method": "weighted_voting",
            "total_weight_a": total_weight_a,
            "total_weight_b": total_weight_b,
            "reasoning": f"Quality-weighted vote favors {majority_winner}"
        }
    
    def _compute_metrics(self, question_difficulty: Optional[float] = None) -> None:
        """Phase 4: Compute disagreement and quality metrics."""
        print("\n[PHASE 4] Computing Metrics")
        
        # Winner distribution
        winners = {}
        for v in self.final_verdicts:
            winners[v.winner] = winners.get(v.winner, 0) + 1
        
        # Disagreement calculation
        unanimous = len(set(v.winner for v in self.final_verdicts)) == 1
        
        # Disagreement level: 0 = unanimous, 1 = max disagreement
        if unanimous:
            disagreement = 0.0
        else:
            # Normalized disagreement (0 to 1)
            unique_winners = len(set(v.winner for v in self.final_verdicts if v.winner))
            disagreement = min((unique_winners - 1) / (self.jury_size - 1), 1.0)
        
        # Confidence variance
        confidences = [v.confidence for v in self.final_verdicts if v.confidence]
        confidence_variance = statistics.variance(confidences) if len(confidences) > 1 else 0.0
        
        # Group confidences by winner
        confidence_by_winner = {}
        for winner in set(v.winner for v in self.final_verdicts):
            confs = [v.confidence for v in self.final_verdicts 
                    if v.winner == winner and v.confidence]
            confidence_by_winner[winner] = confs
        
        self.disagreement_metrics = DisagreementMetrics(
            unanimous=unanimous,
            disagreement_level=disagreement,
            confidence_variance=confidence_variance,
            winner_split=winners,
            confidence_by_winner=confidence_by_winner
        )
        
        print(f"  Unanimous: {unanimous}")
        print(f"  Disagreement Level: {disagreement:.2f}")
        print(f"  Confidence Variance: {confidence_variance:.2f}")
        print(f"  Winner Split: {winners}")
    
    def _compute_agreement_rate(self, verdicts: List[JuryVerdictData]) -> float:
        """Compute percentage of jury in agreement."""
        if not verdicts:
            return 0.0
        
        winners = [v.winner for v in verdicts if v.winner]
        if not winners:
            return 0.0
        
        from collections import Counter
        vote_counts = Counter(winners)
        max_agreement = max(vote_counts.values())
        
        return max_agreement / len(verdicts)
    
    def _get_round_verdicts(self, round_num: int) -> List[JuryVerdictData]:
        """Get verdicts from a specific deliberation round."""
        # First round: initial_verdicts, subsequent: from member history
        if round_num == 0:
            return self.initial_verdicts
        
        all_verdicts = []
        for member in self.members:
            if member.deliberation_history and round_num <= len(member.deliberation_history):
                all_verdicts.append(member.deliberation_history[round_num - 1])
        
        return all_verdicts
    
    def _build_result_dict(self) -> Dict[str, Any]:
        """Build comprehensive result dictionary."""
        return {
            "jury_size": self.jury_size,
            "mode": self.mode.value,
            "initial_verdicts": [v.to_dict() for v in self.initial_verdicts],
            "final_verdicts": [v.to_dict() for v in self.final_verdicts],
            "final_consensus": self.final_consensus,
            "deliberation_outcomes": [o.to_dict() for o in self.deliberation_outcomes],
            "disagreement_metrics": self.disagreement_metrics.to_dict() if self.disagreement_metrics else None,
            "reasoning_quality_scores": [
                v.reasoning_quality_score for v in self.final_verdicts
            ],
            "avg_reasoning_quality": statistics.mean([
                v.reasoning_quality_score for v in self.final_verdicts
                if v.reasoning_quality_score
            ]) if self.final_verdicts else 0.0
        }
    
    def compare_with_single_judge(self, single_judge_verdict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compare jury performance with single judge verdict.
        
        Returns:
            Comparison metrics and analysis
        """
        jury_winner = self.final_consensus["winner"]
        single_winner = single_judge_verdict.get("winner")
        jury_confidence = self.final_consensus.get("confidence", 3)
        single_confidence = single_judge_verdict.get("confidence", 3)
        
        return {
            "agreement": jury_winner == single_winner,
            "jury_verdict": jury_winner,
            "single_judge_verdict": single_winner,
            "jury_confidence": jury_confidence,
            "single_confidence": single_confidence,
            "confidence_difference": abs(jury_confidence - single_confidence),
            "jury_unanimity": self.disagreement_metrics.unanimous if self.disagreement_metrics else False,
            "jury_disagreement_level": self.disagreement_metrics.disagreement_level if self.disagreement_metrics else None,
            "jury_reasoning_quality": statistics.mean([
                v.reasoning_quality_score for v in self.final_verdicts
                if v.reasoning_quality_score
            ]) if self.final_verdicts else 0.0
        }
