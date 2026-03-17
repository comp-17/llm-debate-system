# Multi-Agent Jury Panel System

## Overview

This module implements a comprehensive multi-agent judge panel inspired by **VERDICT** (Kalra et al., 2025), **Kenton et al. (2024)** on scalable oversight, and **Wang et al. (2023)** self-consistency principles.

### Key Features

✓ **Type-Safe Jury Members** - Each judge has well-defined verdict structure with reasoning quality scoring  
✓ **Multiple Decision Modes** - Independent, majority vote, deliberation, weighted voting  
✓ **Multi-Round Deliberation** - Judges can reconsider verdicts based on colleagues' reasoning  
✓ **Disagreement Analysis** - Quantifies jury consensus vs unanimity  
✓ **Difficulty Correlation** - Analyzes how question difficulty affects jury disagreement  
✓ **Reasoning Quality Scoring** - Evaluates quality of individual judge reasoning (0-1 scale)  
✓ **Chain-of-Thought Integration** - Optional CoT reasoning for all judges (Wang et al., 2023)  

---

## Architecture

### Components

```
EnhancedJuryMember (Individual Judge)
├── Independent evaluation with CoT
├── Deliberation-aware reasoning
├── Reasoning quality scoring
└── Verdict history tracking

EnhancedJuryPanel (Judge Coordinator)
├── Independent evaluation phase
├── Multi-round deliberation
├── Consensus determination
├── Metrics computation
└── Single-judge comparison

JuryEvaluationFramework (Experiment Manager)
├── Dual evaluation (single judge + jury)
├── Ground truth comparison
├── Difficulty estimation
├── Analysis suite
└── Results persistence
```

### Jury Modes

1. **INDEPENDENT**: Each judge independently decides; no communication
2. **MAJORITY_VOTE**: Simple majority vote determines winner
3. **DELIBERATION**: Multi-round discussion with verdict reconsideration
4. **WEIGHTED**: Confidence-weighted voting accounting for reasoning quality

---

## Usage Example

### Basic Jury Evaluation

```python
from src.agents.jury_panel import EnhancedJuryPanel, JuryMode
from src.utils.api_client import APIClient

# Initialize
api_client = APIClient(model="claude-3-5-sonnet-20241022")
jury = EnhancedJuryPanel(
    api_client,
    jury_size=3,
    mode=JuryMode.DELIBERATION,
    max_deliberation_rounds=2,
    use_chain_of_thought=True
)

# Evaluate debate
result = jury.evaluate(
    question="Is AI regulation necessary?",
    debater_a_position="Yes, strict regulation prevents misuse...",
    debater_b_position="No, regulation stifles innovation...",
    debate_transcript="[full debate]",
    question_difficulty=0.65  # Optional: for analysis
)

# Access results
print(f"Winner: {result['final_consensus']['winner']}")
print(f"Unanimity: {result['disagreement_metrics']['unanimous']}")
print(f"Deliberation rounds: {len(result['deliberation_outcomes'])}")
```

### Jury vs Single Judge Comparison

```python
from src.agents.judges import JudgeSingle
from src.utils.jury_evaluation import JuryEvaluationFramework

# Setup
judge_single = JudgeSingle(api_client)
jury_panel = EnhancedJuryPanel(api_client, jury_size=3, mode=JuryMode.DELIBERATION)
framework = JuryEvaluationFramework(results_dir="data/results")

# Evaluate same debate with both
single_result, jury_result, comparison = framework.evaluate_debate(
    judge_single,
    jury_panel,
    question="...",
    debater_a_position="...",
    debater_b_position="...",
    debate_transcript="...",
    ground_truth="Debater A",  # Optional
    question_id="q_001"
)

# Analyze results
accuracy = framework.analyze_accuracy_comparison()
difficulty_analysis = framework.analyze_disagreement_vs_difficulty()

# Save all results
framework.save_results("jury_evaluation.json")
framework.print_summary()
```

---

## Metrics & Analysis

### Disagreement Metrics

