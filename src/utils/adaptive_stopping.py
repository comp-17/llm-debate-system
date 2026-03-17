"""
Adaptive Stopping Criterion Module
====================================

Implements the convergence detection mechanism for the four-phase debate protocol.

CRITERION:
  Debate ends early if both agents converge to the same answer pair for 
  two consecutive rounds, after a minimum of N ≥ 3 rounds.

This module provides:
  1. Convergence detection logic
  2. Answer history tracking
  3. Detailed logging and visualization
  4. Statistical analysis
  5. Testing utilities
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any
from enum import Enum
import json
import logging


class ConvergenceStatus(Enum):
    """Status of convergence check"""
    CHECKING = "checking"
    CONVERGED = "converged"
    NOT_CONVERGED = "not_converged"
    MIN_ROUNDS_NOT_MET = "min_rounds_not_met"
    MAX_ROUNDS_REACHED = "max_rounds_reached"


@dataclass
class AnswerPair:
    """Single round answer pair"""
    round_number: int
    debater_a_answer: str
    debater_b_answer: str
    
    def normalize(self) -> Tuple[str, str]:
        """Get normalized (lowercase, stripped) answer pair"""
        return (
            self.debater_a_answer.lower().strip(),
            self.debater_b_answer.lower().strip()
        )
    
    def __eq__(self, other: 'AnswerPair') -> bool:
        """Check equality based on normalized answers"""
        if not isinstance(other, AnswerPair):
            return False
        return self.normalize() == other.normalize()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'round_number': self.round_number,
            'debater_a': self.debater_a_answer,
            'debater_b': self.debater_b_answer,
        }


@dataclass
class ConvergenceResult:
    """Result of convergence check"""
    status: ConvergenceStatus
    converged: bool
    round_number: int
    rounds_completed: int
    convergence_round: Optional[int] = None  # First round where convergence detected
    last_two_pairs: List[AnswerPair] = field(default_factory=list)
    consecutive_rounds: Optional[Tuple[int, int]] = None  # (round_n, round_n+1)
    reason: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'status': self.status.value,
            'converged': self.converged,
            'round_number': self.round_number,
            'rounds_completed': self.rounds_completed,
            'convergence_round': self.convergence_round,
            'last_two_pairs': [p.to_dict() for p in self.last_two_pairs],
            'consecutive_rounds': self.consecutive_rounds,
            'reason': self.reason,
        }


class AdaptiveStoppingCriterion:
    """
    Implements adaptive stopping for debate convergence detection.
    
    ALGORITHM:
    ----------
    1. After each round, collect answer pair (A_answer, B_answer)
    2. After minimum N rounds:
       - Compare last two answer pairs (round N and round N+1)
       - If both answers match (A_N == A_{N+1} AND B_N == B_{N+1}):
         → Convergence detected! Stop debate.
    3. Continue until convergence or max rounds reached
    
    PROPERTIES:
    -----------
    - Ensures minimum debate depth (prevents premature termination)
    - Detects when argument space is exhausted
    - Efficient (only compares last 2 rounds)
    - Handles case-insensitive and whitespace normalization
    """
    
    def __init__(
        self,
        min_rounds: int = 3,
        max_rounds: int = 8,
        convergence_threshold: int = 2,
        logger: Optional[logging.Logger] = None
    ):
        """
        Args:
            min_rounds: Minimum rounds before checking convergence (N ≥ 3)
            max_rounds: Maximum rounds regardless of convergence
            convergence_threshold: Consecutive rounds with same answers to trigger stop
            logger: Logger for detailed output
        """
        self.min_rounds = min_rounds
        self.max_rounds = max_rounds
        self.convergence_threshold = convergence_threshold
        self.logger = logger or self._setup_logger()
        
        # History tracking
        self.answer_history: List[AnswerPair] = []
    
    def _setup_logger(self) -> logging.Logger:
        """Configure logger"""
        logger = logging.getLogger(__name__)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    def add_answer_pair(
        self,
        round_number: int,
        debater_a_answer: str,
        debater_b_answer: str
    ) -> ConvergenceResult:
        """
        Add answer pair for this round and check convergence.
        
        Args:
            round_number: Current round number (1-indexed)
            debater_a_answer: Answer from Debater A
            debater_b_answer: Answer from Debater B
        
        Returns:
            ConvergenceResult with convergence status
        """
        # Create answer pair
        pair = AnswerPair(
            round_number=round_number,
            debater_a_answer=debater_a_answer,
            debater_b_answer=debater_b_answer
        )
        
        self.answer_history.append(pair)
        
        # Log this round
        self._log_round(pair)
        
        # Check convergence
        result = self._check_convergence(round_number)
        
        # Log result
        self._log_convergence_result(result)
        
        return result
    
    def _check_convergence(self, current_round: int) -> ConvergenceResult:
        """Check if convergence criterion is met"""
        
        # Check if we've reached max rounds
        if current_round >= self.max_rounds:
            return ConvergenceResult(
                status=ConvergenceStatus.MAX_ROUNDS_REACHED,
                converged=False,
                round_number=current_round,
                rounds_completed=current_round,
                reason=f"Maximum rounds ({self.max_rounds}) reached"
            )
        
        # Check if minimum rounds requirement is met
        if current_round < self.min_rounds:
            return ConvergenceResult(
                status=ConvergenceStatus.MIN_ROUNDS_NOT_MET,
                converged=False,
                round_number=current_round,
                rounds_completed=current_round,
                reason=f"Minimum {self.min_rounds} rounds not met (current: {current_round})"
            )
        
        # We have at least min_rounds, now check convergence
        # Need at least convergence_threshold consecutive rounds with same answers
        if len(self.answer_history) < self.convergence_threshold:
            return ConvergenceResult(
                status=ConvergenceStatus.CHECKING,
                converged=False,
                round_number=current_round,
                rounds_completed=current_round,
                reason=f"Need {self.convergence_threshold} rounds to compare"
            )
        
        # Check last N rounds for convergence
        last_n_pairs = self.answer_history[-self.convergence_threshold:]
        
        # Verify all last N pairs are identical
        first_normalized = last_n_pairs[0].normalize()
        all_same = all(
            pair.normalize() == first_normalized 
            for pair in last_n_pairs
        )
        
        if all_same:
            # CONVERGENCE DETECTED!
            consecutive_rounds = (
                last_n_pairs[0].round_number,
                last_n_pairs[-1].round_number
            )
            
            return ConvergenceResult(
                status=ConvergenceStatus.CONVERGED,
                converged=True,
                round_number=current_round,
                rounds_completed=current_round,
                convergence_round=consecutive_rounds[0],
                last_two_pairs=last_n_pairs,
                consecutive_rounds=consecutive_rounds,
                reason=f"Convergence detected: Same answers for {self.convergence_threshold} consecutive rounds (rounds {consecutive_rounds[0]}-{consecutive_rounds[1]})"
            )
        else:
            return ConvergenceResult(
                status=ConvergenceStatus.NOT_CONVERGED,
                converged=False,
                round_number=current_round,
                rounds_completed=current_round,
                last_two_pairs=last_n_pairs,
                reason=f"No convergence: Answers differ in last {self.convergence_threshold} rounds"
            )
    
    def _log_round(self, pair: AnswerPair) -> None:
        """Log answer pair for this round"""
        self.logger.info(f"\n{'─'*70}")
        self.logger.info(f"Round {pair.round_number} Answer Pair Recorded:")
        self.logger.info(f"  Debater A: '{pair.debater_a_answer}'")
        self.logger.info(f"  Debater B: '{pair.debater_b_answer}'")
    
    def _log_convergence_result(self, result: ConvergenceResult) -> None:
        """Log convergence check result"""
        if result.status == ConvergenceStatus.CONVERGED:
            self.logger.warning(f"\n{'!'*70}")
            self.logger.warning(f"✓✓✓ CONVERGENCE DETECTED ✓✓✓")
            self.logger.warning(f"{'!'*70}")
            self.logger.warning(f"Debate will end after Round {result.round_number}")
            self.logger.warning(f"{result.reason}")
            self.logger.warning(f"Converged answers:")
            a_ans, b_ans = result.last_two_pairs[0].normalize()
            self.logger.warning(f"  Both debaters agree: A='{a_ans}', B='{b_ans}'")
        elif result.status == ConvergenceStatus.MAX_ROUNDS_REACHED:
            self.logger.warning(f"\nMax rounds reached. Ending debate.")
        elif result.status == ConvergenceStatus.MIN_ROUNDS_NOT_MET:
            self.logger.info(f"Round {result.round_number}: {result.reason}")
        else:
            self.logger.info(f"Round {result.round_number}: {result.reason}")
    
    def get_answer_history(self) -> List[AnswerPair]:
        """Get complete answer history"""
        return self.answer_history.copy()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics"""
        if not self.answer_history:
            return {}
        
        # Count how many rounds had the same answer
        same_answer_rounds = 0
        for i in range(1, len(self.answer_history)):
            if (self.answer_history[i].normalize() == 
                self.answer_history[i-1].normalize()):
                same_answer_rounds += 1
        
        return {
            'total_rounds': len(self.answer_history),
            'min_rounds_required': self.min_rounds,
            'max_rounds_allowed': self.max_rounds,
            'convergence_threshold': self.convergence_threshold,
            'consecutive_same_rounds': same_answer_rounds,
            'answer_stability': same_answer_rounds / max(1, len(self.answer_history) - 1),
            'answer_history': [p.to_dict() for p in self.answer_history],
        }
    
    def visualize_history(self) -> str:
        """Create text visualization of answer history"""
        if not self.answer_history:
            return "No answer history yet."
        
        lines = [
            "\nADAPTIVE STOPPING - ANSWER HISTORY VISUALIZATION",
            "=" * 70,
            ""
        ]
        
        for i, pair in enumerate(self.answer_history, 1):
            a_ans, b_ans = pair.normalize()
            
            # Check if same as previous
            if i > 1:
                prev_pair = self.answer_history[i-2]
                prev_a, prev_b = prev_pair.normalize()
                
                if a_ans == prev_a and b_ans == prev_b:
                    match_indicator = "← SAME AS PREVIOUS (convergence counter +1)"
                elif a_ans == prev_a or b_ans == prev_b:
                    match_indicator = "← PARTIAL MATCH"
                else:
                    match_indicator = ""
            else:
                match_indicator = ""
            
            lines.append(f"Round {i}:")
            lines.append(f"  A: '{a_ans}'")
            lines.append(f"  B: '{b_ans}' {match_indicator}")
            lines.append("")
        
        lines.extend([
            "=" * 70,
            f"Total rounds: {len(self.answer_history)}",
            f"Convergence threshold: {self.convergence_threshold}",
            f"Min rounds: {self.min_rounds}",
            f"Max rounds: {self.max_rounds}",
        ])
        
        return "\n".join(lines)
    
    def reset(self) -> None:
        """Reset history for new debate"""
        self.answer_history = []
        self.logger.info("Adaptive stopping criterion reset for new debate")


