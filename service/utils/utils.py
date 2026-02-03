"""
공통 유틸리티 함수
"""
from datetime import datetime, timezone, timedelta

# Asia/Seoul 시간대 (UTC+9)
KST = timezone(timedelta(hours=9))

def now_kst() -> datetime:
    """
    현재 시간을 KST (Asia/Seoul, UTC+9) 시간대로 반환

    Returns:
        datetime: KST 시간대의 현재 시간
    """
    return datetime.now(KST)

def to_kst(dt: datetime) -> datetime:
    """
    주어진 datetime을 KST 시간대로 변환

    Args:
        dt: 변환할 datetime 객체

    Returns:
        datetime: KST 시간대로 변환된 datetime
    """
    if dt.tzinfo is None:
        # naive datetime인 경우 UTC로 간주하고 KST로 변환
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(KST)

def format_kst(dt: datetime) -> str:
    """
    datetime을 KST 기준 문자열로 포맷

    Args:
        dt: 포맷할 datetime 객체

    Returns:
        str: "YYYY-MM-DD HH:MM:SS KST" 형식의 문자열
    """
    kst_time = to_kst(dt)
    return kst_time.strftime("%Y-%m-%d %H:%M:%S KST")