```python
disagreement_metrics = {
    "unanimous": bool,              # All judges agree
    "disagreement_level": float,    # 0.0=unanimous, 1.0=max disagreement
    "confidence_variance": float,   # Variance in confidence (1-5)
    "winner_split": dict,           # {Debater A: n, Debater B: n}
    "confidence_by_winner": dict    # {Debater A: [3,4,5], Debater B: [2,3]}
}
```

**Interpretation**:
- **unanimity=True** + **disagreement_level=0.0**: All judges agree strongly
- **disagreement_level > 0.5**: Significant disagreement, potentially difficult case
- **High confidence_variance**: Judges have varying certainty

### Deliberation Impact

Tracks whether deliberation improves consensus:

```python
deliberation_outcomes = [
    {
        "round_number": 1,
        "pre_deliberation_agreement": 0.66,   # % agreeing before
        "post_deliberation_agreement": 0.95,  # % agreeing after
        "changed_verdicts": 1,                # Judges who changed mind
        "consensus_confidence_change": 0.5    # Confidence shift
    },
    ...
]
```

**Key Question**: Does deliberation improve agreement without sacrificing confidence?

### Reasoning Quality Scoring

Each judge's reasoning is scored 0-1 based on:
- **Step-by-step reasoning** (0.2): Multiple logical steps
- **Evidence reference** (0.2): Cites debate content
- **Both positions addressed** (0.2): Discusses both debaters
- **Clear justification** (0.2): Explains verdict
- **Confidence calibration** (0.2): Confidence matches reasoning strength

---

## Difficulty Analysis

### Question Difficulty Estimation

Automatically scores questions 0-1 based on:
- Word count (> 50 words: +0.15)
- Negation presence: +0.15
- Temporal reasoning: +0.1
- Numerical reasoning: +0.1
- Conditional logic: +0.1

### Disagreement ↔ Difficulty Correlation

Analyzes whether jury disagreement increases with question difficulty:

```python
analysis = framework.analyze_disagreement_vs_difficulty()
# Returns:
# {
#     "overall_correlation": 0.35,
#     "by_difficulty": {
#         "easy": {"count": 10, "avg_disagreement": 0.15, "unanimous_percentage": 80},
#         "medium": {"count": 15, "avg_disagreement": 0.35, "unanimous_percentage": 40},
#         "hard": {"count": 8, "avg_disagreement": 0.65, "unanimous_percentage": 10}
#     }
# }
```

**Expected Pattern**: Hard questions → higher disagreement, lower unanimity

---

## Accuracy Comparison

When ground truth is available, compares:

```python
accuracy = framework.analyze_accuracy_comparison()
# {
#     "single_judge_accuracy": 78.0,        # % correct
#     "jury_accuracy": 85.0,                # % correct
#     "jury_advantage": 7.0,                # percentage point improvement
#     "when_disagreed_jury_correct": 75.0,  # % when jury disagreed with single judge
# }
```

---

## Uncertainty Calibration

Analyzes whether disagreement indicates uncertainty:

```python
uncertainty = framework.analyze_disagreement_as_uncertainty()
# {
#     "correlations": {
#         "disagreement_vs_confidence": -0.42  # Negative = disagreement ~ low confidence
#     },
#     "high_disagreement_cases": {
#         "count": 12,
#         "avg_confidence": 2.8,
#         "avg_reasoning_quality": 0.62
#     }
# }
```

---

## Configuration

Update `config.yaml` to control jury behavior:

```yaml
judge:
  single_judge: true           # Run single judge baseline
  jury_size: 3                 # Number of jury members (3-5 recommended)
  jury_mode: "deliberation"    # Options: independent, majority_vote, deliberation, weighted
  max_deliberation_rounds: 2   # Max rounds for deliberation mode

evaluation:
  compute_statistics: true
  save_results: true
  results_dir: "data/results"
```

---

## Running Experiments

### Full Experiment (Jury vs Single Judge)

```bash
python run_jury_experiments.py --config config.yaml --samples 20
```

Runs 20 debates and compares single judge vs jury on each.

### Ablation Study

```bash
python run_jury_experiments.py --ablation
```

Compares configurations:
- Single Judge
- 3-person Jury (independent)
- 3-person Jury (deliberation)
- 5-person Jury (independent)
- 5-person Jury (deliberation)

