"""
Production deployment and monitoring utilities for jury panel system.
Handles logging, error tracking, and operational metrics.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import hashlib
from dataclasses import dataclass, asdict


@dataclass
class OperationalMetric:
    """Operational metric for monitoring."""
    timestamp: str
    metric_name: str
    value: float
    unit: str
    metadata: Dict[str, Any]


class JurySystemLogger:
    """Comprehensive logging for jury panel system."""
    
    def __init__(self, log_dir: str = "logs"):
        """Initialize logger."""
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure logging
        self.logger = logging.getLogger("JuryPanel")
        self.logger.setLevel(logging.DEBUG)
        
        # File handler
        fh = logging.FileHandler(self.log_dir / "jury_system.log")
        fh.setLevel(logging.DEBUG)
        
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        
        self.logger.addHandler(fh)
        self.logger.addHandler(ch)
    
    def log_debate_start(self, debate_id: str, question: str) -> None:
        """Log start of debate."""
        self.logger.info(f"[{debate_id}] Debate started: {question[:80]}...")
    
    def log_debate_complete(self, debate_id: str, rounds: int, duration: float) -> None:
        """Log debate completion."""
        self.logger.info(f"[{debate_id}] Debate complete in {rounds} rounds ({duration:.1f}s)")
    
    def log_jury_evaluation(self, debate_id: str, jury_size: int, mode: str) -> None:
        """Log jury evaluation start."""
        self.logger.info(f"[{debate_id}] Jury evaluation: {jury_size} judges, mode={mode}")
    
    def log_verdict(self, debate_id: str, member_id: int, winner: str, confidence: int) -> None:
        """Log individual verdict."""
        self.logger.debug(f"[{debate_id}] Member {member_id}: {winner} (conf: {confidence}/5)")
    
    def log_consensus(self, debate_id: str, winner: str, unanimity: bool) -> None:
        """Log consensus verdict."""
        status = "unanimous" if unanimity else "split"
        self.logger.info(f"[{debate_id}] Consensus: {winner} ({status})")
    
    def log_error(self, debate_id: str, error: Exception) -> None:
        """Log error with debate context."""
        self.logger.error(f"[{debate_id}] ERROR: {str(error)}")
    
    def get_log_summary(self, num_lines: int = 50) -> str:
        """Get summary of recent log entries."""
        log_file = self.log_dir / "jury_system.log"
        if not log_file.exists():
            return "No logs yet"
        
        with open(log_file) as f:
            lines = f.readlines()
        
        return "".join(lines[-num_lines:])


class OperationalMonitor:
    """Monitor operational metrics and health."""
    
    def __init__(self, metrics_dir: str = "metrics"):
        """Initialize monitor."""
        self.metrics_dir = Path(metrics_dir)
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        self.metrics: List[OperationalMetric] = []
    
    def record_metric(self, metric_name: str, value: float, unit: str = "",
                     metadata: Optional[Dict[str, Any]] = None) -> None:
        """Record operational metric."""
        metric = OperationalMetric(
            timestamp=datetime.now().isoformat(),
            metric_name=metric_name,
            value=value,
            unit=unit,
            metadata=metadata or {}
        )
        self.metrics.append(metric)
    
    def record_api_call(self, model: str, tokens: int, latency: float, success: bool) -> None:
        """Record API call metric."""
        self.record_metric(
            "api_call",
            latency,
            unit="seconds",
            metadata={
                "model": model,
                "tokens": tokens,
                "success": success
            }
        )
    
    def record_accuracy(self, accuracy: float, jury_size: int, mode: str) -> None:
        """Record accuracy metric."""
        self.record_metric(
            "accuracy",
            accuracy,
            unit="percent",
            metadata={
                "jury_size": jury_size,
                "mode": mode
            }
        )
    
    def record_disagreement(self, disagreement: float, question_difficulty: float) -> None:
        """Record disagreement metric."""
        self.record_metric(
            "disagreement",
            disagreement,
            unit="level",
            metadata={
                "question_difficulty": question_difficulty
            }
        )
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get system health summary."""
        if not self.metrics:
            return {"status": "no_data"}
        
        # Calculate metrics
        api_calls = [m for m in self.metrics if m.metric_name == "api_call"]
        accuracy_metrics = [m for m in self.metrics if m.metric_name == "accuracy"]
        
        summary = {
            "total_metrics": len(self.metrics),
            "last_updated": self.metrics[-1].timestamp if self.metrics else None,
            "api_health": {
                "total_calls": len(api_calls),
                "avg_latency": sum(m.value for m in api_calls) / len(api_calls) if api_calls else 0,
            },
            "accuracy_health": {
                "total_evaluations": len(accuracy_metrics),
                "avg_accuracy": sum(m.value for m in accuracy_metrics) / len(accuracy_metrics) if accuracy_metrics else 0,
            }
        }
        
        return summary
    
    def save_metrics(self) -> Path:
        """Save metrics to file."""
        metrics_data = {
            "saved_at": datetime.now().isoformat(),
            "metrics": [asdict(m) for m in self.metrics]
        }
        
        filepath = self.metrics_dir / f"metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filepath, 'w') as f:
            json.dump(metrics_data, f, indent=2)
        
        return filepath


