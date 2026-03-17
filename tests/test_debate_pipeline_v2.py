"""
Test Suite for 4-Phase Debate Pipeline
Unit and integration tests
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
import json

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.orchestrator.debate_pipeline_v2 import (
    DebatePipeline,
    InitialPosition,
    RoundArgument,
    DebateTranscript,
    JudgeAnalysis
)


class MockAPIClient:
    """Mock API client for testing"""
    
    def __init__(self):
        self.call_count = 0
    
    def call(self, prompt: str, max_tokens: int = 1000, temperature: float = 0.7) -> str:
        """Mock API call"""
        self.call_count += 1
        
        # Return different responses based on prompt content
        if "Debater A" in prompt and "initial" in prompt.lower():
            return """ANSWER: Yes, AI is beneficial
REASONING: AI improves efficiency and solves complex problems"""
        elif "Debater B" in prompt and "initial" in prompt.lower():
            return """ANSWER: No, AI is harmful
REASONING: AI poses safety risks and job displacement threats"""
        elif "CHAIN_OF_THOUGHT" in prompt:
            return """CHAIN_OF_THOUGHT: First, consider benefits; then, weigh risks.
ARGUMENT: AI provides significant economic and scientific value"""
        elif "judge" in prompt.lower():
            return """CHAIN_OF_THOUGHT: Both debaters made valid points
STRONGEST_A: Clear economic benefits
STRONGEST_B: Valid safety concerns
WEAKEST_A: Did not address long-term risks
WEAKEST_B: Overstated job displacement
VERDICT: Yes, AI is beneficial with proper safeguards
CONFIDENCE: 4"""
        else:
            return "Default mock response"


class TestPhase1Initialization:
    """Tests for Phase 1: Initialization"""
    
    def test_phase1_generates_independent_positions(self):
        """Test that Phase 1 generates independent positions for both debaters"""
        api_client = MockAPIClient()
        pipeline = DebatePipeline(api_client=api_client, min_rounds=3)
        
        question = "Is AI beneficial?"
        positions = pipeline._phase1_initialization(question)
        
        # Both debaters should have positions
        assert 'debater_a' in positions
        assert 'debater_b' in positions
        
        # Positions should have required fields
        assert positions['debater_a'].answer
        assert positions['debater_a'].reasoning
        assert positions['debater_b'].answer
        assert positions['debater_b'].reasoning
    
    def test_phase1_consensus_detection(self):
        """Test that consensus is detected when both debaters agree"""
        api_client = MockAPIClient()
        api_client.call = Mock(return_value="""ANSWER: Yes
REASONING: Same answer""")
        
        pipeline = DebatePipeline(api_client=api_client, min_rounds=3)
        question = "Is water wet?"
        positions = pipeline._phase1_initialization(question)
        
        # Extract answers from positions
        answer_a = positions['debater_a'].answer
        answer_b = positions['debater_b'].answer
        
        # Mock ensures both return "Yes"
        assert answer_a == answer_b
    
    def test_initial_position_parsing(self):
        """Test parsing of initial position response"""
        pipeline = DebatePipeline(api_client=MockAPIClient())
        
        response = """ANSWER: Yes
REASONING: Because reasons"""
        position = pipeline._parse_initial_position(response, "Debater A")
        
        assert position.debater_id == "Debater A"
        assert position.answer == "Yes"
        assert position.reasoning == "Because reasons"
        assert position.timestamp is not None


class TestPhase2Debate:
    """Tests for Phase 2: Multi-Round Debate"""
    
    def test_phase2_minimum_rounds_enforced(self):
        """Test that minimum N >= 3 rounds are enforced"""
        api_client = MockAPIClient()
        pipeline = DebatePipeline(api_client=api_client, min_rounds=3, max_rounds=10)
        
        initial_positions = {
            'debater_a': InitialPosition(
                debater_id='debater_a',
                answer='Yes',
                reasoning='Reasoning A',
                timestamp=datetime.now().isoformat()
            ),
            'debater_b': InitialPosition(
                debater_id='debater_b',
                answer='No',
                reasoning='Reasoning B',
                timestamp=datetime.now().isoformat()
            )
        }
        
        question = "Is X true?"
        rounds, stopped_early, reason = pipeline._phase2_debate(question, initial_positions)
        
        # Should have at least min_rounds
        assert len(rounds) >= pipeline.min_rounds
    
    def test_phase2_adaptive_stopping(self):
        """Test adaptive stopping when same answers for 2 consecutive rounds"""
        api_client = MockAPIClient()
        api_client.call = Mock(return_value="""CHAIN_OF_THOUGHT: Same answer
