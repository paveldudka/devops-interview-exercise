"""Regression tests for the conftest guard that fails skipped baseline checks."""

from pathlib import Path

import pytest

pytest_plugins = ["pytester"]

CONFTEST = (Path(__file__).parent / "conftest.py").read_text(encoding="utf-8")
INI = "[pytest]\nmarkers =\n    baseline: repository checks that must remain green\n"


def prepare(pytester: pytest.Pytester, body: str, name: str = "test_x.py") -> None:
    pytester.makeini(INI)
    pytester.makeconftest(CONFTEST)
    pytester.makepyfile(**{name.removesuffix(".py"): "import pytest\n\n" + body})


@pytest.mark.parametrize(
    "body",
    [
        '@pytest.mark.baseline\n@pytest.mark.skip(reason="wip")\ndef test_a(): ...\n',
        "@pytest.mark.baseline\ndef test_a():\n    pytest.skip('wip')\n",
        "@pytest.mark.baseline\n@pytest.mark.xfail\ndef test_a():\n    assert False\n",
        "@pytest.mark.baseline\n@pytest.mark.xfail\ndef test_a():\n    assert True\n",
    ],
)
def test_skipped_or_xfailed_baseline_check_fails_the_run(
    pytester: pytest.Pytester, body: str
) -> None:
    prepare(pytester, body)
    result = pytester.runpytest("-q")
    assert result.ret == 1
    result.stdout.fnmatch_lines(["*was skipped, xfailed, or xpassed*"])


def test_non_baseline_skips_stay_allowed(pytester: pytest.Pytester) -> None:
    prepare(
        pytester,
        '@pytest.mark.parametrize("env", ["baseline", "prod"])\n'
        "def test_env(env):\n"
        '    if env == "baseline":\n'
        '        pytest.skip("not here")\n'
        "\n"
        "@pytest.mark.baseline\n"
        "def test_a(): ...\n",
    )
    result = pytester.runpytest("-q")
    assert result.ret == 0
    result.assert_outcomes(passed=2, skipped=1)


def test_collection_skip_of_baseline_module_fails_the_run(
    pytester: pytest.Pytester,
) -> None:
    pytester.mkdir("tests")
    prepare(
        pytester,
        'pytest.skip("wip", allow_module_level=True)\n',
        name="tests/test_repository_baseline.py",
    )
    # Subprocess: the real module of the same name is already imported here.
    result = pytester.runpytest_subprocess("-q")
    assert result.ret == 1
    result.stdout.fnmatch_lines(["*was skipped during collection*"])