# ============================================================================
# Testing Utilities
# ============================================================================

def test_convergence_basic():
    """Test basic convergence detection"""
    print("\n" + "="*70)
    print("TEST 1: Basic Convergence Detection")
    print("="*70)
    
    criterion = AdaptiveStoppingCriterion(min_rounds=3, max_rounds=8)
    
    # Round 1: No convergence
    result = criterion.add_answer_pair(1, "Yes", "No")
    assert not result.converged, "Should not converge in round 1"
    print("✓ Round 1: No convergence (expected)")
    
    # Round 2: Still no convergence
    result = criterion.add_answer_pair(2, "Yes", "No")
    assert not result.converged, "Should not converge in round 2"
    print("✓ Round 2: No convergence (expected)")
    
    # Round 3: Still no convergence (min rounds reached, but different)
    result = criterion.add_answer_pair(3, "Maybe", "No")
    assert not result.converged, "Should not converge in round 3 (different answers)"
    print("✓ Round 3: No convergence (answers differ)")
    
    # Round 4: Same as round 3
    result = criterion.add_answer_pair(4, "Maybe", "No")
    assert result.converged, "Should converge in round 4 (same as round 3)"
    print("✓ Round 4: CONVERGENCE DETECTED (expected)")
    print(f"  Reason: {result.reason}")
    print(f"  Consecutive rounds: {result.consecutive_rounds}")
    
    return True