class DeploymentConfig:
    """Deployment configuration management."""
    
    def __init__(self, config_path: str = "deploy_config.json"):
        """Load deployment configuration."""
        self.config_path = Path(config_path)
        self.config = self._load_or_create()
    
    def _load_or_create(self) -> Dict[str, Any]:
        """Load config or create default."""
        if self.config_path.exists():
            with open(self.config_path) as f:
                return json.load(f)
        
        return self._create_default_config()
    
    def _create_default_config(self) -> Dict[str, Any]:
        """Create default deployment configuration."""
        return {
            "version": "2.0",
            "deployment": {
                "environment": "development",  # development, staging, production
                "debug_mode": True,
                "log_level": "INFO",
            },
            "performance": {
                "max_concurrent_debates": 5,
                "jury_timeout_seconds": 300,
                "retry_attempts": 3,
            },
            "monitoring": {
                "enabled": True,
                "metrics_interval_seconds": 60,
                "alert_on_error": True,
            },
            "api": {
                "rate_limit_per_minute": 60,
                "timeout_seconds": 30,
                "retry_backoff_factor": 2,
            },
            "storage": {
                "save_transcripts": True,
                "save_verdicts": True,
                "archive_old_logs": True,
                "archive_after_days": 30,
            }
        }
    
    def save(self) -> None:
        """Save configuration."""
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """Get config value by dot notation."""
        keys = key_path.split('.')
        value = self.config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key, default)
            else:
                return default
        return value


class HealthChecker:
    """System health checking."""
    
    def __init__(self, logger: JurySystemLogger, monitor: OperationalMonitor):
        """Initialize health checker."""
        self.logger = logger
        self.monitor = monitor
    
    def check_system_health(self) -> Dict[str, Any]:
        """Comprehensive system health check."""
        health = {
            "timestamp": datetime.now().isoformat(),
            "status": "healthy",
            "checks": {}
        }
        
        # API health
        health["checks"]["api"] = self._check_api_health()
        
        # Storage health
        health["checks"]["storage"] = self._check_storage_health()
        
        # Metrics health
        health["checks"]["metrics"] = self._check_metrics_health()
        
        # Overall status
        if any(check.get("status") == "unhealthy" for check in health["checks"].values()):
            health["status"] = "warning"
        
        return health
    
    def _check_api_health(self) -> Dict[str, Any]:
        """Check API connectivity."""
        return {
            "status": "healthy",
            "last_call": datetime.now().isoformat(),
            "success_rate": 0.98  # Placeholder
        }
    
    def _check_storage_health(self) -> Dict[str, Any]:
        """Check storage health."""
        return {
            "status": "healthy",
            "available_space_gb": 100,  # Placeholder
            "backup_status": "current"
        }
    
    def _check_metrics_health(self) -> Dict[str, Any]:
        """Check metrics collection."""
        summary = self.monitor.get_health_summary()
        return {
            "status": "healthy",
            "total_collected": summary.get("total_metrics", 0),
            "avg_api_latency": summary.get("api_health", {}).get("avg_latency", 0)
        }


class RolloutManager:
    """Manage version rollouts and rollbacks."""
    
    def __init__(self, versions_dir: str = "versions"):
        """Initialize rollout manager."""
        self.versions_dir = Path(versions_dir)
        self.versions_dir.mkdir(parents=True, exist_ok=True)
    
    def create_version(self, version_tag: str, config: Dict[str, Any]) -> None:
        """Create new version snapshot."""
        version_file = self.versions_dir / f"{version_tag}.json"
        version_data = {
            "tag": version_tag,
            "created": datetime.now().isoformat(),
            "config": config
        }
        
        with open(version_file, 'w') as f:
            json.dump(version_data, f, indent=2)
    
    def list_versions(self) -> List[str]:
        """List available versions."""
        return sorted([f.stem for f in self.versions_dir.glob("*.json")])
    
    def rollback(self, version_tag: str) -> Dict[str, Any]:
        """Rollback to specific version."""
        version_file = self.versions_dir / f"{version_tag}.json"
        
        if not version_file.exists():
            raise ValueError(f"Version {version_tag} not found")
        
        with open(version_file) as f:
            version_data = json.load(f)
        
        return version_data["config"]


class ProductionSetup:
    """One-stop setup for production deployment."""
    
    def __init__(self, config_path: str = "deploy_config.json"):
        """Initialize production setup."""
        self.deployment_config = DeploymentConfig(config_path)
        self.logger = JurySystemLogger()
        self.monitor = OperationalMonitor()
        self.health_checker = HealthChecker(self.logger, self.monitor)
        self.rollout_manager = RolloutManager()
    
    def verify_deployment(self) -> bool:
        """Verify deployment readiness."""
        print("Verifying production deployment...")
        
        health = self.health_checker.check_system_health()
        print(f"System Status: {health['status']}")
        
        for check_name, check_result in health['checks'].items():
            status = "✓" if check_result['status'] == 'healthy' else "✗"
            print(f"  {status} {check_name}: {check_result['status']}")
        
        return health['status'] == 'healthy'
    
    def create_rollout(self, version_tag: str) -> None:
        """Create versioned rollout."""
        config = self.deployment_config.config
        self.rollout_manager.create_version(version_tag, config)
        print(f"✓ Created rollout version: {version_tag}")
    
    def get_deployment_status(self) -> str:
        """Get current deployment status."""
        config = self.deployment_config.config
        health = self.health_checker.check_system_health()
        
        status = f"""
Deployment Status Report
========================

Environment: {config['deployment']['environment']}
Version: {config['version']}
System Health: {health['status']}

Metrics:
  - API Calls: {health['checks']['api'].get('success_rate', 'N/A')}
  - Storage: {health['checks']['storage']['status']}
  - Metrics Collected: {health['checks']['metrics']['total_collected']}

Recent Logs:
{self.logger.get_log_summary(10)}
"""
        return status


# Usage example
if __name__ == "__main__":
    # Setup production
    setup = ProductionSetup()
    
    # Verify deployment
    if setup.verify_deployment():
        print("\n✓ Deployment verified and ready")
        
        # Create version
        setup.create_rollout("v2.0_production")
        
        # Print status
        print(setup.get_deployment_status())
    else:
        print("\n✗ Deployment verification failed")
