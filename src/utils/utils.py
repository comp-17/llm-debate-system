"""Utility functions for prompt management, dataset handling, and logging."""

import json
import os
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

def load_config(config_path: str = "config.yaml") -> dict:
    """Load YAML configuration file."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def load_prompt(prompt_name: str, config_dir: str = "prompts") -> str:
    """Load prompt template from file."""
    prompt_path = os.path.join(config_dir, f"{prompt_name}.txt")
    with open(prompt_path, 'r') as f:
        return f.read()

def format_prompt(template: str, **kwargs) -> str:
    """Format prompt template with variables."""
    return template.format(**kwargs)

def create_debate_context(round_num: int, previous_arguments: Optional[List[Dict]] = None) -> str:
    """Create context string for debate rounds."""
    if round_num == 1:
        return "**ROUND 1 (INITIAL ARGUMENTS):**\nThis is the first round. Present your initial position clearly."
    
    context = f"\n\n**ROUND {round_num} (CONTINUED DEBATE):**\n\nPrevious debate history:\n"
    if previous_arguments:
        for i, arg in enumerate(previous_arguments[-2:], 1):  # Show last 2 arguments
            context += f"\n[Round {arg['round']}] {arg['debater']}: {arg['argument'][:500]}...\n"
    return context

class DebateLogger:
    """Logger for debate transcripts and results."""
    
    def __init__(self, config: dict):
        """Initialize logger with configuration."""
        self.config = config
        self.transcript_dir = config['logging']['transcript_dir']
        self.results_dir = config['evaluation']['results_dir']
        
        # Create directories if they don't exist
        os.makedirs(self.transcript_dir, exist_ok=True)
        os.makedirs(self.results_dir, exist_ok=True)
        
        self.current_debate = None
        
    def start_debate(self, question_id: str, question: str) -> None:
        """Start logging a new debate."""
        self.current_debate = {
            'timestamp': datetime.now().isoformat(),
            'question_id': question_id,
            'question': question,
            'rounds': [],
            'judge_verdict': None,
            'jury_verdicts': None,
            'jury_consensus': None,
            'ground_truth': None,
            'metadata': {}
        }
    
    def log_initial_positions(self, debater_a_answer: str, debater_b_answer: str) -> None:
        """Log initial positions."""
        if not self.current_debate:
            return
        self.current_debate['initial_positions'] = {
            'debater_a': debater_a_answer,
            'debater_b': debater_b_answer
        }
    
    def log_round(self, round_num: int, debater_a_arg: str, debater_b_arg: str) -> None:
        """Log a debate round."""
        if not self.current_debate:
            return
        self.current_debate['rounds'].append({
            'round': round_num,
            'debater_a_argument': debater_a_arg,
            'debater_b_argument': debater_b_arg
        })
    
    def log_judge_verdict(self, verdict: Dict[str, Any]) -> None:
        """Log single judge verdict."""
        if not self.current_debate:
            return
        self.current_debate['judge_verdict'] = verdict
    
    def log_jury_verdicts(self, verdicts: List[Dict], consensus: Dict) -> None:
        """Log jury verdicts and consensus."""
        if not self.current_debate:
            return
        self.current_debate['jury_verdicts'] = verdicts
        self.current_debate['jury_consensus'] = consensus
    
    def set_ground_truth(self, ground_truth: str) -> None:
        """Set ground truth answer."""
        if self.current_debate:
            self.current_debate['ground_truth'] = ground_truth
    
    def save_debate(self) -> str:
        """Save current debate transcript to file."""
        if not self.current_debate:
            raise ValueError("No active debate to save")
        
        filename = f"{self.current_debate['question_id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(self.transcript_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(self.current_debate, f, indent=2)
        
        print(f"Debate transcript saved to {filepath}")
        return filepath
    
    def save_results(self, results: Dict[str, Any], filename: str) -> str:
        """Save analysis results to file."""
        filepath = os.path.join(self.results_dir, filename)
        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to {filepath}")
        return filepath

class DebateDataset:
    """Dataset manager for debate questions."""
    
    @staticmethod
    def load_commonsense_qa() -> List[Dict[str, Any]]:
        """Load commonsense QA questions (sample)."""
        return [
            {
                'id': 'commonsense_001',
                'question': 'Did the Roman Empire exist at the same time as the Mayan civilization?',
                'answer': 'Yes',
                'explanation': 'The Roman Empire (~27 BC - 476 AD) and Mayan civilization (~2000 BC - 1500s AD) overlapped for approximately 500 years.'
            },
            {
                'id': 'commonsense_002',
                'question': 'Can a penguin fly?',
                'answer': 'No',
                'explanation': 'Penguins are flightless birds. While they cannot fly through the air, they can "fly" through water with exceptional speed and agility.'
            },
            {
                'id': 'commonsense_003',
                'question': 'Do all mammals lay eggs?',
                'answer': 'No',
                'explanation': 'Most mammals give birth to live young. Only monotremes (platypus and echidnas) lay eggs.'
            },
            {
                'id': 'commonsense_004',
                'question': 'Is the Great Wall of China visible from space?',
                'answer': 'No',
                'explanation': 'The Great Wall is visible from low Earth orbit with proper equipment, but not from the Moon or high orbit with the naked eye as commonly believed.'
            },
            {
                'id': 'commonsense_005',
                'question': 'Do fish sleep?',
                'answer': 'Yes',
                'explanation': 'Fish do exhibit sleep-like states, though they lack eyelids and may not sleep the way mammals do.'
            }
        ]
    
    @staticmethod
    def load_fact_verification() -> List[Dict[str, Any]]:
        """Load fact verification questions (sample)."""
        return [
            {
                'id': 'factcheck_001',
                'question': 'Does vitamin C supplementation prevent the common cold in the general population?',
                'answer': 'No',
                'explanation': 'Meta-analyses (e.g., Cochrane reviews) show vitamin C does not prevent colds in the general population, though it may slightly reduce symptom duration (~8%).'
            },
            {
                'id': 'factcheck_002',
                'question': 'Is coffee consumption linked to increased risk of heart disease?',
                'answer': 'No',
                'explanation': 'Recent large-scale studies show moderate coffee consumption (3-5 cups daily) is associated with cardiovascular benefits, not increased risk.'
            },
            {
                'id': 'factcheck_003',
                'question': 'Do vaccines cause autism?',
                'answer': 'No',
                'explanation': 'Extensive research involving millions of children has found no link between vaccines and autism. The original study claiming this was fraudulent.'
            },
            {
                'id': 'factcheck_004',
                'question': 'Is sugar the primary cause of Type 2 diabetes?',
                'answer': 'No',
                'explanation': 'While sugar consumption contributes to obesity (a risk factor), Type 2 diabetes is multifactorial involving genetics, physical activity, and overall diet quality.'
            },
            {
                'id': 'factcheck_005',
                'question': 'Do humans use only 10% of their brain?',
                'answer': 'No',
                'explanation': 'Neuroimaging studies show humans use virtually all brain regions, and most of the brain is active almost all the time.'
            }
        ]
    
    @staticmethod
    def load_dataset(domain: str, num_samples: Optional[int] = None, seed: int = 42) -> List[Dict[str, Any]]:
        """Load dataset for specified domain."""
        if domain == 'commonsense_qa':
            dataset = DebateDataset.load_commonsense_qa()
        elif domain == 'fact_verification':
            dataset = DebateDataset.load_fact_verification()
        else:
            raise ValueError(f"Unknown domain: {domain}")
        
        if num_samples:
            import random
            random.seed(seed)
            dataset = random.sample(dataset, min(num_samples, len(dataset)))
        
        return dataset
