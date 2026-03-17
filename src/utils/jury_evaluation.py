"""
Comprehensive jury panel evaluation with single-judge comparison and difficulty analysis.
Implements metrics from VERDICT (Kalra et al., 2025), Kenton et al. (2024), and Wang et al. (2023).
"""

import json
import statistics
from typing import Dict, List, Any, Tuple, Optional
from pathlib import Path
from dataclasses import dataclass, asdict
import numpy as np

from src.agents.jury_panel import EnhancedJuryPanel, JuryMode, DisagreementMetrics
from src.agents.judges import JudgeSingle


@dataclass
class JuryComparison:
    """Comparison metrics between jury and single judge."""
    question_id: str
    question_text: str
    question_difficulty: float
    ground_truth: Optional[str]
    
    # Single Judge
    single_judge_winner: str
    single_judge_confidence: int
    single_judge_correct: bool
    
    # Jury
    jury_size: int
    jury_mode: str
    jury_winner: str
    jury_confidence: float
    jury_correct: bool
    jury_unanimous: bool
    jury_disagreement_level: float
    jury_avg_reasoning_quality: float
    jury_deliberation_rounds: int
    
    # Comparison
    verdicts_match: bool
    confidence_gap: float
    jury_advantage: bool  # Jury more accurate
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class QuestionDifficultyEstimator:
    """Estimate question difficulty based on multiple factors."""
    
    @staticmethod
    def estimate(question: str, question_type: str = "general") -> float:
        """
        Estimate question difficulty (0-1 scale).
        
        Factors:
        - Word count (longer = potentially harder)
        - Number of entities/relations
        - Presence of negation
        - Temporal reasoning required
        - Numerical reasoning
        """
        difficulty = 0.3  # Base difficulty
        
        # Length factor (0-0.2)
        word_count = len(question.split())
        if word_count > 50:
            difficulty += 0.15
        elif word_count > 30:
            difficulty += 0.10
        elif word_count > 20:
            difficulty += 0.05
        
        # Negation (adds 0.15)
        if any(word in question.lower() for word in ["not", "no", "never", "neither"]):
            difficulty += 0.15
        
        # Temporal reasoning (adds 0.1)
        if any(word in question.lower() for word in ["before", "after", "during", "when", "first", "then"]):
            difficulty += 0.1
        
        # Numerical reasoning (adds 0.1)
        if any(char.isdigit() for char in question):
            difficulty += 0.1
        
        # Conditional statements (adds 0.1)
        if any(word in question.lower() for word in ["if", "assuming", "suppose", "given"]):
            difficulty += 0.1
        
        return min(difficulty, 1.0)


