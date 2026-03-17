"""
Comprehensive test suite for jury panel system.
Tests core functionality, edge cases, and performance characteristics.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
from pathlib import Path
from typing import Dict, List, Any

from src.agents.jury_panel import (
    EnhancedJuryMember, EnhancedJuryPanel, JuryMode,
    JuryVerdictData, DisagreementMetrics
)
from src.utils.jury_evaluation import JuryEvaluationFramework, QuestionDifficultyEstimator
from src.utils.batch_experiments import BatchExperimentRunner, ExperimentConfig


class TestJuryMember(unittest.TestCase):
    """Test EnhancedJuryMember functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_api_client = Mock()
        self.member = EnhancedJuryMember(self.mock_api_client, member_id=1)
    
    def test_member_initialization(self):
        """Test jury member initializes correctly."""
        self.assertEqual(self.member.member_id, 1)
        self.assertEqual(self.member.name, "Jury Member 1")
        self.assertTrue(self.member.use_chain_of_thought)
    
    def test_verdict_extraction_winner(self):
        """Test extracting winner from LLM response."""
        response = "After careful analysis, Winner: Debater A is more convincing."
        winner = self.member._extract_winner(response)
        self.assertEqual(winner, "Debater A")
    
    def test_verdict_extraction_confidence(self):
        """Test extracting confidence score."""
        response = "My verdict is clear. Confidence: 4 out of 5."
        confidence = self.member._extract_confidence(response)
        self.assertEqual(confidence, 4)
    
    def test_verdict_extraction_scores(self):
        """Test extracting debater scores."""
        response = "Score: A: 8.5, B: 6.2"
        scores = self.member._extract_scores(response)
        self.assertAlmostEqual(scores["debater_a"], 8.5)
        self.assertAlmostEqual(scores["debater_b"], 6.2)
    
    def test_reasoning_quality_scoring(self):
        """Test reasoning quality scoring."""
        high_quality = """
        First, let me analyze the arguments. Debater A presents strong evidence for their position.
        However, Debater B raises valid counterpoints. After weighing both sides carefully, 
        Debater A's reasoning is more logically coherent. Therefore, Winner: Debater A.
        Confidence: 4
        """
        score = self.member._score_reasoning_quality(high_quality)
        self.assertGreater(score, 0.6)
    
    def test_has_step_by_step_reasoning(self):
        """Test detection of structured reasoning."""
        with_steps = "First, I note X. Second, I observe Y. Therefore, Z."
        without_steps = "Debater A is better."
        
        self.assertTrue(self.member._has_step_by_step_reasoning(with_steps))
        self.assertFalse(self.member._has_step_by_step_reasoning(without_steps))