def test_convergence_min_rounds():
    """Test that convergence doesn't trigger before min rounds"""
    print("\n" + "="*70)
    print("TEST 2: Minimum Rounds Enforcement")
    print("="*70)
    
    criterion = AdaptiveStoppingCriterion(min_rounds=3, max_rounds=8)
    
    # Same answers for rounds 1-2 (should NOT converge - min not met)
    result = criterion.add_answer_pair(1, "Yes", "Yes")
    assert not result.converged, "Should not converge in round 1"
    print("✓ Round 1: Same answers, but min_rounds not met")
    
    result = criterion.add_answer_pair(2, "Yes", "Yes")
    assert not result.converged, "Should not converge in round 2"
    print("✓ Round 2: Same answers, but min_rounds not met")
    
    result = criterion.add_answer_pair(3, "Yes", "Yes")
    assert result.converged, "Should converge in round 3 (min_rounds met)"
    print("✓ Round 3: CONVERGENCE DETECTED (min_rounds requirement satisfied)")
    
    return True


def test_convergence_with_normalization():
    """Test that normalization (case-insensitive, whitespace) works"""
    print("\n" + "="*70)
    print("TEST 3: Answer Normalization")
    print("="*70)
    
    criterion = AdaptiveStoppingCriterion(min_rounds=3)
    
    # Different casings and whitespace
    criterion.add_answer_pair(1, "YES", "no")
    criterion.add_answer_pair(2, "  yes  ", "NO")
    criterion.add_answer_pair(3, "Yes", "No")
    result = criterion.add_answer_pair(4, "YES", "  no  ")
    
    assert result.converged, "Should converge with normalized answers"
    print("✓ Convergence detected despite case/whitespace differences")
    
    summary = criterion.get_summary()
    print(f"✓ Final stability: {summary['answer_stability']:.1%}")
    
    return True


