"""
Four-Phase Debate Protocol Implementation
Based on Irving et al. (2018) and Liang et al. (EMNLP 2024)

Phase 1: Initialization (independent positions)
Phase 2: Multi-Round Debate (N ≥ 3 rounds with adaptive stopping)
Phase 3: Judgment (structured analysis and verdict)
Phase 4: Evaluation (ground truth comparison and recording)
"""

import json
from dataclasses import dataclass, asdict
from typing import Optional, Tuple, List, Dict, Any
from datetime import datetime
import logging

from src.utils.api_client import APIClient


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class InitialPosition:
    """Phase 1 output: debater's initial answer + reasoning"""
    debater_id: int
    answer: str
    reasoning: str
    timestamp: str

@dataclass
class DebateRound:
    """Single round of debate"""
    round_number: int
    debater_a_argument: str
    debater_a_cot: str
    debater_b_counterargument: str
    debater_b_cot: str
    timestamp: str

@dataclass
class JudgeAnalysis:
    """Phase 3 output: structured judge verdict"""
    debater_a_strongest: str
    debater_a_weakest: str
    debater_b_strongest: str
    debater_b_weakest: str
    chain_of_thought: str
    final_verdict: str
    confidence: int
    timestamp: str

@dataclass
class DebateResult:
    """Complete debate record: all 4 phases"""
    question: str
    ground_truth: Optional[str]
    
    # Phase 1
    initial_position_a: InitialPosition
    initial_position_b: InitialPosition
    phase1_consensus: bool
    
    # Phase 2
    debate_rounds: List[DebateRound]
    actual_rounds: int
    stopped_early: bool
    stopping_reason: str
    
    # Phase 3
    judge_analysis: JudgeAnalysis
    
    # Phase 4
    verdict_correct: Optional[bool]
    verdict_matches_a: bool
    verdict_matches_b: bool
    
    # Metadata
    debate_id: str
    timestamp: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict"""
        return {
            'debate_id': self.debate_id,
            'timestamp': self.timestamp,
            'question': self.question,
            'ground_truth': self.ground_truth,
            'phase1': {
                'initial_position_a': asdict(self.initial_position_a),
                'initial_position_b': asdict(self.initial_position_b),
                'consensus': self.phase1_consensus,
            },
            'phase2': {
                'rounds': [asdict(r) for r in self.debate_rounds],
                'actual_rounds': self.actual_rounds,
                'stopped_early': self.stopped_early,
                'stopping_reason': self.stopping_reason,
            },
            'phase3': asdict(self.judge_analysis),
            'phase4': {
                'verdict_correct': self.verdict_correct,
                'verdict_matches_a': self.verdict_matches_a,
                'verdict_matches_b': self.verdict_matches_b,
            }
        }


# ============================================================================
# FOUR-PHASE DEBATE ORCHESTRATOR
# ============================================================================

class FourPhaseDebateOrchestrator:
    """Implements the complete 4-phase debate protocol"""
    
    def __init__(
        self,
        api_client: APIClient,
        min_rounds: int = 3,
        max_rounds: int = 8,
        convergence_threshold: int = 2,
        temperature: float = 0.7,
    ):
        """
        Args:
            api_client: LLM API client
            min_rounds: Minimum rounds before adaptive stopping applies (N ≥ 3)
            max_rounds: Maximum rounds regardless of convergence
            convergence_threshold: Rounds with same answer to trigger early stop
            temperature: Sampling temperature for debaters
        """
        self.api_client = api_client
        self.min_rounds = min_rounds
        self.max_rounds = max_rounds
        self.convergence_threshold = convergence_threshold
        self.temperature = temperature
        self.logger = self._setup_logger()
    
    def _setup_logger(self) -> logging.Logger:
        """Configure logging"""
        logger = logging.getLogger(__name__)
        if not logger.handlers:
            handler = logging.FileHandler('logs/four_phase_debate.log')
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    # ========================================================================
    # PHASE 1: INITIALIZATION
    # ========================================================================
    
    def phase1_initialization(self, question: str) -> Tuple[InitialPosition, InitialPosition, bool]:
        """
        Phase 1: Get independent initial positions from both debaters
        
        Returns:
            (position_a, position_b, is_consensus)
        """
        self.logger.info(f"PHASE 1: Initialization - Question: {question[:100]}...")
        
        # Get Debater A's initial position (independently)
        position_a = self._get_initial_position(
            question=question,
            debater_id=1,
            debater_name="Debater A"
        )
        self.logger.info(f"Debater A position: {position_a.answer}")
        
        # Get Debater B's initial position (independently, no context of A)
        position_b = self._get_initial_position(
            question=question,
            debater_id=2,
            debater_name="Debater B"
        )
        self.logger.info(f"Debater B position: {position_b.answer}")
        
        # Check for consensus
        is_consensus = position_a.answer.strip().lower() == position_b.answer.strip().lower()
        
        if is_consensus:
            self.logger.info("✓ CONSENSUS REACHED in Phase 1 - skipping Phase 2")
        else:
            self.logger.info("✗ No consensus - proceeding to Phase 2")
        
        return position_a, position_b, is_consensus
    
    def _get_initial_position(
        self,
        question: str,
        debater_id: int,
        debater_name: str
    ) -> InitialPosition:
        """Get initial position from one debater (independent, no context)"""
        
        prompt = f"""You are {debater_name} in a structured debate.