class JuryEvaluationFramework:
    """
    Comprehensive framework for evaluating jury panel vs single judge.
    Inspired by VERDICT (Kalra et al., 2025), which uses modular units and verification patterns.
    """
    
    def __init__(self, results_dir: str = "data/results/jury_analysis"):
        """Initialize evaluation framework."""
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.comparisons: List[JuryComparison] = []
        self.difficulty_estimator = QuestionDifficultyEstimator()
    
    def evaluate_debate(
        self,
        single_judge: JudgeSingle,
        jury_panel: EnhancedJuryPanel,
        question: str,
        debater_a_position: str,
        debater_b_position: str,
        debate_transcript: str,
        ground_truth: Optional[str] = None,
        question_id: Optional[str] = None
    ) -> Tuple[Dict[str, Any], Dict[str, Any], JuryComparison]:
        """
        Run both single judge and jury panel on the same debate.
        
        Returns:
            (single_judge_result, jury_result, comparison_metrics)
        """
        question_id = question_id or f"q_{len(self.comparisons)}"
        difficulty = self.difficulty_estimator.estimate(question)
        
        print(f"\n{'='*80}")
        print(f"EVALUATING: {question_id}")
        print(f"Difficulty: {difficulty:.2f}")
        print(f"{'='*80}")
        
        # Single Judge Evaluation
        print("\n[SINGLE JUDGE]")
        single_result = single_judge.evaluate(
            question, debater_a_position, debater_b_position, debate_transcript
        )
        
        # Jury Panel Evaluation
        print("\n[JURY PANEL]")
        jury_result = jury_panel.evaluate(
            question, debater_a_position, debater_b_position, debate_transcript,
            question_difficulty=difficulty
        )
        
        # Build comparison
        comparison = self._build_comparison(
            question_id, question, difficulty, ground_truth,
            single_result, jury_result
        )
        
        self.comparisons.append(comparison)
        
        return single_result, jury_result, comparison
    
    def _build_comparison(
        self,
        question_id: str,
        question: str,
        difficulty: float,
        ground_truth: Optional[str],
        single_result: Dict[str, Any],
        jury_result: Dict[str, Any]
    ) -> JuryComparison:
        """Build comparison metrics."""
        single_winner = single_result.get("winner")
        single_confidence = single_result.get("confidence") or 3
        jury_winner = jury_result["final_consensus"]["winner"]
        jury_confidence = jury_result["final_consensus"].get("confidence") or 3
        
        # Check correctness if ground truth available
        single_correct = (single_winner == ground_truth) if ground_truth else None
        jury_correct = (jury_winner == ground_truth) if ground_truth else None
        
        # Extract metrics
        disagreement_metrics = jury_result["disagreement_metrics"]
        
        return JuryComparison(
            question_id=question_id,
            question_text=question,
            question_difficulty=difficulty,
            ground_truth=ground_truth,
            single_judge_winner=single_winner,
            single_judge_confidence=int(single_confidence) if isinstance(single_confidence, (int, float)) else 3,
            single_judge_correct=single_correct,
            jury_size=jury_result["jury_size"],
            jury_mode=jury_result["mode"],
            jury_winner=jury_winner,
            jury_confidence=float(jury_confidence),
            jury_correct=jury_correct,
            jury_unanimous=disagreement_metrics["unanimous"],
            jury_disagreement_level=disagreement_metrics["disagreement_level"],
            jury_avg_reasoning_quality=jury_result["avg_reasoning_quality"],
            jury_deliberation_rounds=len(jury_result["deliberation_outcomes"]),
            verdicts_match=(single_winner == jury_winner),
            confidence_gap=abs(single_confidence - jury_confidence),
            jury_advantage=jury_correct and not single_correct if (jury_correct and single_correct is not None) else None
        )
    
    def analyze_disagreement_vs_difficulty(self) -> Dict[str, Any]:
        """
        Analyze correlation between jury disagreement and question difficulty.
        
        Returns:
            Correlation analysis and grouped statistics
        """
        if not self.comparisons:
            return {}
        
        difficulties = [c.question_difficulty for c in self.comparisons]
        disagreements = [c.jury_disagreement_level for c in self.comparisons]
        
        # Compute correlation
        if len(difficulties) > 2:
            correlation = np.corrcoef(difficulties, disagreements)[0, 1]
        else:
            correlation = 0.0
        
        # Group by difficulty
        easy = [c for c in self.comparisons if c.question_difficulty < 0.33]
        medium = [c for c in self.comparisons if 0.33 <= c.question_difficulty < 0.67]
        hard = [c for c in self.comparisons if c.question_difficulty >= 0.67]
        
        return {
            "overall_correlation": float(correlation),
            "by_difficulty": {
                "easy": self._difficulty_group_stats(easy),
                "medium": self._difficulty_group_stats(medium),
                "hard": self._difficulty_group_stats(hard)
            },
            "key_findings": self._extract_difficulty_findings(easy, medium, hard)
        }
    
    def _difficulty_group_stats(self, comparisons: List[JuryComparison]) -> Dict[str, Any]:
        """Compute statistics for a group of comparisons."""
        if not comparisons:
            return {"count": 0}
        
        disagreements = [c.jury_disagreement_level for c in comparisons]
        reasoning_qualities = [c.jury_avg_reasoning_quality for c in comparisons]
        unanimities = [c.jury_unanimous for c in comparisons]
        
        return {
            "count": len(comparisons),
            "avg_difficulty": statistics.mean([c.question_difficulty for c in comparisons]),
            "avg_disagreement": statistics.mean(disagreements),
            "median_disagreement": statistics.median(disagreements),
            "unanimous_percentage": 100 * sum(unanimities) / len(unanimities),
            "avg_reasoning_quality": statistics.mean(reasoning_qualities),
            "verdict_matches_single_judge": 100 * sum(1 for c in comparisons if c.verdicts_match) / len(comparisons)
        }
    
    def _extract_difficulty_findings(self, easy, medium, hard) -> List[str]:
        """Extract key findings about difficulty correlation."""
        findings = []
        
        if easy:
            easy_agreement = statistics.mean([1 if c.jury_unanimous else 0 for c in easy])
            findings.append(f"Easy questions: {easy_agreement:.0%} jury unanimity")
        
        if hard:
            hard_agreement = statistics.mean([1 if c.jury_unanimous else 0 for c in hard])
            hard_disagreement = statistics.mean([c.jury_disagreement_level for c in hard])
            findings.append(
                f"Hard questions: {hard_agreement:.0%} unanimity, "
                f"avg disagreement level {hard_disagreement:.2f}"
            )
        
        return findings
    
    def analyze_deliberation_impact(self) -> Dict[str, Any]:
        """
        Analyze whether deliberation improves consensus quality.
        
        Returns:
            Deliberation impact metrics
        """
        results = {
            "total_evaluations": len(self.comparisons),
            "by_deliberation_rounds": {}
        }
        
        # Group by deliberation rounds
        for num_rounds in [0, 1, 2, 3, 4]:
            group = [c for c in self.comparisons if c.jury_deliberation_rounds == num_rounds]
            if group:
                results["by_deliberation_rounds"][num_rounds] = {
                    "count": len(group),
                    "avg_disagreement_reduction": self._avg_disagreement(group),
                    "unanimity_rate": 100 * sum(1 for c in group if c.jury_unanimous) / len(group),
                    "avg_confidence": statistics.mean([c.jury_confidence for c in group]),
                    "accuracy": 100 * sum(1 for c in group if c.jury_correct) / len(group) if any(c.jury_correct for c in group) else None
                }
        
        return results
    
    def _avg_disagreement(self, comparisons: List[JuryComparison]) -> float:
        """Average disagreement for group."""
        if not comparisons:
            return 0.0
        return statistics.mean([c.jury_disagreement_level for c in comparisons])
    
    def analyze_accuracy_comparison(self) -> Dict[str, Any]:
        """
        Compare accuracy: single judge vs jury panel.
        Only runs on cases with ground truth.
        """
        with_truth = [c for c in self.comparisons if c.ground_truth is not None]
        
        if not with_truth:
            return {"error": "No comparisons with ground truth available"}
        
        single_correct = sum(1 for c in with_truth if c.single_judge_correct)
        jury_correct = sum(1 for c in with_truth if c.jury_correct)
        both_correct = sum(1 for c in with_truth if c.single_judge_correct and c.jury_correct)
        disagreement_cases = sum(1 for c in with_truth if not c.verdicts_match)
        
        return {
            "total_with_ground_truth": len(with_truth),
            "single_judge_accuracy": 100 * single_correct / len(with_truth),
            "jury_accuracy": 100 * jury_correct / len(with_truth),
            "both_correct": both_correct,
            "jury_only_correct": jury_correct - both_correct,
            "single_only_correct": single_correct - both_correct,
            "disagreement_cases": disagreement_cases,
            "when_disagreed_jury_correct_percentage": 100 * sum(
                1 for c in with_truth if not c.verdicts_match and c.jury_correct
            ) / disagreement_cases if disagreement_cases > 0 else None
        }
    
    def analyze_disagreement_as_uncertainty(self) -> Dict[str, Any]:
        """
        Analyze whether disagreement level correlates with uncertainty.
        High disagreement might indicate low-confidence cases.
        """
        analysis = {
            "correlations": {},
            "insights": []
        }
        
        # Correlation: disagreement vs confidence
        if len(self.comparisons) > 2:
            disagreements = [c.jury_disagreement_level for c in self.comparisons]
            confidences = [c.jury_confidence for c in self.comparisons]
            
            correlation = np.corrcoef(disagreements, confidences)[0, 1]
            analysis["correlations"]["disagreement_vs_confidence"] = float(correlation)
            
            if correlation < -0.3:
                analysis["insights"].append(
                    "Strong negative correlation: high disagreement associated with low confidence"
                )
        
        # Cases with high disagreement
        high_disagreement = [c for c in self.comparisons if c.jury_disagreement_level > 0.5]
        if high_disagreement:
            avg_conf = statistics.mean([c.jury_confidence for c in high_disagreement])
            analysis["high_disagreement_cases"] = {
                "count": len(high_disagreement),
                "avg_confidence": avg_conf,
                "avg_reasoning_quality": statistics.mean([c.jury_avg_reasoning_quality for c in high_disagreement])
            }
        
        return analysis
    
    def save_results(self, filename: str = "jury_evaluation_results.json") -> Path:
        """Save evaluation results to JSON."""
        results = {
            "summary": {
                "total_comparisons": len(self.comparisons),
                "avg_jury_size": statistics.mean([c.jury_size for c in self.comparisons]) if self.comparisons else 0,
                "avg_disagreement": statistics.mean([c.jury_disagreement_level for c in self.comparisons]) if self.comparisons else 0,
                "unanimity_rate": 100 * sum(1 for c in self.comparisons if c.jury_unanimous) / len(self.comparisons) if self.comparisons else 0
            },
            "comparisons": [c.to_dict() for c in self.comparisons],
            "analysis": {
                "disagreement_vs_difficulty": self.analyze_disagreement_vs_difficulty(),
                "deliberation_impact": self.analyze_deliberation_impact(),
                "accuracy_comparison": self.analyze_accuracy_comparison(),
                "disagreement_as_uncertainty": self.analyze_disagreement_as_uncertainty()
            }
        }
        
        filepath = self.results_dir / filename
        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n✓ Results saved to {filepath}")
        return filepath
    
    def print_summary(self) -> None:
        """Print comprehensive summary report."""
        if not self.comparisons:
            print("No comparisons available")
            return
        
        print("\n" + "="*80)
        print("JURY PANEL EVALUATION SUMMARY")
        print("="*80)
        
        # Basic statistics
        print(f"\nTotal Cases: {len(self.comparisons)}")
        print(f"Jury Size: {self.comparisons[0].jury_size}")
        
        # Agreement
        unanimous = sum(1 for c in self.comparisons if c.jury_unanimous)
        print(f"\nJury Unanimity: {unanimous}/{len(self.comparisons)} ({100*unanimous/len(self.comparisons):.1f}%)")
        
        # Verdicts with single judge
        match = sum(1 for c in self.comparisons if c.verdicts_match)
        print(f"Agreement with Single Judge: {match}/{len(self.comparisons)} ({100*match/len(self.comparisons):.1f}%)")
        
        # Accuracy (if ground truth available)
        with_truth = [c for c in self.comparisons if c.ground_truth]
        if with_truth:
            jury_acc = sum(1 for c in with_truth if c.jury_correct) / len(with_truth)
            single_acc = sum(1 for c in with_truth if c.single_judge_correct) / len(with_truth)
            print(f"\nAccuracy (with ground truth):")
            print(f"  Single Judge: {100*single_acc:.1f}%")
            print(f"  Jury Panel: {100*jury_acc:.1f}%")
            print(f"  Improvement: {100*(jury_acc-single_acc):+.1f}%")
        
        # Difficulty analysis
        difficulty_analysis = self.analyze_disagreement_vs_difficulty()
        if difficulty_analysis.get("overall_correlation") is not None:
            print(f"\nDifficulty Correlation:")
            print(f"  Disagreement ↔ Difficulty Correlation: {difficulty_analysis['overall_correlation']:.2f}")
            if difficulty_analysis.get("by_difficulty"):
                for level, stats in difficulty_analysis["by_difficulty"].items():
                    if stats.get("count"):
                        print(f"  {level.upper()}: {stats['count']} cases, "
                              f"avg disagreement {stats.get('avg_disagreement', 0):.2f}, "
                              f"unanimity {stats.get('unanimous_percentage', 0):.0f}%")
        
        print("\n" + "="*80)
