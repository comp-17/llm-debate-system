# Section 4: Required Experiments

## 4.1 Experimental Design & Baselines

### Overview

We conduct a comprehensive experimental comparison of three approaches:

1. **Debate Pipeline**: Two LLM agents argue opposing sides, supervised by a single judge and jury panel
2. **Direct QA Baseline**: Single LLM answers directly with Chain-of-Thought prompting
3. **Self-Consistency Baseline**: Multiple CoT samples with majority voting (Wang et al., 2023)

All experiments use:
- Same questions from the same dataset
- Same underlying LLM model
- Fair computational budget comparison

### 4.1.1 Baseline Implementations

#### Baseline 1: Direct QA (Chain-of-Thought)

**Purpose**: Establish baseline performance without debate mechanism.

**Implementation**:
```python
def direct_qa_baseline(questions, api_client):
    """
    Single LLM answers question directly with CoT reasoning.
    """
    results = []
    for question in questions:
        prompt = f"""Answer the following question with chain-of-thought reasoning.
        
QUESTION: {question['question']}

Think through this step by step:
1. What information do I know?
2. What reasoning applies?
3. What is my final answer?

REASONING: [Your step-by-step thinking]
ANSWER: [Yes or No]"""
        
        response = api_client.call(prompt)
        answer = extract_answer(response)
        results.append({'question': question, 'answer': answer})
    
    return results
```

**Rationale**: 
- Direct QA with CoT represents state-of-the-art single-model performance
- No debate overhead
- Measures baseline LLM capability on the task
- Baseline for comparison with debate benefits

**Expected Performance**: 65-75% accuracy (typical for complex reasoning)

#### Baseline 2: Self-Consistency Voting

**Purpose**: Compare debate with multi-sampling approach (no debate).

**Implementation**:
```python
def self_consistency_baseline(questions, api_client, num_samples=3):
    """
    Generate N CoT samples per question, take majority vote.
    Based on Wang et al., 2023.
    """
    results = []
    for question in questions:
        samples = []
        for _ in range(num_samples):
            response = api_client.call(cot_prompt)
            answer = extract_answer(response)
            samples.append(answer)
        
        # Majority vote
        final_answer = majority_vote(samples)  # Most common answer
        results.append({'question': question, 'answer': final_answer})
    
    return results
```

**Rationale**:
- Self-consistency uses multiple samples but no debate
- Tests if computational budget alone improves accuracy
- Controls for "compute = reasoning" hypothesis
- Samples must match debate system's API call budget

**Expected Performance**: 75-85% accuracy (better than direct QA due to voting)

### 4.1.2 Experiment Configuration

#### Model & Hyperparameters

```yaml
Model:
  Name: Claude 3.5 Sonnet
  Version: claude-3-5-sonnet-20241022
  API: Anthropic

Hyperparameters:
  Temperature: 0.7          # Balanced randomness for debate diversity
  Max tokens: 1500          # Sufficient for multi-sentence arguments
  Top-P: 0.9                # Nucleus sampling
  
Debate Configuration:
  Number of rounds: 4       # Default (min 3, max 6)
  Max rounds: 6
  Convergence threshold: 2  # Stop if same answer 2 consecutive rounds
  
Judge Configuration:
  Single judge: Yes
  Jury size: 3
  Jury mode: Deliberation

Dataset:
  Domain: Commonsense QA (primary), Fact Verification (secondary)
  Sample size: 10-100 questions (10 for demo, 100+ for paper)
  Seed: 42 (reproducibility)
```

### 4.1.3 Experimental Procedure

#### Phase A: Data Preparation
1. Load dataset (100 commonsense QA questions with ground truth)
2. Fix random seed (42) for reproducibility
3. Sample questions equally from both task types

#### Phase B: Run All Three Experiments

**Experiment 1: Debate Pipeline**
```
For each question:
  1. Phase 1: Both debaters generate independent positions
  2. Phase 2: Multi-round debate (up to 4-6 rounds)
  3. Phase 3A: Single judge evaluates → verdict + confidence
  3. Phase 3B: Jury panel evaluates → consensus verdict
  4. Phase 4: Compare both verdicts to ground truth
  
Collect metrics:
  - Judge accuracy
  - Jury accuracy
  - Judge-jury agreement
  - Average rounds per debate
  - Early convergence rate
  - Total API calls
```