TASK: Generate your initial position on this question WITHOUT seeing the other debater's response.

QUESTION: {question}

INSTRUCTIONS:
1. Think through this step-by-step
2. Provide your answer clearly
3. Give brief reasoning (2-3 sentences)
4. Be concise and direct

FORMAT:
ANSWER: [your answer]
REASONING: [2-3 sentences explaining your reasoning]
CHAIN_OF_THOUGHT: [your step-by-step thinking]
"""
        
        response = self.api_client.generate(
            prompt=prompt,
            temperature=self.temperature,
            max_tokens=500
        )
        
        # Parse response
        answer, reasoning, cot = self._parse_initial_position_response(response)
        
        return InitialPosition(
            debater_id=debater_id,
            answer=answer,
            reasoning=reasoning,
            timestamp=datetime.now().isoformat()
        )
    
    def _parse_initial_position_response(self, response: str) -> Tuple[str, str, str]:
        """Extract answer, reasoning, and CoT from response"""
        try:
            lines = response.strip().split('\n')
            answer = ""
            reasoning = ""
            cot = ""
            
            for i, line in enumerate(lines):
                if line.startswith("ANSWER:"):
                    answer = line.replace("ANSWER:", "").strip()
                elif line.startswith("REASONING:"):
                    reasoning = line.replace("REASONING:", "").strip()
                elif line.startswith("CHAIN_OF_THOUGHT:"):
                    cot = line.replace("CHAIN_OF_THOUGHT:", "").strip()
            
            return answer or response[:100], reasoning or "", cot or ""
        except Exception as e:
            self.logger.error(f"Error parsing initial position: {e}")
            return response[:100], "", ""
    
    # ========================================================================
    # PHASE 2: MULTI-ROUND DEBATE
    # ========================================================================
    
    def phase2_multi_round_debate(
        self,
        question: str,
        position_a: InitialPosition,
        position_b: InitialPosition
    ) -> Tuple[List[DebateRound], int, bool, str]:
        """
        Phase 2: Multi-round debate (N ≥ 3 with adaptive stopping)
        
        Adaptive Stopping Criterion:
        - Minimum rounds: N ≥ 3 (must complete at least 3 rounds)
        - Stopping condition: Same answer pair for 2 consecutive rounds
          * Round N: (A says "X", B says "Y")
          * Round N+1: (A says "X", B says "Y") ← CONVERGED
        - If converged, stop debate and proceed to Phase 3
        
        Returns:
            (debate_rounds, actual_rounds_completed, stopped_early, stopping_reason)
        """
        self.logger.info(f"PHASE 2: Multi-Round Debate (min={self.min_rounds}, max={self.max_rounds})")
        
        debate_rounds: List[DebateRound] = []
        answer_history: List[Tuple[str, str]] = []  # Track all (A_answer, B_answer) pairs
        
        for round_num in range(1, self.max_rounds + 1):
            self.logger.info(f"\n{'='*70}")
            self.logger.info(f"ROUND {round_num} / {self.max_rounds}")
            self.logger.info(f"{'='*70}")
            
            # Build transcript of previous rounds
            transcript = self._build_transcript(
                question=question,
                initial_a=position_a,
                initial_b=position_b,
                rounds=debate_rounds
            )
            
            # Debater A presents argument
            self.logger.info("→ Debater A generating argument...")
            arg_a, cot_a, answer_a = self._get_debater_argument(
                question=question,
                debater_id=1,
                debater_name="Debater A",
                position=position_a.answer,
                transcript=transcript,
                is_initial=(round_num == 1),
                role="argument"
            )
            self.logger.info(f"✓ Debater A: Answer='{answer_a}'")
            
            # Debater B presents counterargument
            self.logger.info("→ Debater B generating counterargument...")
            arg_b, cot_b, answer_b = self._get_debater_argument(
                question=question,
                debater_id=2,
                debater_name="Debater B",
                position=position_b.answer,
                transcript=transcript + f"\n[Debater A Argument]\n{arg_a}",
                is_initial=(round_num == 1),
                role="counterargument"
            )
            self.logger.info(f"✓ Debater B: Answer='{answer_b}'")
            
            # Record round
            debate_round = DebateRound(
                round_number=round_num,
                debater_a_argument=arg_a,
                debater_a_cot=cot_a,
                debater_b_counterargument=arg_b,
                debater_b_cot=cot_b,
                timestamp=datetime.now().isoformat()
            )
            debate_rounds.append(debate_round)
            
            # Track answers for convergence detection
            current_pair = (answer_a.lower().strip(), answer_b.lower().strip())
            answer_history.append(current_pair)
            
            # Log answer history
            self.logger.info(f"\nAnswer History:")
            for i, (a, b) in enumerate(answer_history, 1):
                self.logger.info(f"  Round {i}: A='{a}' | B='{b}'")
            
            # Check adaptive stopping criterion
            convergence_result = self._check_convergence(
                round_num=round_num,
                answer_history=answer_history
            )
            
            if convergence_result['converged']:
                self.logger.info(f"\n{'!'*70}")
                self.logger.info(f"✓✓✓ CONVERGENCE DETECTED ✓✓✓")
                self.logger.info(f"{'!'*70}")
                self.logger.info(f"Stopped at Round {round_num} (minimum {self.min_rounds})")
                self.logger.info(f"Reason: {convergence_result['reason']}")
                self.logger.info(f"Both debaters: A='{convergence_result['answer_a']}', B='{convergence_result['answer_b']}'")
                return debate_rounds, round_num, True, "convergence_2_rounds"
            else:
                self.logger.info(f"\nNo convergence yet: {convergence_result['reason']}")
        
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"Completed max rounds ({self.max_rounds})")
        self.logger.info(f"{'='*70}")
        return debate_rounds, self.max_rounds, False, "max_rounds_reached"
    
    def _check_convergence(
        self,
        round_num: int,
        answer_history: List[Tuple[str, str]]
    ) -> Dict[str, Any]:
        """
        Check if debate has converged (same answer pair for 2 consecutive rounds)
        
        Returns:
            {
                'converged': bool,
                'reason': str (explanation),
                'answer_a': str (if converged),
                'answer_b': str (if converged)
            }
        """
        # Criteria 1: Must have completed minimum rounds
        if round_num < self.min_rounds:
            return {
                'converged': False,
                'reason': f"Round {round_num} < minimum {self.min_rounds}. Not checking convergence yet."
            }
        
        # Criteria 2: Must have at least 2 rounds of history
        if len(answer_history) < 2:
            return {
                'converged': False,
                'reason': "Fewer than 2 rounds of history available."
            }
        
        # Get last two answer pairs
        prev_pair = answer_history[-2]  # Previous round
        curr_pair = answer_history[-1]  # Current round
        
        prev_a, prev_b = prev_pair
        curr_a, curr_b = curr_pair
        
        # Criteria 3: Check if identical
        is_identical = (prev_a == curr_a and prev_b == curr_b)
        
        if is_identical:
            return {
                'converged': True,
                'reason': (
                    f"Round {round_num-1} and Round {round_num} "
                    f"have identical answers (convergence threshold met)"
                ),
                'answer_a': curr_a,
                'answer_b': curr_b
            }
        else:
            changes = []
            if prev_a != curr_a:
                changes.append(f"A: '{prev_a}' → '{curr_a}'")
            if prev_b != curr_b:
                changes.append(f"B: '{prev_b}' → '{curr_b}'")
            
            change_summary = ", ".join(changes) if changes else "No changes"
            
            return {
                'converged': False,
                'reason': f"Answers changed this round: {change_summary}. Keep debating."
            }
    
    def _build_transcript(
        self,
        question: str,
        initial_a: InitialPosition,
        initial_b: InitialPosition,
        rounds: List[DebateRound]
    ) -> str:
        """Build complete debate transcript for context"""
        transcript = f"""DEBATE TRANSCRIPT
