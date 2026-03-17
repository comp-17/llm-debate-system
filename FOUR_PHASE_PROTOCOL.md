# 4-PHASE DEBATE PROTOCOL - IMPLEMENTATION GUIDE

## Overview

This document describes the complete implementation of the 4-phase debate protocol, as specified in the requirements and inspired by Irving et al. (2018) and Liang et al. (EMNLP 2024).

## Protocol Specification

### Phase 1: Initialization

**Objective**: Generate independent initial positions from both debaters

**Process**:
1. Present question to Debater A
2. Debater A generates answer + reasoning WITHOUT seeing Debater B's response
3. Present same question to Debater B independently
4. Debater B generates answer + reasoning WITHOUT seeing Debater A's response
5. Check for immediate consensus

**Consensus Check**:
- If both debaters provide identical answers → Record as consensus
- Skip directly to Phase 3 (Judgment) if consensus reached
- Otherwise, proceed to Phase 2 (Debate)

**Output**: 
- `DebaterPosition` for each debater containing:
  - `answer`: The initial position
  - `reasoning`: 2-3 sentence explanation
  - `timestamp`: When position was generated

### Phase 2: Multi-Round Debate

**Objective**: Conduct adversarial debate with adaptive stopping

**Rules**:
- Minimum N ≥ 3 rounds (enforced)
- Each round: Debater A argues, then Debater B responds
- Both debaters receive FULL transcript from all previous rounds
- Implement CoT (Chain-of-Thought) reasoning for each argument
- Early stopping criterion: Same answer for 2 consecutive rounds

**Round Structure**:
```
Round N:
  - Debater A presents argument (with CoT reasoning)
  - Debater B responds with counterargument (with CoT reasoning)
  - Check convergence criterion
  - If converged for 2+ rounds → Stop debate
```

**Transcript Management**:
- Build complete transcript before each round
- Includes: question, initial positions, all previous arguments
- Both debaters see identical context (full history)

**Early Stopping Conditions**:
1. **Convergence**: If debaters maintain same position for 2 consecutive rounds AND at least 3 rounds completed
2. **Maximum rounds**: If max_rounds (default 6) reached

**Output**:
- List of `DebateArgument` objects, each containing:
  - `round_number`: Which round
  - `debater_id`: A or B
  - `argument`: The argument text (2-3 sentences)
  - `cot_reasoning`: Chain-of-thought reasoning
  - `timestamp`: When generated
- `stopping_reason`: Why debate ended (convergence_round_N or max_rounds_reached_N)

### Phase 3: Judgment

**Objective**: Judge analyzes entire debate and renders verdict

**Judge Requirements**:
1. Receives complete debate transcript (full history)
2. Provides chain-of-thought (CoT) analysis
3. Identifies strongest argument from each debater
4. Identifies weakest argument from each debater
5. Renders final verdict (which position more convincing)
6. Provides confidence score (1-5 scale)

**Judge Analysis Structure**:
```
(a) COT_ANALYSIS: Step-by-step analysis of both arguments
(b) STRONGEST_A: Single strongest argument from Debater A
(c) WEAKEST_A: Single weakest argument from Debater A
(d) STRONGEST_B: Single strongest argument from Debater B
(e) WEAKEST_B: Single weakest argument from Debater B
(f) FINAL_VERDICT: Which debater's position is more convincing and why
(g) CONFIDENCE: 1-5 scale (5 = most confident, 1 = least confident)
(h) REASONING: Detailed explanation for verdict
```

**Output**:
- `JudgeAnalysis` object containing all 8 elements above

### Phase 4: Evaluation

**Objective**: Compare judge verdict against ground truth (if available)

**Evaluation Metrics**:
1. `judge_correct`: Whether judge verdict matches ground truth
2. `both_debaters_correct`: Whether both initial positions were correct
3. `debate_improved_accuracy`: Judge correct AND NOT both debaters correct
   - Indicates debate added value in resolving disagreement

**Output**:
- `DebateResult` containing all phases and evaluation metrics