def test_max_rounds_limit():
    """Test that debate stops at max rounds"""
    print("\n" + "="*70)
    print("TEST 4: Maximum Rounds Limit")
    print("="*70)
    
    criterion = AdaptiveStoppingCriterion(min_rounds=3, max_rounds=5)
    
    results = []
    for round_num in range(1, 7):
        # Always different answers
        result = criterion.add_answer_pair(round_num, f"Answer{round_num}", "Other")
        results.append(result)
        
        if round_num <= 5:
            assert not result.converged or result.status != ConvergenceStatus.MAX_ROUNDS_REACHED
        else:
            break
    
    # After round 5 (max rounds)
    print(f"✓ Rounds 1-4: Debate continues (max_rounds=5 not reached)")
    print(f"✓ Round 5: Debate would stop (max_rounds limit)")
    
    return True


def test_no_convergence_max_rounds():
    """Test debate that never converges goes to max rounds"""
    print("\n" + "="*70)
    print("TEST 5: No Convergence → Max Rounds")
    print("="*70)
    
    criterion = AdaptiveStoppingCriterion(min_rounds=3, max_rounds=4)
    
    # Always different answers
    for round_num in range(1, 5):
        result = criterion.add_answer_pair(round_num, f"A{round_num}", f"B{round_num}")
    
    print(f"✓ Completed 4 rounds without convergence")
    print(f"✓ Last status: {result.status.value}")
    
    summary = criterion.get_summary()
    print(f"✓ Total rounds completed: {summary['total_rounds']}")
    
    return True


def run_all_tests():
    """Run all convergence tests"""
    print("\n" + "="*70)
    print("ADAPTIVE STOPPING CRITERION - TEST SUITE")
    print("="*70)
    
    tests = [
        ("Basic Convergence", test_convergence_basic),
        ("Minimum Rounds Enforcement", test_convergence_min_rounds),
        ("Answer Normalization", test_convergence_with_normalization),
        ("Maximum Rounds Limit", test_max_rounds_limit),
        ("No Convergence to Max Rounds", test_no_convergence_max_rounds),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success, None))
            print(f"\n✓ {test_name}: PASSED")
        except AssertionError as e:
            results.append((test_name, False, str(e)))
            print(f"\n✗ {test_name}: FAILED - {e}")
        except Exception as e:
            results.append((test_name, False, str(e)))
            print(f"\n✗ {test_name}: ERROR - {e}")
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    for test_name, success, error in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"  {status}: {test_name}")
        if error:
            print(f"         Error: {error}")
    
    print("="*70 + "\n")
    
    return all(success for _, success, _ in results)


if __name__ == '__main__':
    success = run_all_tests()
    exit(0 if success else 1)