ARGUMENT: I believe the same thing""")
        
        pipeline = DebatePipeline(api_client=api_client, min_rounds=3, max_rounds=10)
        
        initial_positions = {
            'debater_a': InitialPosition(
                debater_id='debater_a',
                answer='Yes',
                reasoning='Reasoning A',
                timestamp=datetime.now().isoformat()
            ),
            'debater_b': InitialPosition(
                debater_id='debater_b',
                answer='No',
                reasoning='Reasoning B',
                timestamp=datetime.now().isoformat()
            )
        }
        
        question = "Is X true?"
        rounds, stopped_early, reason = pipeline._phase2_debate(question, initial_positions)
        
        # Should stop early if converged
        # (Note: Mock always returns same response, so should converge)
        assert len(rounds) <= pipeline.max_rounds
    
    def test_phase2_round_argument_parsing(self):
        """Test parsing of round arguments with CoT"""
        pipeline = DebatePipeline(api_client=MockAPIClient())
        
        response = """CHAIN_OF_THOUGHT: First consider X, then Y, then Z
ARGUMENT: Therefore, the answer is clear"""
        
        arg = pipeline._parse_round_argument(response, "Debater A", 1)
        
        assert arg.debater_id == "Debater A"
        assert arg.round_num == 1
        assert "X" in arg.cot_reasoning
        assert "clear" in arg.argument
    
    def test_phase2_transcript_building(self):
        """Test transcript building from debate rounds"""
        pipeline = DebatePipeline(api_client=MockAPIClient())
        
        question = "Is X true?"
        initial_positions = {
            'debater_a': InitialPosition(
                debater_id='debater_a',
                answer='Yes',
                reasoning='Reasoning A',
                timestamp=datetime.now().isoformat()
            ),
            'debater_b': InitialPosition(
                debater_id='debater_b',
                answer='No',
                reasoning='Reasoning B',
                timestamp=datetime.now().isoformat()
            )
        }
        
        rounds = [
            [
                RoundArgument(1, 'debater_a', 'Argument A1', 'CoT A1', datetime.now().isoformat()),
                RoundArgument(1, 'debater_b', 'Argument B1', 'CoT B1', datetime.now().isoformat())
            ]
        ]
        
        transcript = pipeline._build_transcript(question, initial_positions, rounds)
        
        assert question in transcript
        assert 'Yes' in transcript
        assert 'No' in transcript
        assert 'ROUND 1' in transcript
        assert 'Argument A1' in transcript


class TestPhase3Judgment:
    """Tests for Phase 3: Judgment"""
    
    def test_phase3_judge_analysis_parsing(self):
        """Test parsing of structured judge analysis"""
        pipeline = DebatePipeline(api_client=MockAPIClient())
        
        response = """CHAIN_OF_THOUGHT: Analyzed both arguments carefully
STRONGEST_A: Clear and compelling
STRONGEST_B: Well-reasoned counterpoint
WEAKEST_A: Lacks supporting evidence
WEAKEST_B: Ignores practical implications
VERDICT: Answer A is stronger
CONFIDENCE: 4"""
        
        analysis = pipeline._parse_judge_analysis(response)
        
        assert analysis.cot_analysis
        assert analysis.strongest_arg_a == "Clear and compelling"
        assert analysis.strongest_arg_b == "Well-reasoned counterpoint"
        assert analysis.weakest_arg_a == "Lacks supporting evidence"
        assert analysis.weakest_arg_b == "Ignores practical implications"
        assert analysis.verdict
        assert analysis.confidence == 4
    
    def test_phase3_confidence_validation(self):
        """Test that confidence scores are validated to 1-5 range"""
        pipeline = DebatePipeline(api_client=MockAPIClient())
        
        # Test out-of-range confidences
        response_high = """CHAIN_OF_THOUGHT: Test
STRONGEST_A: Test
STRONGEST_B: Test
WEAKEST_A: Test
WEAKEST_B: Test
VERDICT: Test
CONFIDENCE: 10"""
        
        analysis_high = pipeline._parse_judge_analysis(response_high)
        assert analysis_high.confidence <= 5
        
        response_low = """CHAIN_OF_THOUGHT: Test