## Implementation Architecture

### Core Classes

#### `MultiPhaseDebateOrchestrator`
Main class orchestrating all 4 phases

```python
class MultiPhaseDebateOrchestrator:
    def __init__(
        self,
        api_client,
        min_rounds: int = 3,
        max_rounds: int = 6,
        convergence_threshold: int = 2,
    )
    
    def run_debate(question: str, ground_truth: Optional[str]) -> DebateResult
```

Methods:
- `_phase1_initialization()` → Tuple[DebaterPosition, DebaterPosition]
- `_phase2_debate()` → Tuple[List[DebateArgument], str]
- `_phase3_judgment()` → JudgeAnalysis
- `_build_result()` → DebateResult

#### Data Classes

```python
@dataclass
class DebaterPosition:
    debater_id: str
    answer: str
    reasoning: str
    timestamp: str

@dataclass
class DebateArgument:
    round_number: int
    debater_id: str
    argument: str
    cot_reasoning: str
    timestamp: str

@dataclass
class JudgeAnalysis:
    cot_analysis: str
    strongest_argument_a: str
    strongest_argument_b: str
    weakest_argument_a: str
    weakest_argument_b: str
    final_verdict: str
    confidence: int
    reasoning: str

@dataclass
class DebateResult:
    question: str
    ground_truth: Optional[str]
    initial_position_a: DebaterPosition
    initial_position_b: DebaterPosition
    consensus_reached: bool
    rounds_executed: int
    debate_arguments: List[DebateArgument]
    stopping_reason: str
    judge_analysis: JudgeAnalysis
    judge_correct: bool
    both_debaters_correct: bool
    debate_improved_accuracy: bool
    timestamp: str
```

## Usage

### Single Debate

```python
from src.orchestrator.debate_orchestrator_4phase import MultiPhaseDebateOrchestrator
from src.utils.api_client import APIClient

api_client = APIClient(api_key="your_key", model="claude-3-5-sonnet-20241022")
orchestrator = MultiPhaseDebateOrchestrator(api_client, min_rounds=3, max_rounds=6)

result = orchestrator.run_debate(
    question="Is climate change primarily caused by human activity?",
    ground_truth="yes"
)

# Access all phases
print(f"Phase 1 - Initial Positions:")
print(f"  A: {result.initial_position_a.answer}")
print(f"  B: {result.initial_position_b.answer}")

print(f"Phase 2 - Debate: {result.rounds_executed} rounds")
print(f"Phase 3 - Judge: {result.judge_analysis.final_verdict}")
print(f"Phase 4 - Evaluation: Judge correct = {result.judge_correct}")

# Save result
orchestrator.save_result(result, "debate_result.json")
```

### Batch Experiments

```python
from run_debate_4phase import FourPhaseExperimentRunner

runner = FourPhaseExperimentRunner(
    model="claude-3-5-sonnet-20241022",
    min_rounds=3,
    max_rounds=6
)

questions = [
    {"question": "Is the Earth flat?", "ground_truth": "no"},
    {"question": "What is 2+2?", "ground_truth": "4"},
    # ... more questions
]

summary = runner.run_batch(questions, output_dir="results")
```

### Command Line

```bash
# Run 5 sample debates
python run_debate_4phase.py --samples 5 --output data/results

# Run with custom settings
python run_debate_4phase.py \
    --samples 50 \
    --model claude-3-5-sonnet-20241022 \
    --min-rounds 3 \
    --max-rounds 8
```

## Output Format

### Individual Debate JSON