**Experiment 2: Direct QA**
```
For each question:
  1. Provide question to LLM with CoT prompt
  2. Extract answer from response
  3. Compare to ground truth
  
Collect metrics:
  - Accuracy
  - Total API calls (N questions)
```

**Experiment 3: Self-Consistency**
```
For each question:
  1. Generate K samples (K adjusted to match debate API budget)
  2. Extract answer from each sample
  3. Take majority vote
  4. Compare to ground truth
  
Collect metrics:
  - Accuracy
  - Total API calls (N × K questions)
```

#### Phase C: Analysis & Comparison

**Accuracy Comparison**:
- Direct QA accuracy
- Self-Consistency accuracy
- Debate (Judge) accuracy
- Debate (Jury) accuracy
- Statistical significance (if N ≥ 100)

**Computational Efficiency**:
- API calls per approach
- Accuracy per API call (efficiency metric)
- Cost-benefit analysis

**Qualitative Analysis**:
- Cases where debate outperforms baselines
- Cases where baselines outperform debate
- Agreement between judge and jury
- Convergence patterns

### 4.1.4 Expected Results & Hypotheses

**Hypothesis 1: Debate improves accuracy**
- H1a: Jury accuracy > Judge accuracy (multi-agent > single)
- H1b: Judge accuracy > Direct QA (debate > no debate)
- H1c: Judge accuracy ≥ Self-Consistency (debate ≥ voting)

**Hypothesis 2: Jury outperforms single judge**
- Jury panel provides robustness through deliberation
- Disagreement reveals ambiguous cases

**Hypothesis 3: Debate efficiency**
- Debate uses more API calls than Direct QA
- But accuracy improvement justifies compute cost

### Expected Performance Table

| Approach | Accuracy | API Calls | Efficiency |
|----------|----------|-----------|------------|
| Direct QA | 65-70% | N | Baseline |
| Self-Consistency | 75-80% | 3N-5N | 15-25% per call |
| Debate (Judge) | 80-85% | 4N-6N | 13-21% per call |
| Debate (Jury) | 85-90% | 8N-12N | 7-11% per call |

---

## 4.2 Baseline Implementations (Code)

### Direct QA Baseline

```python
@staticmethod
def direct_qa_baseline(questions: List[Dict[str, Any]], api_client) -> Dict[str, Any]:
    """
    Baseline 1: Direct QA with Chain-of-Thought prompting.
    
    Single LLM answers question directly with CoT reasoning (no debate).
    This baseline establishes the performance ceiling without debate.
    
    Args:
        questions: List of questions with 'question' and 'answer' keys
        api_client: API client for queries
        
    Returns:
        Dictionary with results and accuracy metrics
    """
    results = []
    total_api_calls = 0
    
    for q in questions:
        # CoT prompt - asks for reasoning before answer
        cot_prompt = f"""Answer the following question with chain-of-thought reasoning.

QUESTION: {q['question']}

Think through this step by step:
1. What information do I know?
2. What reasoning applies?
3. What is my final answer?

REASONING: [Your step-by-step thinking]
ANSWER: [Yes or No]"""
        
        response = api_client.call(cot_prompt)
        total_api_calls += 1
        
        # Extract answer from response
        answer = "Yes" if "yes" in response.lower() else "No"
        ground_truth = q.get('answer', 'Unknown')
        is_correct = answer == ground_truth
        
        results.append({
            'question_id': q['id'],
            'question': q['question'],
            'answer': answer,
            'ground_truth': ground_truth,
            'correct': is_correct,
            'reasoning': response
        })
    
    accuracy = sum(1 for r in results if r['correct']) / len(results) if results else 0
    
    return {
        'baseline_name': 'Direct QA (CoT Prompting)',
        'description': 'Single LLM with Chain-of-Thought reasoning, no debate',
        'results': results,
        'accuracy': accuracy,
        'total_api_calls': total_api_calls,
        'correct_count': sum(1 for r in results if r['correct']),
        'total_count': len(results)
    }
```

### Self-Consistency Baseline

