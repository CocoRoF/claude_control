"""
AutonomousGraph 시각화 스크립트

이 스크립트는 새로운 난이도 기반 AutonomousGraph를 시각화합니다.

사용법:
    python visualize_autonomous_graph.py

출력:
    - autonomous_graph.png: PNG 이미지 파일
    - autonomous_graph.md: Mermaid 다이어그램 (콘솔 출력)
"""

import asyncio
import sys
import os

# 프로젝트 루트 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from service.langgraph.autonomous_graph import AutonomousGraph, AutonomousState, Difficulty


def main():
    print("=" * 60)
    print("AutonomousGraph 시각화")
    print("=" * 60)
    print()

    # Mock 모델 생성 (시각화만 하므로 실제 모델 불필요)
    # AutonomousGraph는 build()만 호출하면 시각화 가능

    class MockModel:
        """시각화용 Mock 모델"""
        session_id = "mock-session"

        async def ainvoke(self, messages):
            """Mock ainvoke"""
            class MockResponse:
                content = "mock response"
            return MockResponse()

    mock_model = MockModel()

    # AutonomousGraph 생성
    print("📊 AutonomousGraph 생성 중...")
    graph = AutonomousGraph(
        model=mock_model,
        session_id="visualization",
        enable_checkpointing=False,
        max_review_retries=3,
    )

    # 그래프 빌드
    print("🔧 그래프 빌드 중...")
    compiled = graph.build()
    print("✅ 그래프 빌드 완료!")
    print()

    # Mermaid 다이어그램 생성
    print("📝 Mermaid 다이어그램:")
    print("-" * 40)
    mermaid = graph.get_mermaid_diagram()
    if mermaid:
        print(mermaid)
        print("-" * 40)

        # Mermaid 파일 저장
        with open("autonomous_graph.md", "w", encoding="utf-8") as f:
            f.write("# AutonomousGraph Mermaid Diagram\n\n")
            f.write("```mermaid\n")
            f.write(mermaid)
            f.write("\n```\n")
        print()
        print("💾 Mermaid 다이어그램 저장됨: autonomous_graph.md")
    else:
        print("⚠️ Mermaid 다이어그램 생성 실패")

    # PNG 이미지 생성 시도
    print()
    print("🖼️ PNG 이미지 생성 시도 중...")
    try:
        png_bytes = graph.visualize()
        if png_bytes:
            with open("autonomous_graph.png", "wb") as f:
                f.write(png_bytes)
            print("✅ PNG 이미지 저장됨: autonomous_graph.png")
        else:
            print("⚠️ PNG 이미지 생성 실패 (graphviz 설치 필요할 수 있음)")
    except Exception as e:
        print(f"⚠️ PNG 이미지 생성 오류: {e}")
        print("   (graphviz 또는 pygraphviz 설치가 필요할 수 있습니다)")

    print()
    print("=" * 60)
    print("그래프 구조 설명:")
    print("=" * 60)
    print("""
    ┌───────────────────────────────────────────────────────────┐
    │                         START                              │
    │                           ↓                                │
    │                  classify_difficulty                       │
    │                    ↙     ↓     ↘                          │
    │               easy    medium    hard                       │
    │                 ↓        ↓        ↓                        │
    │          direct_answer  answer  create_todos               │
    │                 ↓        ↓        ↓                        │
    │                END    review   execute_todo                │
    │                        ↙  ↘       ↓                        │
    │                 approved  rejected  check_progress         │
    │                    ↓        ↓       ↙     ↘               │
    │                   END    answer  continue  complete        │
    │                              (retry) ↓        ↓            │
    │                             execute_todo  final_review     │
    │                                              ↓             │
    │                                         final_answer       │
    │                                              ↓             │
    │                                             END            │
    └───────────────────────────────────────────────────────────┘
    """)

    print()
    print("난이도 분류 기준:")
    print("-" * 40)
    print("EASY: 단순 질문, 사실 조회, 기본 계산")
    print("      예: '2+2는?', '프랑스 수도는?'")
    print()
    print("MEDIUM: 중간 복잡도, 추론 필요, 한 번에 답변 가능")
    print("        예: '광합성 설명해줘', '파이썬 vs 자바스크립트'")
    print()
    print("HARD: 복잡한 작업, 여러 단계, 계획 및 반복 실행 필요")
    print("      예: '웹앱 만들어줘', '이 코드베이스 디버깅해줘'")

    print()
    print("✨ 시각화 완료!")


if __name__ == "__main__":
    main()
