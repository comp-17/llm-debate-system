"""Evaluation and analysis of debate results."""

import json
import os
from typing import Dict, List, Any
from collections import Counter

class DebateEvaluator:
    """Evaluates debate results and computes statistics."""
    
    @staticmethod
    def compute_accuracy(results: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Compute accuracy of debate conclusions against ground truth.
        
        Args:
            results: List of debate results
            
        Returns:
            Dictionary with accuracy metrics
        """
        metrics = {
            'total_debates': len(results),
            'debates_with_ground_truth': 0,
            'judge_accuracy': 0,
            'jury_accuracy': 0,
            'convergence_accuracy': 0
        }
        
        judge_correct = 0
        jury_correct = 0
        convergence_correct = 0
        count_with_truth = 0
        
        for result in results:
            if 'error' in result:
                continue
            
            ground_truth = result.get('ground_truth')
            if not ground_truth:
                continue
            
            count_with_truth += 1
            
            # Check judge accuracy
            if 'judge_verdict' in result:
                judge_winner = result['judge_verdict'].get('winner')
                if judge_winner and self._extract_answer(judge_winner) == ground_truth:
                    judge_correct += 1
            
            # Check jury accuracy
            if 'jury_results' in result:
                jury_winner = result['jury_results']['consensus'].get('winner')
                if jury_winner and self._extract_answer(jury_winner) == ground_truth:
                    jury_correct += 1
            
            # Check convergence accuracy
            final_pos_a = result.get('debater_a_final_position')
            if final_pos_a == ground_truth:
                convergence_correct += 1
        
        if count_with_truth > 0:
            metrics['debates_with_ground_truth'] = count_with_truth
            metrics['judge_accuracy'] = judge_correct / count_with_truth
            metrics['jury_accuracy'] = jury_correct / count_with_truth
            metrics['convergence_accuracy'] = convergence_correct / count_with_truth
        
        return metrics
    
    @staticmethod
    def _extract_answer(winner_string: str) -> str:
        """Extract Yes/No from winner string."""
        if 'Debater A' in winner_string:
            return 'Yes'  # Debater A argues for Yes
        elif 'Debater B' in winner_string:
            return 'No'   # Debater B argues for No
        return 'Unknown'
    
    @staticmethod
    def compute_judge_agreement(results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Compute agreement between single judge and jury consensus.
        
        Args:
            results: List of debate results
            
        Returns:
            Agreement statistics
        """
        agreement_count = 0
        total_count = 0
        
        judge_verdicts = []
        jury_verdicts = []
        
        for result in results:
            if 'error' in result:
                continue
            
            if 'judge_verdict' in result and 'jury_results' in result:
                total_count += 1
                judge_winner = result['judge_verdict'].get('winner')
                jury_winner = result['jury_results']['consensus'].get('winner')
                
                if judge_winner:
                    judge_verdicts.append(judge_winner)
                if jury_winner:
                    jury_verdicts.append(jury_winner)
                
                if judge_winner == jury_winner:
                    agreement_count += 1
        
        agreement_rate = agreement_count / total_count if total_count > 0 else 0
        
        return {
            'agreement_rate': agreement_rate,
            'cases_compared': total_count,
            'agreement_count': agreement_count,
            'judge_verdicts_distribution': Counter(judge_verdicts),
            'jury_verdicts_distribution': Counter(jury_verdicts)
        }
    
    @staticmethod
    def analyze_jury_disagreement(results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze jury member disagreement (BONUS analysis).
        
        Args:
            results: List of debate results
            
        Returns:
            Disagreement analysis
        """
        analysis = {
            'total_debates': len(results),
            'unanimous_verdicts': 0,
            'split_verdicts': 0,
            'average_member_agreement': 0,
            'disagreement_cases': []
        }
        
        total_agreement_score = 0
        case_count = 0
        
        for result in results:
            if 'error' in result or 'jury_results' not in result:
                continue
            
            verdicts = result['jury_results']['individual_verdicts']
            if not verdicts:
                continue
            
            case_count += 1
            winners = [v.get('winner') for v in verdicts]
            winner_counts = Counter(winners)
            
            if len(winner_counts) == 1:
                analysis['unanimous_verdicts'] += 1
            else:
                analysis['split_verdicts'] += 1
                analysis['disagreement_cases'].append({
                    'question_id': result['question_id'],
                    'question': result['question'],
                    'member_verdicts': winners,
                    'consensus': result['jury_results']['consensus'].get('winner')
                })
            
            # Calculate agreement score (how much they agree)
            max_votes = max(winner_counts.values())
            agreement_score = max_votes / len(verdicts)
            total_agreement_score += agreement_score
        
        if case_count > 0:
            analysis['average_member_agreement'] = total_agreement_score / case_count
        
        return analysis
    
    @staticmethod
    def compute_debate_statistics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Compute general debate statistics.
        
        Args:
            results: List of debate results
            
        Returns:
            Statistical summary
        """
        stats = {
            'total_debates': len(results),
            'successful_debates': 0,
            'failed_debates': 0,
            'average_rounds': 0,
            'total_rounds': 0,
            'early_convergence': 0,
            'max_rounds_reached': 0
        }
        
        total_rounds = 0
        successful_count = 0
        
        for result in results:
            if 'error' in result:
                stats['failed_debates'] += 1
            else:
                stats['successful_debates'] += 1
                successful_count += 1
                rounds = result.get('rounds_completed', 0)
                total_rounds += rounds
                
                # Check for early convergence
                if rounds < 6:  # Assumed max rounds
                    stats['early_convergence'] += 1
                else:
                    stats['max_rounds_reached'] += 1
        
        if successful_count > 0:
            stats['average_rounds'] = total_rounds / successful_count
        
        stats['total_rounds'] = total_rounds
        
        return stats
    
    @staticmethod
    def generate_report(results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate comprehensive evaluation report.
        
        Args:
            results: List of debate results
            
        Returns:
            Complete evaluation report
        """
        evaluator = DebateEvaluator()
        
        report = {
            'summary': {
                'total_debates': len(results),
                'successful': sum(1 for r in results if 'error' not in r),
                'failed': sum(1 for r in results if 'error' in r)
            },
            'debate_statistics': evaluator.compute_debate_statistics(results),
            'accuracy_metrics': evaluator.compute_accuracy(results),
            'judge_agreement': evaluator.compute_judge_agreement(results),
            'jury_disagreement_analysis': evaluator.analyze_jury_disagreement(results)
        }
        
        return report


class BaselineComparison:
    """Compare debate system to baseline approaches."""
    
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
ANSWER: [Yes or No]

Respond now:"""
            
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
ANSWER: [Yes or No]

Respond now:"""
                
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
