/**
 * Chair Assets - Isometric office chairs
 * Creates detailed isometric chairs with seat, backrest, legs, and shadow
 *
 * 좌표계 정의 (isometric.md 참조):
 * - gx++ → 우하단 ↘
 * - gy++ → 좌하단 ↙
 *
 * 의자 방향 (facing):
 * - 'SE' = gx++ 방향 (우하단, ↘)
 * - 'SW' = gy++ 방향 (좌하단, ↙)
 * - 'NW' = gx-- 방향 (좌상단, ↖)
 * - 'NE' = gy-- 방향 (우상단, ↗)
 */
window.CompanyView = window.CompanyView || {};

(function () {
    'use strict';

    const ISO = window.CompanyView.ISO;

    // ==================== 의자 색상 팔레트 ====================
    const CHAIR_PALETTE = {
        // 좌석 (쿠션)
        seat: {
            top: 0x4A5568,        // 좌석 상단면 (짙은 회색)
            topLight: 0x5A6578,   // 하이라이트
            front: 0x3D4452,      // 좌석 앞면 (더 어두움)
            side: 0x353D4A,       // 좌석 측면
        },
        // 등받이
        back: {
            front: 0x4A5568,      // 등받이 전면
            side: 0x3D4452,       // 등받이 측면
            top: 0x5A6578,        // 등받이 상단
        },
        // 의자 다리/프레임 (메탈)
        frame: {
            main: 0x2D3748,       // 기본 프레임 색상
            light: 0x4A5568,      // 하이라이트
            dark: 0x1A202C,       // 그림자
        },
        // 그림자
        shadow: 0x000000,
    };

    // ==================== 의자 치수 ====================
    const CHAIR_CONFIG = {
        // 좌석 크기 (타일 비율)
        seatWidth: 0.55,          // 좌석 너비 (타일 대비)
        seatDepth: 0.5,           // 좌석 깊이 (타일 대비)

        // 높이 (픽셀)
        seatHeight: 10,           // 바닥에서 좌석 상단까지
        seatThickness: 3,         // 좌석 쿠션 두께

        // 등받이
        backrestHeight: 18,       // 등받이 높이 (좌석 위)
        backrestThickness: 2,     // 등받이 두께

        // 다리
        legWidth: 2,              // 다리 너비
        legInset: 0.12,           // 모서리에서 안쪽으로 들어간 정도

        // 그림자
        shadowOffsetX: 3,
        shadowOffsetY: 2,
        shadowAlpha: 0.15,
    };

    // ==================== 방향 벡터 ====================
    // 각 방향에 대한 등받이 위치 오프셋 (좌석 기준)
    const FACING_VECTORS = {
        // 'SE' = gx++ 방향을 바라봄 → 등받이는 gx-- 쪽에
        'SE': { backOffsetGx: -1, backOffsetGy: 0 },
        // 'SW' = gy++ 방향을 바라봄 → 등받이는 gy-- 쪽에
        'SW': { backOffsetGx: 0, backOffsetGy: -1 },
        // 'NW' = gx-- 방향을 바라봄 → 등받이는 gx++ 쪽에
        'NW': { backOffsetGx: 1, backOffsetGy: 0 },
        // 'NE' = gy-- 방향을 바라봄 → 등받이는 gy++ 쪽에
        'NE': { backOffsetGx: 0, backOffsetGy: 1 },
    };

    // ==================== 그림자 그리기 ====================
    /**
     * 의자 그림자 (타원형)
     * @param {PIXI.Graphics} g
     * @param {number} cx - 그림자 중심 X
     * @param {number} cy - 그림자 중심 Y
     */
    function drawChairShadow(g, cx, cy) {
        const cfg = CHAIR_CONFIG;
        const seatW = cfg.seatWidth * ISO.TILE_W * 0.5;
        const seatD = cfg.seatDepth * ISO.TILE_H * 0.6;

        g.beginFill(CHAIR_PALETTE.shadow, cfg.shadowAlpha);
        g.drawEllipse(
            cx + cfg.shadowOffsetX,
            cy + cfg.shadowOffsetY,
            seatW * 0.8,
            seatD * 0.7
        );
        g.endFill();
    }

    // ==================== 의자 다리 그리기 ====================
    /**
     * 단일 의자 다리 (소형 직육면체)
     * @param {PIXI.Graphics} g
     * @param {number} x - 다리 바닥 중심 X
     * @param {number} y - 다리 바닥 중심 Y
     * @param {number} legHeight - 다리 높이
     */
    function drawChairLeg(g, x, y, legHeight) {
        const pal = CHAIR_PALETTE.frame;
        const legW = CHAIR_CONFIG.legWidth;

        // 다리 좌측면 (어두움)
        g.beginFill(pal.dark);
        g.moveTo(x - legW / 2, y - legHeight);
        g.lineTo(x, y - legHeight + legW / 3);
        g.lineTo(x, y + legW / 3);
        g.lineTo(x - legW / 2, y);
        g.closePath();
        g.endFill();

        // 다리 우측면 (밝음)
        g.beginFill(pal.main);
        g.moveTo(x + legW / 2, y - legHeight);
        g.lineTo(x, y - legHeight + legW / 3);
        g.lineTo(x, y + legW / 3);
        g.lineTo(x + legW / 2, y);
        g.closePath();
        g.endFill();

        // 다리 상단면
        g.beginFill(pal.light);
        g.moveTo(x, y - legHeight - legW / 4);
        g.lineTo(x + legW / 2, y - legHeight);
        g.lineTo(x, y - legHeight + legW / 3);
        g.lineTo(x - legW / 2, y - legHeight);
        g.closePath();
        g.endFill();
    }

    // ==================== 좌석 그리기 ====================
    /**
     * 의자 좌석 (아이소메트릭 다이아몬드 + 두께)
     * @param {PIXI.Graphics} g
     * @param {Object} corners - 좌석 4개 꼭지점 {top, right, bottom, left}
     * @param {number} seatHeight - 바닥에서 좌석 상단까지
     * @param {number} thickness - 좌석 두께
     */
    function drawChairSeat(g, corners, seatHeight, thickness) {
        const pal = CHAIR_PALETTE.seat;

        // 좌석 위치 (y를 seatHeight만큼 위로)
        const top = { x: corners.top.x, y: corners.top.y - seatHeight };
        const right = { x: corners.right.x, y: corners.right.y - seatHeight };
        const bottom = { x: corners.bottom.x, y: corners.bottom.y - seatHeight };
        const left = { x: corners.left.x, y: corners.left.y - seatHeight };

        // ========== 좌석 측면 (두께 표현) ==========

        // 좌하단 측면 (left → bottom) - 어두운 면
        g.beginFill(pal.side);
        g.moveTo(left.x, left.y);
        g.lineTo(bottom.x, bottom.y);
        g.lineTo(bottom.x, bottom.y + thickness);
        g.lineTo(left.x, left.y + thickness);
        g.closePath();
        g.endFill();

        // 우하단 측면 (bottom → right) - 밝은 면
        g.beginFill(pal.front);
        g.moveTo(bottom.x, bottom.y);
        g.lineTo(right.x, right.y);
        g.lineTo(right.x, right.y + thickness);
        g.lineTo(bottom.x, bottom.y + thickness);
        g.closePath();
        g.endFill();

        // ========== 좌석 상단면 ==========
        g.beginFill(pal.top);
        g.moveTo(top.x, top.y);
        g.lineTo(right.x, right.y);
        g.lineTo(bottom.x, bottom.y);
        g.lineTo(left.x, left.y);
        g.closePath();
        g.endFill();

        // 쿠션 하이라이트 (중앙 부분)
        g.beginFill(pal.topLight, 0.3);
        const cx = (top.x + bottom.x) / 2;
        const cy = (top.y + bottom.y) / 2;
        g.drawEllipse(cx, cy, (right.x - left.x) * 0.25, (bottom.y - top.y) * 0.3);
        g.endFill();

        return { top, right, bottom, left };
    }

    // ==================== 등받이 그리기 ====================
    /**
     * 의자 등받이
     * @param {PIXI.Graphics} g
     * @param {Object} seatCorners - 좌석 꼭지점 (이미 높이 적용된 상태)
     * @param {string} facing - 의자 방향 ('SE', 'SW', 'NW', 'NE')
     * @param {number} backHeight - 등받이 높이
     * @param {number} backThickness - 등받이 두께
     */
    function drawChairBack(g, seatCorners, facing, backHeight, backThickness) {
        const pal = CHAIR_PALETTE.back;

        // 아이소메트릭 카메라는 우상단에서 좌하단을 내려다봄
        // 따라서 gx++ 방향(↘)과 gy++ 방향(↙) 면이 보임
        // gx-- 방향(↖)과 gy-- 방향(↗) 면은 안 보임

        // 등받이 방향별 설정
        // - baseLeft/baseRight: 등받이 하단 좌우 꼭지점
        // - thicknessDir: 두께가 그려지는 방향 ('gx+', 'gx-', 'gy+', 'gy-')
        // - showThickness: 두께 면이 카메라에 보이는지
        // - showLeftSide/showRightSide: 좌우 측면 중 어느 쪽이 보이는지
        let baseLeft, baseRight;
        let thicknessOffsetX = 0;
        let thicknessOffsetY = 0;
        let showThickness = false;
        let showLeftSide = false;
        let showRightSide = false;

        const thicknessPx = backThickness * 3; // 두께를 픽셀 단위로 증폭

        switch (facing) {
            case 'SE': // gx++ 바라봄 → 등받이는 좌상단 가장자리 (left~top)
                baseLeft = seatCorners.left;
                baseRight = seatCorners.top;
                // 등받이 두께는 gx++ 방향(↘)으로 = 사용자 앞쪽
                // 화면상: x+, y+ 방향
                thicknessOffsetX = thicknessPx * 0.5;
                thicknessOffsetY = thicknessPx * 0.25;
                showThickness = true; // gx++ 방향은 보임
                showRightSide = true; // 오른쪽(top) 측면이 보임 (gy++ 방향)
                break;

            case 'SW': // gy++ 바라봄 → 등받이는 우상단 가장자리 (top~right)
                baseLeft = seatCorners.top;
                baseRight = seatCorners.right;
                // 등받이 두께는 gy++ 방향(↙)으로 = 사용자 앞쪽
                // 화면상: x-, y+ 방향
                thicknessOffsetX = -thicknessPx * 0.5;
                thicknessOffsetY = thicknessPx * 0.25;
                showThickness = true; // gy++ 방향은 보임
                showLeftSide = true; // 왼쪽(top) 측면이 보임 (gx++ 방향)
                break;

            case 'NW': // gx-- 바라봄 → 등받이는 우하단 가장자리 (right~bottom)
                baseLeft = seatCorners.right;
                baseRight = seatCorners.bottom;
                // 등받이 두께는 gx-- 방향(↖)으로 = 사용자 앞쪽
                // 화면상: x-, y- 방향 → 카메라에 안 보임
                // 대신 반대쪽(gx++ 방향) 뒷면이 보여야 함
                thicknessOffsetX = thicknessPx * 0.5;
                thicknessOffsetY = thicknessPx * 0.25;
                showThickness = true; // 뒷면(gx++ 방향)이 보임
                showLeftSide = true; // 왼쪽(right) 측면이 보임 (gy++ 방향)
                break;

            case 'NE': // gy-- 바라봄 → 등받이는 좌하단 가장자리 (bottom~left)
                baseLeft = seatCorners.bottom;
                baseRight = seatCorners.left;
                // 등받이 두께는 gy-- 방향(↗)으로 = 사용자 앞쪽
                // 화면상: x+, y- 방향 → 카메라에 안 보임
                // 대신 반대쪽(gy++ 방향) 뒷면이 보여야 함
                thicknessOffsetX = -thicknessPx * 0.5;
                thicknessOffsetY = thicknessPx * 0.25;
                showThickness = true; // 뒷면(gy++ 방향)이 보임
                showRightSide = true; // 오른쪽(left) 측면이 보임 (gx++ 방향)
                break;

            default:
                baseLeft = seatCorners.top;
                baseRight = seatCorners.right;
                thicknessOffsetX = -thicknessPx * 0.5;
                thicknessOffsetY = thicknessPx * 0.25;
                showThickness = true;
        }

        // 등받이 베이스 좌표 (좌석 상단면 위)
        const bl = { x: baseLeft.x, y: baseLeft.y };
        const br = { x: baseRight.x, y: baseRight.y };

        // 등받이 상단 좌표
        const tl = { x: bl.x, y: bl.y - backHeight };
        const tr = { x: br.x, y: br.y - backHeight };

        // 두께가 적용된 뒷면 좌표
        const bl2 = { x: bl.x + thicknessOffsetX, y: bl.y + thicknessOffsetY };
        const br2 = { x: br.x + thicknessOffsetX, y: br.y + thicknessOffsetY };
        const tl2 = { x: tl.x + thicknessOffsetX, y: tl.y + thicknessOffsetY };
        const tr2 = { x: tr.x + thicknessOffsetX, y: tr.y + thicknessOffsetY };

        // ========== 등받이 두께 면 (앞뒤 연결) ==========
        if (showThickness) {
            g.beginFill(pal.side);
            g.moveTo(bl.x, bl.y);
            g.lineTo(br.x, br.y);
            g.lineTo(br2.x, br2.y);
            g.lineTo(bl2.x, bl2.y);
            g.closePath();
            g.endFill();
        }

        // ========== 왼쪽 측면 ==========
        if (showLeftSide) {
            g.beginFill(pal.side, 0.9);
            g.moveTo(bl.x, bl.y);
            g.lineTo(bl2.x, bl2.y);
            g.lineTo(tl2.x, tl2.y);
            g.lineTo(tl.x, tl.y);
            g.closePath();
            g.endFill();
        }

        // ========== 오른쪽 측면 ==========
        if (showRightSide) {
            g.beginFill(pal.side, 0.9);
            g.moveTo(br.x, br.y);
            g.lineTo(br2.x, br2.y);
            g.lineTo(tr2.x, tr2.y);
            g.lineTo(tr.x, tr.y);
            g.closePath();
            g.endFill();
        }

        // ========== 등받이 전면 ==========
        g.beginFill(pal.front);
        g.moveTo(bl.x, bl.y);
        g.lineTo(br.x, br.y);
        g.lineTo(tr.x, tr.y);
        g.lineTo(tl.x, tl.y);
        g.closePath();
        g.endFill();

        // ========== 등받이 상단면 ==========
        g.beginFill(pal.top);
        g.moveTo(tl.x, tl.y);
        g.lineTo(tr.x, tr.y);
        g.lineTo(tr2.x, tr2.y);
        g.lineTo(tl2.x, tl2.y);
        g.closePath();
        g.endFill();

        // ========== 등받이 장식 (수평선) ==========
        g.lineStyle(1, pal.side, 0.5);
        const midYOffset = backHeight * 0.3;
        // 상단 장식선
        g.moveTo(bl.x, bl.y - midYOffset - 2);
        g.lineTo(br.x, br.y - midYOffset - 2);
        // 하단 장식선
        g.moveTo(bl.x, bl.y - midYOffset + 4);
        g.lineTo(br.x, br.y - midYOffset + 4);
        g.lineStyle(0);
    }

    // ==================== 메인 의자 생성 함수 ====================
    /**
     * 아이소메트릭 의자 생성
     * @param {number} gridX - 그리드 X 좌표
     * @param {number} gridY - 그리드 Y 좌표
     * @param {string} facing - 의자 방향 ('SE', 'SW', 'NW', 'NE')
     * @returns {Object} { base: PIXI.Container, backrest: PIXI.Container }
     *                   base: 그림자+다리+좌석 (테이블 아래)
     *                   backrest: 등받이 (테이블 위)
     */
    function createChair(gridX, gridY, facing = 'SW') {
        const cfg = CHAIR_CONFIG;
        const seatW = cfg.seatWidth;
        const seatD = cfg.seatDepth;
        const seatHeight = cfg.seatHeight;
        const thickness = cfg.seatThickness;
        const backHeight = cfg.backrestHeight;
        const backThickness = cfg.backrestThickness;
        const legInset = cfg.legInset;

        // ========== 좌석 꼭지점 계산 (로컬 좌표, 원점 = 의자 중심) ==========
        const halfW = seatW / 2;
        const halfD = seatD / 2;

        // 아이소메트릭 꼭지점 (로컬 좌표)
        const topPos = ISO.gridToScreen(-halfW, -halfD);
        const rightPos = ISO.gridToScreen(halfW, -halfD);
        const bottomPos = ISO.gridToScreen(halfW, halfD);
        const leftPos = ISO.gridToScreen(-halfW, halfD);

        const corners = {
            top: { x: topPos.x, y: topPos.y },
            right: { x: rightPos.x, y: rightPos.y },
            bottom: { x: bottomPos.x, y: bottomPos.y },
            left: { x: leftPos.x, y: leftPos.y },
        };

        // ========== Base 컨테이너 (그림자 + 다리 + 좌석) ==========
        const baseContainer = new PIXI.Container();
        const baseG = new PIXI.Graphics();

        // 그림자
        drawChairShadow(baseG, 0, 0);

        // 다리 4개
        const legOffsetW = halfW - legInset;
        const legOffsetD = halfD - legInset;
        const legHeight = seatHeight - thickness;

        const legPositions = [
            ISO.gridToScreen(-legOffsetW, -legOffsetD),
            ISO.gridToScreen(legOffsetW, -legOffsetD),
            ISO.gridToScreen(legOffsetW, legOffsetD),
            ISO.gridToScreen(-legOffsetW, legOffsetD),
        ];

        // 깊이 순서에 따라 다리 그리기 (뒤쪽부터)
        drawChairLeg(baseG, legPositions[0].x, legPositions[0].y, legHeight);
        drawChairLeg(baseG, legPositions[1].x, legPositions[1].y, legHeight);
        drawChairLeg(baseG, legPositions[3].x, legPositions[3].y, legHeight);
        drawChairLeg(baseG, legPositions[2].x, legPositions[2].y, legHeight);

        // 좌석
        const seatCorners = drawChairSeat(baseG, corners, seatHeight, thickness);

        baseContainer.addChild(baseG);

        // ========== Backrest 컨테이너 (등받이) ==========
        const backrestContainer = new PIXI.Container();
        const backrestG = new PIXI.Graphics();

        drawChairBack(backrestG, seatCorners, facing, backHeight, backThickness);

        backrestContainer.addChild(backrestG);

        // ========== 위치 및 깊이 설정 ==========
        const screenPos = ISO.gridToScreen(gridX, gridY);

        baseContainer.x = screenPos.x;
        baseContainer.y = screenPos.y;
        // 의자 하단은 테이블보다 먼저 렌더링 (테이블 아래)
        baseContainer.zIndex = ISO.depthKey(gridX, gridY, -300);

        backrestContainer.x = screenPos.x;
        backrestContainer.y = screenPos.y;

        // 등받이의 실제 위치를 반영한 zIndex 계산
        // facing에 따라 등받이가 의자 기준 어느 방향에 있는지 결정
        let backrestGridX = gridX;
        let backrestGridY = gridY;
        const backOffset = 0.5; // 등받이 위치 오프셋

        switch (facing) {
            case 'SE': // 등받이가 gx-- 방향
                backrestGridX -= backOffset;
                break;
            case 'SW': // 등받이가 gy-- 방향
                backrestGridY -= backOffset;
                break;
            case 'NW': // 등받이가 gx++ 방향
                backrestGridX += backOffset;
                break;
            case 'NE': // 등받이가 gy++ 방향
                backrestGridY += backOffset;
                break;
        }

        // 등받이는 실제 위치 기준으로 depth 계산 + 테이블보다 확실히 위에 렌더링
        // layer를 높게 설정하여 (gx+gy) 차이를 상쇄
        backrestContainer.zIndex = ISO.depthKey(backrestGridX, backrestGridY, 200);

        return { base: baseContainer, backrest: backrestContainer };
    }

    // ==================== Export ====================
    window.CompanyView.ChairAssets = {
        CHAIR_PALETTE,
        CHAIR_CONFIG,
        createChair,
    };

})();
