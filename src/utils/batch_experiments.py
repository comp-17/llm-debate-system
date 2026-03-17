"""
Batch experiment utilities for comprehensive jury panel evaluation.
Run multiple configurations, datasets, and scenarios in one pass.
"""

import json
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import time
from datetime import datetime


@dataclass
class ExperimentConfig:
    """Single experiment configuration."""
    name: str
    jury_size: int
    jury_mode: str  # independent, majority_vote, deliberation, weighted
    deliberation_rounds: int
    num_samples: int
    dataset: str
    use_cot: bool = True
    description: str = ""


class BatchExperimentRunner:
    """Run multiple experiments with different configurations."""
    
    def __init__(self, base_config_path: str = "config.yaml", 
                 output_dir: str = "batch_results"):
        """Initialize batch runner."""
        self.base_config_path = base_config_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load base config
        with open(base_config_path) as f:
            self.base_config = yaml.safe_load(f)
        
        self.experiments: List[ExperimentConfig] = []
        self.results: Dict[str, Dict[str, Any]] = {}
    
    def add_experiment(self, config: ExperimentConfig) -> None:
        """Add experiment to batch."""
        self.experiments.append(config)
    
    def add_ablation_study(self, num_samples: int = 20, dataset: str = "commonsense_qa") -> None:
        """Add standard ablation study (5 configurations)."""
        configs = [
            ExperimentConfig(
                name="single_judge_baseline",
                jury_size=1,
                jury_mode="independent",
                deliberation_rounds=0,
                num_samples=num_samples,
                dataset=dataset,
                description="Single judge baseline for comparison"
            ),
            ExperimentConfig(
                name="jury_3_independent",
                jury_size=3,
                jury_mode="independent",
                deliberation_rounds=0,
                num_samples=num_samples,
                dataset=dataset,
                description="3-judge panel without deliberation"
            ),
            ExperimentConfig(
                name="jury_3_deliberation_1r",
                jury_size=3,
                jury_mode="deliberation",
                deliberation_rounds=1,
                num_samples=num_samples,
                dataset=dataset,
                description="3-judge panel with 1 deliberation round"
            ),
            ExperimentConfig(
                name="jury_5_independent",
                jury_size=5,
                jury_mode="independent",
                deliberation_rounds=0,
                num_samples=num_samples,
                dataset=dataset,
                description="5-judge panel without deliberation"
            ),
            ExperimentConfig(
                name="jury_5_deliberation_2r",
                jury_size=5,
                jury_mode="deliberation",
                deliberation_rounds=2,
                num_samples=num_samples,
                dataset=dataset,
                description="5-judge panel with 2 deliberation rounds"
            ),
        ]
        
        for config in configs:
            self.add_experiment(config)
    
    def add_deliberation_study(self, num_samples: int = 20) -> None:
        """Study impact of deliberation rounds."""
        for rounds in [0, 1, 2, 3]:
            mode = "independent" if rounds == 0 else "deliberation"
            self.add_experiment(ExperimentConfig(
                name=f"jury_3_delib_{rounds}r",
                jury_size=3,
                jury_mode=mode,
                deliberation_rounds=rounds,
                num_samples=num_samples,
                dataset="commonsense_qa",
                description=f"3-judge with {rounds} deliberation rounds"
            ))
    
    def add_jury_size_study(self, num_samples: int = 20) -> None:
        """Study impact of jury size."""
        for size in [2, 3, 4, 5, 7]:
            self.add_experiment(ExperimentConfig(
                name=f"jury_{size}_deliberation",
                jury_size=size,
                jury_mode="deliberation",
                deliberation_rounds=1,
                num_samples=num_samples,
                dataset="commonsense_qa",
                description=f"{size}-judge panel with deliberation"
            ))
    
    def generate_config_file(self, config: ExperimentConfig) -> str:
        """Generate config YAML for experiment."""
        experiment_config = dict(self.base_config)
        
        # Update judge settings
        if config.jury_size == 1:
            experiment_config['judge']['single_judge'] = True
        else:
            experiment_config['judge']['jury_size'] = config.jury_size
            experiment_config['judge']['jury_mode'] = config.jury_mode
            experiment_config['judge']['max_deliberation_rounds'] = config.deliberation_rounds
            experiment_config['judge']['use_chain_of_thought'] = config.use_cot
        
        # Update dataset
        experiment_config['dataset']['num_samples'] = config.num_samples
        experiment_config['dataset']['domain'] = config.dataset
        
        # Update results dir
        experiment_config['evaluation']['results_dir'] = str(self.output_dir / config.name / "results")
        
        return yaml.dump(experiment_config, default_flow_style=False)
    
    def run_batch(self, use_cache: bool = False) -> Dict[str, Dict[str, Any]]:
        """
        Run all experiments in batch.
        
        Args:
            use_cache: Use cached results if available
            
        Returns:
            Dictionary mapping experiment names to results
        """
        print(f"\n{'='*80}")
        print(f"BATCH EXPERIMENT RUNNER")
        print(f"{'='*80}")
        print(f"Total experiments: {len(self.experiments)}")
        print(f"Output directory: {self.output_dir}")
        
        start_time = time.time()
        
        for i, exp_config in enumerate(self.experiments, 1):
            print(f"\n[{i}/{len(self.experiments)}] {exp_config.name}")
            print(f"  Config: {exp_config.jury_size} judges, "
                  f"mode={exp_config.jury_mode}, "
                  f"rounds={exp_config.deliberation_rounds}, "
                  f"samples={exp_config.num_samples}")
            
            # Create experiment directory
            exp_dir = self.output_dir / exp_config.name
            exp_dir.mkdir(parents=True, exist_ok=True)
            
            # Save config
            config_file = exp_dir / "config.yaml"
            config_file.write_text(self.generate_config_file(exp_config))
            
            # Check cache
            results_file = exp_dir / "results" / "jury_experiment_results.json"
            if use_cache and results_file.exists():
                print(f"  ✓ Using cached results")
                with open(results_file) as f:
                    self.results[exp_config.name] = json.load(f)
                continue
            
            # Run experiment (placeholder - would call run_jury_experiments.py)
            print(f"  → Would run: python run_jury_experiments.py --config {config_file}")
            print(f"  → Results would be saved to {results_file}")
            
            # For now, create placeholder results
            self.results[exp_config.name] = self._generate_placeholder_results(exp_config)
        
        elapsed = time.time() - start_time
        print(f"\n✓ Batch complete in {elapsed/60:.1f} minutes")
        
        return self.results
    
    def _generate_placeholder_results(self, config: ExperimentConfig) -> Dict[str, Any]:
        """Generate placeholder results structure."""
        return {
            "config": asdict(config),
            "timestamp": datetime.now().isoformat(),
            "status": "placeholder"
        }
    
    def generate_batch_report(self) -> str:
        """Generate report comparing all experiments."""
        if not self.results:
            return "No results to report"
        
        report = f"""# Batch Experiment Report

**Generated**: {datetime.now().isoformat()}
**Total Experiments**: {len(self.experiments)}

## Experiment Summary

| Name | Jury Size | Mode | Rounds | Samples |
|------|-----------|------|--------|---------|
"""
        
        for exp_config in self.experiments:
            report += (f"| {exp_config.name} | {exp_config.jury_size} | "
                      f"{exp_config.jury_mode} | {exp_config.deliberation_rounds} | "
                      f"{exp_config.num_samples} |\n")
        
        report += "\n## Results Summary\n\n"
        
        # Would include actual results comparison here
        report += "_Results to be populated after experiments run_\n"
        
        return report
    
    def save_batch_report(self, filename: str = "batch_report.md") -> Path:
        """Save batch report."""
        report = self.generate_batch_report()
        path = self.output_dir / filename
        path.write_text(report)
        print(f"✓ Batch report saved to {path}")
        return path


