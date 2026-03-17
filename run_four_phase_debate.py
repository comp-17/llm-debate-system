#!/usr/bin/env python3
"""
Four-Phase Debate Pipeline Runner
Implements Irving et al. (2018) + Liang et al. (EMNLP 2024) protocol
"""

import json
import argparse
from pathlib import Path
from typing import List, Dict, Any

from src.orchestrator.four_phase_debate import FourPhaseDebateOrchestrator
from src.utils.api_client import APIClient


# ============================================================================
# SAMPLE QUESTIONS AND GROUND TRUTH
# ============================================================================

SAMPLE_QUESTIONS = [
    {
        "id": "q1",
        "question": "Is water wet?",
        "ground_truth": "Yes",
        "category": "basic"
    },
    {
        "id": "q2",
        "question": "Should artificial intelligence be heavily regulated by governments?",
        "ground_truth": "It depends on context, but yes some regulation is needed",
        "category": "policy"
    },
    {
        "id": "q3",
        "question": "Did humans land on the moon in 1969?",
        "ground_truth": "Yes",
        "category": "factual"
    },
    {
        "id": "q4",
        "question": "Is climate change primarily caused by human activity?",
        "ground_truth": "Yes",
        "category": "scientific"
    },
    {
        "id": "q5",
        "question": "Should social media companies be held responsible for user-generated content?",
        "ground_truth": "Arguably yes, with nuance",
        "category": "policy"
    },
]


# ============================================================================
# RESULTS STORAGE
# ============================================================================

def save_debate_result(result: Dict[str, Any], output_dir: Path) -> Path:
    """Save individual debate result to JSON"""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    result_path = output_dir / f"{result['debate_id']}.json"
    with open(result_path, 'w') as f:
        json.dump(result, f, indent=2)
    
    return result_path


def save_results_summary(results: List[Dict[str, Any]], output_dir: Path) -> Path:
    """Save summary of all results"""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    summary = {
        "total_debates": len(results),
        "timestamp": results[0]["timestamp"] if results else "",
        "results": results
    }
    
    summary_path = output_dir / "results_summary.json"
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)
    
    return summary_path


# ============================================================================
# STATISTICS
# ============================================================================

def compute_statistics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute statistics from debate results"""
    
    if not results:
        return {}
    
    correct_count = sum(1 for r in results if r.get('phase4', {}).get('verdict_correct'))
    total_with_truth = sum(1 for r in results if r.get('ground_truth') is not None)
    
    avg_rounds = sum(r['phase2']['actual_rounds'] for r in results) / len(results)
    avg_confidence = sum(r['phase3']['confidence'] for r in results) / len(results)
    
    early_stops = sum(1 for r in results if r['phase2']['stopped_early'])
    consensus_phase1 = sum(1 for r in results if r['phase1']['consensus'])
    
    stats = {
        'total_debates': len(results),
        'accuracy': correct_count / total_with_truth if total_with_truth > 0 else None,
        'correct_verdicts': correct_count,
        'total_with_ground_truth': total_with_truth,
        'avg_rounds_completed': avg_rounds,
        'avg_judge_confidence': avg_confidence,
        'early_stops_count': early_stops,
        'early_stop_rate': early_stops / len(results),
        'phase1_consensus_count': consensus_phase1,
        'phase1_consensus_rate': consensus_phase1 / len(results),
    }
    
    return stats


# ============================================================================
# MAIN RUNNER
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='Run 4-phase debate pipeline')
    parser.add_argument('--samples', type=int, default=3,
                       help='Number of debate samples to run')
    parser.add_argument('--min-rounds', type=int, default=3,
                       help='Minimum rounds before adaptive stopping applies')
    parser.add_argument('--max-rounds', type=int, default=8,
                       help='Maximum rounds regardless of convergence')
    parser.add_argument('--temperature', type=float, default=0.7,
                       help='Temperature for debater sampling')
    parser.add_argument('--output-dir', type=str, default='data/four_phase_results',
                       help='Output directory for results')
    parser.add_argument('--sample-seed', type=int, default=42,
                       help='Random seed for question sampling')
    
    args = parser.parse_args()
    
    # Initialize API client
    api_client = APIClient()
    
    # Initialize orchestrator
    orchestrator = FourPhaseDebateOrchestrator(
        api_client=api_client,
        min_rounds=args.min_rounds,
        max_rounds=args.max_rounds,
        temperature=args.temperature
    )
    
    # Run debates
    results = []
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n{'='*70}")
    print(f"FOUR-PHASE DEBATE PIPELINE")
    print(f"{'='*70}")
    print(f"Running {args.samples} debates")
    print(f"Min rounds: {args.min_rounds}, Max rounds: {args.max_rounds}")
    print(f"Output: {output_dir}")
    print(f"{'='*70}\n")
    
    for i in range(args.samples):
        # Select question
        question_data = SAMPLE_QUESTIONS[i % len(SAMPLE_QUESTIONS)]
        
        print(f"\n[{i+1}/{args.samples}] Running debate on: {question_data['question'][:60]}...")
        
        try:
            # Run debate
            result = orchestrator.run_debate(
                question=question_data['question'],
                ground_truth=question_data['ground_truth'],
                debate_id=f"debate_{i+1:03d}_{question_data['id']}"
            )
            
            # Save result
            result_dict = result.to_dict()
            results.append(result_dict)
            
            result_path = save_debate_result(result_dict, output_dir)
            print(f"✓ Saved: {result_path}")
            
            # Print summary
            print(f"  - Initial A: {result.initial_position_a.answer}")
            print(f"  - Initial B: {result.initial_position_b.answer}")
            print(f"  - Consensus: {result.phase1_consensus}")
            print(f"  - Rounds: {result.actual_rounds} (stopped early: {result.stopped_early})")
            print(f"  - Judge verdict: {result.judge_analysis.final_verdict}")
            print(f"  - Confidence: {result.judge_analysis.confidence}/5")
            if result.ground_truth:
                print(f"  - Verdict correct: {result.verdict_correct}")
            
        except Exception as e:
            print(f"✗ Error running debate: {e}")
    
    # Save all results
    print(f"\n{'='*70}")
    print("SAVING RESULTS")
    print(f"{'='*70}\n")
    
    summary_path = save_results_summary(results, output_dir)
    print(f"✓ Saved summary: {summary_path}")
    
    # Compute and print statistics
    stats = compute_statistics(results)
    
    print(f"\n{'='*70}")
    print("STATISTICS")
    print(f"{'='*70}")
    print(f"Total debates: {stats['total_debates']}")
    if stats['total_with_ground_truth'] > 0:
        print(f"Accuracy: {stats['accuracy']:.1%} ({stats['correct_verdicts']}/{stats['total_with_ground_truth']})")
    print(f"Average rounds: {stats['avg_rounds_completed']:.1f}")
    print(f"Average judge confidence: {stats['avg_judge_confidence']:.2f}/5")
    print(f"Early stops: {stats['early_stop_count']}/{stats['total_debates']} ({stats['early_stop_rate']:.1%})")
    print(f"Phase 1 consensus: {stats['phase1_consensus_count']}/{stats['total_debates']} ({stats['phase1_consensus_rate']:.1%})")
    print(f"{'='*70}\n")
    
    # Save statistics
    stats_path = output_dir / "statistics.json"
    with open(stats_path, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"✓ Saved statistics: {stats_path}\n")
    
    return 0


if __name__ == '__main__':
    exit(main())