class TestJuryPanel(unittest.TestCase):
    """Test EnhancedJuryPanel functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_api_client = Mock()
        self.jury = EnhancedJuryPanel(
            self.mock_api_client,
            jury_size=3,
            mode=JuryMode.INDEPENDENT
        )
    
    def test_jury_initialization(self):
        """Test jury panel initializes with correct members."""
        self.assertEqual(len(self.jury.members), 3)
        self.assertEqual(self.jury.jury_size, 3)
        self.assertEqual(self.jury.mode, JuryMode.INDEPENDENT)
    
    def test_majority_vote_consensus(self):
        """Test majority voting consensus."""
        # Create mock verdicts: 2 for A, 1 for B
        verdicts = [
            JuryVerdictData(1, "Debater A", 4, "reasoning", {}, 0.75),
            JuryVerdictData(2, "Debater A", 3, "reasoning", {}, 0.72),
            JuryVerdictData(3, "Debater B", 2, "reasoning", {}, 0.65),
        ]
        self.jury.final_verdicts = verdicts
        
        consensus = self.jury._consensus_majority_vote()
        self.assertEqual(consensus['winner'], "Debater A")
        self.assertEqual(consensus['vote_breakdown']["Debater A"], 2)
    
    def test_weighted_consensus(self):
        """Test confidence-weighted consensus."""
        # High quality A, low quality B
        verdicts = [
            JuryVerdictData(1, "Debater A", 5, "strong reasoning", {}, 0.9),
            JuryVerdictData(2, "Debater B", 4, "weak reasoning", {}, 0.4),
        ]
        self.jury.final_verdicts = verdicts
        
        consensus = self.jury._consensus_weighted()
        # A should win due to higher quality weight
        self.assertEqual(consensus['winner'], "Debater A")
    
    def test_disagreement_metrics_unanimous(self):
        """Test disagreement metrics for unanimous case."""
        verdicts = [
            JuryVerdictData(1, "Debater A", 4, "reasoning", {}, 0.75),
            JuryVerdictData(2, "Debater A", 4, "reasoning", {}, 0.75),
            JuryVerdictData(3, "Debater A", 5, "reasoning", {}, 0.80),
        ]
        self.jury.final_verdicts = verdicts
        self.jury._compute_metrics()
        
        self.assertTrue(self.jury.disagreement_metrics.unanimous)
        self.assertEqual(self.jury.disagreement_metrics.disagreement_level, 0.0)
    
    def test_disagreement_metrics_split(self):
        """Test disagreement metrics for split case."""
        verdicts = [
            JuryVerdictData(1, "Debater A", 4, "reasoning", {}, 0.75),
            JuryVerdictData(2, "Debater B", 3, "reasoning", {}, 0.70),
        ]
        self.jury.final_verdicts = verdicts
        self.jury._compute_metrics()
        
        self.assertFalse(self.jury.disagreement_metrics.unanimous)
        self.assertGreater(self.jury.disagreement_metrics.disagreement_level, 0.0)


class TestDifficultyEstimator(unittest.TestCase):
    """Test QuestionDifficultyEstimator."""
    
    def test_easy_question(self):
        """Test difficulty estimation for easy question."""
        easy_q = "Is water wet?"
        difficulty = QuestionDifficultyEstimator.estimate(easy_q)
        self.assertLess(difficulty, 0.4)
    
    def test_hard_question(self):
        """Test difficulty estimation for hard question."""
        hard_q = (
            "Given that X cannot occur without Y, but Y can occur without X, "
            "and Z prevents both X and Y, what conditions enable X given the constraints?"
        )
        difficulty = QuestionDifficultyEstimator.estimate(hard_q)
        self.assertGreater(difficulty, 0.6)
    
    def test_negation_adds_difficulty(self):
        """Test that negation increases difficulty score."""
        q1 = "Is this true?"
        q2 = "Is this NOT true?"
        
        d1 = QuestionDifficultyEstimator.estimate(q1)
        d2 = QuestionDifficultyEstimator.estimate(q2)
        
        self.assertLess(d1, d2)
    
    def test_temporal_reasoning_adds_difficulty(self):
        """Test that temporal markers increase difficulty."""
        q1 = "What happened?"
        q2 = "What happened before X and after Y?"
        
        d1 = QuestionDifficultyEstimator.estimate(q1)
        d2 = QuestionDifficultyEstimator.estimate(q2)
        
        self.assertLess(d1, d2)


class TestJuryEvaluation(unittest.TestCase):
    """Test JuryEvaluationFramework."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.framework = JuryEvaluationFramework(results_dir="/tmp/test_results")
    
    def test_comparison_creation(self):
        """Test creating jury comparison."""
        from src.utils.jury_evaluation import JuryComparison
        
        comparison = JuryComparison(
            question_id="q1",
            question_text="Test question",
            question_difficulty=0.5,
            ground_truth="Debater A",
            single_judge_winner="Debater A",
            single_judge_confidence=4,
            single_judge_correct=True,
            jury_size=3,
            jury_mode="deliberation",
            jury_winner="Debater A",
            jury_confidence=4.2,
            jury_correct=True,
            jury_unanimous=True,
            jury_disagreement_level=0.0,
            jury_avg_reasoning_quality=0.78,
            jury_deliberation_rounds=1,
            verdicts_match=True,
            confidence_gap=0.2,
            jury_advantage=False,
        )
        
        self.assertEqual(comparison.question_id, "q1")
        self.assertTrue(comparison.verdicts_match)
        self.assertEqual(comparison.jury_size, 3)


