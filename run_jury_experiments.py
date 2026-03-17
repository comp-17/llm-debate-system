#!/usr/bin/env python3
"""
Comprehensive experiment runner: Debate System with Jury Panel Evaluation.

Runs debates and evaluates verdicts using:
1. Single Judge (baseline)
2. Jury Panel with Independent evaluation
3. Jury Panel with Deliberation
4. Compares accuracies and analyzes disagreement vs difficulty

Inspired by:
- Irving et al. (2018): AI Safety via Debate
- Kalra et al. (2025): VERDICT library for judge-time compute
- Kenton et al. (2024): Weak LLM judges on strong LLMs
- Wang et al. (2023): Self-Consistency in Chain-of-Thought
"""

import json
import yaml
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional
import statistics

# Local imports
from src.agents.debaters import DebaterA, DebaterB
from src.agents.judges import JudgeSingle, JuryPanel
from src.agents.jury_panel import EnhancedJuryPanel, JuryMode
from src.orchestrator.debate_orchestrator import DebateOrchestrator
from src.utils.api_client import APIClient
from src.utils.evaluation import Evaluator
from src.utils.jury_evaluation import JuryEvaluationFramework, QuestionDifficultyEstimator
from src.utils.utils import load_config, save_json, load_dataset


class ComprehensiveJuryExperiment:
    """Run comprehensive jury panel experiments with detailed analysis."""
    
    def __init__(self, config_path: str = "config.yaml"):
        """Initialize experiment with configuration."""
        self.config = load_config(config_path)
        self.api_client = APIClient(
            model=self.config['model']['name'],
            temperature=self.config['model']['temperature'],
            max_tokens=self.config['model']['max_tokens']
        )
        self.results = {
            "config": self.config,
            "experiments": {}
        }
    
    def run_full_experiment(self, num_samples: Optional[int] = None) -> Dict[str, Any]:
        """
        Run comprehensive experiment comparing single judge vs jury panels.
        
        Experiment setup:
        1. Load dataset
        2. For each question:
           a. Run single judge
           b. Run jury (independent)
           c. Run jury (deliberation)
           d. Compare and analyze
        3. Aggregate results and save
        """
        # Get dataset
        dataset = load_dataset(
            self.config['dataset']['domain'],
            num_samples=num_samples or self.config['dataset']['num_samples'],
            seed=self.config['dataset']['sample_seed']
        )
        
        print(f"\n{'='*80}")
        print(f"COMPREHENSIVE JURY PANEL EXPERIMENT")
        print(f"{'='*80}")
        print(f"Dataset: {self.config['dataset']['domain']}")
        print(f"Samples: {len(dataset)}")
        print(f"Jury Size: {self.config['judge']['jury_size']}")
        print(f"Jury Mode: {self.config['judge']['jury_mode']}")
        
        # Initialize components
        judge_single = JudgeSingle(self.api_client)
        jury_independent = EnhancedJuryPanel(
            self.api_client,
            jury_size=self.config['judge']['jury_size'],
            mode=JuryMode.INDEPENDENT,
            use_chain_of_thought=True
        )
        jury_deliberation = EnhancedJuryPanel(
            self.api_client,
            jury_size=self.config['judge']['jury_size'],
            mode=JuryMode.DELIBERATION,
            max_deliberation_rounds=2,
            use_chain_of_thought=True
        )
        
        # Initialize evaluation framework
        evaluator = JuryEvaluationFramework(
            results_dir=self.config['evaluation']['results_dir']
        )
        
        # Run debates and evaluate
        debate_count = 0
        for item in dataset:
            try:
                debate_count += 1
                print(f"\n[{debate_count}/{len(dataset)}] Processing...")
                
                question = item['question']
                ground_truth = item.get('ground_truth')
                question_id = item.get('id', f"q_{debate_count}")
                
                # Run debate
                orchestrator = DebateOrchestrator(self.api_client, self.config)
                debate_result = orchestrator.orchestrate_debate(question)
                
                # Evaluate with single judge
                single_result = judge_single.evaluate(
                    question,
                    debate_result['debater_a_final_answer'],
                    debate_result['debater_b_final_answer'],
                    debate_result['transcript']
                )
                
                # Evaluate with jury (independent)
                jury_indep_result = jury_independent.evaluate(
                    question,
                    debate_result['debater_a_final_answer'],
                    debate_result['debater_b_final_answer'],
                    debate_result['transcript']
                )
                
                # Evaluate with jury (deliberation)
                jury_delib_result = jury_deliberation.evaluate(
                    question,
                    debate_result['debater_a_final_answer'],
                    debate_result['debater_b_final_answer'],
                    debate_result['transcript']
                )
                
                # Compare
                _, _, comparison = evaluator.evaluate_debate(
                    judge_single,
                    jury_deliberation,
                    question,
                    debate_result['debater_a_final_answer'],
                    debate_result['debater_b_final_answer'],
                    debate_result['transcript'],
                    ground_truth=ground_truth,
                    question_id=question_id
                )
                
                self.results["experiments"][question_id] = {
                    "question": question,
                    "ground_truth": ground_truth,
                    "debate": debate_result,
                    "single_judge": single_result,
                    "jury_independent": jury_indep_result,
                    "jury_deliberation": jury_delib_result,
                    "comparison": comparison.to_dict()
                }
                
            except Exception as e:
                print(f"  ERROR: {e}")
                continue
        
        # Aggregate results
        self.results["aggregated_analysis"] = self._aggregate_analysis(evaluator)
        
        # Save results
        results_file = self._save_results()
        print(f"\n✓ Results saved to {results_file}")
        
        # Print summary
        evaluator.print_summary()
        
        return self.results
    
    def _aggregate_analysis(self, evaluator: JuryEvaluationFramework) -> Dict[str, Any]:
        """Aggregate all analysis results."""
        return {
            "accuracy_comparison": evaluator.analyze_accuracy_comparison(),
            "disagreement_vs_difficulty": evaluator.analyze_disagreement_vs_difficulty(),
            "deliberation_impact": evaluator.analyze_deliberation_impact(),
            "disagreement_as_uncertainty": evaluator.analyze_disagreement_as_uncertainty()
        }
    
    def _save_results(self) -> Path:
        """Save comprehensive results to JSON."""
        results_dir = Path(self.config['evaluation']['results_dir'])
        results_dir.mkdir(parents=True, exist_ok=True)
        
        results_file = results_dir / "jury_experiment_results.json"
        save_json(self.results, results_file)
        
        return results_file
    
    def run_ablation_study(self) -> Dict[str, Any]:
        """
        Run ablation study comparing different jury configurations:
        1. Single Judge
        2. Jury (3 members, independent)
        3. Jury (3 members, deliberation)
        4. Jury (5 members, independent)
        5. Jury (5 members, deliberation)
        """
        print(f"\n{'='*80}")
        print(f"JURY PANEL ABLATION STUDY")
        print(f"{'='*80}")
        
        ablation_results = {}
        
        # Load small dataset for ablation
        dataset = load_dataset(
            self.config['dataset']['domain'],
            num_samples=min(10, self.config['dataset']['num_samples']),
            seed=self.config['dataset']['sample_seed']
        )
        
        configurations = [
            ("single_judge", None, None),
            ("jury_3_independent", 3, JuryMode.INDEPENDENT),
            ("jury_3_deliberation", 3, JuryMode.DELIBERATION),
            ("jury_5_independent", 5, JuryMode.INDEPENDENT),
            ("jury_5_deliberation", 5, JuryMode.DELIBERATION),
        ]
        
        for config_name, jury_size, jury_mode in configurations:
            print(f"\n[{config_name}]")
            
            results = []
            for i, item in enumerate(dataset[:3]):  # Quick test with 3 samples
                question = item['question']
                ground_truth = item.get('ground_truth')
                
                # Run debate
                orchestrator = DebateOrchestrator(self.api_client, self.config)
                debate_result = orchestrator.orchestrate_debate(question)
                
                if jury_size is None:
                    # Single judge
                    judge = JudgeSingle(self.api_client)
                    result = judge.evaluate(
                        question,
                        debate_result['debater_a_final_answer'],
                        debate_result['debater_b_final_answer'],
                        debate_result['transcript']
                    )
                    results.append({
                        "winner": result.get('winner'),
                        "correct": result.get('winner') == ground_truth if ground_truth else None
                    })
                else:
                    # Jury panel
                    jury = EnhancedJuryPanel(
                        self.api_client,
                        jury_size=jury_size,
                        mode=jury_mode,
                        use_chain_of_thought=True
                    )
                    result = jury.evaluate(
                        question,
                        debate_result['debater_a_final_answer'],
                        debate_result['debater_b_final_answer'],
                        debate_result['transcript']
                    )
                    results.append({
                        "winner": result['final_consensus']['winner'],
                        "unanimous": result['disagreement_metrics']['unanimous'],
                        "disagreement": result['disagreement_metrics']['disagreement_level'],
                        "reasoning_quality": result['avg_reasoning_quality'],
                        "correct": result['final_consensus']['winner'] == ground_truth if ground_truth else None
                    })
            
            # Aggregate
            ablation_results[config_name] = {
                "avg_correct": statistics.mean([r.get('correct') or 0 for r in results]),
                "num_samples": len(results),
                "details": results
            }
        
        return ablation_results


def main():
    """Main entry point for jury panel experiments."""
    parser = argparse.ArgumentParser(
        description="Run comprehensive jury panel evaluation experiment"
    )
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--samples", type=int, help="Number of samples (overrides config)")
    parser.add_argument("--ablation", action="store_true", help="Run ablation study")
    parser.add_argument("--output", default="results", help="Output directory")
    
    args = parser.parse_args()
    
    # Create experiment
    experiment = ComprehensiveJuryExperiment(config_path=args.config)
    
    if args.ablation:
        # Run ablation study
        ablation_results = experiment.run_ablation_study()
        save_json(ablation_results, Path(args.output) / "ablation_results.json")
    else:
        # Run full experiment
        experiment.run_full_experiment(num_samples=args.samples)


if __name__ == "__main__":
    main()
