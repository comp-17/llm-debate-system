# 4-Phase Debate Pipeline - Complete Implementation Guide

## Overview

This document describes the complete implementation of the 4-phase debate pipeline per the specification:
- **Phase 1**: Initialization (independent initial positions)
- **Phase 2**: Multi-round debate (N ≥ 3 rounds with adaptive stopping)
- **Phase 3**: Judgment (structured judge analysis)
- **Phase 4**: Evaluation (comparison with ground truth)

## Files Structure

```
├── src/orchestrator/
│   └── debate_pipeline_v2.py          # Core 4-phase pipeline
├── src/utils/
│   └── debate_api_client.py           # LLM API client
├── tests/
│   └── test_debate_pipeline_v2.py     # Comprehensive test suite
├── run_debate_pipeline.py             # Runner script
└── [Other supporting files]
```

## Phase 1: Initialization

### Purpose
Generate independent initial positions from both debaters without inter-debater communication.

### Implementation

**Key Steps:**
1. Present question to Debater A independently
2. Debater A generates answer + brief reasoning
3. Present question to Debater B independently (does NOT see A's response)
4. Debater B generates answer + brief reasoning
5. Check for consensus

**Output:**
```python
InitialPosition(
    debater_id: str,      # "debater_a" or "debater_b"
    answer: str,          # The proposed answer
    reasoning: str,       # Brief reasoning (3-4 sentences)
    timestamp: str        # ISO timestamp
)
```

**Consensus Check:**
If both debaters propose the same answer → skip to Phase 3

**Code Reference:**
- Main function: `DebatePipeline._phase1_initialization(question)`
- Prompt generation: `_prompt_initial_position(debater_id, question)`
- Parsing: `_parse_initial_position(response, debater_id)`

### Example Flow

```
Question: "Is AI beneficial?"

Debater A (independent): 
  - Answer: "Yes"
  - Reasoning: "AI solves complex problems..."

Debater B (independent, doesn't see A):
  - Answer: "No"
  - Reasoning: "AI poses safety risks..."

Result: No consensus → proceed to Phase 2
```

## Phase 2: Multi-Round Debate

### Purpose
Enable iterative argument and counter-argument with adaptive termination.

### Implementation

**Key Requirements:**
1. **Minimum N ≥ 3 rounds** (enforced)
2. **Alternating turns**: Debater A → Debater B → Debater A → ...
3. **Full context**: Both debaters receive complete transcript from all previous rounds
4. **Chain-of-Thought**: Both debaters provide step-by-step reasoning in each round
5. **Adaptive stopping**: End debate early if same answer for 2 consecutive rounds

### Round Structure

Each round consists of:
1. **Debater A makes argument** (receives full transcript from previous rounds)
2. **Debater B responds** (receives full transcript + A's current argument)

### Adaptive Stopping Criterion

```python
# After each round, check:
if (
    A's_committed_answer_round_N == A's_committed_answer_round_N-1
    AND
    B's_committed_answer_round_N == B's_committed_answer_round_N-1
    AND
    round_N >= min_rounds
):
    stop_debate("Convergence detected")
```

**Rationale**: If both debaters maintain the same position across consecutive rounds despite seeing each other's arguments, further debate is unlikely to change positions.

### Output Per Round

```python
RoundArgument(
    round_num: int,       # Round number (1-indexed)
    debater_id: str,      # "debater_a" or "debater_b"
    argument: str,        # The argument text
    cot_reasoning: str,   # Chain-of-thought analysis
    timestamp: str        # ISO timestamp
)
```

### Code Reference
- Main function: `DebatePipeline._phase2_debate(question, initial_positions)`
- Prompt generation: `_prompt_debater_argument(...)`
- Parsing: `_parse_round_argument(response, debater_id, round_num)`
- Transcript building: `_build_transcript(question, initial_positions, rounds)`

### Example Flow (3 Rounds)

```
ROUND 1:
  Debater A argues: "AI is beneficial because..."
  Debater B responds: "But AI creates risks..."

ROUND 2:
  Debater A: "Those risks are manageable..."
  Debater B: "Still, the dangers outweigh benefits..."

ROUND 3:
  Debater A: "We disagree, but my position stands..."
  Debater B: "I maintain my opposition..."

Check: Same answers in rounds 2 and 3? No → continue
If yes and > min_rounds → stop debate
```

## Phase 3: Judgment

### Purpose
Judge analyzes complete debate and produces structured verdict.

### Input
- Original question
- Complete debate transcript (all rounds)
- Initial positions from Phase 1

### Required Judge Outputs

The judge must produce FIVE key outputs:

1. **Chain-of-Thought Analysis** (a)
   - Analyze key arguments from both debaters
   - Identify strongest points
   - Note weaknesses or gaps

2. **Strongest Argument from Debater A** (b)
   - Identify A's most compelling point
   - Explain why it's strong

3. **Strongest Argument from Debater B** (c)
   - Identify B's most compelling point
   - Explain why it's strong

4. **Final Verdict** (c)
   - Which debater's answer is better supported?
   - Why? (2-3 sentences)

5. **Confidence Score** (d)
   - Scale 1-5 (1=very uncertain, 5=very confident)
   - Reflects certainty in the verdict

### Output Structure

```python
JudgeAnalysis(
    cot_analysis: str,           # CoT analysis
    strongest_arg_a: str,        # Strongest from A
    strongest_arg_b: str,        # Strongest from B
    weakest_arg_a: str,          # Weakest from A
    weakest_arg_b: str,          # Weakest from B
    verdict: str,                # Final answer selected
    confidence: int              # 1-5 scale
)
```

### Judge Prompt Template

```
You are a judge evaluating a structured debate.

QUESTION: [question]

COMPLETE DEBATE TRANSCRIPT:
[full transcript with all rounds]

Your task: Provide comprehensive analysis of both debaters' arguments.

REQUIREMENTS:
1. Chain-of-Thought Analysis: Analyze key points from each debater
2. Strongest Argument A: Identify Debater A's best point
3. Strongest Argument B: Identify Debater B's best point
4. Weakest Argument A: Identify Debater A's weakest point
5. Weakest Argument B: Identify Debater B's weakest point
6. Final Verdict: Which debater's answer is stronger? Why?
7. Confidence: Rate your confidence 1-5 (1=very uncertain, 5=very confident)

Format exactly as:
CHAIN_OF_THOUGHT: [analysis]
STRONGEST_A: [A's best argument]
STRONGEST_B: [B's best argument]
WEAKEST_A: [A's weakest argument]
WEAKEST_B: [B's weakest argument]
VERDICT: [which answer wins and why]
CONFIDENCE: [1-5]
```

### Code Reference
- Main function (debate): `DebatePipeline._phase3_judgment_debate(...)`
- Main function (consensus): `DebatePipeline._phase3_judgment_consensus(...)`
- Prompt generation: `_prompt_judge_analysis(question, transcript)`
- Parsing: `_parse_judge_analysis(response)`

## Phase 4: Evaluation

### Purpose
Evaluate judge's verdict against ground truth and record all intermediate data.

### Implementation

**Tasks:**
1. Compare judge's verdict to ground truth answer
2. Record match/mismatch
3. Save all intermediate data for analysis

### Output

```python
Metrics = {
    'judge_verdict': str,           # What the judge decided
    'ground_truth': Optional[str],  # The correct answer
    'match': Optional[bool],        # Did verdict match truth?
    'evaluation_timestamp': str     # When evaluation occurred
}
```

### Code Reference
- Main function: `DebatePipeline._phase4_evaluation(verdict, ground_truth)`

## Complete Pipeline Execution

### Full Debate Flow

```python
# Initialize pipeline
pipeline = DebatePipeline(
    api_client=client,
    min_rounds=3,        # Minimum debate rounds
    max_rounds=10        # Maximum debate rounds
)

# Run complete debate
transcript = pipeline.run_full_debate(
    debate_id='debate_001',
    question='Is AI beneficial?',
    ground_truth='yes'  # Optional: for Phase 4 evaluation
)

# Export results
results = pipeline.export_transcript(transcript)
```

### Return Structure

```python
DebateTranscript(
    debate_id: str,
    question: str,
    ground_truth: Optional[str],
    
    # Phase 1 Results
    initial_positions: Dict[str, InitialPosition],
    consensus_reached: bool,
    consensus_answer: Optional[str],
    skipped_to_phase_3: bool,
    
    # Phase 2 Results
    rounds: List[List[RoundArgument]],
    total_rounds: int,
    stopped_early: bool,
    early_stop_reason: Optional[str],
    
    # Phase 3 Results
    judge_cot_analysis: str,
    strongest_argument_a: str,
    strongest_argument_b: str,
    weakest_argument_a: str,
    weakest_argument_b: str,
    final_verdict: str,
    confidence_score: int,  # 1-5
    
    # Phase 4 Results
    ground_truth_match: Optional[bool],
    evaluation_metrics: Dict
)
```

## Running Debates

### Single Debate

```bash
python run_debate_pipeline.py --single --model claude-3-5-sonnet-20241022
```

### Batch Debates

```bash
python run_debate_pipeline.py --num-debates 5 --min-rounds 3 --max-rounds 10
```

### With Custom Output Directory

```bash
python run_debate_pipeline.py --num-debates 5 --output-dir results/my_experiment
```

## Testing

Run comprehensive test suite:

```bash
pytest tests/test_debate_pipeline_v2.py -v
```

Test coverage includes:
- Phase 1: Independent position generation, consensus detection
- Phase 2: Multi-round debate, adaptive stopping, transcript building
- Phase 3: Structured judge analysis, confidence validation
- Phase 4: Ground truth evaluation
- Full pipeline integration
- Prompt generation and parsing

## Data Flow Example

```
Question: "Is X true?"

PHASE 1:
  ├─ Debater A generates position independently → "Yes, because..."
  ├─ Debater B generates position independently → "No, because..."
  └─ Consensus check → No consensus

PHASE 2 (3+ rounds):
  ├─ Round 1:
  │  ├─ A argues with CoT
  │  └─ B responds with CoT
  ├─ Round 2:
  │  ├─ A argues (sees round 1) with CoT
  │  └─ B responds (sees A's argument) with CoT
  ├─ Round 3:
  │  ├─ A argues (sees rounds 1-2) with CoT
  │  └─ B responds (sees A's argument) with CoT
  └─ Convergence check → If same 2 rounds, stop

PHASE 3:
  ├─ Judge receives full transcript
  └─ Judge produces:
     ├─ CoT analysis
     ├─ Strongest A
     ├─ Strongest B
     ├─ Weakest A
     ├─ Weakest B
     ├─ Verdict
     └─ Confidence (1-5)

PHASE 4:
  ├─ Compare verdict to ground truth
  └─ Record match/mismatch

OUTPUT: Complete DebateTranscript with all data
```

## Key Design Decisions

### 1. Independent Initial Positions
- **Why**: Avoids anchoring effects; each debater generates genuine position
- **How**: API calls sequential without sharing responses

### 2. Full Transcript Context
- **Why**: Ensures debaters engage with each other's arguments
- **How**: Rebuild transcript after each round, pass to next debater

### 3. Adaptive Stopping
- **Why**: Avoids unnecessary rounds when debate converged
- **How**: Track committed answers per round; stop if 2 consecutive rounds match

### 4. Structured Judge Output
- **Why**: Enables systematic analysis and comparison
- **How**: Prompt requires specific format; parse structured fields

### 5. Chain-of-Thought in All Phases
- **Why**: Improves reasoning quality (Wei et al., 2022)
- **How**: Every debater and judge output includes step-by-step reasoning

## Customization

### Adjust Debate Parameters

```python
pipeline = DebatePipeline(
    api_client=client,
    min_rounds=5,        # Require at least 5 rounds
    max_rounds=15        # Allow up to 15 rounds
)
```

### Use Different Model

```python
from src.utils.debate_api_client import DebateAPIClient

client = DebateAPIClient(model="claude-opus-4-1")
pipeline = DebatePipeline(api_client=client)
```

### Modify Prompts

Override prompt generation methods:

```python
class CustomPipeline(DebatePipeline):
    def _prompt_debater_argument(self, ...):
        # Custom prompt template
        return "..."
```

## Output Files

After running debates:

```
data/results/
├── debate_001.json          # Individual debate results
├── debate_002.json
├── ...
├── batch_results.json       # All debates combined
└── report.json              # Analysis report
```

### Report Contents

```json
{
  "total_debates": 5,
  "debates_with_consensus": 1,
  "debates_with_convergence": 2,
  "average_rounds": 4.2,
  "average_confidence": 3.8,
  "accuracy_vs_ground_truth": 0.80,
  "debates": [...]
}
```

## Troubleshooting

### Pipeline stops at Phase 1
- Check API key in environment
- Verify question format
- Check mock responses if using MockAPIClient

### Rounds exceed max_rounds
- Increase `max_rounds` parameter
- Debaters may not be converging
- Check if adaptive stopping criterion is working

### Judge confidence always same value
- Check judge prompt is being sent correctly
- Verify confidence parsing in `_parse_judge_analysis`
- Ensure model receives format instructions

## References

- Irving et al. (2018): "AI Safety via Debate" - arXiv:1805.00899
- Liang et al. (2024): Multi-Agent Debate - EMNLP 2024
- Wei et al. (2022): Chain-of-Thought Prompting - NeurIPS 2022