```json
{
  "question": "Is climate change primarily caused by human activity?",
  "ground_truth": "yes",
  "phase1": {
    "initial_position_a": {
      "debater_id": "A",
      "answer": "Yes, human activity is the primary cause",
      "reasoning": "Multiple studies show...",
      "timestamp": "2025-03-15T10:00:00"
    },
    "initial_position_b": {
      "debater_id": "B",
      "answer": "It's a complex mix of natural and human factors",
      "reasoning": "Natural cycles also play a role...",
      "timestamp": "2025-03-15T10:00:05"
    },
    "consensus_reached": false
  },
  "phase2": {
    "rounds_executed": 3,
    "stopping_reason": "convergence_round_3",
    "arguments": [
      {
        "round_number": 1,
        "debater_id": "A",
        "argument": "The evidence clearly shows...",
        "cot_reasoning": "First, I consider...",
        "timestamp": "2025-03-15T10:00:10"
      },
      // ... more arguments
    ]
  },
  "phase3": {
    "cot_analysis": "Both debaters present...",
    "strongest_argument_a": "The scientific consensus is strong",
    "strongest_argument_b": "Natural cycles do influence climate",
    "weakest_argument_a": "Did not address counterpoint",
    "weakest_argument_b": "Underestimated human contribution",
    "final_verdict": "Human activity is the primary cause",
    "confidence": 4,
    "reasoning": "While natural factors matter, the evidence strongly supports..."
  },
  "phase4": {
    "judge_correct": true,
    "both_debaters_correct": false,
    "debate_improved_accuracy": true
  },
  "timestamp": "2025-03-15T10:05:00"
}
```

### Batch Summary JSON

```json
{
  "total_debates": 50,
  "timestamp": "2025-03-15T11:00:00",
  "phases_completed": {
    "phase1_init": 50,
    "phase2_debate": 50,
    "phase3_judgment": 50,
    "phase4_evaluation": 50
  },
  "debate_metrics": {
    "avg_rounds": 3.2,
    "consensus_reached": 5,
    "early_stops": 32,
    "max_round_limits": 13
  },
  "accuracy_metrics": {
    "judge_correct": 42,
    "judge_accuracy_pct": 84.0,
    "debate_improved": 12,
    "accuracy_improvement_pct": 24.0
  },
  "judge_confidence": {
    "avg_confidence": 3.6,
    "confidence_dist": {
      "1": 2,
      "2": 5,
      "3": 18,
      "4": 20,
      "5": 5
    }
  }
}
```

## Key Features

### 1. Independent Phase 1
- Debaters generate positions completely independently
- No knowledge of opponent's answer
- Enables genuine divergence detection

### 2. Full Context Phase 2
- Each round includes complete transcript history
- Debaters see all previous arguments
- Enables informed rebuttals and position refinement

### 3. Adaptive Stopping
- Minimum 3 rounds enforced (Irving et al. 2018)
- Early exit on convergence (2 consecutive rounds)
- Prevents unnecessary debate when consensus emerges

### 4. Structured Judgment (Phase 3)
- Judge must provide all 8 analysis components
- CoT reasoning from judge
- Strongest/weakest argument identification
- Confidence calibration

### 5. Automatic Evaluation (Phase 4)
- Ground truth comparison (when available)
- Metrics on judge accuracy
- Tracks whether debate improved accuracy

## Validation

### Compliance with Requirements

✅ Phase 1: Independent positions + consensus check  
✅ Phase 2: Multi-round debate (N≥3) with adaptive stopping  
✅ Phase 3: Judge CoT + strongest/weakest args + verdict + confidence  
✅ Phase 4: Ground truth evaluation + metrics  

### Compliance with Irving et al. (2018)

✅ Multi-round alternating debate  
✅ Pre-committed answers  
✅ Full debate visibility to judge  
✅ Zero-sum format (one verdict)  
✅ Emphasis on "harder to lie than refute lie"  

### Compliance with Liang et al. (2024)

✅ Multi-agent debate structure  
✅ Adversarial format  
✅ Iterative refinement through rounds  
✅ Degeneration-of-thought prevention through evidence review  

## Files

- `src/orchestrator/debate_orchestrator_4phase.py` - Core implementation
- `run_debate_4phase.py` - Experiment runner and CLI
- `data/results_4phase/` - Output directory for results

## Next Steps

1. Run experiments with sample questions
2. Evaluate debate accuracy vs. single-judge baseline
3. Analyze convergence patterns
4. Test with domain-specific questions
5. Compare different judge models
