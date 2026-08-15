"""작업1 — 요리명별_조리과정_60282건 CSV를 recipes/recipe_steps 테이블에 적재.

db.py의 get_client() 문서에 이미 이 파일 이름이 예시로 언급돼 있다: 진짜로
대량의 실데이터를 저장하는 작업이라 allow_mock=False로 고정한다(가짜 메모리에
적재해봐야 "성공했다"는 착각만 주므로, Supabase 자격증명 없이는 아예 실행되지
않게 막는다).

## 이 스크립트가 CSV 원본을 그대로 넣지 않고 손보는 이유(전부 실측 확인됨)

1. 요리명(CKG_NM) 앞뒤 공백 — "닭볶음탕"과 "닭볶음탕 "처럼 같은 요리가 다른
   행으로 잡혀있다(86쌍). 표준 레시피 선정(6.1 규칙: 동일 요리명 중 조회수
   1위 채택)을 여기서 먼저 적용해 승자만 남긴다 — db/schema.sql의
   uq_recipes_dish_name_standard 제약이 이걸 못 하면 insert 단계에서 막아준다.
2. CKG_MTRL_CN/COOKING_STEPS 컬럼의 19.4%(11,683/60,282행)에 눈에 안 보이는
   제어문자(0x07)가 섞여 있다(ml_practice/common/text_normalize.py에 팀원이
   이미 확인해 기록해둠). TTS 발음과 정규식 매칭을 깨뜨리므로 저장 전에 제거한다.
3. CKG_MTRL_CN(297건)/CKG_INBUN_NM(2,870건) 빈 값은 빈 문자열이 아니라 null로
   저장한다 — 이후 로직(재료대체 검색 등)이 "없음"으로 자연스럽게 처리하도록.

재시딩 시 중복 적재 방지: recipes.external_id(원본 CSV의 RCP_SNO)를 이미 DB에
있는지 배치마다 먼저 확인하고, 있으면 건너뛴다(업서트 대신 이 방식을 쓴 이유는
tests/fake_supabase.py가 upsert를 구현하고 있지 않아서이기도 하고, select+insert만
쓰면 이 프로젝트의 다른 orchestration 코드와 동일한 방식이라 이해하기 쉽다).
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

# 이 파일은 src/orchestration/load_data.py에 있다. "orchestration.db"처럼 절대
# import를 쓰려면 src/가 sys.path에 있어야 하고, ml_practice(프로젝트 루트 바로
# 아래)의 유틸을 쓰려면 루트도 있어야 한다. pytest는 tests/conftest.py가 src/만
# 넣어주므로, 이 스크립트를 직접 실행할 때도(`python src/orchestration/load_data.py`)
# 똑같이 동작하도록 여기서 둘 다 방어적으로 추가한다.
_SRC_DIR = Path(__file__).resolve().parents[1]
_PROJECT_ROOT = _SRC_DIR.parent
for _path in (_SRC_DIR, _PROJECT_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from ml_practice.common.text_normalize import strip_control_chars  # noqa: E402
from orchestration.db import get_client  # noqa: E402

DEFAULT_CSV = _PROJECT_ROOT / "요리명별_조리과정_60282건_샘플형식.csv"
DEFAULT_BATCH_SIZE = 500

_STEP_PREFIX_RE = re.compile(r"^\d+\.\s*")


def _clean(text: str) -> str:
    return strip_control_chars(text).strip()


def parse_steps(cooking_steps: str) -> list[str]:
    """COOKING_STEPS 원문("1. ...\\n2. ...")을 번호 없는 텍스트 목록으로 분리한다."""
    lines = [_clean(line) for line in cooking_steps.split("\n")]
    return [_STEP_PREFIX_RE.sub("", line) for line in lines if line]


def dedupe_by_dish_name(csv_path: Path) -> tuple[list[dict], list[dict]]:
    """요리명(공백 제거) 기준으로 묶어 조회수 1위만 남긴다(6.1 표준선정규칙).

    반환값: (남긴 행 목록, 버린 행 목록 — 감사(audit) 로그용으로 사유와 함께)
    """
    winners: dict[str, dict] = {}
    discarded: list[dict] = []

    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            dish_name = row["CKG_NM"].strip()
            view_count = int(row["INQ_CNT"])
            current = winners.get(dish_name)
            if current is None:
                winners[dish_name] = row
                continue
            if view_count > int(current["INQ_CNT"]):
                discarded.append({**current, "discard_reason": f'"{dish_name}" 중복, 조회수 낮음'})
                winners[dish_name] = row
            else:
                discarded.append({**row, "discard_reason": f'"{dish_name}" 중복, 조회수 낮음'})

    return list(winners.values()), discarded


def build_recipe_payload(row: dict) -> tuple[dict, list[str]]:
    """CSV 한 행 -> (recipes에 넣을 딕셔너리, recipe_steps 텍스트 목록)."""
    ingredients = _clean(row["CKG_MTRL_CN"])
    servings = row["CKG_INBUN_NM"].strip()
    recipe = {
        "dish_name": row["CKG_NM"].strip(),
        "ingredients": ingredients or None,
        "servings": servings or None,
        "source": "api_standard",
        "view_count": int(row["INQ_CNT"]),
        "external_id": int(row["RCP_SNO"]),
    }
    steps = parse_steps(row["COOKING_STEPS"])
    return recipe, steps


def _chunks(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def load_data(
    csv_path: Path = DEFAULT_CSV,
    client=None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    limit: int | None = None,
    dry_run: bool = False,
) -> dict:
    """CSV를 읽어 recipes/recipe_steps에 적재한다. 반환값은 실행 요약 통계."""
    client = client or get_client(allow_mock=False)

    rows, discarded = dedupe_by_dish_name(csv_path)
    unique_dish_names = len(rows)
    if limit is not None:
        rows = rows[:limit]

    inserted_recipes = 0
    skipped_existing = 0
    inserted_steps = 0

    for batch in _chunks(rows, batch_size):
        payloads = []
        steps_by_external_id = {}
        for row in batch:
            recipe, steps = build_recipe_payload(row)
            payloads.append(recipe)
            steps_by_external_id[recipe["external_id"]] = steps

        external_ids = [p["external_id"] for p in payloads]
        existing = (
            client.table("recipes")
            .select("external_id")
            .in_("external_id", external_ids)
            .execute()
            .data
        )
        existing_ids = {r["external_id"] for r in existing}
        new_payloads = [p for p in payloads if p["external_id"] not in existing_ids]
        skipped_existing += len(payloads) - len(new_payloads)

        if not new_payloads:
            continue
        if dry_run:
            inserted_recipes += len(new_payloads)
            inserted_steps += sum(len(steps_by_external_id[p["external_id"]]) for p in new_payloads)
            continue

        inserted = client.table("recipes").insert(new_payloads).execute().data
        step_payload = [
            {"recipe_id": recipe["id"], "step_number": i, "step_text": text, "source": "api_standard"}
            for recipe in inserted
            for i, text in enumerate(steps_by_external_id[recipe["external_id"]], start=1)
        ]
        if step_payload:
            client.table("recipe_steps").insert(step_payload).execute()

        inserted_recipes += len(inserted)
        inserted_steps += len(step_payload)

    if discarded:
        _write_discard_log(csv_path, discarded)

    return {
        "unique_dish_names_in_csv": unique_dish_names,  # limit과 무관하게 항상 파일 전체 기준
        "duplicate_dish_names_discarded": len(discarded),
        "recipes_processed_this_run": len(rows),  # limit 적용된 실제 처리 건수
        "recipes_inserted": inserted_recipes,
        "recipes_skipped_existing": skipped_existing,
        "steps_inserted": inserted_steps,
        "dry_run": dry_run,
    }


def _write_discard_log(csv_path: Path, discarded: list[dict]) -> Path:
    """조회수 낮아서 버린 중복 행을 감사용으로 남긴다(왜 60,282건이 아닌지 추적 가능하게)."""
    log_path = csv_path.parent / "data" / "standard" / "load_data_discarded_duplicates.csv"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["RCP_SNO", "CKG_NM", "INQ_CNT", "discard_reason"])
        writer.writeheader()
        for row in discarded:
            writer.writerow(
                {
                    "RCP_SNO": row["RCP_SNO"],
                    "CKG_NM": row["CKG_NM"],
                    "INQ_CNT": row["INQ_CNT"],
                    "discard_reason": row["discard_reason"],
                }
            )
    return log_path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="적재할 CSV 경로")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--limit", type=int, default=None, help="테스트용: 앞에서 N개 요리명만 적재")
    parser.add_argument(
        "--dry-run", action="store_true", help="실제로 insert하지 않고 통계만 확인(먼저 이걸로 검증 권장)"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    summary = load_data(
        csv_path=args.csv,
        batch_size=args.batch_size,
        limit=args.limit,
        dry_run=args.dry_run,
    )
    for key, value in summary.items():
        print(f"{key}: {value}")
