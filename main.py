#!/usr/bin/env python3
"""Main entry point for the LLM Debate System."""

import json
import sys
import os
from datetime import datetime
from src.utils.utils import load_config, DebateDataset, DebateLogger
from src.orchestrator.debate_orchestrator import DebateOrchestrator
from src.utils.evaluation import DebateEvaluator, BaselineComparison

def main():
    """Run the complete debate system."""
    
    print("=" * 80)
    print("LLM DEBATE SYSTEM - WITH MULTI-AGENT JUDGE PANEL")
    print("=" * 80)
    
    # Load configuration
    config = load_config("config.yaml")
    print(f"\nConfiguration loaded:")
    print(f"  Model: {config['model']['name']}")
    print(f"  Domain: {config['dataset']['domain']}")
    print(f"  Samples: {config['dataset']['num_samples']}")
    print(f"  Jury Size: {config['judge']['jury_size']}")
    
    # Initialize orchestrator
    orchestrator = DebateOrchestrator(config)
    
    # Load dataset
    print(f"\nLoading {config['dataset']['domain']} dataset...")
    dataset = DebateDataset.load_dataset(
        config['dataset']['domain'],
        config['dataset']['num_samples'],
        config['dataset']['sample_seed']
    )
    print(f"Loaded {len(dataset)} questions")
    
    # Run debates
    print(f"\nStarting debate batch...\n")
    results = orchestrator.run_batch(dataset)
    
    # Evaluation
    print(f"\n{'='*80}")
    print("EVALUATION AND ANALYSIS")
    print("=" * 80)
    
    report = DebateEvaluator.generate_report(results)
    
    print(f"\nDebate Statistics:")
    print(f"  Total debates: {report['debate_statistics']['total_debates']}")
    print(f"  Successful: {report['debate_statistics']['successful_debates']}")
    print(f"  Failed: {report['debate_statistics']['failed_debates']}")
    print(f"  Average rounds: {report['debate_statistics']['average_rounds']:.1f}")
    
    print(f"\nAccuracy Metrics:")
    print(f"  Judge accuracy: {report['accuracy_metrics']['judge_accuracy']:.2%}")
    print(f"  Jury accuracy: {report['accuracy_metrics']['jury_accuracy']:.2%}")
    print(f"  Convergence accuracy: {report['accuracy_metrics']['convergence_accuracy']:.2%}")
    
    print(f"\nJudge vs Jury Agreement:")
    print(f"  Agreement rate: {report['judge_agreement']['agreement_rate']:.2%}")
    print(f"  Cases compared: {report['judge_agreement']['cases_compared']}")
    
    print(f"\nJury Disagreement Analysis (BONUS):")
    print(f"  Total debates: {report['jury_disagreement_analysis']['total_debates']}")
    print(f"  Unanimous verdicts: {report['jury_disagreement_analysis']['unanimous_verdicts']}")
    print(f"  Split verdicts: {report['jury_disagreement_analysis']['split_verdicts']}")
    print(f"  Average member agreement: {report['jury_disagreement_analysis']['average_member_agreement']:.2%}")
    
    # Save results
    print(f"\nSaving results...")
    logger = DebateLogger(config)
    
    results_file = logger.save_results(
        {
            'timestamp': datetime.now().isoformat(),
            'config': config,
            'results': results,
            'evaluation_report': report
        },
        f"debate_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    
    # Save API statistics
    stats = orchestrator.get_stats()
    print(f"\nAPI Statistics:")
    print(f"  Total API calls: {stats['total_api_calls']}")
    print(f"  Model: {stats['model']}")
    
    print(f"\n{'='*80}")
    print(f"Debate system completed successfully!")
    print(f"Results saved to: {results_file}")
    print("=" * 80)
    
    return results, report

if __name__ == "__main__":
    try:
        results, report = main()
    except Exception as e:
        print(f"ERROR: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