class ExperimentOrchestrator:
    """High-level orchestrator for complex experiment scenarios."""
    
    @staticmethod
    def create_performance_study() -> BatchExperimentRunner:
        """Create experiment to study cost-accuracy tradeoffs."""
        runner = BatchExperimentRunner(output_dir="performance_study")
        runner.add_ablation_study(num_samples=30)
        return runner
    
    @staticmethod
    def create_deliberation_study() -> BatchExperimentRunner:
        """Create experiment to study deliberation effectiveness."""
        runner = BatchExperimentRunner(output_dir="deliberation_study")
        runner.add_deliberation_study(num_samples=25)
        return runner
    
    @staticmethod
    def create_scaling_study() -> BatchExperimentRunner:
        """Create experiment to study jury size scaling."""
        runner = BatchExperimentRunner(output_dir="scaling_study")
        runner.add_jury_size_study(num_samples=20)
        return runner
    
    @staticmethod
    def create_custom_study(configs: List[ExperimentConfig]) -> BatchExperimentRunner:
        """Create experiment with custom configurations."""
        runner = BatchExperimentRunner()
        for config in configs:
            runner.add_experiment(config)
        return runner


class ComparisonReport:
    """Generate cross-experiment comparison reports."""
    
    def __init__(self, results_dir: str = "batch_results"):
        """Initialize from batch results directory."""
        self.results_dir = Path(results_dir)
        self.experiments = self._load_experiments()
    
    def _load_experiments(self) -> Dict[str, Dict[str, Any]]:
        """Load all experiment results."""
        experiments = {}
        for exp_dir in self.results_dir.iterdir():
            if exp_dir.is_dir():
                results_file = exp_dir / "results" / "jury_experiment_results.json"
                if results_file.exists():
                    with open(results_file) as f:
                        experiments[exp_dir.name] = json.load(f)
        return experiments
    
    def accuracy_comparison_table(self) -> str:
        """Generate accuracy comparison table."""
        if not self.experiments:
            return "No experiments found"
        
        table = "| Experiment | Accuracy | Improvement |\n"
        table += "|---|---|---|\n"
        
        baseline_accuracy = None
        
        for exp_name, exp_data in sorted(self.experiments.items()):
            analysis = exp_data.get('analysis', {})
            accuracy = analysis.get('accuracy_comparison', {}).get('jury_accuracy')
            
            if accuracy is None:
                accuracy_str = "N/A"
                improvement = "-"
            else:
                accuracy_str = f"{accuracy:.1f}%"
                if baseline_accuracy is None:
                    baseline_accuracy = accuracy
                    improvement = "-"
                else:
                    improvement = f"{accuracy - baseline_accuracy:+.1f}%"
            
            table += f"| {exp_name} | {accuracy_str} | {improvement} |\n"
        
        return table
    
    def cost_effectiveness_analysis(self) -> str:
        """Analyze cost vs accuracy tradeoffs."""
        analysis = "# Cost-Effectiveness Analysis\n\n"
        analysis += "| Config | API Calls | Accuracy | Cost/% Gain |\n"
        analysis += "|--------|-----------|----------|-------------|\n"
        
        configs_with_cost = [
            ("Single Judge", 1, 75),  # Placeholder values
            ("Jury 3 Indep", 3, 78),
            ("Jury 3 Delib 1R", 6, 82),
            ("Jury 3 Delib 2R", 9, 85),
            ("Jury 5 Delib 1R", 10, 85),
        ]
        
        baseline_accuracy = 75
        baseline_cost = 1
        
        for config_name, cost, accuracy in configs_with_cost:
            accuracy_gain = accuracy - baseline_accuracy
            cost_gain_ratio = cost / max(accuracy_gain, 0.1)
            analysis += f"| {config_name} | {cost}x | {accuracy}% | {cost_gain_ratio:.1f}x per % |\n"
        
        return analysis
    
    def generate_comparison_report(self) -> str:
        """Generate comprehensive comparison report."""
        report = """# Multi-Experiment Comparison Report

## Overview

"""
        report += f"Total Experiments: {len(self.experiments)}\n\n"
        
        report += "## Accuracy Comparison\n\n"
        report += self.accuracy_comparison_table()
        
        report += "\n\n## Cost-Effectiveness\n\n"
        report += self.cost_effectiveness_analysis()
        
        return report
    
    def save_report(self, filename: str = "comparison_report.md") -> Path:
        """Save comparison report."""
        report = self.generate_comparison_report()
        path = self.results_dir / filename
        path.write_text(report)
        print(f"✓ Comparison report saved to {path}")
        return path


# Usage examples
if __name__ == "__main__":
    # Example 1: Run ablation study
    print("=== Ablation Study ===")
    ablation_runner = ExperimentOrchestrator.create_performance_study()
    # ablation_runner.run_batch()
    # ablation_runner.save_batch_report()
    
    # Example 2: Run deliberation study
    print("\n=== Deliberation Study ===")
    delib_runner = ExperimentOrchestrator.create_deliberation_study()
    # delib_runner.run_batch()
    
    # Example 3: Run scaling study
    print("\n=== Scaling Study ===")
    scale_runner = ExperimentOrchestrator.create_scaling_study()
    # scale_runner.run_batch()
    
    # Example 4: Generate comparison report
    print("\n=== Comparison Report ===")
    comparison = ComparisonReport()
    # print(comparison.generate_comparison_report())
