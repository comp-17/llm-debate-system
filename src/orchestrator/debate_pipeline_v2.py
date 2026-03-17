"""
Complete 4-Phase Debate Pipeline Implementation
Per specification: Phase 1 (Initialization), Phase 2 (Multi-Round Debate), 
Phase 3 (Judgment), Phase 4 (Evaluation)

Inspired by Irving et al. (2018) and Liang et al. (EMNLP 2024)
"""

import json
from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class InitialPosition:
    """Debater's initial independent position"""
    debater_id: str
    answer: str
    reasoning: str
    timestamp: str


@dataclass
class RoundArgument:
    """Single round argument from a debater"""
    round_num: int
    debater_id: str
    argument: str
    cot_reasoning: str
    timestamp: str


@dataclass
class DebateTranscript:
    """Complete debate record"""
    debate_id: str
    question: str
    ground_truth: Optional[str]
    
    # Phase 1: Initialization
    initial_positions: Dict[str, InitialPosition]
    consensus_reached: bool
    consensus_answer: Optional[str]
    skipped_to_phase_3: bool
    
    # Phase 2: Multi-Round Debate
    rounds: List[List[RoundArgument]]  # rounds[i] contains arguments from round i
    total_rounds: int
    stopped_early: bool
    early_stop_reason: Optional[str]
    
    # Phase 3: Judgment
    judge_cot_analysis: str
    strongest_argument_a: str
    strongest_argument_b: str
    weakest_argument_a: str
    weakest_argument_b: str
    final_verdict: str
    confidence_score: int  # 1-5
    
    # Phase 4: Evaluation
    ground_truth_match: Optional[bool]
    evaluation_metrics: Dict


@dataclass
class JudgeAnalysis:
    """Structured judge analysis"""
    cot_analysis: str
    strongest_arg_a: str
    strongest_arg_b: str
    weakest_arg_a: str
    weakest_arg_b: str
    verdict: str
    confidence: int


