"""발표용 시나리오. 날짜, 작업 큐(무작위 seed), 구름을 미리 정해 두어 리허설과 발표에서 같은 장면이 나옵니다.

    python -m controller.main --scenario 1 --gui ...     (또는 icdf 1)

구름 시간은 칸 번호(30분 = 1칸, 0 = 00:00, 47 = 23:30)로 적습니다.
시나리오 1, 2는 구름이 자동으로 들어갑니다 (화면 버튼과 조도센서는 무시).
시나리오 3은 구름을 정해 두지 않습니다. 심사위원이 조도센서(구름판)나 화면 버튼으로 직접 올립니다.

숫자는 2026-11-19에 시연 엔진의 스케줄러로 확인한 값입니다 (변경 1회 = 4.5 g 포함).
"""

SCENARIOS = {
    "1": {
        "key": "long",
        "title": "시나리오 1 · 긴 구름",
        "title_en": "Scenario 1 · Long cloud",
        "day": "2025-09-14",
        "days": 1,
        "slot_seconds": 1.0,   # 하루 48초
        "seed": 22,
        # 03:00 ~ 08:30 (6시간) 계속 구름
        "clouds": [(6, 17)],
        "note": "Google 1,521 g (구름 속 9칸 실행) / YAX 1,285 g (6번 미룸, 구름 속 3칸) → YAX 15% 적게",
    },
    "2": {
        "key": "short",
        "title": "시나리오 2 · 짧은 구름 여러 번",
        "title_en": "Scenario 2 · Several short clouds",
        "day": "2025-06-07",
        "days": 1,
        "slot_seconds": 1.0,   # 하루 48초
        "seed": 20,
        # 07:00, 10:30, 13:30, 18:00, 20:30에 30분~1시간씩
        "clouds": [(14, 15), (21, 22), (27, 27), (36, 37), (41, 41)],
        "note": "Google 1,326 g / YAX 1,293 g (1번만 바꿈). 같은 조건에서 지금 오차에만 반응하면 12번 바꾸고 1,368 g (Google보다 나쁨)",
    },
    "3": {
        "key": "free",
        "title": "시나리오 3 · 직접 구름을 올려 보세요",
        "title_en": "Scenario 3 · Move the cloud yourself",
        "day": "2025-09-14",
        "days": 5,
        "slot_seconds": 1.0,   # 하루 48초, 5일 약 4분 (심사위원이 구름판을 옮길 시간은 충분)
        "seed": 100,      # 날마다 seed + (몇째 날)
        "clouds": None,   # 조도센서·버튼으로 직접
        "note": "5일 연속 재생 (약 4분), 누적 탄소는 5일 합계",
    },
}

ALIASES = {v["key"]: k for k, v in SCENARIOS.items()}


def get(name: str) -> dict:
    key = ALIASES.get(name, name)
    if key not in SCENARIOS:
        raise SystemExit(f"시나리오 {name!r}가 없습니다. 고를 수 있는 것: " +
                         ", ".join(f"{k} ({v['key']})" for k, v in SCENARIOS.items()))
    return SCENARIOS[key]


def cloud_plan(sc: dict, delta: float) -> dict[int, float] | None:
    """시나리오의 구름을 {칸: 더할 값}으로. 구름을 정해 두지 않은 시나리오는 None."""
    if sc.get("clouds") is None:
        return None
    plan = {}
    for a, b in sc["clouds"]:
        for t in range(a, b + 1):
            plan[t] = delta
    return plan