---

## Output Format

Results saved as `jury_experiment_results.json`:

```json
{
  "summary": {
    "total_comparisons": 20,
    "avg_jury_size": 3,
    "avg_disagreement": 0.23,
    "unanimity_rate": 65
  },
  "comparisons": [
    {
      "question_id": "q_001",
      "question_text": "...",
      "question_difficulty": 0.45,
      "single_judge_winner": "Debater A",
      "single_judge_confidence": 4,
      "jury_winner": "Debater A",
      "jury_confidence": 4.2,
      "jury_unanimous": true,
      "jury_disagreement_level": 0.0,
      "jury_avg_reasoning_quality": 0.78,
      "verdicts_match": true
    },
    ...
  ],
  "analysis": {
    "accuracy_comparison": {...},
    "disagreement_vs_difficulty": {...},
    "deliberation_impact": {...},
    "disagreement_as_uncertainty": {...}
  }
}
```

---

## Expected Results

Based on **Kenton et al. (2024)** and **VERDICT (Kalra et al., 2025)**:

| Metric | Expected Value | Interpretation |
|--------|---|---|
| Jury Accuracy vs Single | +5-15% | Panel should outperform single judge |
| Unanimity Rate | 60-75% | Most questions should have clear consensus |
| Disagreement ↔ Difficulty Correlation | 0.3-0.5 | Harder questions → more disagreement |
| Deliberation Agreement Improvement | +10-20% | Deliberation drives consensus |
| Reasoning Quality (Jury) | 0.70-0.80 | Most judges reason clearly |

---

## Theoretical Foundations

This implementation is grounded in:

1. **Irving et al. (2018)** - Debate as PSPACE-complete verification
2. **Wang et al. (2023)** - Self-consistency & chain-of-thought reasoning
3. **Kenton et al. (2024)** - Weak LLMs can judge strong LLMs effectively
4. **Kalra et al. (2025)** - VERDICT: Modular reasoning units with verification patterns
5. **Brown-Cohen et al. (2024)** - Doubly-efficient debate with constant oracle queries

---

## Advanced Usage

### Custom Jury Member Initialization

```python
jury = EnhancedJuryPanel(
    api_client,
    jury_size=5,
    mode=JuryMode.WEIGHTED,  # Use confidence weighting
    use_chain_of_thought=True,
    max_deliberation_rounds=3
)
```

### Accessing Individual Judge Reasoning

```python
result = jury.evaluate(...)

for verdict in result['final_verdicts']:
    print(f"Member {verdict['member_id']}:")
    print(f"  Winner: {verdict['winner']}")
    print(f"  Confidence: {verdict['confidence']}/5")
    print(f"  Reasoning Quality: {verdict['reasoning_quality_score']:.2f}")
```

### Fine-Grained Difficulty Analysis

```python
easy_cases = [c for c in comparisons if c.question_difficulty < 0.33]
hard_cases = [c for c in comparisons if c.question_difficulty >= 0.67]

easy_unanimity = sum(1 for c in easy_cases if c.jury_unanimous) / len(easy_cases)
hard_unanimity = sum(1 for c in hard_cases if c.jury_unanimous) / len(hard_cases)

print(f"Easy questions unanimity: {easy_unanimity:.0%}")
print(f"Hard questions unanimity: {hard_unanimity:.0%}")
```

---

## Troubleshooting

**Q: Why is disagreement high for seemingly simple questions?**  
A: Could indicate ambiguous debate content or inconsistent judge reasoning. Check reasoning quality scores.

**Q: Deliberation isn't improving agreement**  
A: Try increasing max_deliberation_rounds or using weighted voting instead.

**Q: Some judges giving low confidence despite agreeing with others**  
A: Check reasoning_quality_score; low quality → low calibrated confidence.

---

## Future Enhancements

- [ ] Dynamic jury sizing based on initial disagreement
- [ ] Judge specialization (e.g., "logic expert", "evidence evaluator")
- [ ] Structured argumentation mining from debate transcripts
- [ ] Bayesian belief updating during deliberation
- [ ] Cross-debate bias detection

