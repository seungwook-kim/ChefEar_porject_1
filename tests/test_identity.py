"""identity.py 테스트 — 작업3 쿠키 UUID 개인화. 실제 브라우저/Streamlit 없이
get/[]=/save 인터페이스만 흉내낸 대역으로 로직만 검증한다.
"""
from orchestration.identity import COOKIE_KEY, get_or_create_anon_id


class FakeCookies(dict):
    def __init__(self):
        super().__init__()
        self.saved = False

    def save(self):
        self.saved = True


def test_creates_and_persists_new_id_when_missing():
    cookies = FakeCookies()

    anon_id = get_or_create_anon_id(cookies)

    assert anon_id
    assert cookies[COOKIE_KEY] == anon_id
    assert cookies.saved is True


def test_reuses_existing_id_without_resaving():
    cookies = FakeCookies()
    cookies[COOKIE_KEY] = "already-there"

    anon_id = get_or_create_anon_id(cookies)

    assert anon_id == "already-there"
    assert cookies.saved is False  # 이미 있으면 다시 save() 안 함
