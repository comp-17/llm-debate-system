"""
4-PHASE DEBATE PROTOCOL IMPLEMENTATION
Inspired by Irving et al. (2018) and Liang et al. (EMNLP 2024)

Phase 1: Initialization (independent positions, consensus check)
Phase 2: Multi-Round Debate (N≥3 rounds, adaptive stopping)
Phase 3: Judgment (judge analysis with CoT, strongest/weakest args, verdict)
Phase 4: Evaluation (ground truth comparison)
"""

import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class DebaterPosition:
    """Initial position from a debater (Phase 1)"""
    debater_id: str
    answer: str
    reasoning: str
    timestamp: str


@dataclass
class DebateArgument:
    """Single argument in debate (Phase 2)"""
    round_number: int
    debater_id: str
    argument: str
    cot_reasoning: str
    timestamp: str


@dataclass
class JudgeAnalysis:
    """Judge's analysis (Phase 3)"""
    cot_analysis: str
    strongest_argument_a: str
    strongest_argument_b: str
    weakest_argument_a: str
    weakest_argument_b: str
    final_verdict: str
    confidence: int
    reasoning: str


@dataclass
class DebateResult:
    """Complete debate result (all phases)"""
    question: str
    ground_truth: Optional[str]
    
    # Phase 1
    initial_position_a: DebaterPosition
    initial_position_b: DebaterPosition
    consensus_reached: bool
    
    # Phase 2
    rounds_executed: int
    debate_arguments: List[DebateArgument]
    stopping_reason: str
    
    # Phase 3
    judge_analysis: JudgeAnalysis
    
    # Phase 4
    judge_correct: bool
    both_debaters_correct: bool
    debate_improved_accuracy: bool
    
    timestamp: str


