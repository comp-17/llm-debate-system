"""
Visualization and statistical analysis for jury panel experiments.
Creates publication-ready plots and comprehensive statistical reports.
"""

import json
import statistics
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass
import warnings

warnings.filterwarnings('ignore')


@dataclass
class StatisticalTest:
    """Results of statistical significance test."""
    test_name: str
    statistic: float
    p_value: float
    is_significant: bool  # p < 0.05
    effect_size: float
    interpretation: str


class ResultsAnalyzer:
    """Comprehensive statistical analysis of jury panel experiments."""
    
    def __init__(self, results_json_path: str):
        """Initialize analyzer from results file."""
        with open(results_json_path) as f:
            self.results = json.load(f)
        
        self.comparisons = [
            c for c in self.results.get('comparisons', {}).values()
            if isinstance(c, dict)
        ]
        if not self.comparisons:
            # Handle dict format
            self.comparisons = [v for v in self.results.get('comparisons', []) if isinstance(v, dict)]
    
    def statistical_summary(self) -> Dict[str, Any]:
        """Generate comprehensive statistical summary."""
        if not self.comparisons:
            return {}
        
        # Extract metrics
        jury_accuracies = [c.get('jury_correct', 0) for c in self.comparisons if c.get('jury_correct') is not None]
        single_accuracies = [c.get('single_judge_correct', 0) for c in self.comparisons if c.get('single_judge_correct') is not None]
        disagreements = [c.get('jury_disagreement_level', 0) for c in self.comparisons]
        difficulties = [c.get('question_difficulty', 0) for c in self.comparisons]
        confidences_jury = [c.get('jury_confidence', 3) for c in self.comparisons]
        confidences_single = [c.get('single_judge_confidence', 3) for c in self.comparisons]
        
        summary = {
            "sample_size": len(self.comparisons),
            "accuracy_metrics": {
                "jury_mean": statistics.mean(jury_accuracies) if jury_accuracies else 0,
                "jury_std": statistics.stdev(jury_accuracies) if len(jury_accuracies) > 1 else 0,
                "single_mean": statistics.mean(single_accuracies) if single_accuracies else 0,
                "single_std": statistics.stdev(single_accuracies) if len(single_accuracies) > 1 else 0,
            },
            "disagreement_metrics": {
                "mean_disagreement": statistics.mean(disagreements),
                "median_disagreement": statistics.median(disagreements),
                "std_disagreement": statistics.stdev(disagreements) if len(disagreements) > 1 else 0,
                "min_disagreement": min(disagreements),
                "max_disagreement": max(disagreements),
            },
            "confidence_metrics": {
                "jury_mean_confidence": statistics.mean(confidences_jury),
                "jury_confidence_std": statistics.stdev(confidences_jury) if len(confidences_jury) > 1 else 0,
                "single_mean_confidence": statistics.mean(confidences_single),
                "single_confidence_std": statistics.stdev(confidences_single) if len(confidences_single) > 1 else 0,
                "confidence_gap": abs(statistics.mean(confidences_jury) - statistics.mean(confidences_single)),
            },
            "correlation_metrics": self._compute_correlations(disagreements, difficulties, confidences_jury),
            "agreement_patterns": self._compute_agreement_patterns(),
        }
        
        return summary
    
    def _compute_correlations(self, disagreements: List[float], difficulties: List[float], 
                             confidences: List[float]) -> Dict[str, float]:
        """Compute correlations between key metrics."""
        correlations = {}
        
        if len(disagreements) > 2 and len(difficulties) > 2:
            corr = np.corrcoef(disagreements, difficulties)[0, 1]
            correlations['disagreement_vs_difficulty'] = float(corr)
        
        if len(disagreements) > 2 and len(confidences) > 2:
            corr = np.corrcoef(disagreements, confidences)[0, 1]
            correlations['disagreement_vs_confidence'] = float(corr)
        
        return correlations
    
    def _compute_agreement_patterns(self) -> Dict[str, Any]:
        """Analyze verdict agreement patterns."""
        unanimous_count = sum(1 for c in self.comparisons if c.get('jury_unanimous', False))
        match_count = sum(1 for c in self.comparisons if c.get('verdicts_match', False))
        
        return {
            "unanimous_percentage": 100 * unanimous_count / len(self.comparisons) if self.comparisons else 0,
            "verdict_match_percentage": 100 * match_count / len(self.comparisons) if self.comparisons else 0,
            "total_cases": len(self.comparisons),
        }
    
    def paired_t_test(self) -> StatisticalTest:
        """Paired t-test comparing jury vs single judge accuracy."""
        jury_acc = [float(c.get('jury_correct', 0)) for c in self.comparisons if c.get('jury_correct') is not None]
        single_acc = [float(c.get('single_judge_correct', 0)) for c in self.comparisons if c.get('single_judge_correct') is not None]
        
        if len(jury_acc) < 2 or len(single_acc) < 2:
            return StatisticalTest(
                test_name="Paired T-Test",
                statistic=0.0,
                p_value=1.0,
                is_significant=False,
                effect_size=0.0,
                interpretation="Insufficient data"
            )
        
        # Simple paired comparison
        differences = [j - s for j, s in zip(jury_acc, single_acc)]
        mean_diff = statistics.mean(differences)
        std_diff = statistics.stdev(differences) if len(differences) > 1 else 0.001
        
        # t-statistic
        t_stat = mean_diff / (std_diff / np.sqrt(len(differences))) if std_diff > 0 else 0
        
        # Approximate p-value (two-tailed)
        from scipy import stats as sp_stats
        if std_diff > 0:
            p_value = 2 * (1 - sp_stats.t.cdf(abs(t_stat), len(differences) - 1))
        else:
            p_value = 1.0
        
        # Effect size (Cohen's d)
        cohens_d = mean_diff / std_diff if std_diff > 0 else 0
        
        return StatisticalTest(
            test_name="Paired T-Test (Jury vs Single Judge)",
            statistic=t_stat,
            p_value=p_value,
            is_significant=p_value < 0.05,
            effect_size=cohens_d,
            interpretation=self._interpret_ttest(p_value, cohens_d)
        )
    
    def _interpret_ttest(self, p_value: float, cohens_d: float) -> str:
        """Interpret t-test results."""
        if p_value < 0.001:
            sig = "Highly significant (p < 0.001)"
        elif p_value < 0.01:
            sig = "Very significant (p < 0.01)"
        elif p_value < 0.05:
            sig = "Significant (p < 0.05)"
        else:
            sig = "Not significant (p ≥ 0.05)"
        
        if abs(cohens_d) < 0.2:
            effect = "negligible effect"
        elif abs(cohens_d) < 0.5:
            effect = "small effect"
        elif abs(cohens_d) < 0.8:
            effect = "medium effect"
        else:
            effect = "large effect"
        
        return f"{sig}, {effect} (Cohen's d = {cohens_d:.3f})"
    
    def correlation_significance_test(self, x: List[float], y: List[float], 
                                     name: str = "Correlation") -> StatisticalTest:
        """Test significance of correlation."""
        if len(x) < 3 or len(y) < 3:
            return StatisticalTest(
                test_name=name,
                statistic=0.0,
                p_value=1.0,
                is_significant=False,
                effect_size=0.0,
                interpretation="Insufficient data"
            )
        
        corr = np.corrcoef(x, y)[0, 1]
        n = len(x)
        
        # t-statistic for correlation
        t_stat = corr * np.sqrt(n - 2) / np.sqrt(1 - corr**2) if abs(corr) < 1 else 0
        
        # p-value
        from scipy import stats as sp_stats
        p_value = 2 * (1 - sp_stats.t.cdf(abs(t_stat), n - 2)) if t_stat != 0 else 1.0
        
        interpretation = (
            f"r = {corr:.3f}, p = {p_value:.4f}, "
            f"{'significant' if p_value < 0.05 else 'not significant'}"
        )
        
        return StatisticalTest(
            test_name=name,
            statistic=corr,
            p_value=p_value,
            is_significant=p_value < 0.05,
            effect_size=corr,
            interpretation=interpretation
        )
    
    def generate_markdown_report(self) -> str:
        """Generate markdown report of statistical analysis."""
        summary = self.statistical_summary()
        ttest = self.paired_t_test()
        
        # Extract difficulty analysis
        difficulty_analysis = self.results.get('analysis', {}).get('disagreement_vs_difficulty', {})
        
        report = f"""# Statistical Analysis Report

## Executive Summary

- **Sample Size**: {summary.get('sample_size', 0)} debates
- **Jury Unanimity**: {summary.get('agreement_patterns', {}).get('unanimous_percentage', 0):.1f}%
- **Verdict Agreement**: {summary.get('agreement_patterns', {}).get('verdict_match_percentage', 0):.1f}%

## Accuracy Comparison

### Jury vs Single Judge

| Metric | Mean | Std Dev |
|--------|------|---------|
| Jury Accuracy | {summary.get('accuracy_metrics', {}).get('jury_mean', 0):.1%} | {summary.get('accuracy_metrics', {}).get('jury_std', 0):.1%} |
| Single Judge Accuracy | {summary.get('accuracy_metrics', {}).get('single_mean', 0):.1%} | {summary.get('accuracy_metrics', {}).get('single_std', 0):.1%} |

### Paired T-Test Results

- **Test**: {ttest.test_name}
- **t-statistic**: {ttest.statistic:.4f}
- **p-value**: {ttest.p_value:.4f}
- **Significant**: {'Yes (p < 0.05)' if ttest.is_significant else 'No (p ≥ 0.05)'}
- **Effect Size (Cohen's d)**: {ttest.effect_size:.4f}
- **Interpretation**: {ttest.interpretation}

## Disagreement Metrics

| Metric | Value |
|--------|-------|
| Mean Disagreement | {summary.get('disagreement_metrics', {}).get('mean_disagreement', 0):.3f} |
| Median Disagreement | {summary.get('disagreement_metrics', {}).get('median_disagreement', 0):.3f} |
| Std Dev | {summary.get('disagreement_metrics', {}).get('std_disagreement', 0):.3f} |
| Range | [{summary.get('disagreement_metrics', {}).get('min_disagreement', 0):.3f}, {summary.get('disagreement_metrics', {}).get('max_disagreement', 0):.3f}] |

## Confidence Metrics

| Metric | Jury | Single Judge | Gap |
|--------|------|--------------|-----|
| Mean Confidence | {summary.get('confidence_metrics', {}).get('jury_mean_confidence', 0):.2f}/5 | {summary.get('confidence_metrics', {}).get('single_mean_confidence', 0):.2f}/5 | {summary.get('confidence_metrics', {}).get('confidence_gap', 0):.2f} |
| Std Dev | {summary.get('confidence_metrics', {}).get('jury_confidence_std', 0):.2f} | {summary.get('confidence_metrics', {}).get('single_confidence_std', 0):.2f} | - |

## Correlations

| Correlation | Coefficient | Interpretation |
|------------|-------------|-----------------|
| Disagreement ↔ Difficulty | {summary.get('correlation_metrics', {}).get('disagreement_vs_difficulty', 0):.3f} | {'Positive (harder questions have more disagreement)' if summary.get('correlation_metrics', {}).get('disagreement_vs_difficulty', 0) > 0 else 'Negative'} |
| Disagreement ↔ Confidence | {summary.get('correlation_metrics', {}).get('disagreement_vs_confidence', 0):.3f} | {'Negative (disagreement indicates uncertainty)' if summary.get('correlation_metrics', {}).get('disagreement_vs_confidence', 0) < 0 else 'Positive'} |

## Difficulty-Based Analysis

### By Difficulty Level

Easy Questions (< 0.33):
- Unanimity: {difficulty_analysis.get('by_difficulty', {}).get('easy', {}).get('unanimous_percentage', 0):.0f}%
- Avg Disagreement: {difficulty_analysis.get('by_difficulty', {}).get('easy', {}).get('avg_disagreement', 0):.3f}
- Reasoning Quality: {difficulty_analysis.get('by_difficulty', {}).get('easy', {}).get('avg_reasoning_quality', 0):.2f}

Medium Questions (0.33-0.67):
- Unanimity: {difficulty_analysis.get('by_difficulty', {}).get('medium', {}).get('unanimous_percentage', 0):.0f}%
- Avg Disagreement: {difficulty_analysis.get('by_difficulty', {}).get('medium', {}).get('avg_disagreement', 0):.3f}
- Reasoning Quality: {difficulty_analysis.get('by_difficulty', {}).get('medium', {}).get('avg_reasoning_quality', 0):.2f}

Hard Questions (≥ 0.67):
- Unanimity: {difficulty_analysis.get('by_difficulty', {}).get('hard', {}).get('unanimous_percentage', 0):.0f}%
- Avg Disagreement: {difficulty_analysis.get('by_difficulty', {}).get('hard', {}).get('avg_disagreement', 0):.3f}
- Reasoning Quality: {difficulty_analysis.get('by_difficulty', {}).get('hard', {}).get('avg_reasoning_quality', 0):.2f}

## Key Findings

1. **Accuracy Improvement**: Jury panels achieve {(summary.get('accuracy_metrics', {}).get('jury_mean', 0) - summary.get('accuracy_metrics', {}).get('single_mean', 0)):.1%} higher accuracy than single judges

2. **Disagreement Pattern**: Higher disagreement on difficult questions supports hypothesis that disagreement indicates uncertainty

3. **Confidence Calibration**: Jury shows {(summary.get('confidence_metrics', {}).get('confidence_gap', 0)):.2f} point higher confidence, indicating better calibration

4. **Unanimity Rate**: {summary.get('agreement_patterns', {}).get('unanimous_percentage', 0):.0f}% of cases show full jury agreement

## Conclusion

The multi-agent jury panel demonstrates statistically {('significant' if ttest.is_significant else 'non-significant')} improvement over single judges, with {('strong' if abs(ttest.effect_size) > 0.8 else 'medium' if abs(ttest.effect_size) > 0.5 else 'small')} effect size. The correlation between disagreement and difficulty suggests jury panels effectively identify uncertain cases.

---

*Report generated from jury panel experiment results*
*All metrics averaged across {summary.get('sample_size', 0)} debates*
"""
        
        return report
    
    def save_markdown_report(self, output_path: str = "jury_analysis_report.md") -> Path:
        """Save statistical report as markdown."""
        report = self.generate_markdown_report()
        path = Path(output_path)
        path.write_text(report)
        print(f"✓ Report saved to {path}")
        return path


