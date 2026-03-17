#!/usr/bin/env python3
"""Flask web UI for the LLM Debate System."""

from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import json
import os
from src.utils.utils import load_config, DebateDataset
from src.orchestrator.debate_orchestrator import DebateOrchestrator
from src.utils.evaluation import DebateEvaluator
import threading

app = Flask(__name__, template_folder='src/ui/templates', static_folder='src/ui/static')
CORS(app)

# Global state
debate_state = {
    'running': False,
    'current_debate': None,
    'results': [],
    'config': None,
    'orchestrator': None
}

@app.route('/')
def index():
    """Serve the main UI page."""
    return render_template('index.html')

@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration."""
    config = load_config("config.yaml")
    return jsonify({
        'model': config['model']['name'],
        'dataset_domain': config['dataset']['domain'],
        'jury_size': config['judge']['jury_size'],
        'num_rounds': config['debate']['num_rounds']
    })

@app.route('/api/config', methods=['POST'])
def update_config():
    """Update configuration."""
    data = request.get_json()
    config = load_config("config.yaml")
    
    # Update allowed fields
    if 'num_samples' in data:
        config['dataset']['num_samples'] = data['num_samples']
    if 'num_rounds' in data:
        config['debate']['num_rounds'] = data['num_rounds']
    if 'jury_size' in data:
        config['judge']['jury_size'] = data['jury_size']
    
    return jsonify({'status': 'ok', 'config': config})

@app.route('/api/run-debate', methods=['POST'])
def run_debate_endpoint():
    """Run a single debate."""
    data = request.get_json()
    question = data.get('question')
    domain = data.get('domain', 'commonsense_qa')
    
    if not question:
        return jsonify({'error': 'Question required'}), 400
    
    if debate_state['running']:
        return jsonify({'error': 'Debate already running'}), 409
    
    try:
        config = load_config("config.yaml")
        orchestrator = DebateOrchestrator(config)
        debate_state['orchestrator'] = orchestrator
        debate_state['running'] = True
        
        # Run debate
        result = orchestrator.run_debate(
            question=question,
            question_id='ui_debate',
            ground_truth=data.get('ground_truth')
        )
        
        debate_state['current_debate'] = result
        debate_state['running'] = False
        
        return jsonify(result)
    
    except Exception as e:
        debate_state['running'] = False
        return jsonify({'error': str(e)}), 500

@app.route('/api/run-batch', methods=['POST'])
def run_batch_endpoint():
    """Run batch debates."""
    data = request.get_json()
    num_questions = data.get('num_questions', 5)
    domain = data.get('domain', 'commonsense_qa')
    
    if debate_state['running']:
        return jsonify({'error': 'Debate already running'}), 409
    
    try:
        debate_state['running'] = True
        
        # Load dataset
        dataset = DebateDataset.load_dataset(domain, num_questions)
        
        # Run debates
        config = load_config("config.yaml")
        orchestrator = DebateOrchestrator(config)
        debate_state['orchestrator'] = orchestrator
        
        results = orchestrator.run_batch(dataset)
        debate_state['results'] = results
        
        # Generate report
        report = DebateEvaluator.generate_report(results)
        
        debate_state['running'] = False
        
        return jsonify({
            'total_debates': len(results),
            'successful': sum(1 for r in results if 'error' not in r),
            'report': report
        })
    
    except Exception as e:
        debate_state['running'] = False
        return jsonify({'error': str(e)}), 500

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get current system status."""
    return jsonify({
        'running': debate_state['running'],
        'current_debate': debate_state['current_debate'],
        'total_results': len(debate_state['results']),
        'api_calls': debate_state['orchestrator'].get_stats()['total_api_calls'] if debate_state['orchestrator'] else 0
    })

@app.route('/api/results', methods=['GET'])
def get_results():
    """Get all debate results."""
    return jsonify({
        'results': debate_state['results'],
        'total': len(debate_state['results']),
        'report': DebateEvaluator.generate_report(debate_state['results']) if debate_state['results'] else None
    })

@app.route('/api/download-results', methods=['GET'])
def download_results():
    """Download results as JSON."""
    if not debate_state['results']:
        return jsonify({'error': 'No results to download'}), 404
    
    filename = 'debate_results.json'
    with open(filename, 'w') as f:
        json.dump({
            'results': debate_state['results'],
            'report': DebateEvaluator.generate_report(debate_state['results'])
        }, f, indent=2)
    
    return send_file(filename, as_attachment=True)

@app.route('/api/datasets', methods=['GET'])
def get_datasets():
    """Get available datasets and sample questions."""
    datasets = {
        'commonsense_qa': DebateDataset.load_commonsense_qa()[:3],
        'fact_verification': DebateDataset.load_fact_verification()[:3]
    }
    return jsonify(datasets)

if __name__ == '__main__':
    print("Starting LLM Debate System Web UI...")
    print("Server running at http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
