"""i18n 테스트 (v28.47) — 키 누락·포맷 불일치·언어 무관 결과 보장.

핵심은 **키 누락 자동 검출**이다. 한쪽 언어에만 키를 넣고 잊으면 GUI에서 그 자리만
다른 언어로 뜨는데, 사람 눈으로 전수 확인하기 어렵다(경고문 다수가 조건부라 화면에
잘 안 나온다). 여기서 기계적으로 잡는다.
"""
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from front_electrode import i18n  # noqa: E402


@pytest.fixture(autouse=True)
def _restore_language():
    """테스트가 전역 언어 상태를 오염시키지 않도록 원복(설정 파일은 건드리지 않음)."""
    before = i18n.get_language()
    yield
    i18n.set_language(before, persist=False)


def test_key_sets_identical():
    """KO/EN 키 집합이 완전히 동일해야 한다 — 한쪽에만 있으면 번역 누락."""
    gaps = i18n.missing_keys()
    assert not gaps, "언어별 누락 키: " + "; ".join(
        f"{lang}: {keys}" for lang, keys in gaps.items())


def test_all_languages_declared():
    """STRINGS의 언어와 LANGUAGES 선언이 일치하고 기본값이 실제로 존재해야 한다."""
    assert set(i18n.STRINGS) == set(i18n.LANGUAGES)
    assert i18n.DEFAULT_LANGUAGE in i18n.LANGUAGES
    assert i18n.DEFAULT_LANGUAGE == "en", "기본 언어는 English (외국인 사용자 기준)"
    for lang in i18n.LANGUAGES:
        assert i18n.label_for(lang), f"{lang}: 표시 이름 없음"


def _placeholders(s):
    """'{name}' / '{name:.2f}' 형태의 자리표시자 이름 집합."""
    return {m.split(":")[0].split("!")[0]
            for m in re.findall(r"\{([^{}]+)\}", s)}


def test_placeholders_match_across_languages():
    """같은 키의 포맷 자리표시자가 언어마다 같아야 한다.

    다르면 한 언어에서만 KeyError가 나거나(또는 T()의 폴백으로) 값이 빠진 문장이
    표시된다 — 번역하다 {nbb}를 빠뜨리는 실수를 잡는다.
    """
    base = i18n.STRINGS[i18n.DEFAULT_LANGUAGE]
    for lang, table in i18n.STRINGS.items():
        if lang == i18n.DEFAULT_LANGUAGE:
            continue
        for key, text in table.items():
            assert _placeholders(text) == _placeholders(base[key]), (
                f"{key}: {lang} 자리표시자가 {i18n.DEFAULT_LANGUAGE}와 다름 "
                f"({_placeholders(text)} vs {_placeholders(base[key])})")


def test_T_returns_selected_language():
    i18n.set_language("en", persist=False)
    assert i18n.T("note.range_fields") == i18n.STRINGS["en"]["note.range_fields"]
    i18n.set_language("ko", persist=False)
    assert i18n.T("note.range_fields") == i18n.STRINGS["ko"]["note.range_fields"]


def test_T_formats_arguments():
    i18n.set_language("en", persist=False)
    out = i18n.T("prog.running_n", done=3, total=12)
    assert "3" in out and "12" in out and "{" not in out


def test_T_unknown_key_does_not_raise():
    """모르는 키로 GUI가 죽으면 안 된다 — 눈에 띄는 형태로 표시만 한다."""
    assert i18n.T("no.such.key") == "[no.such.key]"


def test_T_bad_format_args_does_not_raise():
    """포맷 인자가 어긋나도 예외 없이 원문을 돌려준다."""
    out = i18n.T("prog.running_n", wrong_name=1)
    assert isinstance(out, str) and out


def test_set_language_rejects_unknown():
    i18n.set_language("en", persist=False)
    assert i18n.set_language("fr", persist=False) == "en"
    assert i18n.get_language() == "en"


def test_settings_roundtrip(tmp_path, monkeypatch):
    """선택한 언어가 설정 파일에 저장되고 다음 실행에서 복원되는지."""
    monkeypatch.setattr(i18n, "SETTINGS_DIR", str(tmp_path))
    monkeypatch.setattr(i18n, "SETTINGS_PATH", str(tmp_path / "settings.json"))
    i18n.set_language("ko", persist=True)
    assert i18n.load_settings()["language"] == "ko"
    i18n.reset_language_cache()               # 다음 실행 흉내
    assert i18n.get_language() == "ko"
    i18n.reset_language_cache()


def test_settings_failure_is_silent(monkeypatch, tmp_path):
    """설정 저장이 실패해도(읽기 전용 등) 예외가 새어나오면 안 된다."""
    bad = tmp_path / "not_a_dir"
    bad.write_text("x", encoding="utf-8")
    monkeypatch.setattr(i18n, "SETTINGS_DIR", str(bad / "sub"))
    monkeypatch.setattr(i18n, "SETTINGS_PATH", str(bad / "sub" / "settings.json"))
    assert i18n.save_settings({"language": "ko"}) is False
    assert i18n.load_settings() == {}


def test_no_korean_left_in_english_table():
    """EN 테이블에 한글이 남아 있으면 번역 누락이다."""
    hangul = re.compile(r"[가-힣]")
    bad = {k: v for k, v in i18n.STRINGS["en"].items() if hangul.search(v)}
    assert not bad, f"EN 문자열에 한글 잔존: {sorted(bad)}"


def test_ui_module_uses_no_hardcoded_korean():
    """ui.py 본문(주석·docstring 제외)에 한글 리터럴이 남아 있지 않아야 한다.

    문자열 중앙화가 실제로 지켜졌는지 기계적으로 확인한다. 주석과 docstring은
    개발자용이라 한국어를 유지하므로 AST로 코드 문자열만 골라 검사한다.
    """
    import ast
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "front_electrode", "ui.py")
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    tree = ast.parse(src)
    # docstring 노드는 제외 대상 — 그 값들을 미리 수집해 두고 건너뛴다.
    doc_nodes = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            body = getattr(node, "body", None)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                doc_nodes.add(id(body[0].value))
    hangul = re.compile(r"[가-힣]")
    offenders = [node.value for node in ast.walk(tree)
                 if isinstance(node, ast.Constant) and isinstance(node.value, str)
                 and id(node) not in doc_nodes and hangul.search(node.value)]
    assert not offenders, f"ui.py에 하드코딩된 한글 문자열: {offenders}"
