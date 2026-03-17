"""
Runner script for 4-Phase Debate Pipeline
Executes complete debates and records results
"""

import json
import logging
import sys
from pathlib import Path
from typing import List, Dict, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.orchestrator.debate_pipeline_v2 import DebatePipeline
from src.utils.debate_api_client import DebateAPIClient


class DebateRunner:
    """Orchestrates debate pipeline execution"""
    
    def __init__(
        self,
        model: str = "claude-3-5-sonnet-20241022",
        min_rounds: int = 3,
        max_rounds: int = 10,
        output_dir: str = "data/results"
    ):
        """
        Initialize debate runner
        
        Args:
            model: LLM model to use
            min_rounds: Minimum debate rounds
            max_rounds: Maximum debate rounds
            output_dir: Directory for results
        """
        self.api_client = DebateAPIClient(model=model)
        self.pipeline = DebatePipeline(
            api_client=self.api_client,
            min_rounds=min_rounds,
            max_rounds=max_rounds
        )
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def run_debate(
        self,
        debate_id: str,
        question: str,
        ground_truth: Optional[str] = None
    ) -> Dict:
        """
        Run single debate
        
        Args:
            debate_id: Unique debate identifier
            question: Debate question
            ground_truth: Ground truth answer for evaluation
            
        Returns:
            Debate transcript as dict
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"Running Debate: {debate_id}")
        logger.info(f"Question: {question}")
        logger.info(f"Ground Truth: {ground_truth}")
        logger.info(f"{'='*80}\n")
        
        # Run full pipeline
        transcript = self.pipeline.run_full_debate(
            debate_id=debate_id,
            question=question,
            ground_truth=ground_truth
        )
        
        # Export to dict
        result = self.pipeline.export_transcript(transcript)
        
        # Save to file
        output_file = self.output_dir / f"{debate_id}.json"
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        logger.info(f"\nDebate results saved to {output_file}")
        
        return result
    
    def run_batch(self, debates: List[Dict]) -> List[Dict]:
        """
        Run batch of debates
        
        Args:
            debates: List of dicts with keys: debate_id, question, ground_truth
            
        Returns:
            List of debate results
        """
        results = []
        
        for i, debate_config in enumerate(debates, 1):
            logger.info(f"\n{'='*80}")
            logger.info(f"Debate {i}/{len(debates)}")
            logger.info(f"{'='*80}\n")
            
            result = self.run_debate(
                debate_id=debate_config['debate_id'],
                question=debate_config['question'],
                ground_truth=debate_config.get('ground_truth')
            )
            results.append(result)
        
        # Save batch results
        batch_file = self.output_dir / "batch_results.json"
        with open(batch_file, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"\nBatch results saved to {batch_file}")
        
        return results
    
    def generate_report(self, results: List[Dict]) -> Dict:
        """
        Generate analysis report from results
        
        Args:
            results: List of debate results
            
        Returns:
            Report with statistics
        """
        logger.info("\n=== GENERATING REPORT ===\n")
        
        report = {
            'total_debates': len(results),
            'debates_with_consensus': 0,
            'debates_with_convergence': 0,
            'average_rounds': 0,
            'average_confidence': 0,
            'accuracy_vs_ground_truth': None,
            'debates': []
        }
        
        total_rounds = 0
        total_confidence = 0
        matches = 0
        evaluated = 0
        
        for result in results:
            debate_summary = {
                'debate_id': result['debate_id'],
                'question': result['question'],
                'phases': {
                    'phase1_consensus': result['phase1_initialization']['consensus_reached'],
                    'phase2_rounds': result['phase2_debate']['total_rounds'],
                    'phase2_stopped_early': result['phase2_debate']['stopped_early'],
                    'phase3_verdict': result['phase3_judgment']['final_verdict'],
                    'phase3_confidence': result['phase3_judgment']['confidence_score'],
                    'phase4_match': result['phase4_evaluation']['ground_truth_match']
                }
            }
            
            report['debates'].append(debate_summary)
            
            # Accumulate statistics
            if result['phase1_initialization']['consensus_reached']:
                report['debates_with_consensus'] += 1
            
            if result['phase2_debate']['stopped_early']:
                report['debates_with_convergence'] += 1
            
            total_rounds += result['phase2_debate']['total_rounds']
            total_confidence += result['phase3_judgment']['confidence_score']
            
            if result['phase4_evaluation']['ground_truth_match'] is not None:
                evaluated += 1
                if result['phase4_evaluation']['ground_truth_match']:
                    matches += 1
        
        # Calculate averages
        if len(results) > 0:
            report['average_rounds'] = total_rounds / len(results)
            report['average_confidence'] = total_confidence / len(results)
        
        if evaluated > 0:
            report['accuracy_vs_ground_truth'] = matches / evaluated
        
        # Save report
        report_file = self.output_dir / "report.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        logger.info(f"Report saved to {report_file}")
        
        # Print summary
        logger.info(f"\n=== DEBATE REPORT ===")
        logger.info(f"Total debates: {report['total_debates']}")
        logger.info(f"Consensus reached: {report['debates_with_consensus']}")
        logger.info(f"Early convergence: {report['debates_with_convergence']}")
        logger.info(f"Average rounds: {report['average_rounds']:.1f}")
        logger.info(f"Average confidence: {report['average_confidence']:.1f}/5")
        if report['accuracy_vs_ground_truth'] is not None:
            logger.info(f"Accuracy vs ground truth: {report['accuracy_vs_ground_truth']:.1%}")
        
        return report


# ============================================================================
# EXAMPLE DEBATES
# ============================================================================

EXAMPLE_DEBATES = [
    {
        'debate_id': 'debate_001',
        'question': 'Is artificial intelligence more beneficial or harmful to society?',
        'ground_truth': 'beneficial'
    },
    {
        'debate_id': 'debate_002',
        'question': 'Should governments regulate social media platforms?',
        'ground_truth': 'yes'
    },
    {
        'debate_id': 'debate_003',
        'question': 'Is climate change primarily caused by human activity?',
        'ground_truth': 'yes'
    },
    {
        'debate_id': 'debate_004',
        'question': 'Will remote work become the norm in the future?',
        'ground_truth': 'yes'
    },
    {
        'debate_id': 'debate_005',
        'question': 'Is renewable energy more sustainable than fossil fuels?',
        'ground_truth': 'yes'
    }
]


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run 4-Phase Debate Pipeline')
    parser.add_argument('--model', default='claude-3-5-sonnet-20241022', help='LLM model')
    parser.add_argument('--min-rounds', type=int, default=3, help='Minimum debate rounds')
    parser.add_argument('--max-rounds', type=int, default=10, help='Maximum debate rounds')
    parser.add_argument('--num-debates', type=int, default=1, help='Number of debates to run')
    parser.add_argument('--output-dir', default='data/results', help='Output directory')
    parser.add_argument('--single', action='store_true', help='Run single example debate')
    
    args = parser.parse_args()
    
    # Initialize runner
    runner = DebateRunner(
        model=args.model,
        min_rounds=args.min_rounds,
        max_rounds=args.max_rounds,
        output_dir=args.output_dir
    )
    
    if args.single:
        # Run single debate
        debate = EXAMPLE_DEBATES[0]
        result = runner.run_debate(
            debate_id=debate['debate_id'],
            question=debate['question'],
            ground_truth=debate.get('ground_truth')
        )
        logger.info(f"\nFinal Verdict: {result['phase3_judgment']['final_verdict']}")
        logger.info(f"Confidence: {result['phase3_judgment']['confidence_score']}/5")
    else:
        # Run batch
        debates_to_run = EXAMPLE_DEBATES[:args.num_debates]
        results = runner.run_batch(debates_to_run)
        
        # Generate report
        report = runner.generate_report(results)


if __name__ == '__main__':
    main()
