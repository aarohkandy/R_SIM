from __future__ import annotations

import pytest

from rocketsim.cli import main


def test_phase_command_stub_exits_visibly(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["sensitivity"])

    captured = capsys.readouterr()
    assert raised.value.code == 2
    assert "intentionally stubbed in Phase 0" in captured.err
    assert "Phase 15" in captured.err
