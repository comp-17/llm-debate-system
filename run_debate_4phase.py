"""
Experiment runner for 4-phase debate protocol
Tests the complete multi-round debate system with phase-based execution
"""

import json
import logging
import sys
from pathlib import Path
from datetime import datetime

from src.utils.api_client import APIClient
from src.orchestrator.debate_orchestrator_4phase import (
    MultiPhaseDebateOrchestrator,
    DebateResult
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FourPhaseExperimentRunner:
    """Run controlled experiments using 4-phase debate protocol"""
    
    def __init__(
        self,
        api_key: str = None,
        model: str = "claude-3-5-sonnet-20241022",
        min_rounds: int = 3,
        max_rounds: int = 6,
    ):
        """Initialize experiment runner"""
        self.api_client = APIClient(api_key=api_key, model=model)
        self.orchestrator = MultiPhaseDebateOrchestrator(
            api_client=self.api_client,
            min_rounds=min_rounds,
            max_rounds=max_rounds,
            convergence_threshold=2,
        )
        self.results = []
        
    def run_single_debate(
        self,
        question: str,
        ground_truth: str = None,
        question_id: str = None,
    ) -> DebateResult:
        """Run a single debate with 4-phase protocol"""
        
        if not question_id:
            question_id = f"q_{len(self.results)}"
        
        logger.info(f"{'='*80}")
        logger.info(f"Debate {question_id}: {question}")
        logger.info(f"{'='*80}")
        
        try:
            result = self.orchestrator.run_debate(
                question=question,
                ground_truth=ground_truth,
            )
            self.results.append(result)
            
            # Print summary
            self._print_result_summary(result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in debate {question_id}: {str(e)}")
            raise
    
    def run_batch(
        self,
        questions: list,
        output_dir: str = "data/results",
    ) -> dict:
        """
        Run batch of debates
        
        Args:
            questions: List of dicts with 'question' and optionally 'ground_truth'
            output_dir: Directory to save results
            
        Returns:
            Summary statistics
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Running {len(questions)} debates...")
        
        for idx, q_data in enumerate(questions, 1):
            logger.info(f"\n[{idx}/{len(questions)}]")
            
            try:
                self.run_single_debate(
                    question=q_data['question'],
                    ground_truth=q_data.get('ground_truth'),
                    question_id=q_data.get('id', f"q_{idx}"),
                )
            except Exception as e:
                logger.error(f"Failed on question {idx}: {str(e)}")
                continue
        
        # Compute summary statistics
        summary = self._compute_summary()
        
        # Save results
        self._save_results(output_dir, summary)
        
        return summary
    
    def _print_result_summary(self, result: DebateResult):
        """Print summary of a single debate"""
        print(f"\n{'='*80}")
        print("DEBATE RESULT SUMMARY")
        print(f"{'='*80}")
        
        print(f"\nPhase 1 - Initialization:")
        print(f"  Debater A: {result.initial_position_a.answer}")
        print(f"  Debater B: {result.initial_position_b.answer}")
        print(f"  Consensus: {result.consensus_reached}")
        
        print(f"\nPhase 2 - Debate:")
        print(f"  Rounds: {result.rounds_executed}")
        print(f"  Stopping reason: {result.stopping_reason}")
        
        print(f"\nPhase 3 - Judge Verdict:")
        print(f"  Verdict: {result.judge_analysis.final_verdict}")
        print(f"  Confidence: {result.judge_analysis.confidence}/5")
        print(f"  Strongest A: {result.judge_analysis.strongest_argument_a[:100]}...")
        print(f"  Strongest B: {result.judge_analysis.strongest_argument_b[:100]}...")
        
        if result.ground_truth:
            print(f"\nPhase 4 - Evaluation:")
            print(f"  Ground truth: {result.ground_truth}")
            print(f"  Judge correct: {result.judge_correct}")
            print(f"  Debate improved accuracy: {result.debate_improved_accuracy}")
        
        print(f"{'='*80}\n")
    
    def _compute_summary(self) -> dict:
        """Compute summary statistics"""
        if not self.results:
            return {}
        
        n = len(self.results)
        
        summary = {
            "total_debates": n,
            "timestamp": datetime.now().isoformat(),
            "phases_completed": {
                "phase1_init": n,
                "phase2_debate": n,
                "phase3_judgment": n,
                "phase4_evaluation": sum(1 for r in self.results if r.ground_truth),
            },
            "debate_metrics": {
                "avg_rounds": sum(r.rounds_executed for r in self.results) / n,
                "consensus_reached": sum(1 for r in self.results if r.consensus_reached),
                "early_stops": sum(1 for r in self.results if "convergence" in r.stopping_reason),
                "max_round_limits": sum(1 for r in self.results if "max_rounds" in r.stopping_reason),
            },
            "accuracy_metrics": {
                "judge_correct": sum(1 for r in self.results if r.judge_correct),
                "debate_improved": sum(1 for r in self.results if r.debate_improved_accuracy),
            },
            "judge_confidence": {
                "avg_confidence": sum(r.judge_analysis.confidence for r in self.results) / n,
                "confidence_dist": {
                    i: sum(1 for r in self.results if r.judge_analysis.confidence == i)
                    for i in range(1, 6)
                }
            }
        }
        
        # Compute accuracy only if ground truth available
        results_with_gt = [r for r in self.results if r.ground_truth]
        if results_with_gt:
            n_gt = len(results_with_gt)
            summary["accuracy_metrics"]["judge_accuracy_pct"] = (
                sum(1 for r in results_with_gt if r.judge_correct) / n_gt * 100
            )
            summary["accuracy_metrics"]["accuracy_improvement_pct"] = (
                sum(1 for r in results_with_gt if r.debate_improved_accuracy) / n_gt * 100
            )
        
        return summary
    
    def _save_results(self, output_dir: str, summary: dict):
        """Save all results to JSON files"""
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # Save individual results
        for idx, result in enumerate(self.results, 1):
            filepath = Path(output_dir) / f"debate_{idx:03d}.json"
            self.orchestrator.save_result(result, str(filepath))
        
        # Save summary
        summary_file = Path(output_dir) / "summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"Results saved to {output_dir}")
        logger.info(f"\nSummary: {json.dumps(summary, indent=2)}")


def create_sample_questions() -> list:
    """Create sample questions for testing"""
    return [
        {
            "id": "q1",
            "question": "Is the Earth flat or spherical?",
            "ground_truth": "spherical",
        },
        {
            "id": "q2",
            "question": "What is 2 + 2?",
            "ground_truth": "4",
        },
        {
            "id": "q3",
            "question": "Should artificial intelligence be regulated by governments?",
            "ground_truth": "yes",  # Subjective but grounded
        },
        {
            "id": "q4",
            "question": "Is climate change primarily caused by human activity?",
            "ground_truth": "yes",
        },
        {
            "id": "q5",
            "question": "Was World War II fought primarily in Europe and Asia?",
            "ground_truth": "yes",
        },
    ]


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run 4-phase debate experiments")
    parser.add_argument("--samples", type=int, default=5, help="Number of samples to run")
    parser.add_argument("--output", type=str, default="data/results_4phase", help="Output directory")
    parser.add_argument("--model", type=str, default="claude-3-5-sonnet-20241022", help="LLM model")
    parser.add_argument("--min-rounds", type=int, default=3, help="Minimum debate rounds")
    parser.add_argument("--max-rounds", type=int, default=6, help="Maximum debate rounds")
    
    args = parser.parse_args()
    
    logger.info("Starting 4-Phase Debate Experiment Runner")
    logger.info(f"Model: {args.model}")
    logger.info(f"Min rounds: {args.min_rounds}, Max rounds: {args.max_rounds}")
    
    # Initialize runner
    runner = FourPhaseExperimentRunner(
        model=args.model,
        min_rounds=args.min_rounds,
        max_rounds=args.max_rounds,
    )
    
    # Load questions
    all_questions = create_sample_questions()
    questions = all_questions[:args.samples]
    
    logger.info(f"Running {len(questions)} debates...")
    
    # Run batch experiment
    summary = runner.run_batch(questions, output_dir=args.output)
    
    print(f"\n{'='*80}")
    print("EXPERIMENT SUMMARY")
    print(f"{'='*80}")
    print(json.dumps(summary, indent=2))
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
