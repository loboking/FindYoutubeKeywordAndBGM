"""텔레그램 알림. TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID 환경변수 없으면 스킵."""
import config as C


def send(message: str) -> bool:
    """텔레그램 메시지 전송. 성공 시 True, 스킵/실패 시 False."""
    if not (C.TELEGRAM_BOT_TOKEN and C.TELEGRAM_CHAT_ID):
        print("텔레그램 토큰/chat_id 미설정 → 스킵")
        return False
    import requests
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{C.TELEGRAM_BOT_TOKEN}/sendMessage",
            data={
                "chat_id": C.TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
        if r.status_code == 200:
            print("텔레그램 전송 완료")
            return True
        print(f"텔레그램 전송 실패: HTTP {r.status_code} {r.text[:120]}")
        return False
    except Exception as e:
        print(f"텔레그램 전송 실패: {e}")
        return False


def get_chat_id(token: str) -> str | None:
    """토큰으로 최근 메시지의 chat_id 추출 (봇에게 먼저 메시지 보내야 함). 일회용 도구."""
    import requests
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=15)
        data = r.json()
        if not data.get("ok") or not data.get("result"):
            return None
        # 가장 최근 메시지의 chat.id
        for upd in reversed(data["result"]):
            msg = upd.get("message") or upd.get("channel_post")
            if msg and msg.get("chat"):
                return str(msg["chat"]["id"])
        return None
    except Exception:
        return None


if __name__ == "__main__":
    # chat_id 추출 도구: python3 notify.py <token>
    import sys
    if len(sys.argv) >= 2:
        cid = get_chat_id(sys.argv[1])
        print(f"chat_id: {cid}" if cid else "메시지를 찾지 못함 (봇에게 먼저 메시지 보내세요)")
    else:
        print("사용: python3 notify.py <bot_token>")
