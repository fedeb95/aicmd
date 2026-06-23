import os
from pathlib import Path
from typer.testing import CliRunner
from aicmd import cli, configure

runner = CliRunner()

def test_set_timeout_without_provider(tmp_path, monkeypatch):
    # Ensure we start with a clean config file
    config_path = Path.home() / '.aicmd.yaml'
    if config_path.exists():
        config_path.unlink()
    # Run configure set with only timeout
    result = runner.invoke(configure.app, ['set', '--timeout', '120'])
    assert result.exit_code == 0
    # Verify config file contains timeout and no provider key
    cfg = {}
    with open(config_path, 'r') as f:
        for line in f:
            if ':' in line:
                k, v = line.strip().split(':', 1)
                cfg[k.strip()] = v.strip()
    assert cfg.get('timeout') == '120'
    # provider should not be set
    assert 'provider' not in cfg

def test_summarize_uses_config_timeout(monkeypatch):
    # Set timeout in config
    config_path = Path.home() / '.aicmd.yaml'
    config_path.write_text('timeout: 5\nprovider: ollama\n')
    # Mock provider to avoid real HTTP call
    class DummyProvider:
        def summarize(self, text, *, model=None, max_tokens=256, timeout=60):
            assert timeout == 5
            return 'dummy summary'
    monkeypatch.setattr('aicmd.providers.get_provider', lambda _: DummyProvider())
    result = runner.invoke(cli.app, ['summarize', '--model', 'test-model'], input='hello')
    assert result.exit_code == 0
    assert 'dummy summary' in result.output
