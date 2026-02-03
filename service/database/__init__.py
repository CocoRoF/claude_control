"""
데이터베이스 모듈 초기화

HTTP 기반 DatabaseClient를 사용하여 xgen-core의 데이터베이스 서비스에 접근합니다.

사용 가능한 클래스:
- DatabaseClient: HTTP 기반 데이터베이스 클라이언트
"""
from service.database.database_client import DatabaseClient

__all__ = ['DatabaseClient']