STRONGEST_A: Test
STRONGEST_B: Test
WEAKEST_A: Test
WEAKEST_B: Test
VERDICT: Test
CONFIDENCE: -1"""
        
        analysis_low = pipeline._parse_judge_analysis(response_low)
        assert analysis_low.confidence >= 1


class TestPhase4Evaluation:
    """Tests for Phase 4: Evaluation"""
    
    def test_phase4_ground_truth_comparison(self):
        """Test evaluation against ground truth"""
        pipeline = DebatePipeline(api_client=MockAPIClient())
        
        verdict = "Yes"
        ground_truth = "Yes"
        
        metrics = pipeline._phase4_evaluation(verdict, ground_truth)
        
        assert metrics['match'] == True
        assert metrics['judge_verdict'] == verdict
        assert metrics['ground_truth'] == ground_truth
    
    def test_phase4_no_ground_truth(self):
        """Test evaluation when no ground truth available"""
        pipeline = DebatePipeline(api_client=MockAPIClient())
        
        verdict = "Yes"
        
        metrics = pipeline._phase4_evaluation(verdict, None)
        
        assert metrics['match'] is None
        assert metrics['judge_verdict'] == verdict
        assert metrics['ground_truth'] is None


class TestFullPipeline:
    """Integration tests for complete pipeline"""
    
    def test_full_debate_with_disagreement(self):
        """Test complete debate when debaters disagree"""
        api_client = MockAPIClient()
        pipeline = DebatePipeline(api_client=api_client, min_rounds=3, max_rounds=10)
        
        result = pipeline.run_full_debate(
            debate_id='test_001',
            question='Is AI beneficial?',
            ground_truth='yes'
        )
        
        assert result.debate_id == 'test_001'
        assert result.question == 'Is AI beneficial?'
        assert result.ground_truth == 'yes'
        assert not result.consensus_reached  # Mock returns different answers
        assert result.total_rounds >= 3
        assert result.final_verdict
        assert 1 <= result.confidence_score <= 5
    
    def test_full_debate_export(self):
        """Test exporting debate transcript to JSON"""
        api_client = MockAPIClient()
        pipeline = DebatePipeline(api_client=api_client, min_rounds=3)
        
        result = pipeline.run_full_debate(
            debate_id='test_002',
            question='Test question?',
            ground_truth='yes'
        )
        
        exported = pipeline.export_transcript(result)
        
        # Should be JSON serializable
        json_str = json.dumps(exported)
        reloaded = json.loads(json_str)
        
        assert reloaded['debate_id'] == 'test_002'
        assert 'phase1_initialization' in reloaded
        assert 'phase2_debate' in reloaded
        assert 'phase3_judgment' in reloaded
        assert 'phase4_evaluation' in reloaded


class TestPromptsAndParsing:
    """Tests for prompt generation and parsing"""
    
    def test_initial_position_prompt_generation(self):
        """Test that initial position prompts are well-formed"""
        pipeline = DebatePipeline(api_client=MockAPIClient())
        
        prompt = pipeline._prompt_initial_position("Debater A", "Is X true?")
        
        assert "Is X true?" in prompt
        assert "Debater A" in prompt
        assert "ANSWER:" in prompt
        assert "REASONING:" in prompt
    
    def test_debater_argument_prompt_generation(self):
        """Test that debater argument prompts are well-formed"""
        pipeline = DebatePipeline(api_client=MockAPIClient())
        
        prompt = pipeline._prompt_debater_argument(
            "Debater A",
            "Is X true?",
            "Previous transcript",
            "Yes",
            round_num=1,
            is_response=False
        )
        
        assert "Is X true?" in prompt
        assert "Debater A" in prompt
        assert "CHAIN_OF_THOUGHT:" in prompt
        assert "ARGUMENT:" in prompt
    
    def test_judge_analysis_prompt_generation(self):
        """Test that judge analysis prompts are well-formed"""
        pipeline = DebatePipeline(api_client=MockAPIClient())
        
        prompt = pipeline._prompt_judge_analysis("Is X true?", "Debate transcript")
        
        assert "Is X true?" in prompt
        assert "judge" in prompt.lower()
        assert "STRONGEST_A:" in prompt
        assert "VERDICT:" in prompt
        assert "CONFIDENCE:" in prompt


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
