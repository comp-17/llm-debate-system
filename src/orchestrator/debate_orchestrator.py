"""Main orchestrator for the debate system."""

from typing import Dict, List, Any, Optional, Tuple
from src.agents.debaters import DebaterA, DebaterB
from src.agents.judges import JudgeSingle, JuryPanel
from src.utils.api_client import APIClient
from src.utils.utils import DebateLogger

class DebateOrchestrator:
    """Orchestrates the complete debate pipeline."""
    
    def __init__(self, config: dict):
        """Initialize orchestrator with configuration."""
        self.config = config
        self.api_client = APIClient(config)
        self.logger = DebateLogger(config)
        
        # Initialize agents
        self.debater_a = DebaterA(self.api_client)
        self.debater_b = DebaterB(self.api_client)
        
        # Initialize judges
        self.judge_single = JudgeSingle(self.api_client)
        self.jury_panel = JuryPanel(self.api_client, config['judge']['jury_size'])
    
    def run_debate(self, question: str, question_id: str, ground_truth: Optional[str] = None) -> Dict[str, Any]:
        """
        Run complete debate pipeline for a single question.
        
        Args:
            question: The question to debate
            question_id: Unique identifier for the question
            ground_truth: Optional ground truth answer for evaluation
            
        Returns:
            Complete debate result including all phases
        """
        print(f"\n{'='*80}")
        print(f"DEBATE: {question}")
        print(f"{'='*80}")
        
        # Phase 1: Initialization
        print("\n[PHASE 1] INITIALIZATION")
        self.logger.start_debate(question_id, question)
        if ground_truth:
            self.logger.set_ground_truth(ground_truth)
        
        debater_a_position, debater_a_arg = self.debater_a.initial_argument(question, ground_truth)
        print(f"Debater A position: {debater_a_position}")
        
        # FIXED: Debater B generates position independently WITHOUT seeing Debater A's position
        debater_b_position, debater_b_arg = self.debater_b.initial_argument(question, ground_truth)
        print(f"Debater B position: {debater_b_position}")
        
        self.logger.log_initial_positions(debater_a_position, debater_b_position)
        
        # Check for immediate consensus
        if debater_a_position == debater_b_position:
            print("\n[CONSENSUS REACHED] Both debaters agreed in initialization phase.")
            self.convergence_count = 2
        
        # Phase 2: Multi-Round Debate
        print("\n[PHASE 2] MULTI-ROUND DEBATE")
        debate_transcript = self._build_transcript_prefix(question, debater_a_position, debater_b_position, debater_a_arg, debater_b_arg)
        
        round_num = 2
        convergence_count = 0
        last_round_converged = False
        
        while round_num <= self.config['debate']['max_rounds']:
            print(f"\n--- Round {round_num} ---")
            
            # Debater A rebuttal
            debater_a_rebuttal = self.debater_a.rebut(
                question, debater_b_position, debater_b_arg, round_num
            )
            print(f"Debater A rebuttal generated.")
            
            # FIXED: Extract current position from Debater A's rebuttal
            debater_a_position = self.debater_a._extract_answer_from_response(debater_a_rebuttal)
            if debater_a_position == "Unknown":
                debater_a_position = self.debater_a.position  # Keep previous position if extraction fails
            else:
                self.debater_a.position = debater_a_position  # Update internal position
            print(f"Debater A current position: {debater_a_position}")
            
            # Debater B rebuttal
            debater_b_rebuttal = self.debater_b.rebut(
                question, debater_a_position, debater_a_arg, round_num
            )
            print(f"Debater B rebuttal generated.")
            
            # FIXED: Extract current position from Debater B's rebuttal
            debater_b_position = self.debater_b._extract_answer_from_response(debater_b_rebuttal)
            if debater_b_position == "Unknown":
                debater_b_position = self.debater_b.position  # Keep previous position if extraction fails
            else:
                self.debater_b.position = debater_b_position  # Update internal position
            print(f"Debater B current position: {debater_b_position}")
            
            # Log round
            self.logger.log_round(round_num, debater_a_rebuttal, debater_b_rebuttal)
            
            # Update transcript
            debate_transcript += f"\n\n**[Round {round_num}]**\n\nDebater A: {debater_a_rebuttal}\n\nDebater B: {debater_b_rebuttal}"
            
            # FIXED: Check for convergence with updated positions
            current_round_converged = (debater_a_position == debater_b_position)
            print(f"Convergence check: A={debater_a_position}, B={debater_b_position}, Converged={current_round_converged}")
            
            if current_round_converged:
                if last_round_converged:
                    convergence_count += 1
                    print(f"[CONVERGENCE] Debaters converged for {convergence_count}/{self.config['debate']['convergence_threshold']} required rounds.")
                    if convergence_count >= self.config['debate']['convergence_threshold']:
                        print(f"[EARLY STOP] Debaters converged to '{debater_a_position}' for {convergence_count} consecutive rounds. Ending debate.")
                        break
                else:
                    convergence_count = 1
                    print(f"[CONVERGENCE] First convergence detected. Monitoring for consecutive convergence...")
            else:
                convergence_count = 0
            
            last_round_converged = current_round_converged
            
            # Check for max rounds
            if round_num >= self.config['debate']['max_rounds']:
                print(f"\n[MAX ROUNDS] Reached maximum rounds ({self.config['debate']['max_rounds']}).")
                break
            
            # Update for next round
            debater_a_arg = debater_a_rebuttal
            debater_b_arg = debater_b_rebuttal
            round_num += 1
        
        # Phase 3: Judgment
        print("\n[PHASE 3] JUDGMENT")
        
        result = {
            'question_id': question_id,
            'question': question,
            'debater_a_final_position': debater_a_position,
            'debater_b_final_position': debater_b_position,
            'rounds_completed': round_num - 1,
            'ground_truth': ground_truth,
        }
        
        # Single Judge Evaluation
        if self.config['judge']['single_judge']:
            print("Single judge evaluating...")
            judge_verdict = self.judge_single.evaluate(
                question, debater_a_position, debater_b_position, debate_transcript
            )
            self.logger.log_judge_verdict(judge_verdict)
            result['judge_verdict'] = judge_verdict
            print(f"Judge verdict: {judge_verdict['winner']} (Confidence: {judge_verdict['confidence']})")
        
        # Jury Panel Evaluation (BONUS)
        print("Jury panel evaluating...")
        jury_results = self.jury_panel.evaluate(
            question, debater_a_position, debater_b_position, debate_transcript
        )
        
        print("Jury members deliberating...")
        jury_deliberation = self.jury_panel.deliberate(
            question, debater_a_position, debater_b_position, debate_transcript
        )
        
        self.logger.log_jury_verdicts(jury_deliberation['individual_verdicts'], jury_deliberation['consensus_verdict'])
        result['jury_results'] = {
            'individual_verdicts': jury_deliberation['individual_verdicts'],
            'consensus': jury_deliberation['consensus_verdict']
        }
        
        consensus_winner = self.jury_panel.get_consensus_winner()
        print(f"Jury consensus: {consensus_winner}")
        
        # Save transcript
        self.logger.save_debate()
        
        return result
    
    def run_batch(self, questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Run debates on a batch of questions.
        
        Args:
            questions: List of question dictionaries with 'id', 'question', and 'answer' keys
            
        Returns:
            List of debate results
        """
        results = []
        total = len(questions)
        
        for idx, q in enumerate(questions, 1):
            print(f"\n[{idx}/{total}] Processing question {q.get('id', 'unknown')}...")
            
            try:
                result = self.run_debate(
                    question=q['question'],
                    question_id=q['id'],
                    ground_truth=q.get('answer')
                )
                results.append(result)
            except Exception as e:
                print(f"ERROR processing question {q.get('id')}: {str(e)}")
                results.append({
                    'question_id': q.get('id'),
                    'question': q.get('question'),
                    'error': str(e)
                })
        
        return results
    
    def _build_transcript_prefix(self, question: str, pos_a: str, pos_b: str,
                                arg_a: str, arg_b: str) -> str:
        """Build initial debate transcript."""
        transcript = f"""
DEBATE TRANSCRIPT
================

Question: {question}

Initial Positions:
- Debater A: {pos_a}
- Debater B: {pos_b}

**[Round 1]**

Debater A: {arg_a}

Debater B: {arg_b}
"""
        return transcript
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about API usage and system state."""
        return {
            'total_api_calls': self.api_client.get_call_count(),
            'debater_a_rounds': len(self.debater_a.argument_history),
            'debater_b_rounds': len(self.debater_b.argument_history),
            'model': self.config['model']['name']
        }