===============================
QUESTION: {question}

INITIAL POSITIONS:
- Debater A: {initial_a.answer}
- Debater B: {initial_b.answer}

"""
        
        for round_data in rounds:
            transcript += f"""ROUND {round_data.round_number}:
[Debater A Argument]
{round_data.debater_a_argument}

[Debater B Counterargument]
{round_data.debater_b_counterargument}

"""
        
        return transcript
    
    def _get_debater_argument(
        self,
        question: str,
        debater_id: int,
        debater_name: str,
        position: str,
        transcript: str,
        is_initial: bool,
        role: str  # "argument" or "counterargument"
    ) -> Tuple[str, str, str]:
        """Get one debater's argument for this round"""
        
        if is_initial:
            role_instruction = "present your initial argument"
        else:
            role_instruction = (
                "present a counterargument" if role == "counterargument" 
                else "strengthen your argument"
            )
        
        prompt = f"""You are {debater_name} in a structured debate.

YOUR POSITION: {position}

PREVIOUS DEBATE CONTEXT:
{transcript}

TASK: {role_instruction} supporting your position.

INSTRUCTIONS:
1. Review the full context above
2. Use chain-of-thought reasoning
3. Present a clear, focused argument (2-3 sentences)
4. Address the strongest point from your opponent (if not initial round)
5. Stay focused on why your answer is correct

FORMAT:
ARGUMENT: [your argument - 2-3 sentences]
CHAIN_OF_THOUGHT: [step-by-step reasoning]
YOUR_ANSWER: [restate your final answer clearly]
"""
        
        response = self.api_client.generate(
            prompt=prompt,
            temperature=self.temperature,
            max_tokens=600
        )
        
        # Parse response
        argument, cot, answer = self._parse_argument_response(response)
        
        return argument, cot, answer
    
    def _parse_argument_response(self, response: str) -> Tuple[str, str, str]:
        """Extract argument, CoT, and answer from response"""
        try:
            lines = response.strip().split('\n')
            argument = ""
            cot = ""
            answer = ""
            
            for line in lines:
                if line.startswith("ARGUMENT:"):
                    argument = line.replace("ARGUMENT:", "").strip()
                elif line.startswith("CHAIN_OF_THOUGHT:"):
                    cot = line.replace("CHAIN_OF_THOUGHT:", "").strip()
                elif line.startswith("YOUR_ANSWER:"):
                    answer = line.replace("YOUR_ANSWER:", "").strip()
            
            return argument or response[:200], cot or "", answer or ""
        except Exception as e:
            self.logger.error(f"Error parsing argument: {e}")
            return response[:200], "", ""
    
    # ========================================================================
    # PHASE 3: JUDGMENT
    # ========================================================================
    
    def phase3_judgment(
        self,
        question: str,
        position_a: InitialPosition,
        position_b: InitialPosition,
        debate_rounds: List[DebateRound]
    ) -> JudgeAnalysis:
        """
        Phase 3: Judge analyzes debate and produces structured verdict
        
        Judge must produce:
        1. CoT analysis of both arguments
        2. Strongest argument from Debater A
        3. Weakest argument from Debater A
        4. Strongest argument from Debater B
        5. Weakest argument from Debater B
        6. Final verdict (which answer is correct)
        7. Confidence score (1-5)
        """
        self.logger.info("PHASE 3: Judgment")
        
        transcript = self._build_transcript(
            question=question,
            initial_a=position_a,
            initial_b=position_b,
            rounds=debate_rounds
        )
        
        prompt = f"""You are an expert judge evaluating a structured debate.

{transcript}

YOUR TASK: Provide a comprehensive analysis of this debate.

INSTRUCTIONS:
1. Analyze both debaters' arguments step-by-step
2. Identify the strongest and weakest points from each side
3. Determine which answer is most likely correct
4. Provide your reasoning clearly
5. Rate your confidence (1=very uncertain, 5=completely certain)

REQUIRED OUTPUT FORMAT:

CHAIN_OF_THOUGHT:
[Your step-by-step analysis of the debate, considering all arguments from both sides]

DEBATER_A_STRONGEST:
[The single strongest argument from Debater A]

DEBATER_A_WEAKEST:
[The weakest or most problematic argument from Debater A]

DEBATER_B_STRONGEST:
[The single strongest argument from Debater B]

DEBATER_B_WEAKEST:
[The weakest or most problematic argument from Debater B]

FINAL_VERDICT:
[Your final answer - which position is correct: "{position_a.answer}" or "{position_b.answer}"?]

CONFIDENCE:
[1-5 scale: How confident are you in this verdict? Explain briefly.]
"""
        
        response = self.api_client.generate(
            prompt=prompt,
            temperature=0.5,  # Lower temperature for judge consistency
            max_tokens=1500
        )
        
        # Parse judge response
        analysis = self._parse_judge_response(response, position_a.answer, position_b.answer)
        
        self.logger.info(f"Judge verdict: {analysis.final_verdict} (confidence: {analysis.confidence}/5)")
        
        return analysis
    
    def _parse_judge_response(
        self,
        response: str,
        answer_a: str,
        answer_b: str
    ) -> JudgeAnalysis:
        """Parse structured judge response"""
        try:
            lines = response.strip().split('\n')
            cot = ""
            strongest_a = ""
            weakest_a = ""
            strongest_b = ""
            weakest_b = ""
            verdict = ""
            confidence = 3
            
            current_section = None
            section_content = []
            
            for line in lines:
                if line.startswith("CHAIN_OF_THOUGHT:"):
                    if section_content and current_section:
                        setattr(self, f'_temp_{current_section}', ' '.join(section_content))
                    current_section = "cot"
                    section_content = [line.replace("CHAIN_OF_THOUGHT:", "").strip()]
                elif line.startswith("DEBATER_A_STRONGEST:"):
                    if section_content and current_section:
                        setattr(self, f'_temp_{current_section}', ' '.join(section_content))
                    current_section = "strongest_a"
                    section_content = [line.replace("DEBATER_A_STRONGEST:", "").strip()]
                elif line.startswith("DEBATER_A_WEAKEST:"):
                    if section_content and current_section:
                        setattr(self, f'_temp_{current_section}', ' '.join(section_content))
                    current_section = "weakest_a"
                    section_content = [line.replace("DEBATER_A_WEAKEST:", "").strip()]
                elif line.startswith("DEBATER_B_STRONGEST:"):
                    if section_content and current_section:
                        setattr(self, f'_temp_{current_section}', ' '.join(section_content))
                    current_section = "strongest_b"
                    section_content = [line.replace("DEBATER_B_STRONGEST:", "").strip()]
                elif line.startswith("DEBATER_B_WEAKEST:"):
                    if section_content and current_section:
                        setattr(self, f'_temp_{current_section}', ' '.join(section_content))
                    current_section = "weakest_b"
                    section_content = [line.replace("DEBATER_B_WEAKEST:", "").strip()]
                elif line.startswith("FINAL_VERDICT:"):
                    if section_content and current_section:
                        setattr(self, f'_temp_{current_section}', ' '.join(section_content))
                    current_section = "verdict"
                    section_content = [line.replace("FINAL_VERDICT:", "").strip()]
                elif line.startswith("CONFIDENCE:"):
                    if section_content and current_section:
                        setattr(self, f'_temp_{current_section}', ' '.join(section_content))
                    current_section = "confidence"
                    section_content = [line.replace("CONFIDENCE:", "").strip()]
                else:
                    if current_section:
                        section_content.append(line)
            
            # Get final section
            if section_content and current_section:
                if current_section == "cot":
                    cot = ' '.join(section_content)
                elif current_section == "strongest_a":
                    strongest_a = ' '.join(section_content)
                elif current_section == "weakest_a":
                    weakest_a = ' '.join(section_content)
                elif current_section == "strongest_b":
                    strongest_b = ' '.join(section_content)
                elif current_section == "weakest_b":
                    weakest_b = ' '.join(section_content)
                elif current_section == "verdict":
                    verdict = ' '.join(section_content)
                elif current_section == "confidence":
                    # Extract confidence number
                    conf_text = ' '.join(section_content)
                    for char in conf_text:
                        if char.isdigit():
                            confidence = int(char)
                            break
            
            return JudgeAnalysis(
                debater_a_strongest=strongest_a or "Not specified",
                debater_a_weakest=weakest_a or "Not specified",
                debater_b_strongest=strongest_b or "Not specified",
                debater_b_weakest=weakest_b or "Not specified",
                chain_of_thought=cot or response[:500],
                final_verdict=verdict or answer_a,
                confidence=confidence,
                timestamp=datetime.now().isoformat()
            )
        except Exception as e:
            self.logger.error(f"Error parsing judge response: {e}")
            return JudgeAnalysis(
                debater_a_strongest="Parse error",
                debater_a_weakest="Parse error",
                debater_b_strongest="Parse error",
                debater_b_weakest="Parse error",
                chain_of_thought=response[:500],
                final_verdict=answer_a,
                confidence=1,
                timestamp=datetime.now().isoformat()
            )
    
    # ========================================================================
    # PHASE 4: EVALUATION
    # ========================================================================
    
    def phase4_evaluation(
        self,
        judge_analysis: JudgeAnalysis,
        ground_truth: Optional[str],
        position_a: InitialPosition,
        position_b: InitialPosition
    ) -> Tuple[Optional[bool], bool, bool]:
        """
        Phase 4: Evaluate judge verdict against ground truth
        
        Returns:
            (verdict_correct, verdict_matches_a, verdict_matches_b)
        """
        self.logger.info("PHASE 4: Evaluation")
        
        # Check which position the verdict matches
        verdict_matches_a = judge_analysis.final_verdict.lower().strip() == position_a.answer.lower().strip()
        verdict_matches_b = judge_analysis.final_verdict.lower().strip() == position_b.answer.lower().strip()
        
        # Compare to ground truth if available
        verdict_correct = None
        if ground_truth:
            verdict_correct = judge_analysis.final_verdict.lower().strip() == ground_truth.lower().strip()
            status = "✓ CORRECT" if verdict_correct else "✗ INCORRECT"
            self.logger.info(f"Verdict vs Ground Truth: {status}")
            self.logger.info(f"Judge said: {judge_analysis.final_verdict}")
            self.logger.info(f"Ground truth: {ground_truth}")
        
        self.logger.info(f"Verdict matches Debater A: {verdict_matches_a}")
        self.logger.info(f"Verdict matches Debater B: {verdict_matches_b}")
        
        return verdict_correct, verdict_matches_a, verdict_matches_b
    
    # ========================================================================
    # FULL PIPELINE
    # ========================================================================
    
    def run_debate(
        self,
        question: str,
        ground_truth: Optional[str] = None,
        debate_id: Optional[str] = None
    ) -> DebateResult:
        """
        Run complete 4-phase debate pipeline
        """
        if debate_id is None:
            debate_id = f"debate_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"STARTING DEBATE: {debate_id}")
        self.logger.info(f"Question: {question}")
        self.logger.info(f"Ground Truth: {ground_truth}")
        self.logger.info(f"{'='*70}\n")
        
        try:
            # ===== PHASE 1: INITIALIZATION =====
            position_a, position_b, is_consensus = self.phase1_initialization(question)
            
            if is_consensus:
                # Early termination - skip Phase 2
                debate_rounds = []
                actual_rounds = 0
                stopped_early = True
                stopping_reason = "phase1_consensus"
            else:
                # ===== PHASE 2: MULTI-ROUND DEBATE =====
                debate_rounds, actual_rounds, stopped_early, stopping_reason = (
                    self.phase2_multi_round_debate(question, position_a, position_b)
                )
            
            # ===== PHASE 3: JUDGMENT =====
            judge_analysis = self.phase3_judgment(
                question=question,
                position_a=position_a,
                position_b=position_b,
                debate_rounds=debate_rounds
            )
            
            # ===== PHASE 4: EVALUATION =====
            verdict_correct, verdict_matches_a, verdict_matches_b = self.phase4_evaluation(
                judge_analysis=judge_analysis,
                ground_truth=ground_truth,
                position_a=position_a,
                position_b=position_b
            )
            
            # ===== COMPILE RESULTS =====
            result = DebateResult(
                question=question,
                ground_truth=ground_truth,
                initial_position_a=position_a,
                initial_position_b=position_b,
                phase1_consensus=is_consensus,
                debate_rounds=debate_rounds,
                actual_rounds=actual_rounds,
                stopped_early=stopped_early,
                stopping_reason=stopping_reason,
                judge_analysis=judge_analysis,
                verdict_correct=verdict_correct,
                verdict_matches_a=verdict_matches_a,
                verdict_matches_b=verdict_matches_b,
                debate_id=debate_id,
                timestamp=datetime.now().isoformat()
            )
            
            self.logger.info(f"\nDEBATE COMPLETE: {debate_id}")
            self.logger.info(f"Result: {result.to_dict()}\n")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in debate pipeline: {e}", exc_info=True)
            raise
