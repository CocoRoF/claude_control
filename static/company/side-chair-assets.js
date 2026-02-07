/**
 * Side Chair Assets - 프리미엄 빨간색 오피스 체어
 * 고품질 아이소메트릭 렌더링: 풍부한 그라데이션, 입체 쿠션, 정교한 음영
 *
 * 좌표계 정의 (isometric.md 참조):
 * - gx++ → 우하단 ↘
 * - gy++ → 좌하단 ↙
 */
window.CompanyView = window.CompanyView || {};

(function () {
    'use strict';

    const ISO = window.CompanyView.ISO;

    // ==================== 프리미엄 색상 팔레트 ====================
    const SIDE_CHAIR_PALETTE = {
        // 좌석 및 등받이 (프리미엄 레드 톤)
        cushion: {
            highlight: 0xF1948A,  // 밝은 하이라이트
            light: 0xE74C3C,      // 밝은 면
            main: 0xDC3545,       // 메인 컬러
            mid: 0xC0392B,        // 중간톤
            dark: 0xA93226,       // 어두운 면
            shadow: 0x922B21,     // 깊은 그림자
            edge: 0x7B241C,       // 가장 어두운 가장자리
        },
        // 프레임 (프리미엄 다크 메탈)
        frame: {
            highlight: 0x5D6D7E,  // 금속 반사광
            light: 0x4A5568,      // 밝은 부분
            main: 0x2D3748,       // 메인
            dark: 0x1A202C,       // 어두운 부분
            shadow: 0x0D1117,     // 그림자
        },
        // 크롬 기둥
        chrome: {
            highlight: 0xBDC3C7,  // 크롬 하이라이트
            light: 0x95A5A6,      // 밝은 면
            main: 0x7F8C8D,       // 메인
            dark: 0x566573,       // 어두운 면
            shadow: 0x2C3E50,     // 그림자
        },
        // 그림자
        shadow: 0x000000,
    };

    // ==================== 프리미엄 치수 ====================
    const SIDE_CHAIR_CONFIG = {
        seatWidth: 0.52,
        seatDepth: 0.48,
        seatHeight: 13,
        seatThickness: 5,
        seatCushionDepth: 3,      // 쿠션 볼록함

        backrestHeight: 24,
        backrestThickness: 5,
        backrestCurveTop: 4,      // 상단 곡선
        backrestCurveSide: 2,     // 측면 곡선

        poleWidth: 4,
        poleHeight: 9,

        baseRadius: 0.38,
        wheelCount: 5,
        wheelWidth: 4,
        wheelHeight: 3,
        legThickness: 2.5,

        shadowBlur: 0.22,
    };

    // ==================== 유틸리티: 색상 보간 ====================
    function lerpColor(c1, c2, t) {
        const r1 = (c1 >> 16) & 0xFF, g1 = (c1 >> 8) & 0xFF, b1 = c1 & 0xFF;
        const r2 = (c2 >> 16) & 0xFF, g2 = (c2 >> 8) & 0xFF, b2 = c2 & 0xFF;
        const r = Math.round(r1 + (r2 - r1) * t);
        const g = Math.round(g1 + (g2 - g1) * t);
        const b = Math.round(b1 + (b2 - b1) * t);
        return (r << 16) | (g << 8) | b;
    }

    // ==================== 프리미엄 그림자 ====================
    function drawPremiumShadow(g, cx, cy) {
        const cfg = SIDE_CHAIR_CONFIG;
        const radius = cfg.baseRadius * ISO.TILE_W * 0.55;

        // 다중 레이어 소프트 그림자
        for (let i = 3; i >= 0; i--) {
            const scale = 1 + i * 0.15;
            const alpha = cfg.shadowBlur * (0.3 - i * 0.06);
            g.beginFill(SIDE_CHAIR_PALETTE.shadow, alpha);
            g.drawEllipse(cx + 3 + i, cy + 3 + i * 0.5, radius * scale, radius * 0.5 * scale);
            g.endFill();
        }
    }

    // ==================== 프리미엄 바퀴 베이스 ====================
    function drawPremiumWheeledBase(g, cx, cy) {
        const cfg = SIDE_CHAIR_CONFIG;
        const pal = SIDE_CHAIR_PALETTE.frame;
        const baseRadius = cfg.baseRadius * ISO.TILE_W * 0.5;

        // 5개 다리와 바퀴
        for (let i = 0; i < cfg.wheelCount; i++) {
            const angle = (i / cfg.wheelCount) * Math.PI * 2 - Math.PI / 2;
            const legEndX = cx + Math.cos(angle) * baseRadius;
            const legEndY = cy + Math.sin(angle) * baseRadius * 0.5;

            // 다리 - 3D 효과 (두께감)
            const legMidX = cx + Math.cos(angle) * baseRadius * 0.5;
            const legMidY = cy + Math.sin(angle) * baseRadius * 0.5 * 0.5;

            // 다리 상단면
            g.beginFill(pal.light);
            g.moveTo(cx - 1.5, cy - 0.5);
            g.lineTo(cx + 1.5, cy + 0.5);
            g.lineTo(legEndX + 1.5, legEndY + 0.5);
            g.lineTo(legEndX - 1.5, legEndY - 0.5);
            g.closePath();
            g.endFill();

            // 다리 측면 (아래쪽)
            g.beginFill(pal.dark);
            g.moveTo(cx - 1.5, cy - 0.5);
            g.lineTo(legEndX - 1.5, legEndY - 0.5);
            g.lineTo(legEndX - 1.5, legEndY + 1);
            g.lineTo(cx - 1.5, cy + 1);
            g.closePath();
            g.endFill();

            // 바퀴 하우징
            g.beginFill(pal.shadow);
            g.drawEllipse(legEndX, legEndY + 2, cfg.wheelWidth + 1, cfg.wheelHeight * 0.6);
            g.endFill();

            // 바퀴 본체
            g.beginFill(pal.main);
            g.drawEllipse(legEndX, legEndY + 1.5, cfg.wheelWidth, cfg.wheelHeight * 0.55);
            g.endFill();

            // 바퀴 상단 하이라이트
            g.beginFill(pal.highlight, 0.5);
            g.drawEllipse(legEndX - 1, legEndY + 0.5, cfg.wheelWidth * 0.5, cfg.wheelHeight * 0.25);
            g.endFill();

            // 바퀴 중앙 축
            g.beginFill(pal.light);
            g.drawCircle(legEndX, legEndY + 1.5, 1.2);
            g.endFill();
        }

        // 중앙 허브 - 3D 효과
        g.beginFill(pal.shadow);
        g.drawEllipse(cx, cy + 1.5, 6, 3);
        g.endFill();

        g.beginFill(pal.main);
        g.drawEllipse(cx, cy + 0.5, 5.5, 2.8);
        g.endFill();

        g.beginFill(pal.light);
        g.drawEllipse(cx, cy, 5, 2.5);
        g.endFill();

        g.beginFill(pal.highlight, 0.4);
        g.drawEllipse(cx - 1, cy - 0.5, 2.5, 1.2);
        g.endFill();
    }

    // ==================== 프리미엄 크롬 기둥 ====================
    function drawPremiumPole(g, cx, baseY, topY) {
        const pal = SIDE_CHAIR_PALETTE.chrome;
        const width = SIDE_CHAIR_CONFIG.poleWidth;

        // 기둥 그림자
        g.beginFill(pal.shadow, 0.3);
        g.moveTo(cx + width / 2 + 1, baseY + 1);
        g.lineTo(cx + width / 2 + 1, topY + 1);
        g.lineTo(cx + 1, topY + 2);
        g.lineTo(cx + 1, baseY + 2);
        g.closePath();
        g.endFill();

        // 기둥 좌측 (어두운 면)
        g.beginFill(pal.dark);
        g.moveTo(cx - width / 2, baseY);
        g.lineTo(cx - width / 4, baseY + 1);
        g.lineTo(cx - width / 4, topY + 1);
        g.lineTo(cx - width / 2, topY);
        g.closePath();
        g.endFill();

        // 기둥 중앙 (메인)
        g.beginFill(pal.main);
        g.moveTo(cx - width / 4, baseY + 1);
        g.lineTo(cx + width / 4, baseY + 1);
        g.lineTo(cx + width / 4, topY + 1);
        g.lineTo(cx - width / 4, topY + 1);
        g.closePath();
        g.endFill();

        // 기둥 우측 (밝은 면 - 하이라이트)
        g.beginFill(pal.light);
        g.moveTo(cx + width / 4, baseY + 1);
        g.lineTo(cx + width / 2, baseY);
        g.lineTo(cx + width / 2, topY);
        g.lineTo(cx + width / 4, topY + 1);
        g.closePath();
        g.endFill();

        // 크롬 반사광 스트라이프
        g.beginFill(pal.highlight, 0.6);
        g.moveTo(cx + width / 3, baseY + 0.5);
        g.lineTo(cx + width / 2.5, baseY + 0.5);
        g.lineTo(cx + width / 2.5, topY + 0.5);
        g.lineTo(cx + width / 3, topY + 0.5);
        g.closePath();
        g.endFill();

        // 기둥 상단 캡
        g.beginFill(pal.dark);
        g.drawEllipse(cx, topY + 1, width / 2 + 2, 2);
        g.endFill();

        g.beginFill(pal.main);
        g.drawEllipse(cx, topY, width / 2 + 1.5, 1.8);
        g.endFill();

        g.beginFill(pal.highlight, 0.5);
        g.drawEllipse(cx - 0.5, topY - 0.3, 2, 0.8);
        g.endFill();

        // 기둥 하단 연결부
        g.beginFill(pal.shadow);
        g.drawEllipse(cx, baseY + 1, width / 2 + 1, 1.5);
        g.endFill();
    }

    // ==================== 프리미엄 좌석 ====================
    function drawPremiumSeat(g, corners, seatHeight, thickness) {
        const pal = SIDE_CHAIR_PALETTE.cushion;
        const cushionDepth = SIDE_CHAIR_CONFIG.seatCushionDepth;

        const top = { x: corners.top.x, y: corners.top.y - seatHeight };
        const right = { x: corners.right.x, y: corners.right.y - seatHeight };
        const bottom = { x: corners.bottom.x, y: corners.bottom.y - seatHeight };
        const left = { x: corners.left.x, y: corners.left.y - seatHeight };

        // 좌석 하단 그림자
        g.beginFill(pal.edge, 0.4);
        g.moveTo(left.x + 2, left.y + thickness + 2);
        g.lineTo(bottom.x + 2, bottom.y + thickness + 2);
        g.lineTo(right.x + 2, right.y + thickness + 2);
        g.lineTo(bottom.x, bottom.y + thickness + 1);
        g.lineTo(left.x, left.y + thickness + 1);
        g.closePath();
        g.endFill();

        // 좌측 측면 (어두운 면)
        g.beginFill(pal.shadow);
        g.moveTo(left.x, left.y);
        g.lineTo(bottom.x, bottom.y);
        g.lineTo(bottom.x, bottom.y + thickness);
        g.lineTo(left.x, left.y + thickness);
        g.closePath();
        g.endFill();

        // 좌측 측면 그라데이션 효과
        g.beginFill(pal.dark, 0.7);
        const midLB = { x: (left.x + bottom.x) / 2, y: (left.y + bottom.y) / 2 };
        g.moveTo(left.x, left.y);
        g.lineTo(midLB.x, midLB.y);
        g.lineTo(midLB.x, midLB.y + thickness);
        g.lineTo(left.x, left.y + thickness);
        g.closePath();
        g.endFill();

        // 우측 측면 (더 어두운 면)
        g.beginFill(pal.edge);
        g.moveTo(bottom.x, bottom.y);
        g.lineTo(right.x, right.y);
        g.lineTo(right.x, right.y + thickness);
        g.lineTo(bottom.x, bottom.y + thickness);
        g.closePath();
        g.endFill();

        // 좌석 상단 베이스
        g.beginFill(pal.main);
        g.moveTo(top.x, top.y);
        g.lineTo(right.x, right.y);
        g.lineTo(bottom.x, bottom.y);
        g.lineTo(left.x, left.y);
        g.closePath();
        g.endFill();

        // 쿠션 볼록한 효과 - 다중 레이어
        const cx = (top.x + bottom.x) / 2;
        const cy = (top.y + bottom.y) / 2;
        const w = (right.x - left.x);
        const h = (bottom.y - top.y);

        // 쿠션 외곽 그림자
        g.beginFill(pal.dark, 0.3);
        g.drawEllipse(cx, cy + 1, w * 0.42, h * 0.45);
        g.endFill();

        // 쿠션 메인 볼록함
        g.beginFill(pal.main);
        g.drawEllipse(cx, cy, w * 0.4, h * 0.42);
        g.endFill();

        // 쿠션 밝은 영역 1
        g.beginFill(pal.light, 0.6);
        g.drawEllipse(cx - 2, cy - 1, w * 0.28, h * 0.3);
        g.endFill();

        // 쿠션 하이라이트
        g.beginFill(pal.highlight, 0.4);
        g.drawEllipse(cx - 4, cy - 2, w * 0.15, h * 0.15);
        g.endFill();

        // 쿠션 가장자리 음영 (왼쪽 위)
        g.beginFill(pal.mid, 0.4);
        g.moveTo(top.x + 2, top.y + 1);
        g.lineTo(left.x + 3, left.y - 1);
        g.quadraticCurveTo(cx - w * 0.3, cy, left.x + 5, left.y + 2);
        g.lineTo(top.x + 4, top.y + 3);
        g.closePath();
        g.endFill();

        // 쿠션 가장자리 음영 (오른쪽 아래)
        g.beginFill(pal.dark, 0.35);
        g.moveTo(right.x - 2, right.y - 1);
        g.lineTo(bottom.x - 2, bottom.y - 2);
        g.quadraticCurveTo(cx + w * 0.25, cy + h * 0.2, right.x - 4, right.y + 1);
        g.closePath();
        g.endFill();

        // 스티칭 라인 (더 세밀하게)
        g.lineStyle(0.8, pal.shadow, 0.25);
        // 대각선 스티칭
        g.moveTo(top.x + 3, top.y + 2);
        g.lineTo(bottom.x - 3, bottom.y - 2);
        g.moveTo(left.x + 3, left.y - 2);
        g.lineTo(right.x - 3, right.y + 2);
        // 가장자리 스티칭
        g.moveTo(top.x + 2, top.y + 1);
        g.lineTo(right.x - 2, right.y + 1);
        g.moveTo(left.x + 2, left.y);
        g.lineTo(bottom.x - 2, bottom.y);
        g.lineStyle(0);

        return { top, right, bottom, left };
    }

    // ==================== 프리미엄 등받이 ====================
    function drawPremiumBack(g, seatCorners, facing, backHeight, backThickness) {
        const pal = SIDE_CHAIR_PALETTE.cushion;

        let baseLeft, baseRight;
        let thicknessOffsetX = 0;
        let thicknessOffsetY = 0;
        let isLeftVisible = false;
        let isRightVisible = false;

        const thicknessPx = backThickness * 2.5;

        switch (facing) {
            case 'SE':
                baseLeft = seatCorners.left;
                baseRight = seatCorners.top;
                thicknessOffsetX = thicknessPx * 0.5;
                thicknessOffsetY = thicknessPx * 0.25;
                isRightVisible = true;
                break;
            case 'SW':
                baseLeft = seatCorners.top;
                baseRight = seatCorners.right;
                thicknessOffsetX = -thicknessPx * 0.5;
                thicknessOffsetY = thicknessPx * 0.25;
                isLeftVisible = true;
                break;
            case 'NW':
                baseLeft = seatCorners.right;
                baseRight = seatCorners.bottom;
                thicknessOffsetX = thicknessPx * 0.5;
                thicknessOffsetY = thicknessPx * 0.25;
                isLeftVisible = true;
                break;
            case 'NE':
                baseLeft = seatCorners.bottom;
                baseRight = seatCorners.left;
                thicknessOffsetX = -thicknessPx * 0.5;
                thicknessOffsetY = thicknessPx * 0.25;
                isRightVisible = true;
                break;
            default:
                baseLeft = seatCorners.top;
                baseRight = seatCorners.right;
                thicknessOffsetX = -thicknessPx * 0.5;
                thicknessOffsetY = thicknessPx * 0.25;
                isLeftVisible = true;
        }

        const bl = { x: baseLeft.x, y: baseLeft.y };
        const br = { x: baseRight.x, y: baseRight.y };

        // 둥근 상단을 위한 곡선 포인트
        const curveTop = SIDE_CHAIR_CONFIG.backrestCurveTop;
        const tl = { x: bl.x, y: bl.y - backHeight };
        const tr = { x: br.x, y: br.y - backHeight };
        const midTopX = (tl.x + tr.x) / 2;
        const midTopY = (tl.y + tr.y) / 2 - curveTop;

        // 뒷면 좌표
        const bl2 = { x: bl.x + thicknessOffsetX, y: bl.y + thicknessOffsetY };
        const br2 = { x: br.x + thicknessOffsetX, y: br.y + thicknessOffsetY };
        const tl2 = { x: tl.x + thicknessOffsetX, y: tl.y + thicknessOffsetY };
        const tr2 = { x: tr.x + thicknessOffsetX, y: tr.y + thicknessOffsetY };
        const midTop2X = midTopX + thicknessOffsetX;
        const midTop2Y = midTopY + thicknessOffsetY;

        // 등받이 하단 연결면 (두께) - 그라데이션
        g.beginFill(pal.edge);
        g.moveTo(bl.x, bl.y);
        g.lineTo(br.x, br.y);
        g.lineTo(br2.x, br2.y);
        g.lineTo(bl2.x, bl2.y);
        g.closePath();
        g.endFill();

        // 등받이 왼쪽 측면
        if (isLeftVisible) {
            g.beginFill(pal.shadow);
            g.moveTo(bl.x, bl.y);
            g.lineTo(bl2.x, bl2.y);
            g.lineTo(tl2.x, tl2.y);
            g.lineTo(tl.x, tl.y);
            g.closePath();
            g.endFill();

            // 측면 그라데이션
            g.beginFill(pal.dark, 0.6);
            g.moveTo(bl.x, bl.y);
            g.lineTo(bl2.x, bl2.y);
            g.lineTo(bl2.x + (tl2.x - bl2.x) * 0.5, bl2.y + (tl2.y - bl2.y) * 0.5);
            g.lineTo(bl.x + (tl.x - bl.x) * 0.5, bl.y + (tl.y - bl.y) * 0.5);
            g.closePath();
            g.endFill();
        }

        // 등받이 오른쪽 측면
        if (isRightVisible) {
            g.beginFill(pal.dark);
            g.moveTo(br.x, br.y);
            g.lineTo(br2.x, br2.y);
            g.lineTo(tr2.x, tr2.y);
            g.lineTo(tr.x, tr.y);
            g.closePath();
            g.endFill();

            // 측면 그라데이션
            g.beginFill(pal.mid, 0.5);
            g.moveTo(br.x, br.y);
            g.lineTo(br2.x, br2.y);
            g.lineTo(br2.x + (tr2.x - br2.x) * 0.4, br2.y + (tr2.y - br2.y) * 0.4);
            g.lineTo(br.x + (tr.x - br.x) * 0.4, br.y + (tr.y - br.y) * 0.4);
            g.closePath();
            g.endFill();
        }

        // 등받이 전면 베이스
        g.beginFill(pal.main);
        g.moveTo(bl.x, bl.y);
        g.lineTo(br.x, br.y);
        g.lineTo(tr.x, tr.y);
        g.quadraticCurveTo(midTopX, midTopY, tl.x, tl.y);
        g.closePath();
        g.endFill();

        // 쿠션 볼록함 효과 - 다중 레이어
        const backCx = (bl.x + br.x) / 2;
        const backCy = (bl.y + tl.y) / 2;
        const backW = Math.abs(br.x - bl.x);
        const backH = backHeight;

        // 쿠션 외곽 그림자
        g.beginFill(pal.dark, 0.25);
        g.drawEllipse(backCx + 1, backCy + 2, backW * 0.35, backH * 0.35);
        g.endFill();

        // 쿠션 메인 볼록함
        g.beginFill(pal.main, 0.8);
        g.drawEllipse(backCx, backCy, backW * 0.32, backH * 0.32);
        g.endFill();

        // 쿠션 밝은 영역
        g.beginFill(pal.light, 0.5);
        g.drawEllipse(backCx - 2, backCy - 3, backW * 0.22, backH * 0.22);
        g.endFill();

        // 하이라이트
        g.beginFill(pal.highlight, 0.45);
        g.drawEllipse(backCx - 4, backCy - 5, backW * 0.12, backH * 0.12);
        g.endFill();

        // 가장자리 음영 (하단)
        g.beginFill(pal.dark, 0.3);
        g.moveTo(bl.x + 2, bl.y - 2);
        g.lineTo(br.x - 2, br.y - 2);
        g.quadraticCurveTo(backCx, bl.y - backH * 0.15, bl.x + 4, bl.y - 4);
        g.closePath();
        g.endFill();

        // 등받이 상단면 (둥근 곡선)
        g.beginFill(pal.mid);
        g.moveTo(tl.x, tl.y);
        g.quadraticCurveTo(midTopX, midTopY, tr.x, tr.y);
        g.lineTo(tr2.x, tr2.y);
        g.quadraticCurveTo(midTop2X, midTop2Y, tl2.x, tl2.y);
        g.closePath();
        g.endFill();

        // 상단면 하이라이트
        g.beginFill(pal.light, 0.6);
        g.moveTo(tl.x + 2, tl.y + 0.5);
        g.quadraticCurveTo(midTopX, midTopY + 1, tr.x - 2, tr.y + 0.5);
        g.lineTo(tr.x - 3, tr.y + 1.5);
        g.quadraticCurveTo(midTopX, midTopY + 2, tl.x + 3, tl.y + 1.5);
        g.closePath();
        g.endFill();

        // 프리미엄 스티칭 라인
        g.lineStyle(0.8, pal.shadow, 0.3);
        // 수평 스티칭
        const stitch1Y = bl.y - backH * 0.25;
        const stitch2Y = bl.y - backH * 0.5;
        const stitch3Y = bl.y - backH * 0.75;
        g.moveTo(bl.x + 2, stitch1Y + (br.y - bl.y) * 0.25);
        g.lineTo(br.x - 2, stitch1Y + (br.y - bl.y) * 0.75);
        g.moveTo(bl.x + 2, stitch2Y + (br.y - bl.y) * 0.25);
        g.lineTo(br.x - 2, stitch2Y + (br.y - bl.y) * 0.75);
        g.moveTo(bl.x + 3, stitch3Y + (br.y - bl.y) * 0.25);
        g.lineTo(br.x - 3, stitch3Y + (br.y - bl.y) * 0.75);
        g.lineStyle(0);

        // 가장자리 림 라이트
        g.lineStyle(1, pal.highlight, 0.2);
        g.moveTo(tl.x + 1, tl.y - 1);
        g.quadraticCurveTo(midTopX, midTopY - 1, tr.x - 1, tr.y - 1);
        g.lineStyle(0);
    }

    // ==================== 메인 생성 함수 ====================
    function createSideChair(gridX, gridY, facing = 'SW') {
        const cfg = SIDE_CHAIR_CONFIG;

        const halfW = cfg.seatWidth / 2;
        const halfD = cfg.seatDepth / 2;

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

        // Base 컨테이너
        const baseContainer = new PIXI.Container();
        const baseG = new PIXI.Graphics();

        drawPremiumShadow(baseG, 0, 0);
        drawPremiumWheeledBase(baseG, 0, 0);
        drawPremiumPole(baseG, 0, 0, -cfg.seatHeight + cfg.seatThickness);
        const seatCorners = drawPremiumSeat(baseG, corners, cfg.seatHeight, cfg.seatThickness);

        baseContainer.addChild(baseG);

        // Backrest 컨테이너
        const backrestContainer = new PIXI.Container();
        const backrestG = new PIXI.Graphics();

        drawPremiumBack(backrestG, seatCorners, facing, cfg.backrestHeight, cfg.backrestThickness);

        backrestContainer.addChild(backrestG);

        // 위치 및 깊이
        const screenPos = ISO.gridToScreen(gridX, gridY);

        baseContainer.x = screenPos.x;
        baseContainer.y = screenPos.y;
        baseContainer.zIndex = ISO.depthKey(gridX, gridY, -300);

        backrestContainer.x = screenPos.x;
        backrestContainer.y = screenPos.y;

        let backrestGridX = gridX;
        let backrestGridY = gridY;
        const backOffset = 0.5;

        switch (facing) {
            case 'SE': backrestGridX -= backOffset; break;
            case 'SW': backrestGridY -= backOffset; break;
            case 'NW': backrestGridX += backOffset; break;
            case 'NE': backrestGridY += backOffset; break;
        }

        backrestContainer.zIndex = ISO.depthKey(backrestGridX, backrestGridY, 200);

        return { base: baseContainer, backrest: backrestContainer };
    }

    // Export
    window.CompanyView.SideChairAssets = {
        SIDE_CHAIR_PALETTE,
        SIDE_CHAIR_CONFIG,
        createSideChair,
    };

})();
