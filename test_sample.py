#!/usr/bin/env python3
"""
Sample test script demonstrating how to use the LLM Debate System.
Run with: python test_sample.py
"""

import sys
from src.utils.utils import load_config, DebateDataset, DebateLogger
from src.orchestrator.debate_orchestrator import DebateOrchestrator
from src.utils.evaluation import DebateEvaluator

def test_single_debate():
    """Test a single debate."""
    print("\n" + "="*80)
    print("TEST 1: Single Debate with Custom Question")
    print("="*80)
    
    config = load_config("config.yaml")
    orchestrator = DebateOrchestrator(config)
    
    result = orchestrator.run_debate(
        question="Did the Roman Empire exist at the same time as the Mayan civilization?",
        question_id="test_custom_001",
        ground_truth="Yes"
    )
    
    print("\nResult Summary:")
    print(f"  Question: {result['question']}")
    print(f"  Debater A final position: {result['debater_a_final_position']}")
    print(f"  Debater B final position: {result['debater_b_final_position']}")
    print(f"  Rounds completed: {result['rounds_completed']}")
    print(f"  Ground truth: {result['ground_truth']}")
    
    if 'judge_verdict' in result:
        print(f"  Judge winner: {result['judge_verdict']['winner']}")
        print(f"  Judge confidence: {result['judge_verdict']['confidence']}")
    
    if 'jury_results' in result:
        consensus = result['jury_results']['consensus']
        print(f"  Jury consensus: {consensus['winner']}")
        print(f"  Jury confidence: {consensus['confidence']}")
        
        # Show jury member breakdown
        verdicts = result['jury_results']['individual_verdicts']
        print(f"  Jury breakdown: {[v['winner'] for v in verdicts]}")
    
    return result

def test_batch_debates():
    """Test batch debate processing."""
    print("\n" + "="*80)
    print("TEST 2: Batch Debates (3 questions)")
    print("="*80)
    
    config = load_config("config.yaml")
    config['dataset']['num_samples'] = 3  # Reduce for quick test
    
    orchestrator = DebateOrchestrator(config)
    dataset = DebateDataset.load_dataset(
        config['dataset']['domain'],
        num_samples=3
    )
    
    print(f"\nRunning {len(dataset)} debates...")
    results = orchestrator.run_batch(dataset)
    
    print(f"\nBatch Results:")
    print(f"  Total debates: {len(results)}")
    print(f"  Successful: {sum(1 for r in results if 'error' not in r)}")
    print(f"  Failed: {sum(1 for r in results if 'error' in r)}")
    
    return results

def test_evaluation():
    """Test evaluation metrics."""
    print("\n" + "="*80)
    print("TEST 3: Evaluation & Metrics")
    print("="*80)
    
    config = load_config("config.yaml")
    config['dataset']['num_samples'] = 5  # Quick test
    
    orchestrator = DebateOrchestrator(config)
    dataset = DebateDataset.load_dataset(
        config['dataset']['domain'],
        num_samples=5
    )
    
    print(f"\nRunning evaluation on {len(dataset)} debates...")
    results = orchestrator.run_batch(dataset)
    
    # Generate evaluation report
    report = DebateEvaluator.generate_report(results)
    
    print("\nEvaluation Results:")
    print(f"  Total debates: {report['summary']['total_debates']}")
    print(f"  Successful: {report['summary']['successful']}")
    
    print(f"\nAccuracy Metrics:")
    print(f"  Judge accuracy: {report['accuracy_metrics']['judge_accuracy']:.2%}")
    print(f"  Jury accuracy: {report['accuracy_metrics']['jury_accuracy']:.2%}")
    
    print(f"\nJudge-Jury Agreement:")
    print(f"  Agreement rate: {report['judge_agreement']['agreement_rate']:.2%}")
    print(f"  Cases compared: {report['judge_agreement']['cases_compared']}")
    
    print(f"\nJury Disagreement Analysis (BONUS):")
    disagreement = report['jury_disagreement_analysis']
    print(f"  Total debates: {disagreement['total_debates']}")
    print(f"  Unanimous verdicts: {disagreement['unanimous_verdicts']}")
    print(f"  Split verdicts: {disagreement['split_verdicts']}")
    print(f"  Avg member agreement: {disagreement['average_member_agreement']:.2%}")
    
    # Show disagreement cases
    if disagreement['disagreement_cases']:
        print(f"\nSample Disagreement Case:")
        case = disagreement['disagreement_cases'][0]
        print(f"  Question: {case['question'][:80]}...")
        print(f"  Member verdicts: {case['member_verdicts']}")
        print(f"  Consensus: {case['consensus']}")
    
    return results, report

def test_jury_panel_bonus():
    """Test jury panel bonus feature specifically."""
    print("\n" + "="*80)
    print("TEST 4: BONUS - Jury Panel Analysis")
    print("="*80)
    
    config = load_config("config.yaml")
    config['judge']['jury_size'] = 5  # Test with larger panel
    config['dataset']['num_samples'] = 3
    
    orchestrator = DebateOrchestrator(config)
    dataset = DebateDataset.load_dataset(
        config['dataset']['domain'],
        num_samples=3
    )
    
    print(f"\nTesting jury panel with size = {config['judge']['jury_size']}...")
    results = orchestrator.run_batch(dataset)
    
    report = DebateEvaluator.generate_report(results)
    
    print(f"\nJury Panel Results (Size = {config['judge']['jury_size']}):")
    disagreement = report['jury_disagreement_analysis']
    
    print(f"  Average member agreement: {disagreement['average_member_agreement']:.2%}")
    print(f"  Unanimous: {disagreement['unanimous_verdicts']}/{disagreement['total_debates']}")
    print(f"  Split: {disagreement['split_verdicts']}/{disagreement['total_debates']}")
    
    # Analyze how panel size affects agreement
    print(f"\n  Note: Larger panels (5+) may show more diverse reasoning")
    print(f"  but converge to same consensus due to diversity benefits")
    
    return results, report

def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("LLM DEBATE SYSTEM - SAMPLE TEST SUITE")
    print("="*80)
    
    try:
        # Test 1: Single debate
        test_single_debate()
        
        # Test 2: Batch debates
        test_batch_debates()
        
        # Test 3: Evaluation
        test_evaluation()
        
        # Test 4: Jury panel bonus
        test_jury_panel_bonus()
        
        print("\n" + "="*80)
        print("✅ ALL TESTS COMPLETED SUCCESSFULLY")
        print("="*80)
        print("\nNext steps:")
        print("  1. Review debate transcripts in logs/transcripts/")
        print("  2. Check results in data/results/")
        print("  3. Read BLOG_POST.md for detailed analysis")
        print("  4. Run 'python web_ui.py' for interactive exploration")
        print("  5. Scale up with config.yaml dataset.num_samples: 100+")
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