class MultiPhaseDebateOrchestrator:
    """Orchestrates the 4-phase debate protocol"""
    
    def __init__(
        self,
        api_client,
        min_rounds: int = 3,
        max_rounds: int = 6,
        convergence_threshold: int = 2,
    ):
        """
        Initialize debate orchestrator.
        
        Args:
            api_client: API client for LLM calls
            min_rounds: Minimum debate rounds (must be ≥3)
            max_rounds: Maximum debate rounds
            convergence_threshold: Rounds of same answer to trigger early stop
        """
        self.api_client = api_client
        self.min_rounds = max(min_rounds, 3)  # Enforce minimum 3
        self.max_rounds = max_rounds
        self.convergence_threshold = convergence_threshold
        
    def run_debate(
        self,
        question: str,
        ground_truth: Optional[str] = None,
    ) -> DebateResult:
        """
        Run complete 4-phase debate protocol.
        
        Args:
            question: The debate question
            ground_truth: Ground truth answer for evaluation (optional)
            
        Returns:
            Complete DebateResult with all phases
        """
        logger.info(f"Starting 4-phase debate: {question}")
        
        # Phase 1: Initialization
        pos_a, pos_b = self._phase1_initialization(question)
        
        # Check for consensus in Phase 1
        consensus_reached = pos_a.answer.lower().strip() == pos_b.answer.lower().strip()
        
        if consensus_reached:
            logger.info("Consensus reached in Phase 1 - skipping to Phase 3")
            judge_analysis = self._phase3_judgment(
                question, pos_a, pos_b, arguments=[]
            )
            return self._build_result(
                question, ground_truth, pos_a, pos_b, 
                consensus_reached=True, arguments=[], 
                judge_analysis=judge_analysis, 
                stopping_reason="consensus_phase1"
            )
        
        # Phase 2: Multi-Round Debate
        arguments, stopping_reason = self._phase2_debate(
            question, pos_a, pos_b
        )
        
        # Phase 3: Judgment
        judge_analysis = self._phase3_judgment(
            question, pos_a, pos_b, arguments
        )
        
        # Phase 4: Evaluation
        result = self._build_result(
            question, ground_truth, pos_a, pos_b,
            consensus_reached=False, arguments=arguments,
            judge_analysis=judge_analysis,
            stopping_reason=stopping_reason
        )
        
        logger.info(f"Debate complete: {result.judge_analysis.final_verdict}")
        return result
    
    # ==================== PHASE 1: INITIALIZATION ====================
    
    def _phase1_initialization(self, question: str) -> Tuple[DebaterPosition, DebaterPosition]:
        """
        Phase 1: Generate independent initial positions.
        
        Each debater generates their answer + reasoning WITHOUT seeing the other's response.
        """
        logger.info("=== PHASE 1: INITIALIZATION ===")
        logger.info("Generating independent initial positions...")
        
        # Get Debater A's position
        pos_a = self._get_initial_position(question, "A")
        
        # Get Debater B's position (independently, no knowledge of A's answer)
        pos_b = self._get_initial_position(question, "B")
        
        logger.info(f"Debater A: {pos_a.answer}")
        logger.info(f"Debater B: {pos_b.answer}")
        
        return pos_a, pos_b
    
    def _get_initial_position(self, question: str, debater_id: str) -> DebaterPosition:
        """Get initial position from one debater (independently)"""
        prompt = f"""You are Debater {debater_id} in a debate. You have NOT seen the other debater's response.

Question: {question}

Generate YOUR initial position on this question. Provide:
1. Your answer (be concise - one short sentence)
2. Your reasoning (2-3 sentences explaining why)

Format:
ANSWER: [your answer]
REASONING: [your reasoning]"""
        
        response = self.api_client.call(prompt)
        
        # Parse response
        answer = self._extract_between(response, "ANSWER:", "REASONING:").strip()
        reasoning = self._extract_after(response, "REASONING:").strip()
        
        return DebaterPosition(
            debater_id=debater_id,
            answer=answer,
            reasoning=reasoning,
            timestamp=datetime.now().isoformat()
        )
    
    # ==================== PHASE 2: MULTI-ROUND DEBATE ====================
    
    def _phase2_debate(
        self,
        question: str,
        pos_a: DebaterPosition,
        pos_b: DebaterPosition,
    ) -> Tuple[List[DebateArgument], str]:
        """
        Phase 2: Multi-round debate with adaptive stopping.
        
        Rules:
        - Minimum N≥3 rounds
        - Early stopping if same answer for 2 consecutive rounds
        - Full transcript context in each round
        """
        logger.info("=== PHASE 2: MULTI-ROUND DEBATE ===")
        
        arguments: List[DebateArgument] = []
        previous_answers: Dict[str, str] = {}  # Track previous round answers
        
        for round_num in range(1, self.max_rounds + 1):
            logger.info(f"--- Round {round_num} ---")
            
            # Build transcript of previous rounds
            transcript = self._build_transcript(
                question, pos_a, pos_b, arguments
            )
            
            # Debater A presents argument
            arg_a = self._get_argument(
                question, "A", transcript, arguments, round_num
            )
            arguments.append(arg_a)
            
            # Debater B responds with counterargument
            arg_b = self._get_argument(
                question, "B", transcript, arguments, round_num
            )
            arguments.append(arg_b)
            
            # Extract current answers from arguments for convergence detection
            current_a = arg_a.argument[:50].lower()
            current_b = arg_b.argument[:50].lower()
            
            # Check adaptive stopping criterion: same answer for N consecutive rounds
            if round_num >= self.min_rounds and len(previous_answers) > 0:
                if (current_a == previous_answers.get("a") and 
                    current_b == previous_answers.get("b")):
                    logger.info(f"Convergence detected at round {round_num}")
                    return arguments, f"convergence_round_{round_num}"
            
            previous_answers = {"a": current_a, "b": current_b}
        
        # Reached max rounds
        return arguments, f"max_rounds_reached_{self.max_rounds}"
    
    def _get_argument(
        self,
        question: str,
        debater_id: str,
        transcript: str,
        previous_arguments: List[DebateArgument],
        round_num: int,
    ) -> DebateArgument:
        """Get argument from debater in current round with CoT"""
        
        is_rebuttal = len(previous_arguments) > 0
        role = "rebuttal" if is_rebuttal and debater_id == "B" else "argument"
        
        prompt = f"""You are Debater {debater_id} in a debate.

Question: {question}

Previous debate transcript:
{transcript}

Round {round_num}: You are now making your {role}.

Think through your {role} step-by-step (REASONING), then present your {role} (ARGUMENT).
Your answer should be 2-3 sentences maximum.

Format your response EXACTLY as:
REASONING: [your step-by-step thinking]
ARGUMENT: [your {role}]"""
        
        response = self.api_client.call(prompt)
        
        reasoning = self._extract_between(response, "REASONING:", "ARGUMENT:").strip()
        argument = self._extract_after(response, "ARGUMENT:").strip()
        
        return DebateArgument(
            round_number=round_num,
            debater_id=debater_id,
            argument=argument,
            cot_reasoning=reasoning,
            timestamp=datetime.now().isoformat()
        )
    
    def _build_transcript(
        self,
        question: str,
        pos_a: DebaterPosition,
        pos_b: DebaterPosition,
        arguments: List[DebateArgument],
    ) -> str:
        """Build full debate transcript with all previous rounds"""
        transcript = f"Question: {question}\n\n"
        transcript += f"Initial Positions:\n"
        transcript += f"  Debater A: {pos_a.answer}\n    Reasoning: {pos_a.reasoning}\n"
        transcript += f"  Debater B: {pos_b.answer}\n    Reasoning: {pos_b.reasoning}\n\n"
        
        for arg in arguments:
            transcript += f"Round {arg.round_number}, Debater {arg.debater_id}:\n"
            transcript += f"  Argument: {arg.argument}\n"
            transcript += f"  (CoT: {arg.cot_reasoning})\n\n"
        
        return transcript
    
    # ==================== PHASE 3: JUDGMENT ====================
    
    def _phase3_judgment(
        self,
        question: str,
        pos_a: DebaterPosition,
        pos_b: DebaterPosition,
        arguments: List[DebateArgument],
    ) -> JudgeAnalysis:
        """
        Phase 3: Judge analyzes debate and renders verdict.
        
        Judge must produce:
        (a) Chain-of-thought analysis
        (b) Strongest/weakest arguments identification
        (c) Final verdict
        (d) Confidence score (1-5)
        """
        logger.info("=== PHASE 3: JUDGMENT ===")
        
        # Build debate transcript for judge
        transcript = self._build_transcript(question, pos_a, pos_b, arguments)
        
        prompt = f"""You are a neutral judge evaluating a debate.

Question: {question}

Debate Transcript:
{transcript}

Provide a thorough analysis of this debate. Your response MUST include ALL of these sections:

1. COT_ANALYSIS: Your step-by-step chain-of-thought analysis of both debaters' arguments
2. STRONGEST_A: The single strongest argument from Debater A
3. WEAKEST_A: The single weakest argument from Debater A  
4. STRONGEST_B: The single strongest argument from Debater B
5. WEAKEST_B: The single weakest argument from Debater B
6. VERDICT: Your final verdict (which debater's position is more convincing and why)
7. CONFIDENCE: Your confidence level (1-5, where 5 is most confident, 1 is least)
8. REASONING: Detailed reasoning for your verdict

Format EXACTLY as:
COT_ANALYSIS: [analysis]
STRONGEST_A: [argument]
WEAKEST_A: [argument]
STRONGEST_B: [argument]
WEAKEST_B: [argument]
VERDICT: [verdict]
CONFIDENCE: [1-5]
REASONING: [reasoning]"""
        
        response = self.api_client.call(prompt)
        
        # Extract all sections
        cot = self._extract_between(response, "COT_ANALYSIS:", "STRONGEST_A:").strip()
        strongest_a = self._extract_between(response, "STRONGEST_A:", "WEAKEST_A:").strip()
        weakest_a = self._extract_between(response, "WEAKEST_A:", "STRONGEST_B:").strip()
        strongest_b = self._extract_between(response, "STRONGEST_B:", "WEAKEST_B:").strip()
        weakest_b = self._extract_between(response, "WEAKEST_B:", "VERDICT:").strip()
        verdict = self._extract_between(response, "VERDICT:", "CONFIDENCE:").strip()
        confidence_str = self._extract_between(response, "CONFIDENCE:", "REASONING:").strip()
        reasoning = self._extract_after(response, "REASONING:").strip()
        
        # Parse confidence (handle various formats)
        try:
            confidence = int(''.join(c for c in confidence_str if c.isdigit())[:1])
            confidence = max(1, min(5, confidence))  # Clamp to 1-5
        except:
            confidence = 3
        
        logger.info(f"Judge verdict: {verdict} (Confidence: {confidence}/5)")
        
        return JudgeAnalysis(
            cot_analysis=cot,
            strongest_argument_a=strongest_a,
            strongest_argument_b=strongest_b,
            weakest_argument_a=weakest_a,
            weakest_argument_b=weakest_b,
            final_verdict=verdict,
            confidence=confidence,
            reasoning=reasoning
        )
    
    # ==================== PHASE 4: EVALUATION ====================
    
    def _build_result(
        self,
        question: str,
        ground_truth: Optional[str],
        pos_a: DebaterPosition,
        pos_b: DebaterPosition,
        consensus_reached: bool,
        arguments: List[DebateArgument],
        judge_analysis: JudgeAnalysis,
        stopping_reason: str,
    ) -> DebateResult:
        """
        Phase 4: Evaluate debate against ground truth.
        """
        logger.info("=== PHASE 4: EVALUATION ===")
        
        # Determine correctness
        judge_correct = False
        both_debaters_correct = False
        debate_improved_accuracy = False
        
        if ground_truth:
            gt_lower = ground_truth.lower().strip()
            judge_verdict_lower = judge_analysis.final_verdict.lower()
            pos_a_lower = pos_a.answer.lower().strip()
            pos_b_lower = pos_b.answer.lower().strip()
            
            # Check if verdict matches ground truth
            judge_correct = gt_lower in judge_verdict_lower or judge_verdict_lower in gt_lower
            
            # Check if debaters were correct
            debater_a_correct = gt_lower in pos_a_lower or pos_a_lower in gt_lower
            debater_b_correct = gt_lower in pos_b_lower or pos_b_lower in gt_lower
            both_debaters_correct = debater_a_correct and debater_b_correct
            
            # Did debate improve accuracy?
            debate_improved_accuracy = judge_correct and not both_debaters_correct
            
            logger.info(f"Ground truth: {ground_truth}")
            logger.info(f"Judge correct: {judge_correct}")
            logger.info(f"Debate improved: {debate_improved_accuracy}")
        
        return DebateResult(
            question=question,
            ground_truth=ground_truth,
            initial_position_a=pos_a,
            initial_position_b=pos_b,
            consensus_reached=consensus_reached,
            rounds_executed=len(arguments) // 2 if arguments else 0,
            debate_arguments=arguments,
            stopping_reason=stopping_reason,
            judge_analysis=judge_analysis,
            judge_correct=judge_correct,
            both_debaters_correct=both_debaters_correct,
            debate_improved_accuracy=debate_improved_accuracy,
            timestamp=datetime.now().isoformat(),
        )
    
    # ==================== UTILITIES ====================
    
    def _extract_between(self, text: str, start: str, end: str) -> str:
        """Extract text between two markers"""
        try:
            start_idx = text.find(start)
            end_idx = text.find(end)
            if start_idx >= 0 and end_idx > start_idx:
                return text[start_idx + len(start):end_idx]
        except:
            pass
        return ""
    
    def _extract_after(self, text: str, marker: str) -> str:
        """Extract text after marker"""
        try:
            idx = text.find(marker)
            if idx >= 0:
                return text[idx + len(marker):]
        except:
            pass
        return ""
    
    def save_result(self, result: DebateResult, filepath: str) -> None:
        """Save debate result to JSON"""
        data = {
            "question": result.question,
            "ground_truth": result.ground_truth,
            "phase1": {
                "initial_position_a": asdict(result.initial_position_a),
                "initial_position_b": asdict(result.initial_position_b),
                "consensus_reached": result.consensus_reached,
            },
            "phase2": {
                "rounds_executed": result.rounds_executed,
                "stopping_reason": result.stopping_reason,
                "arguments": [asdict(arg) for arg in result.debate_arguments],
            },
            "phase3": asdict(result.judge_analysis),
            "phase4": {
                "judge_correct": result.judge_correct,
                "both_debaters_correct": result.both_debaters_correct,
                "debate_improved_accuracy": result.debate_improved_accuracy,
            },
            "timestamp": result.timestamp,
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Debate result saved to {filepath}")
