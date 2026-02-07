/**
 * Conference Table - 3x5 대형 회의 테이블
 * 아이소메트릭 뷰에서 디테일한 회의용 책상을 렌더링
 *
 * 좌표계 정의 (isometric.md 참조):
 * - gx++ → 우하단 ↘
 * - gy++ → 좌하단 ↙
 * - gridToScreen(gx, gy) → 타일 중심의 화면 좌표
 */
window.CompanyView = window.CompanyView || {};

(function () {
    'use strict';

    const ISO = window.CompanyView.ISO;

    // ==================== 테이블 색상 팔레트 ====================
    const TABLE_PALETTE = {
        // 테이블 상판 (따뜻한 나무 톤)
        top: {
            main: 0xD4A574,        // 메인 나무색
            light: 0xE5BC8A,       // 하이라이트
            dark: 0xC49464,        // 그림자
        },
        // 테이블 측면
        side: {
            left: 0xA67C52,        // 좌측면 (어두움) - 좌하단 방향
            right: 0xBE9468,       // 우측면 (밝음) - 우하단 방향
        },
        // 테이블 다리
        leg: {
            main: 0x4A4A4A,        // 메탈릭 그레이
            highlight: 0x5A5A5A,
            shadow: 0x3A3A3A,
        },
        // 테두리
        trim: 0x8B6914,
    };

    // ==================== 테이블 치수 ====================
    const TABLE_CONFIG = {
        // 그리드 크기 (타일 단위)
        // 5x3 테이블: gx 방향 5타일, gy 방향 3타일
        gridWidth: 5,             // gx 방향 5타일 (우하단 ↘)
        gridHeight: 3,            // gy 방향 3타일 (좌하단 ↙)

        // 높이 (픽셀)
        tableHeight: 16,          // 테이블 전체 높이 (바닥에서 상판 상단까지)
        topThickness: 4,          // 상판 두께

        // 다리 설정
        legInset: 0.4,            // 모서리에서 안쪽으로 들어간 정도 (그리드 단위)
        legWidth: 6,              // 다리 너비
        legDepth: 4,              // 다리 깊이
    };

    // ==================== 테이블 다리 그리기 ====================
    /**
     * @param {PIXI.Graphics} g - 그래픽스 객체
     * @param {number} x - 화면 X 좌표 (바닥 위치)
     * @param {number} y - 화면 Y 좌표 (바닥 위치)
     * @param {number} legHeight - 다리 높이
     */
    function drawTableLeg(g, x, y, legHeight) {
        const pal = TABLE_PALETTE.leg;
        const legW = TABLE_CONFIG.legWidth;
        const legD = TABLE_CONFIG.legDepth;

        // 바닥 그림자
        g.beginFill(0x000000, 0.2);
        g.drawEllipse(x, y + 2, legW / 2 + 2, legD / 2 + 1);
        g.endFill();

        // 다리 좌측면 (어두움)
        g.beginFill(pal.shadow);
        g.moveTo(x - legW / 2, y - legHeight);
        g.lineTo(x, y - legHeight + legD / 2);
        g.lineTo(x, y + legD / 2);
        g.lineTo(x - legW / 2, y);
        g.closePath();
        g.endFill();

        // 다리 우측면 (밝음)
        g.beginFill(pal.main);
        g.moveTo(x + legW / 2, y - legHeight);
        g.lineTo(x, y - legHeight + legD / 2);
        g.lineTo(x, y + legD / 2);
        g.lineTo(x + legW / 2, y);
        g.closePath();
        g.endFill();

        // 다리 상단면 (아이소메트릭 다이아몬드)
        g.beginFill(pal.highlight);
        g.moveTo(x, y - legHeight - legD / 2);
        g.lineTo(x + legW / 2, y - legHeight);
        g.lineTo(x, y - legHeight + legD / 2);
        g.lineTo(x - legW / 2, y - legHeight);
        g.closePath();
        g.endFill();
    }

    // ==================== 테이블 상판 그리기 ====================
    /**
     * @param {PIXI.Graphics} g - 그래픽스 객체
     * @param {Object} corners - 상판 4개 꼭지점 {top, right, bottom, left}
     * @param {number} tableHeight - 바닥에서 상판 상단까지 높이
     * @param {number} thickness - 상판 두께
     */
    function drawTableTop(g, corners, tableHeight, thickness) {
        const pal = TABLE_PALETTE.top;
        const sidePal = TABLE_PALETTE.side;

        // 상판 위치 (y를 tableHeight만큼 위로)
        const top = { x: corners.top.x, y: corners.top.y - tableHeight };
        const right = { x: corners.right.x, y: corners.right.y - tableHeight };
        const bottom = { x: corners.bottom.x, y: corners.bottom.y - tableHeight };
        const left = { x: corners.left.x, y: corners.left.y - tableHeight };

        // ========== 상판 측면 (두께 표현) ==========

        // 좌하단 측면 (left → bottom 방향) - 어두운 면
        g.beginFill(sidePal.left);
        g.moveTo(left.x, left.y);
        g.lineTo(bottom.x, bottom.y);
        g.lineTo(bottom.x, bottom.y + thickness);
        g.lineTo(left.x, left.y + thickness);
        g.closePath();
        g.endFill();

        // 우하단 측면 (bottom → right 방향) - 밝은 면
        g.beginFill(sidePal.right);
        g.moveTo(bottom.x, bottom.y);
        g.lineTo(right.x, right.y);
        g.lineTo(right.x, right.y + thickness);
        g.lineTo(bottom.x, bottom.y + thickness);
        g.closePath();
        g.endFill();

        // ========== 상판 상단면 ==========
        g.beginFill(pal.main);
        g.moveTo(top.x, top.y);
        g.lineTo(right.x, right.y);
        g.lineTo(bottom.x, bottom.y);
        g.lineTo(left.x, left.y);
        g.closePath();
        g.endFill();

        // 하이라이트 (좌상단 부분)
        g.beginFill(pal.light, 0.35);
        const cx = (top.x + bottom.x) / 2;
        const cy = (top.y + bottom.y) / 2;
        g.moveTo(top.x, top.y);
        g.lineTo(cx + (right.x - cx) * 0.3, cy + (right.y - cy) * 0.3);
        g.lineTo(cx, cy);
        g.lineTo(cx + (left.x - cx) * 0.3, cy + (left.y - cy) * 0.3);
        g.closePath();
        g.endFill();

        // 그림자 (우하단 부분)
        g.beginFill(pal.dark, 0.25);
        g.moveTo(bottom.x, bottom.y);
        g.lineTo(cx + (right.x - cx) * 0.7, cy + (right.y - cy) * 0.7);
        g.lineTo(cx, cy);
        g.lineTo(cx + (left.x - cx) * 0.7, cy + (left.y - cy) * 0.7);
        g.closePath();
        g.endFill();

        // ========== 테두리 ==========
        g.lineStyle(1, TABLE_PALETTE.trim, 0.5);
        g.moveTo(top.x, top.y);
        g.lineTo(right.x, right.y);
        g.lineTo(bottom.x, bottom.y);
        g.lineTo(left.x, left.y);
        g.lineTo(top.x, top.y);
        g.lineStyle(0);

        // 나무결
        g.lineStyle(1, pal.dark, 0.1);
        for (let i = 1; i < 6; i++) {
            const t = i / 6;
            const x1 = left.x + (top.x - left.x) * t;
            const y1 = left.y + (top.y - left.y) * t;
            const x2 = bottom.x + (right.x - bottom.x) * t;
            const y2 = bottom.y + (right.y - bottom.y) * t;
            g.moveTo(x1, y1);
            g.lineTo(x2, y2);
        }
        g.lineStyle(0);
    }

    // ==================== 메인 테이블 생성 함수 ====================
    /**
     * 3x5 회의 테이블 생성
     * @param {number} gridX - 시작 그리드 X 좌표
     * @param {number} gridY - 시작 그리드 Y 좌표
     * @returns {PIXI.Container} 테이블 컨테이너
     */
    function createConferenceTable(gridX, gridY) {
        const container = new PIXI.Container();
        const g = new PIXI.Graphics();

        const W = TABLE_CONFIG.gridWidth;   // 3
        const H = TABLE_CONFIG.gridHeight;  // 5
        const tableHeight = TABLE_CONFIG.tableHeight;
        const thickness = TABLE_CONFIG.topThickness;
        const legInset = TABLE_CONFIG.legInset;

        // ========== 상판 꼭지점 계산 (상대 좌표, 원점 = 그리드 0,0) ==========
        // 아이소메트릭 다이아몬드 영역 (W x H 타일)의 4개 꼭지점
        //
        // 좌표계:
        //   gx++ → ↘ (우하단)
        //   gy++ → ↙ (좌하단)
        //
        //                  top (gx=0, gy=0의 위쪽 꼭지점)
        //                   ◆
        //                 ↗   ↘
        //     left      ◆       ◆      right
        //  (gy=H 끝)       ↘   ↗    (gx=W 끝)
        //                   ◆
        //                 bottom

        // 각 꼭지점 계산 - 바닥면 기준
        const topPos = ISO.gridToScreen(0, 0);
        const rightPos = ISO.gridToScreen(W, 0);
        const bottomPos = ISO.gridToScreen(W, H);
        const leftPos = ISO.gridToScreen(0, H);

        const corners = {
            top:    { x: topPos.x,    y: topPos.y - ISO.TILE_H / 2 },
            right:  { x: rightPos.x,  y: rightPos.y - ISO.TILE_H / 2 },
            bottom: { x: bottomPos.x, y: bottomPos.y - ISO.TILE_H / 2 },
            left:   { x: leftPos.x,   y: leftPos.y - ISO.TILE_H / 2 },
        };

        // ========== 다리 위치 계산 ==========
        // 4개 모서리에서 안쪽으로 들어간 위치
        // 다리는 상판 영역 안쪽에 위치해야 함
        // 중요: 상판과 같은 좌표계 사용 (y에서 TILE_H/2 빼기)
        const leg0 = ISO.gridToScreen(legInset, legInset);
        const leg1 = ISO.gridToScreen(W - legInset, legInset);
        const leg2 = ISO.gridToScreen(W - legInset, H - legInset);
        const leg3 = ISO.gridToScreen(legInset, H - legInset);

        const legPositions = [
            { x: leg0.x, y: leg0.y - ISO.TILE_H / 2 },  // 뒤쪽 좌측
            { x: leg1.x, y: leg1.y - ISO.TILE_H / 2 },  // 뒤쪽 우측
            { x: leg2.x, y: leg2.y - ISO.TILE_H / 2 },  // 앞쪽 우측
            { x: leg3.x, y: leg3.y - ISO.TILE_H / 2 },  // 앞쪽 좌측
        ];

        // 다리 높이 = 상판 높이 - 상판 두께
        const legHeight = tableHeight - thickness;

        // ========== 그림자 ==========
        g.beginFill(0x000000, 0.12);
        g.moveTo(corners.top.x + 4, corners.top.y + 4);
        g.lineTo(corners.right.x + 4, corners.right.y + 4);
        g.lineTo(corners.bottom.x + 4, corners.bottom.y + 4);
        g.lineTo(corners.left.x + 4, corners.left.y + 4);
        g.closePath();
        g.endFill();

        // ========== 다리 4개 모두 그리기 (상판보다 먼저) ==========
        // 깊이 순서: 뒤쪽 → 앞쪽 (gx+gy 작은 것부터)
        // 뒤쪽 다리 2개
        drawTableLeg(g, legPositions[0].x, legPositions[0].y, legHeight);  // 뒤쪽 좌측
        drawTableLeg(g, legPositions[1].x, legPositions[1].y, legHeight);  // 뒤쪽 우측
        // 앞쪽 다리 2개 (상판 측면 아래에 일부 보임)
        drawTableLeg(g, legPositions[3].x, legPositions[3].y, legHeight);  // 앞쪽 좌측
        drawTableLeg(g, legPositions[2].x, legPositions[2].y, legHeight);  // 앞쪽 우측

        // ========== 상판 ==========
        drawTableTop(g, corners, tableHeight, thickness);

        container.addChild(g);

        // ========== 위치 및 깊이 설정 ==========
        const screenPos = ISO.gridToScreen(gridX, gridY);
        container.x = screenPos.x;
        container.y = screenPos.y;

        // 깊이 정렬 (테이블 중앙 기준)
        container.zIndex = ISO.depthKey(
            gridX + W / 2,
            gridY + H / 2,
            1
        );

        return container;
    }

    // ==================== Export ====================
    window.CompanyView.ConferenceTable = {
        TABLE_PALETTE,
        TABLE_CONFIG,
        createConferenceTable,
    };

})();
