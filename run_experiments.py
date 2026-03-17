#!/usr/bin/env python3
"""
Experiment Runner: Compare Debate System vs Baselines

This script runs the complete experimental suite comparing:
1. Debate Pipeline (with single judge and jury panel)
2. Direct QA Baseline (CoT prompting)
3. Self-Consistency Baseline (majority voting)

All experiments use the same questions and model to ensure fair comparison.
"""

import json
import sys
from datetime import datetime
from typing import Dict, List, Any

from src.utils.utils import load_config, DebateDataset, DebateLogger
from src.orchestrator.debate_orchestrator import DebateOrchestrator
from src.utils.evaluation import DebateEvaluator, BaselineComparison


def run_experiments(num_questions: int = 10, domain: str = "commonsense_qa") -> Dict[str, Any]:
    """
    Run complete experimental suite comparing all approaches.
    
    Args:
        num_questions: Number of questions to test on (default 10 for quick test, use 100+ for paper)
        domain: Dataset domain (commonsense_qa or fact_verification)
        
    Returns:
        Complete results dictionary with all experiments
    """
    print("=" * 80)
    print("LLM DEBATE SYSTEM - EXPERIMENTAL COMPARISON")
    print("=" * 80)
    print(f"\nExperiment Setup:")
    print(f"  Questions: {num_questions}")
    print(f"  Domain: {domain}")
    print(f"  Timestamp: {datetime.now().isoformat()}")
    
    # Load configuration
    config = load_config("config.yaml")
    config['dataset']['num_samples'] = num_questions
    config['dataset']['domain'] = domain
    
    print(f"\nModel Configuration:")
    print(f"  Model: {config['model']['name']}")
    print(f"  Temperature: {config['model']['temperature']}")
    print(f"  Max tokens: {config['model']['max_tokens']}")
    print(f"  Debate rounds: {config['debate']['num_rounds']}")
    print(f"  Jury size: {config['judge']['jury_size']}")
    
    # Load dataset
    print(f"\nLoading dataset...")
    dataset = DebateDataset.load_dataset(domain, num_questions, config['dataset']['sample_seed'])
    print(f"Loaded {len(dataset)} questions from {domain}")
    
    # Initialize results
    all_results = {
        'timestamp': datetime.now().isoformat(),
        'config': {
            'model': config['model']['name'],
            'temperature': config['model']['temperature'],
            'max_tokens': config['model']['max_tokens'],
            'debate_rounds': config['debate']['num_rounds'],
            'jury_size': config['judge']['jury_size'],
            'num_questions': num_questions,
            'domain': domain
        },
        'dataset': dataset,
        'experiments': {}
    }
    
    # ========================================================================
    # EXPERIMENT 1: Debate Pipeline (with jury panel)
    # ========================================================================
    print("\n" + "=" * 80)
    print("EXPERIMENT 1: DEBATE PIPELINE (with Jury Panel)")
    print("=" * 80)
    
    try:
        orchestrator = DebateOrchestrator(config)
        debate_results = orchestrator.run_batch(dataset)
        debate_report = DebateEvaluator.generate_report(debate_results)
        
        all_results['experiments']['debate'] = {
            'name': 'Multi-Agent Debate with Jury Panel',
            'description': 'Two debaters argue opposing sides, judged by single judge and jury panel',
            'results': debate_results,
            'report': debate_report,
            'api_calls': orchestrator.api_client.get_call_count(),
            'judge_accuracy': debate_report['accuracy_metrics']['judge_accuracy'],
            'jury_accuracy': debate_report['accuracy_metrics']['jury_accuracy'],
            'judge_jury_agreement': debate_report['judge_agreement']['agreement_rate'],
            'jury_unanimity': debate_report['jury_disagreement_analysis']['unanimous_verdicts'] / max(1, debate_report['jury_disagreement_analysis']['total_debates']),
            'average_rounds': debate_report['debate_statistics']['average_rounds']
        }
        
        print(f"\nDebate Results:")
        print(f"  Total debates: {debate_report['summary']['total_debates']}")
        print(f"  Successful: {debate_report['summary']['successful']}")
        print(f"  Judge accuracy: {debate_report['accuracy_metrics']['judge_accuracy']:.2%}")
        print(f"  Jury accuracy: {debate_report['accuracy_metrics']['jury_accuracy']:.2%}")
        print(f"  Judge-jury agreement: {debate_report['judge_agreement']['agreement_rate']:.2%}")
        print(f"  Jury unanimity: {debate_report['jury_disagreement_analysis']['unanimous_verdicts']}/{debate_report['jury_disagreement_analysis']['total_debates']}")
        print(f"  Average rounds: {debate_report['debate_statistics']['average_rounds']:.1f}")
        print(f"  API calls: {orchestrator.api_client.get_call_count()}")
        
    except Exception as e:
        print(f"ERROR in debate experiment: {str(e)}")
        import traceback
        traceback.print_exc()
        all_results['experiments']['debate'] = {'error': str(e)}
    
    # ========================================================================
    # EXPERIMENT 2: Direct QA Baseline
    # ========================================================================
    print("\n" + "=" * 80)
    print("EXPERIMENT 2: DIRECT QA BASELINE (CoT Prompting)")
    print("=" * 80)
    
    try:
        api_client = orchestrator.api_client  # Reuse from debate experiment
        initial_api_calls = api_client.get_call_count()
        
        direct_qa = BaselineComparison.direct_qa_baseline(dataset, api_client)
        
        direct_qa['api_calls'] = api_client.get_call_count() - initial_api_calls
        
        all_results['experiments']['direct_qa'] = direct_qa
        
        print(f"\nDirect QA Results:")
        print(f"  Total questions: {direct_qa['total_count']}")
        print(f"  Correct: {direct_qa['correct_count']}")
        print(f"  Accuracy: {direct_qa['accuracy']:.2%}")
        print(f"  API calls: {direct_qa['api_calls']}")
        
    except Exception as e:
        print(f"ERROR in direct QA experiment: {str(e)}")
        import traceback
        traceback.print_exc()
        all_results['experiments']['direct_qa'] = {'error': str(e)}
    
    # ========================================================================
    # EXPERIMENT 3: Self-Consistency Baseline
    # ========================================================================
    print("\n" + "=" * 80)
    print("EXPERIMENT 3: SELF-CONSISTENCY BASELINE (Majority Voting)")
    print("=" * 80)
    
    try:
        api_client = orchestrator.api_client  # Reuse
        initial_api_calls = api_client.get_call_count()
        
        # Calculate num_samples to match debate system's API call count
        debate_api_calls = all_results['experiments']['debate']['api_calls']
        # Rough estimate: debate uses ~4-5 calls per question (2 debaters + judge + jury)
        # For fair comparison, use enough samples to match debate computational budget
        num_samples = max(3, debate_api_calls // max(1, len(dataset)))
        
        print(f"\nRunning self-consistency with {num_samples} samples per question...")
        print(f"(to match debate system's computational budget of ~{debate_api_calls} API calls)")
        
        self_consistency = BaselineComparison.self_consistency_baseline(
            dataset, 
            api_client, 
            num_samples=num_samples
        )
        
        self_consistency['api_calls'] = api_client.get_call_count() - initial_api_calls
        
        all_results['experiments']['self_consistency'] = self_consistency
        
        print(f"\nSelf-Consistency Results:")
        print(f"  Total questions: {self_consistency['total_count']}")
        print(f"  Samples per question: {num_samples}")
        print(f"  Correct: {self_consistency['correct_count']}")
        print(f"  Accuracy: {self_consistency['accuracy']:.2%}")
        print(f"  API calls: {self_consistency['api_calls']}")
        
    except Exception as e:
        print(f"ERROR in self-consistency experiment: {str(e)}")
        import traceback
        traceback.print_exc()
        all_results['experiments']['self_consistency'] = {'error': str(e)}
    
    # ========================================================================
    # COMPARISON AND ANALYSIS
    # ========================================================================
    print("\n" + "=" * 80)
    print("EXPERIMENTAL COMPARISON SUMMARY")
    print("=" * 80)
    
    comparison = create_comparison(all_results)
    all_results['comparison'] = comparison
    
    print("\nAccuracy Comparison:")
    print(f"  Debate (Judge):         {comparison['accuracy']['debate_judge']:.2%}")
    print(f"  Debate (Jury):          {comparison['accuracy']['debate_jury']:.2%}")
    print(f"  Direct QA:              {comparison['accuracy']['direct_qa']:.2%}")
    print(f"  Self-Consistency:       {comparison['accuracy']['self_consistency']:.2%}")
    
    print(f"\nImprovement over baselines:")
    if comparison['accuracy']['direct_qa'] > 0:
        improvement = (comparison['accuracy']['debate_jury'] - comparison['accuracy']['direct_qa']) / comparison['accuracy']['direct_qa']
        print(f"  Debate vs Direct QA:    {improvement:+.2%}")
    
    if comparison['accuracy']['self_consistency'] > 0:
        improvement = (comparison['accuracy']['debate_jury'] - comparison['accuracy']['self_consistency']) / comparison['accuracy']['self_consistency']
        print(f"  Debate vs Self-Consistency: {improvement:+.2%}")
    
    print(f"\nComputational Cost (API calls):")
    print(f"  Debate:          {comparison['api_calls']['debate']}")
    print(f"  Direct QA:       {comparison['api_calls']['direct_qa']}")
    print(f"  Self-Consistency: {comparison['api_calls']['self_consistency']}")
    
    print(f"\nEfficiency (Accuracy per API call):")
    if comparison['api_calls']['debate'] > 0:
        print(f"  Debate:          {comparison['accuracy']['debate_jury'] / comparison['api_calls']['debate']:.4f}")
    if comparison['api_calls']['direct_qa'] > 0:
        print(f"  Direct QA:       {comparison['accuracy']['direct_qa'] / comparison['api_calls']['direct_qa']:.4f}")
    if comparison['api_calls']['self_consistency'] > 0:
        print(f"  Self-Consistency: {comparison['accuracy']['self_consistency'] / comparison['api_calls']['self_consistency']:.4f}")
    
    # ========================================================================
    # SAVE RESULTS
    # ========================================================================
    logger = DebateLogger(config)
    results_file = logger.save_results(
        all_results,
        f"experiment_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    
    print(f"\n{'=' * 80}")
    print(f"Results saved to: {results_file}")
    print("=" * 80)
    
    return all_results


def create_comparison(all_results: Dict[str, Any]) -> Dict[str, Any]:
    """Create comparison summary of all experiments."""
    comparison = {
        'accuracy': {},
        'api_calls': {},
        'summary': {}
    }
    
    # Extract accuracy metrics
    if 'debate' in all_results['experiments'] and 'error' not in all_results['experiments']['debate']:
        debate = all_results['experiments']['debate']
        comparison['accuracy']['debate_judge'] = debate.get('judge_accuracy', 0)
        comparison['accuracy']['debate_jury'] = debate.get('jury_accuracy', 0)
        comparison['api_calls']['debate'] = debate.get('api_calls', 0)
    
    if 'direct_qa' in all_results['experiments'] and 'error' not in all_results['experiments']['direct_qa']:
        direct_qa = all_results['experiments']['direct_qa']
        comparison['accuracy']['direct_qa'] = direct_qa.get('accuracy', 0)
        comparison['api_calls']['direct_qa'] = direct_qa.get('api_calls', 0)
    
    if 'self_consistency' in all_results['experiments'] and 'error' not in all_results['experiments']['self_consistency']:
        sc = all_results['experiments']['self_consistency']
        comparison['accuracy']['self_consistency'] = sc.get('accuracy', 0)
        comparison['api_calls']['self_consistency'] = sc.get('api_calls', 0)
    
    # Create summary
    comparison['summary'] = {
        'best_accuracy_method': max(
            comparison['accuracy'].items(), 
            key=lambda x: x[1]
        )[0] if comparison['accuracy'] else 'N/A',
        'best_accuracy': max(comparison['accuracy'].values()) if comparison['accuracy'] else 0
    }
    
    return comparison


def main():
    """Run experiments."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run debate system experiments')
    parser.add_argument('--num-questions', type=int, default=10,
                        help='Number of questions to test on (default: 10, use 100+ for paper)')
    parser.add_argument('--domain', type=str, default='commonsense_qa',
                        choices=['commonsense_qa', 'fact_verification'],
                        help='Dataset domain')
    
    args = parser.parse_args()
    
    try:
        results = run_experiments(args.num_questions, args.domain)
        
        print(f"\n✅ Experiments completed successfully!")
        print(f"Results file saved to: data/results/")
        
        return 0
    except Exception as e:
        print(f"\n❌ Experiment failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