class DebatePipeline:
    """Complete 4-phase debate orchestration"""
    
    def __init__(self, api_client, min_rounds: int = 3, max_rounds: int = 10):
        """
        Args:
            api_client: LLM API client
            min_rounds: Minimum debate rounds (default 3)
            max_rounds: Maximum debate rounds
        """
        self.api_client = api_client
        self.min_rounds = min_rounds
        self.max_rounds = max_rounds
        
    def run_full_debate(
        self,
        debate_id: str,
        question: str,
        ground_truth: Optional[str] = None
    ) -> DebateTranscript:
        """
        Execute complete 4-phase debate pipeline
        
        Args:
            debate_id: Unique debate identifier
            question: The debate question/problem
            ground_truth: Ground truth answer for evaluation (Phase 4)
            
        Returns:
            DebateTranscript with all phases completed
        """
        logger.info(f"Starting debate {debate_id}: {question}")
        
        # ==================================================================
        # PHASE 1: INITIALIZATION
        # ==================================================================
        logger.info("=== PHASE 1: INITIALIZATION ===")
        initial_positions = self._phase1_initialization(question)
        
        # Check for consensus
        consensus_reached = (
            initial_positions['debater_a'].answer == 
            initial_positions['debater_b'].answer
        )
        
        if consensus_reached:
            logger.info("Consensus reached in Phase 1, skipping to Phase 3")
            consensus_answer = initial_positions['debater_a'].answer
            
            # Phase 3 with consensus
            judge_analysis = self._phase3_judgment_consensus(
                question,
                initial_positions,
                consensus_answer
            )
            
            # Phase 4 evaluation
            evaluation_metrics = self._phase4_evaluation(
                consensus_answer,
                ground_truth
            )
            
            return DebateTranscript(
                debate_id=debate_id,
                question=question,
                ground_truth=ground_truth,
                initial_positions=initial_positions,
                consensus_reached=True,
                consensus_answer=consensus_answer,
                skipped_to_phase_3=True,
                rounds=[],
                total_rounds=0,
                stopped_early=True,
                early_stop_reason="Consensus in Phase 1",
                judge_cot_analysis=judge_analysis.cot_analysis,
                strongest_argument_a=judge_analysis.strongest_arg_a,
                strongest_argument_b=judge_analysis.strongest_arg_b,
                weakest_argument_a=judge_analysis.weakest_arg_a,
                weakest_argument_b=judge_analysis.weakest_arg_b,
                final_verdict=judge_analysis.verdict,
                confidence_score=judge_analysis.confidence,
                ground_truth_match=evaluation_metrics.get('match'),
                evaluation_metrics=evaluation_metrics
            )
        
        # ==================================================================
        # PHASE 2: MULTI-ROUND DEBATE (N ≥ 3)
        # ==================================================================
        logger.info("=== PHASE 2: MULTI-ROUND DEBATE ===")
        rounds, stopped_early, early_stop_reason = self._phase2_debate(
            question,
            initial_positions
        )
        
        # ==================================================================
        # PHASE 3: JUDGMENT
        # ==================================================================
        logger.info("=== PHASE 3: JUDGMENT ===")
        judge_analysis = self._phase3_judgment_debate(
            question,
            initial_positions,
            rounds
        )
        
        # ==================================================================
        # PHASE 4: EVALUATION
        # ==================================================================
        logger.info("=== PHASE 4: EVALUATION ===")
        evaluation_metrics = self._phase4_evaluation(
            judge_analysis.verdict,
            ground_truth
        )
        
        # Construct and return complete transcript
        transcript = DebateTranscript(
            debate_id=debate_id,
            question=question,
            ground_truth=ground_truth,
            initial_positions=initial_positions,
            consensus_reached=False,
            consensus_answer=None,
            skipped_to_phase_3=False,
            rounds=rounds,
            total_rounds=len(rounds),
            stopped_early=stopped_early,
            early_stop_reason=early_stop_reason,
            judge_cot_analysis=judge_analysis.cot_analysis,
            strongest_argument_a=judge_analysis.strongest_arg_a,
            strongest_argument_b=judge_analysis.strongest_arg_b,
            weakest_argument_a=judge_analysis.weakest_arg_a,
            weakest_argument_b=judge_analysis.weakest_arg_b,
            final_verdict=judge_analysis.verdict,
            confidence_score=judge_analysis.confidence,
            ground_truth_match=evaluation_metrics.get('match'),
            evaluation_metrics=evaluation_metrics
        )
        
        logger.info(f"Debate {debate_id} completed")
        return transcript
    
    # ======================================================================
    # PHASE 1: INITIALIZATION
    # ======================================================================
    
    def _phase1_initialization(self, question: str) -> Dict[str, InitialPosition]:
        """
        Phase 1: Generate independent initial positions
        
        Each debater generates answer + reasoning WITHOUT seeing the other's response
        """
        logger.info("Phase 1: Generating independent initial positions")
        
        positions = {}
        
        # Debater A - independent generation
        logger.info("Requesting initial position from Debater A")
        response_a = self.api_client.call(
            prompt=self._prompt_initial_position("Debater A", question),
            max_tokens=500
        )
        positions['debater_a'] = self._parse_initial_position(
            response_a, "Debater A"
        )
        logger.info(f"Debater A initial position: {positions['debater_a'].answer}")
        
        # Debater B - independent generation (NOT seeing A's response)
        logger.info("Requesting initial position from Debater B")
        response_b = self.api_client.call(
            prompt=self._prompt_initial_position("Debater B", question),
            max_tokens=500
        )
        positions['debater_b'] = self._parse_initial_position(
            response_b, "Debater B"
        )
        logger.info(f"Debater B initial position: {positions['debater_b'].answer}")
        
        return positions
    
    def _prompt_initial_position(self, debater_id: str, question: str) -> str:
        """Generate prompt for independent initial position"""
        return f"""You are {debater_id} in a structured debate.

Your task: Generate your initial position on the following question WITHOUT knowing the other debater's answer.

Question: {question}

IMPORTANT: Generate ONLY your own position. Do not speculate about the other side.

Please provide:
1. Your answer (concise)
2. Your brief reasoning (3-4 sentences)

Format your response exactly as:
ANSWER: [your answer here]
REASONING: [your reasoning here]"""

    def _parse_initial_position(self, response: str, debater_id: str) -> InitialPosition:
        """Parse initial position from debater response"""
        lines = response.strip().split('\n')
        answer = ""
        reasoning = ""
        
        for line in lines:
            if line.startswith("ANSWER:"):
                answer = line.replace("ANSWER:", "").strip()
            elif line.startswith("REASONING:"):
                reasoning = line.replace("REASONING:", "").strip()
        
        return InitialPosition(
            debater_id=debater_id,
            answer=answer,
            reasoning=reasoning,
            timestamp=datetime.now().isoformat()
        )
    
    # ======================================================================
    # PHASE 2: MULTI-ROUND DEBATE
    # ======================================================================
    
    def _phase2_debate(
        self,
        question: str,
        initial_positions: Dict[str, InitialPosition]
    ) -> Tuple[List[List[RoundArgument]], bool, Optional[str]]:
        """
        Phase 2: Multi-round debate with adaptive stopping
        
        Requirements:
        - Minimum N ≥ 3 rounds
        - Each round: Debater A argues, then Debater B responds
        - Both see full transcript from previous rounds
        - Stop early if same answer for 2 consecutive rounds
        """
        logger.info("Phase 2: Starting multi-round debate")
        
        rounds: List[List[RoundArgument]] = []
        stopped_early = False
        early_stop_reason = None
        consecutive_same_answers = 0
        last_round_answers = {
            'debater_a': None,
            'debater_b': None
        }
        
        for round_num in range(1, self.max_rounds + 1):
            logger.info(f"\n--- Round {round_num} ---")
            
            # Build transcript from previous rounds
            transcript = self._build_transcript(
                question,
                initial_positions,
                rounds
            )
            
            round_arguments = []
            
            # Debater A makes argument
            logger.info(f"Round {round_num}: Debater A arguing")
            response_a = self.api_client.call(
                prompt=self._prompt_debater_argument(
                    "Debater A",
                    question,
                    transcript,
                    initial_positions['debater_a'].answer,
                    round_num
                ),
                max_tokens=600
            )
            arg_a = self._parse_round_argument(response_a, "Debater A", round_num)
            round_arguments.append(arg_a)
            logger.info(f"Debater A argument: {arg_a.argument[:100]}...")
            
            # Debater B responds
            logger.info(f"Round {round_num}: Debater B responding")
            response_b = self.api_client.call(
                prompt=self._prompt_debater_argument(
                    "Debater B",
                    question,
                    transcript + f"\n\nDebater A Argument (Round {round_num}):\n{arg_a.argument}",
                    initial_positions['debater_b'].answer,
                    round_num,
                    is_response=True
                ),
                max_tokens=600
            )
            arg_b = self._parse_round_argument(response_b, "Debater B", round_num)
            round_arguments.append(arg_b)
            logger.info(f"Debater B argument: {arg_b.argument[:100]}...")
            
            rounds.append(round_arguments)
            
            # ===== ADAPTIVE STOPPING CRITERION =====
            # Check if both debaters maintain same answer for 2 consecutive rounds
            current_answers = {
                'debater_a': self._extract_answer_from_argument(arg_a.argument),
                'debater_b': self._extract_answer_from_argument(arg_b.argument)
            }
            
            if (current_answers['debater_a'] == last_round_answers['debater_a'] and
                current_answers['debater_b'] == last_round_answers['debater_b']):
                consecutive_same_answers += 1
                logger.info(f"Same answers for {consecutive_same_answers} consecutive rounds")
                
                if consecutive_same_answers >= 2 and round_num >= self.min_rounds:
                    logger.info("Convergence detected: stopping debate early")
                    stopped_early = True
                    early_stop_reason = f"Convergence after {round_num} rounds"
                    break
            else:
                consecutive_same_answers = 0
            
            last_round_answers = current_answers
            
            # Minimum rounds check
            if round_num < self.min_rounds:
                logger.info(f"Minimum rounds ({self.min_rounds}) not reached, continuing")
                continue
            
            # Log current state
            logger.info(f"Round {round_num} complete. Total rounds: {round_num}")
        
        return rounds, stopped_early, early_stop_reason
    
    def _build_transcript(
        self,
        question: str,
        initial_positions: Dict[str, InitialPosition],
        rounds: List[List[RoundArgument]]
    ) -> str:
        """Build complete debate transcript for context"""
        lines = [
            f"QUESTION: {question}\n",
            f"INITIAL POSITIONS:",
            f"  Debater A: {initial_positions['debater_a'].answer}",
            f"  Debater B: {initial_positions['debater_b'].answer}\n"
        ]
        
        for i, round_args in enumerate(rounds, 1):
            lines.append(f"ROUND {i}:")
            for arg in round_args:
                lines.append(f"  {arg.debater_id}:")
                lines.append(f"    {arg.argument}")
        
        return "\n".join(lines)
    
    def _prompt_debater_argument(
        self,
        debater_id: str,
        question: str,
        transcript: str,
        initial_answer: str,
        round_num: int,
        is_response: bool = False
    ) -> str:
        """Generate prompt for debater argument with CoT"""
        response_type = "RESPONSE" if is_response else "ARGUMENT"
        
        return f"""You are {debater_id} in a structured debate.

Question: {question}

Your committed answer: {initial_answer}

FULL DEBATE TRANSCRIPT SO FAR:
{transcript}

Your task in Round {round_num}:
Provide a {response_type} supporting your answer with chain-of-thought reasoning.

Requirements:
1. Start with chain-of-thought analysis (step-by-step reasoning)
2. Present a clear, compelling argument supporting your answer
3. Address specific points from the transcript if this is a response
4. Keep to 150-200 words

Format exactly as:
CHAIN_OF_THOUGHT: [step-by-step reasoning]
ARGUMENT: [your argument]"""

    def _parse_round_argument(
        self,
        response: str,
        debater_id: str,
        round_num: int
    ) -> RoundArgument:
        """Parse round argument from response"""
        cot = ""
        argument = ""
        
        lines = response.strip().split('\n')
        for line in lines:
            if line.startswith("CHAIN_OF_THOUGHT:"):
                cot = line.replace("CHAIN_OF_THOUGHT:", "").strip()
            elif line.startswith("ARGUMENT:"):
                argument = line.replace("ARGUMENT:", "").strip()
        
        return RoundArgument(
            round_num=round_num,
            debater_id=debater_id,
            argument=argument,
            cot_reasoning=cot,
            timestamp=datetime.now().isoformat()
        )
    
    def _extract_answer_from_argument(self, argument: str) -> str:
        """Extract primary answer commitment from argument"""
        # Simple heuristic: look for answer indicators
        for marker in ["answer is", "conclude", "believe", "claim"]:
            if marker in argument.lower():
                return argument[:100]  # Simplified
        return argument[:50]
    
    # ======================================================================
    # PHASE 3: JUDGMENT
    # ======================================================================
    
    def _phase3_judgment_debate(
        self,
        question: str,
        initial_positions: Dict[str, InitialPosition],
        rounds: List[List[RoundArgument]]
    ) -> JudgeAnalysis:
        """
        Phase 3: Judge analysis with required outputs:
        (a) CoT analysis of both arguments
        (b) Strongest argument from each side
        (c) Weakest argument from each side
        (d) Final verdict
        (e) Confidence 1-5
        """
        logger.info("Phase 3: Judge analyzing complete debate")
        
        # Build full debate transcript for judge
        transcript = self._build_transcript(question, initial_positions, rounds)
        
        # Request structured judge analysis
        response = self.api_client.call(
            prompt=self._prompt_judge_analysis(question, transcript),
            max_tokens=1500
        )
        
        analysis = self._parse_judge_analysis(response)
        logger.info(f"Judge verdict: {analysis.verdict}")
        logger.info(f"Confidence: {analysis.confidence}/5")
        
        return analysis
    
    def _phase3_judgment_consensus(
        self,
        question: str,
        initial_positions: Dict[str, InitialPosition],
        consensus_answer: str
    ) -> JudgeAnalysis:
        """Phase 3 judgment when consensus reached in Phase 1"""
        logger.info("Phase 3: Evaluating consensus")
        
        response = self.api_client.call(
            prompt=self._prompt_judge_consensus(
                question,
                consensus_answer,
                initial_positions
            ),
            max_tokens=800
        )
        
        analysis = self._parse_judge_analysis(response)
        return analysis
    
    def _prompt_judge_analysis(self, question: str, transcript: str) -> str:
        """Generate prompt for structured judge analysis"""
        return f"""You are a judge evaluating a structured debate.

QUESTION: {question}

COMPLETE DEBATE TRANSCRIPT:
{transcript}

Your task: Provide comprehensive analysis of both debaters' arguments.

REQUIREMENTS:
1. Chain-of-Thought Analysis: Analyze key points from each debater
2. Strongest Argument A: Identify Debater A's best point
3. Strongest Argument B: Identify Debater B's best point
4. Weakest Argument A: Identify Debater A's weakest point
5. Weakest Argument B: Identify Debater B's weakest point
6. Final Verdict: Which debater's answer is stronger? Why?
7. Confidence: Rate your confidence 1-5 (1=very uncertain, 5=very confident)

Format exactly as:
CHAIN_OF_THOUGHT: [your analysis]
STRONGEST_A: [Debater A's best argument]
STRONGEST_B: [Debater B's best argument]
WEAKEST_A: [Debater A's weakest argument]
WEAKEST_B: [Debater B's weakest argument]
VERDICT: [which answer wins and why]
CONFIDENCE: [1-5]"""

    def _prompt_judge_consensus(
        self,
        question: str,
        consensus_answer: str,
        initial_positions: Dict[str, InitialPosition]
    ) -> str:
        """Judge analysis when consensus reached"""
        return f"""You are a judge evaluating a debate that reached consensus in Phase 1.

QUESTION: {question}

Both debaters independently agreed on: {consensus_answer}

Debater A reasoning: {initial_positions['debater_a'].reasoning}
Debater B reasoning: {initial_positions['debater_b'].reasoning}

Evaluate whether this consensus is well-reasoned.

Format:
CHAIN_OF_THOUGHT: [analysis]
STRONGEST_A: [quality of A's reasoning]
STRONGEST_B: [quality of B's reasoning]
WEAKEST_A: [any gaps in A's reasoning]
WEAKEST_B: [any gaps in B's reasoning]
VERDICT: {consensus_answer}
CONFIDENCE: [1-5]"""

    def _parse_judge_analysis(self, response: str) -> JudgeAnalysis:
        """Parse structured judge analysis"""
        fields = {
            'CHAIN_OF_THOUGHT': '',
            'STRONGEST_A': '',
            'STRONGEST_B': '',
            'WEAKEST_A': '',
            'WEAKEST_B': '',
            'VERDICT': '',
            'CONFIDENCE': '3'
        }
        
        lines = response.strip().split('\n')
        for line in lines:
            for field in fields:
                if line.startswith(f"{field}:"):
                    fields[field] = line.replace(f"{field}:", "").strip()
        
        # Parse confidence as integer
        try:
            confidence = int(fields['CONFIDENCE'])
            confidence = max(1, min(5, confidence))
        except ValueError:
            confidence = 3
        
        return JudgeAnalysis(
            cot_analysis=fields['CHAIN_OF_THOUGHT'],
            strongest_arg_a=fields['STRONGEST_A'],
            strongest_arg_b=fields['STRONGEST_B'],
            weakest_arg_a=fields['WEAKEST_A'],
            weakest_arg_b=fields['WEAKEST_B'],
            verdict=fields['VERDICT'],
            confidence=confidence
        )
    
    # ======================================================================
    # PHASE 4: EVALUATION
    # ======================================================================
    
    def _phase4_evaluation(
        self,
        judge_verdict: str,
        ground_truth: Optional[str]
    ) -> Dict:
        """
        Phase 4: Evaluate judge verdict against ground truth
        
        Records:
        - Whether verdict matches ground truth
        - Intermediate data for analysis
        """
        logger.info("Phase 4: Evaluating verdict against ground truth")
        
        metrics = {
            'judge_verdict': judge_verdict,
            'ground_truth': ground_truth,
            'match': None,
            'evaluation_timestamp': datetime.now().isoformat()
        }
        
        if ground_truth is not None:
            # Simple string matching (can be extended)
            match = judge_verdict.lower().strip() == ground_truth.lower().strip()
            metrics['match'] = match
            logger.info(f"Verdict matches ground truth: {match}")
        
        return metrics
    
    def export_transcript(self, transcript: DebateTranscript) -> Dict:
        """Export transcript to JSON-serializable dict"""
        data = {
            'debate_id': transcript.debate_id,
            'question': transcript.question,
            'ground_truth': transcript.ground_truth,
            'phase1_initialization': {
                'consensus_reached': transcript.consensus_reached,
                'consensus_answer': transcript.consensus_answer,
                'skipped_to_phase_3': transcript.skipped_to_phase_3,
                'initial_positions': {
                    k: asdict(v) for k, v in transcript.initial_positions.items()
                }
            },
            'phase2_debate': {
                'total_rounds': transcript.total_rounds,
                'stopped_early': transcript.stopped_early,
                'early_stop_reason': transcript.early_stop_reason,
                'rounds': [
                    [asdict(arg) for arg in round_args]
                    for round_args in transcript.rounds
                ]
            },
            'phase3_judgment': {
                'cot_analysis': transcript.judge_cot_analysis,
                'strongest_argument_a': transcript.strongest_argument_a,
                'strongest_argument_b': transcript.strongest_argument_b,
                'weakest_argument_a': transcript.weakest_argument_a,
                'weakest_argument_b': transcript.weakest_argument_b,
                'final_verdict': transcript.final_verdict,
                'confidence_score': transcript.confidence_score
            },
            'phase4_evaluation': {
                'ground_truth_match': transcript.ground_truth_match,
                'metrics': transcript.evaluation_metrics
            }
        }
        return data