class TestBatchExperiments(unittest.TestCase):
    """Test batch experiment utilities."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.runner = BatchExperimentRunner(output_dir="/tmp/test_batch")
    
    def test_add_ablation_study(self):
        """Test adding ablation study configurations."""
        self.runner.add_ablation_study(num_samples=10)
        self.assertEqual(len(self.runner.experiments), 5)
    
    def test_experiment_config_generation(self):
        """Test YAML config generation."""
        config = ExperimentConfig(
            name="test_exp",
            jury_size=3,
            jury_mode="deliberation",
            deliberation_rounds=1,
            num_samples=20,
            dataset="commonsense_qa",
        )
        
        yaml_config = self.runner.generate_config_file(config)
        self.assertIn("jury_size: 3", yaml_config)
        self.assertIn("jury_mode: deliberation", yaml_config)
    
    def test_add_deliberation_study(self):
        """Test deliberation study setup."""
        self.runner.add_deliberation_study(num_samples=15)
        self.assertEqual(len(self.runner.experiments), 4)  # 0, 1, 2, 3 rounds
    
    def test_add_jury_size_study(self):
        """Test jury size study setup."""
        self.runner.add_jury_size_study(num_samples=15)
        self.assertEqual(len(self.runner.experiments), 5)  # Sizes: 2,3,4,5,7


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_api_client = Mock()
    
    def test_empty_verdict_response(self):
        """Test handling of empty LLM response."""
        member = EnhancedJuryMember(self.mock_api_client, 1)
        verdict = member._parse_verdict("")
        
        self.assertIsNone(verdict.winner)
        self.assertIsNone(verdict.confidence)
    
    def test_malformed_confidence(self):
        """Test handling of invalid confidence values."""
        member = EnhancedJuryMember(self.mock_api_client, 1)
        
        # Confidence outside range
        confidence = member._extract_confidence("Confidence: 10")
        self.assertIsNone(confidence)
        
        # Non-numeric confidence
        confidence = member._extract_confidence("Confidence: very high")
        self.assertIsNone(confidence)
    
    def test_single_member_panel(self):
        """Test panel with only 1 member (edge case)."""
        jury = EnhancedJuryPanel(self.mock_api_client, jury_size=1)
        self.assertEqual(len(jury.members), 1)
    
    def test_large_jury_panel(self):
        """Test panel with many members."""
        jury = EnhancedJuryPanel(self.mock_api_client, jury_size=10)
        self.assertEqual(len(jury.members), 10)


class TestPerformance(unittest.TestCase):
    """Test performance characteristics."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_api_client = Mock()
    
    def test_verdict_parsing_performance(self):
        """Test that verdict parsing is fast."""
        import time
        member = EnhancedJuryMember(self.mock_api_client, 1)
        
        long_response = "reasoning " * 1000 + "Winner: Debater A. Confidence: 4"
        
        start = time.time()
        for _ in range(100):
            member._parse_verdict(long_response)
        elapsed = time.time() - start
        
        # Should complete 100 parses in < 1 second
        self.assertLess(elapsed, 1.0)
    
    def test_metrics_computation_performance(self):
        """Test that metrics computation scales well."""
        import time
        jury = EnhancedJuryPanel(self.mock_api_client, jury_size=5)
        
        # Create many verdicts
        verdicts = [
            JuryVerdictData(i, "Debater A" if i % 2 == 0 else "Debater B", 
                          3 + i % 2, "reasoning", {}, 0.7 + i * 0.01)
            for i in range(1, 100)
        ]
        jury.final_verdicts = verdicts
        
        start = time.time()
        jury._compute_metrics()
        elapsed = time.time() - start
        
        # Should complete metrics for 100 cases in < 100ms
        self.assertLess(elapsed, 0.1)


class TestIntegration(unittest.TestCase):
    """Integration tests for full system."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_api_client = Mock()
    
    def test_full_jury_evaluation_flow(self):
        """Test complete jury evaluation workflow."""
        jury = EnhancedJuryPanel(
            self.mock_api_client,
            jury_size=3,
            mode=JuryMode.INDEPENDENT
        )
        
        # Mock API responses
        mock_responses = [
            "After analysis, Winner: Debater A. Confidence: 4",
            "Winner: Debater A. Confidence: 3",
            "Winner: Debater B. Confidence: 2",
        ]
        
        self.mock_api_client.call = Mock(side_effect=mock_responses)
        
        # Run evaluation (would normally call LLM)
        result = jury.evaluate(
            question="Test question",
            debater_a_position="Position A",
            debater_b_position="Position B",
            debate_transcript="Debate transcript"
        )
        
        # Check structure
        self.assertIn('jury_verdicts', result)
        self.assertIn('disagreement_metrics', result)
        self.assertEqual(len(result['jury_verdicts']), 3)


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestJuryMember))
    suite.addTests(loader.loadTestsFromTestCase(TestJuryPanel))
    suite.addTests(loader.loadTestsFromTestCase(TestDifficultyEstimator))
    suite.addTests(loader.loadTestsFromTestCase(TestJuryEvaluation))
    suite.addTests(loader.loadTestsFromTestCase(TestBatchExperiments))
    suite.addTests(loader.loadTestsFromTestCase(TestEdgeCases))
    suite.addTests(loader.loadTestsFromTestCase(TestPerformance))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
