# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""등록용 자료의 수치를 저장소에서 실측해 생성한다.

왜 필요한가: docs/registration_material.md의 규모·테스트 수·버전이 수동 기재라
v28.49 기준으로 작성된 뒤 5판 동안 낡았다(파일 40→46, 라인 19,137→21,144,
테스트 81→147, 버전 v28.49→v28.55). 손으로 적는 한 같은 일이 반복된다.

  python scripts/gen_registration_stats.py                     # 조각을 표준출력으로
  python scripts/gen_registration_stats.py --from-log run.txt  # 테스트 수를 로그에서
  python scripts/gen_registration_stats.py --run-tests         # pytest 직접 실행(느림)
  python scripts/gen_registration_stats.py --from-log run.txt --write   # 문서 갱신
  python scripts/gen_registration_stats.py --from-log run.txt --check   # 최신인지 검사

--write는 문서의 센티넬 주석 사이만 교체한다:
    <!-- STATS:BEGIN <이름> -->  ...생성 구간...  <!-- STATS:END <이름> -->
센티넬 밖의 서술은 건드리지 않는다.

테스트 수는 추측하지 않는다. --from-log 나 --run-tests 없이 --write/--check 를
쓰면 거부한다 — 조용히 옛 숫자를 남기는 것이 이 스크립트가 없애려는 문제다.
"""
import argparse
import os
import re
import subprocess
import sys
from collections import OrderedDict

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
DOC = os.path.join(_ROOT, "docs", "registration_material.md")
ENGINE = os.path.join(_ROOT, "2L_FEST.py")

# 라인 수 집계 단위. 앞에서부터 먼저 맞는 접두사로 분류하며, 어디에도 안 맞으면
# "본체 엔진 (루트)"로 간다. 새 디렉터리가 생기면 여기에 추가하면 된다.
UNITS = OrderedDict((
    ("tests/", "`tests/` — 단위·회귀 테스트"),
    ("front_electrode/", "`front_electrode/` — 전면전극 최적화 모듈"),
    ("solcore_xval/", "`solcore_xval/` — 외부 솔버 교차검증 도구"),
    ("scripts/", "`scripts/` — 헤드리스 드라이버"),
))
ROOT_UNIT = "본체 엔진 (루트) — 계산 엔진 + 메인 GUI + 검증 스크립트"


def _git(*args):
    """git 호출. 실패하면 None을 돌려주고 호출자가 판단한다."""
    try:
        r = subprocess.run(("git",) + args, capture_output=True, text=True,
                           timeout=20, cwd=_ROOT)
    except Exception:
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def collect_scale():
    """git 추적 파일 기준 규모. (dict) 반환."""
    py_out = _git("ls-files", "*.py")
    if py_out is None:
        raise RuntimeError("git ls-files 실패 — 저장소 안에서 실행해야 한다")
    py_files = [p for p in py_out.splitlines() if p.strip()]

    per_unit = OrderedDict((label, 0) for label in UNITS.values())
    per_unit[ROOT_UNIT] = 0
    total = 0
    for rel in py_files:
        path = os.path.join(_ROOT, rel)
        try:
            with open(path, "rb") as fh:
                n = sum(1 for _ in fh)
        except OSError:
            continue
        total += n
        for prefix, label in UNITS.items():
            if rel.startswith(prefix):
                per_unit[label] += n
                break
        else:
            per_unit[ROOT_UNIT] += n

    all_out = _git("ls-files")
    tracked = len([p for p in (all_out or "").splitlines() if p.strip()])

    engine_lines = 0
    try:
        with open(ENGINE, "rb") as fh:
            engine_lines = sum(1 for _ in fh)
    except OSError:
        pass

    return {
        "py_files": len(py_files),
        "py_lines": total,
        "tracked_files": tracked,
        "per_unit": per_unit,
        "engine_lines": engine_lines,
    }


def collect_version():
    """엔진 __build__와 git 이력."""
    version = date = "unknown"
    try:
        # __build__는 파일 앞부분의 긴 changelog docstring 뒤에 있다. 앞 N바이트만
        # 읽으면 changelog가 길어질수록 놓친다(실측: 20k로 자르니 unknown이 나왔다).
        # 전체를 읽고 __build__ 블록에서만 뽑는다 — changelog 본문에도 "version"
        # 문자열이 나올 수 있으므로 블록을 먼저 좁힌다.
        with open(ENGINE, encoding="utf-8") as fh:
            src = fh.read()
        blk = re.search(r"__build__\s*=\s*\{(.*?)\}", src, re.S)
        if blk:
            body = blk.group(1)
            m = re.search(r'"version":\s*"([^"]+)"', body)
            if m:
                version = m.group(1)
            m = re.search(r'"date":\s*"([^"]+)"', body)
            if m:
                date = m.group(1)
    except OSError:
        pass

    commits = _git("rev-list", "--count", "HEAD") or "unknown"
    sha = _git("rev-parse", "--short", "HEAD") or "unknown"
    # dirty 여부는 **문서에 넣지 않는다.** --write가 문서를 고치는 순간 트리가
    # 더러워지므로, SHA에 -dirty를 박으면 커밋할 때마다 값이 또 달라져 순환한다.
    # 문서에는 깨끗한 SHA만 남기고, dirty는 실행 시 경고로만 알린다.
    # untracked 파일은 커밋된 소스를 바꾸지 않으므로 제외한다.
    dirty = bool(_git("status", "--porcelain", "--untracked-files=no"))
    first = _git("log", "--reverse", "--format=%ad", "--date=short")
    last = _git("log", "-1", "--format=%ad", "--date=short")
    return {
        "version": version,
        "build_date": date,
        "commits": commits,
        "sha": sha,
        "dirty": dirty,
        "first_commit": (first or "").splitlines()[0] if first else "unknown",
        "last_commit": last or "unknown",
    }


def collect_env():
    """측정 환경 — 이 스크립트를 돌린 인터프리터 기준."""
    py = ".".join(str(x) for x in sys.version_info[:3])
    out = {"python": py}
    for name in ("numpy", "scipy", "matplotlib"):
        try:
            out[name] = __import__(name).__version__
        except Exception:
            out[name] = "미설치"
    return out


# 요약 줄의 각 항목을 **이름으로** 뽑는다. 순서·인접성에 기대지 않는다.
#
# v28.67에서 고쳤다. 이전 정규식은 `passed → deselected → xfailed → failed`가
# 그 순서로 **붙어 있을 때만** 맞았다. pytest는 값이 0인 항목을 아예 빼고
# 출력하므로 항목 집합이 실행마다 달라지는데, 중간에 새 항목이 하나 끼면
# 뒤쪽이 통째로 None이 된다. 실제로 그렇게 됐다:
#
#     600 passed, 4 skipped, 2 deselected, 6 xfailed
#                 ^^^^^^^^^ 새 항목
#
# `4 skipped`가 끼자 deselected·xfailed가 매칭되지 않아 **둘 다 0으로 기록**됐다.
# 등록 자료에 "xfail 0건 / 느린 핀 0건"이라고 적힐 뻔했다 — 오류도 경고도 없이,
# 그냥 숫자가 틀린 채로. 문서가 사실을 말해야 하는 자리라 조용한 오답이 특히 나쁘다.
_COUNT_RE = re.compile(
    "([0-9]+)[ \t]+"
    "(passed|failed|skipped|deselected|xfailed|xpassed|errors?|warnings?)"
    "(?![a-zA-Z])")

_KNOWN = ("passed", "failed", "skipped", "deselected", "xfailed", "xpassed",
          "error", "warning")


def parse_pytest_summary(text):
    """pytest -q 요약 줄에서 항목별 건수를 뽑는다.

    실패 건수가 있으면 그대로 담는다 — 등록 자료에 '실패 0건'이라고 쓰려면
    실제로 0인지 확인해야 한다.

    요약 줄 판정: `N passed`를 포함하는 **마지막** 줄. 진행 표시(`....`)와
    실패 상세 블록에는 그 형태가 없다.
    """
    best = None
    for line in text.splitlines():
        counts = {}
        for n, kind in _COUNT_RE.findall(line):
            counts[kind.rstrip("s") if kind.startswith(("error", "warning"))
                   else kind] = int(n)
        if "passed" in counts:
            best = counts
    if best is None:
        raise ValueError(
            "pytest 요약 줄을 찾지 못했다 (예: '600 passed, 4 skipped, "
            "2 deselected, 6 xfailed')")
    return {k: int(best.get(k, 0)) for k in _KNOWN}


def run_tests():
    """pytest -m "not slow" 를 직접 실행한다. 느리다(약 20분)."""
    print("  pytest -q -m \"not slow\" 실행 중 — 약 20분 걸린다...", flush=True)
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-m", "not slow"],
                       capture_output=True, text=True, cwd=_ROOT)
    return parse_pytest_summary(r.stdout + r.stderr)


# --- 마크다운 조각 생성 -------------------------------------------------------

def block_scale(s):
    lines = [
        "| 항목 | 값 |",
        "|---|---|",
        f"| Python 소스 파일 | {s['py_files']}개 |",
        f"| Python 총 라인 수 | {s['py_lines']:,}줄 |",
        f"| 저장소 추적 파일 총계 | {s['tracked_files']}개 |",
        f"| 그중 `2L_FEST.py` (엔진+GUI 단일 파일) | {s['engine_lines']:,}줄 |",
        "",
        "구성 단위별 라인 수:",
        "",
        "| 단위 | 라인 수 |",
        "|---|---|",
    ]
    for label, n in sorted(s["per_unit"].items(), key=lambda kv: -kv[1]):
        if n:
            lines.append(f"| {label} | {n:,} |")
    return "\n".join(lines)


def block_version(v):
    return "\n".join([
        f"- **버전 관리 이력**: {v['first_commit']} ~ {v['last_commit']}, "
        f"커밋 {v['commits']}건",
        "  (형상관리 도입 시점의 버전이 이미 v28.18이므로, 실제 개발 착수는 그 이전이다.",
        "   본 문서의 기간은 형상관리 기록이 남아 있는 구간을 뜻한다.)",
        f"- **현재 버전**: {v['version']} ({v['build_date']})",
        f"- **측정 시점 커밋**: `{v['sha']}`",
    ])


def block_tests(t, env):
    # v28.67: 건너뜀도 적는다. 빼 두면 "통과+xfail+실패"의 합이 수집
    # 수와 안 맞아, 합을 맞춰 보는 사람에게 문서가 틀린 것처럼 보인다.
    fail_txt = "실패 0건" if t["failed"] == 0 else f"**실패 {t['failed']}건**"
    skip_txt = (f" / 건너뜀 {t['skipped']}건" if t["skipped"] else "")
    return (
        f"`pytest -m \"not slow\"` 실행 결과 **{t['passed']}건 통과 / "
        f"{t['xfailed']}건 예상된 실패(xfail){skip_txt} / {fail_txt}**\n"
        f"(측정 환경: Python {env['python']}, numpy {env['numpy']}, "
        f"scipy {env['scipy']}).\n\n"
        f"느린 전체 크기 셀 핀 {t['deselected']}건은 실행 시간(조합당 약 17분) 때문에 "
        f"기본 실행에서 제외하고 필요 시 별도로 돌린다."
    )


def block_header(v):
    return (f"작성 기준: **{v['version']}** ({v['build_date']}), 커밋 `{v['sha']}`. "
            f"아래 수치는 `scripts/gen_registration_stats.py`가 저장소에서 실측해 "
            f"생성한다 — 손으로 고치지 말 것.")


def build_blocks(with_tests=None):
    s, v, env = collect_scale(), collect_version(), collect_env()
    blocks = {
        "header": block_header(v),
        "scale": block_scale(s),
        "version": block_version(v),
    }
    if with_tests is not None:
        blocks["tests"] = block_tests(with_tests, env)
    return blocks


# --- 문서 갱신 ---------------------------------------------------------------

# --check 비교에서 제외할 변동성 필드. 커밋 SHA와 커밋 수는 --write가 문서를
# 고치는 순간 또 달라지므로 원리상 수렴하지 않는다. 이들 때문에 --check가 영구히
# 빨간불이 되면 게이트로 쓸 수 없다. 진짜 낡음(규모·버전·테스트 수)만 본다.
_VOLATILE = (
    (re.compile(r"커밋 `[0-9a-f]+`"), "커밋 `<sha>`"),
    (re.compile(r"`[0-9a-f]{7,40}`"), "`<sha>`"),
    (re.compile(r"커밋 \d+건"), "커밋 <n>건"),
    (re.compile(r"\d{4}-\d{2}-\d{2} ~ \d{4}-\d{2}-\d{2}"), "<기간>"),
)


def _normalize_volatile(text):
    for pat, repl in _VOLATILE:
        text = pat.sub(repl, text)
    return text


def _pattern(name):
    return re.compile(
        r"(<!-- STATS:BEGIN %s -->\n)(.*?)(\n<!-- STATS:END %s -->)"
        % (re.escape(name), re.escape(name)), re.S)


def apply_blocks(doc_text, blocks):
    """센티넬 사이를 교체한다. 반환: (새 본문, 교체된 이름 목록, 누락된 이름 목록)."""
    changed, missing = [], []
    out = doc_text
    for name, body in blocks.items():
        pat = _pattern(name)
        if not pat.search(out):
            missing.append(name)
            continue
        new = pat.sub(lambda m: m.group(1) + body + m.group(3), out, count=1)
        if new != out:
            changed.append(name)
        out = new
    return out, changed, missing


def main():
    ap = argparse.ArgumentParser(
        description="등록용 자료 수치를 저장소에서 실측해 생성/갱신한다.")
    ap.add_argument("--from-log", dest="from_log", default=None,
                    help="pytest 출력이 담긴 로그 파일에서 테스트 수를 읽는다")
    ap.add_argument("--run-tests", action="store_true",
                    help="pytest -m \"not slow\"를 직접 실행한다 (약 20분)")
    ap.add_argument("--write", action="store_true",
                    help="docs/registration_material.md의 센티넬 구간을 갱신한다")
    ap.add_argument("--check", action="store_true",
                    help="문서가 최신인지 검사만 한다. 낡았으면 exit 1")
    args = ap.parse_args()

    tests = None
    if args.from_log:
        with open(args.from_log, encoding="utf-8", errors="replace") as fh:
            tests = parse_pytest_summary(fh.read())
    elif args.run_tests:
        tests = run_tests()

    if (args.write or args.check) and tests is None:
        ap.error("--write / --check 에는 테스트 수가 필요하다. "
                 "--from-log <파일> 또는 --run-tests 를 함께 줄 것. "
                 "(추측해서 적지 않는 것이 이 스크립트의 목적이다)")

    blocks = build_blocks(tests)

    if collect_version()["dirty"]:
        print("⚠ 추적 파일에 미커밋 변경이 있다 — 기록된 커밋 SHA가 실제 측정 상태와"
              " 다를 수 있다. 커밋 후 다시 돌리는 편이 정확하다.", file=sys.stderr)

    if not (args.write or args.check):
        for name, body in blocks.items():
            print(f"<!-- STATS:BEGIN {name} -->")
            print(body)
            print(f"<!-- STATS:END {name} -->\n")
        if tests is None:
            print("※ 테스트 수는 --from-log 나 --run-tests 를 줘야 나온다.",
                  file=sys.stderr)
        return 0

    with open(DOC, encoding="utf-8") as fh:
        original = fh.read()
    updated, changed, missing = apply_blocks(original, blocks)

    if missing:
        print(f"❌ 센티넬 누락: {missing}\n"
              f"   문서에 <!-- STATS:BEGIN <이름> --> / <!-- STATS:END <이름> --> 를 "
              f"넣어야 갱신된다.", file=sys.stderr)
        return 2

    if args.check:
        if _normalize_volatile(updated) != _normalize_volatile(original):
            print(f"❌ 문서가 낡았다 — 갱신 필요 구간: {changed}\n"
                  f"   python scripts/gen_registration_stats.py "
                  f"--from-log <로그> --write", file=sys.stderr)
            return 1
        print("✅ 문서 수치가 저장소 실측과 일치한다 "
              "(커밋 SHA·커밋 수·기간은 변동성 필드라 비교에서 제외).")
        return 0

    if updated == original:
        print("변경 없음 — 이미 최신이다.")
        return 0
    tmp = DOC + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(updated)
    os.replace(tmp, DOC)
    print(f"✅ 갱신 완료: {', '.join(changed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