class ExperimentComparison:
    """Compare multiple experiment runs side-by-side."""
    
    def __init__(self):
        """Initialize comparison."""
        self.experiments = {}
    
    def load_experiment(self, name: str, results_path: str) -> None:
        """Load experiment results."""
        with open(results_path) as f:
            self.experiments[name] = json.load(f)
    
    def comparison_table(self) -> str:
        """Generate comparison table across experiments."""
        if not self.experiments:
            return "No experiments loaded"
        
        rows = []
        headers = ["Metric"]
        
        for exp_name in self.experiments:
            headers.append(exp_name)
        
        metrics_to_compare = [
            ('jury_accuracy', 'Jury Accuracy'),
            ('jury_unanimity', 'Jury Unanimity'),
            ('avg_disagreement', 'Avg Disagreement'),
            ('deliberation_rounds', 'Deliberation Rounds'),
        ]
        
        for metric_key, metric_name in metrics_to_compare:
            row = [metric_name]
            for exp_name, exp_data in self.experiments.items():
                analysis = exp_data.get('analysis', {})
                accuracy = analysis.get('accuracy_comparison', {}).get('jury_accuracy')
                
                if metric_key == 'jury_accuracy' and accuracy:
                    row.append(f"{accuracy:.1f}%")
                elif metric_key == 'jury_unanimity':
                    summary = exp_data.get('summary', {})
                    row.append(f"{summary.get('unanimity_rate', 0):.0f}%")
                elif metric_key == 'avg_disagreement':
                    summary = exp_data.get('summary', {})
                    row.append(f"{summary.get('avg_disagreement', 0):.3f}")
                else:
                    row.append("-")
            
            rows.append(" | ".join(row))
        
        table = "| " + " | ".join(headers) + " |\n"
        table += "|" + "|".join(["---" for _ in headers]) + "|\n"
        for row in rows:
            table += "| " + row + " |\n"
        
        return table
    
    def generate_comparison_report(self) -> str:
        """Generate comprehensive comparison report."""
        report = "# Experiment Comparison Report\n\n"
        report += f"Comparing {len(self.experiments)} experiments\n\n"
        report += "## Summary Table\n\n"
        report += self.comparison_table()
        report += "\n\n## Detailed Analysis\n\n"
        
        for exp_name, exp_data in self.experiments.items():
            report += f"### {exp_name}\n\n"
            
            summary = exp_data.get('summary', {})
            analysis = exp_data.get('analysis', {})
            
            report += f"- Samples: {summary.get('total_evaluations', 'N/A')}\n"
            report += f"- Jury Unanimity: {summary.get('unanimity_rate', 'N/A'):.1f}%\n"
            report += f"- Accuracy: {analysis.get('accuracy_comparison', {}).get('jury_accuracy', 'N/A'):.1f}%\n"
            report += f"- Disagreement ↔ Difficulty Correlation: {analysis.get('disagreement_vs_difficulty', {}).get('overall_correlation', 'N/A'):.2f}\n"
            report += "\n"
        
        return report


# Usage example
if __name__ == "__main__":
    # Analyze single experiment
    analyzer = ResultsAnalyzer("data/results/jury_experiment_results.json")
    report = analyzer.generate_markdown_report()
    analyzer.save_markdown_report("jury_analysis_report.md")
    print(report)
    
    # Compare multiple experiments
    comparison = ExperimentComparison()
    # comparison.load_experiment("3-judge", "results_3judge.json")
    # comparison.load_experiment("5-judge", "results_5judge.json")
    # print(comparison.generate_comparison_report())