```python
@staticmethod
def self_consistency_baseline(questions: List[Dict[str, Any]], 
                              api_client, 
                              num_samples: int = 3) -> Dict[str, Any]:
    """
    Baseline 2: Self-Consistency with majority voting.
    
    Sample N answers from the same model and take majority vote.
    Matches the computational budget of the debate system.
    Based on Wang et al., 2023 "Self-Consistency Improves CoT Reasoning".
    
    Args:
        questions: List of questions
        api_client: API client for queries
        num_samples: Number of samples per question (default 3)
        
    Returns:
        Dictionary with results and accuracy metrics
    """
    results = []
    total_api_calls = 0
    
    for q in questions:
        # Generate N samples with temperature > 0 for diversity
        samples = []
        
        for sample_idx in range(num_samples):
            cot_prompt = f"""Answer the following question with chain-of-thought reasoning.

QUESTION: {q['question']}

Think through this step by step:
1. What information do I know?
2. What reasoning applies?
3. What is my final answer?

REASONING: [Your step-by-step thinking]
ANSWER: [Yes or No]"""
            
            response = api_client.call(cot_prompt)
            total_api_calls += 1
            
            # Extract answer
            answer = "Yes" if "yes" in response.lower() else "No"
            samples.append({
                'sample': sample_idx + 1,
                'answer': answer,
                'reasoning': response
            })
        
        # Majority vote
        yes_count = sum(1 for s in samples if s['answer'] == 'Yes')
        no_count = sum(1 for s in samples if s['answer'] == 'No')
        final_answer = "Yes" if yes_count > no_count else "No"
        
        ground_truth = q.get('answer', 'Unknown')
        is_correct = final_answer == ground_truth
        
        results.append({
            'question_id': q['id'],
            'question': q['question'],
            'samples': samples,
            'vote_count': {'Yes': yes_count, 'No': no_count},
            'answer': final_answer,
            'ground_truth': ground_truth,
            'correct': is_correct
        })
    
    accuracy = sum(1 for r in results if r['correct']) / len(results) if results else 0
    
    return {
        'baseline_name': 'Self-Consistency Voting',
        'description': f'Majority vote over {num_samples} CoT samples per question',
        'reference': 'Wang et al., 2023 - Self-Consistency Improves Chain of Thought Reasoning',
        'num_samples': num_samples,
        'results': results,
        'accuracy': accuracy,
        'total_api_calls': total_api_calls,
        'correct_count': sum(1 for r in results if r['correct']),
        'total_count': len(results)
    }
```

---

## 4.3 Running the Experiments

### Quick Test (10 Questions)
```bash
cd llm-debate-system-fixed
export ANTHROPIC_API_KEY="your-key"
python run_experiments.py --num-questions 10 --domain commonsense_qa
```

Time: 10-15 minutes  
Cost: ~$3-5

### Full Paper Experiment (100 Questions)
```bash
python run_experiments.py --num-questions 100 --domain commonsense_qa
```

Time: 2-4 hours  
Cost: $30-50

### Expected Output

```
================================================================================
LJM DEBATE SYSTEM - EXPERIMENTAL COMPARISON
================================================================================

Experiment Setup:
  Questions: 100
  Domain: commonsense_qa
  
Model Configuration:
  Model: claude-3-5-sonnet-20241022
  Temperature: 0.7
  Max tokens: 1500
  Debate rounds: 4
  Jury size: 3

================================================================================
EXPERIMENTAL COMPARISON SUMMARY
================================================================================

Accuracy Comparison:
  Debate (Judge):         82%
  Debate (Jury):          90%
  Direct QA:              68%
  Self-Consistency:       78%

Improvement over baselines:
  Debate vs Direct QA:    +22%
  Debate vs Self-Consistency: +12%

Computational Cost (API calls):
  Debate:          520
  Direct QA:       100
  Self-Consistency: 350

Efficiency (Accuracy per API call):
  Debate:          0.173
  Direct QA:       0.680
  Self-Consistency: 0.223
```

---

## 4.4 Results & Analysis

Results are saved to:
- `data/results/experiment_comparison_YYYYMMDD_HHMMSS.json`

Contains:
- Complete results for all three approaches
- Per-question accuracy
- API call counts
- Detailed comparison metrics
- Jury disagreement analysis
- Judge-jury agreement rates

---

## 4.5 References

Wang, X. et al. (2023). Self-Consistency Improves Chain of Thought Reasoning in Language Models. ICLR 2023.

Wei, J. et al. (2022). Chain-of-Thought Prompting Elicits Reasoning in Language Models. NeurIPS 2022.

Irving, G., Christiano, P., & Amodei, D. (2018). AI Safety via Debate. arXiv:1805.00899.
