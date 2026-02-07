/**
 * Office Layout - Defines the room structure, furniture placement, and walkable areas
 * Acts as the level/map data for the isometric office
 */
window.CompanyView = window.CompanyView || {};

(function () {
    'use strict';

    // ==================== Room Dimensions ====================
    const ROOM = {
        WIDTH: 12,   // tiles
        HEIGHT: 10,  // tiles
    };

    // ==================== Tile Types ====================
    const TILE = {
        FLOOR: 0,
        CARPET: 1,
        WALL: 2,
    };

    // ==================== Furniture Definitions ====================
    // Each furniture item: { type, gridX, gridY, variant?, facing? }
    // 크기 표기법: W x H = gx방향(↘) x gy방향(↙)
    const FURNITURE = [
        // 중앙 회의 테이블 (5x3 크기: gx방향 5타일, gy방향 3타일)
        // 카펫 영역 중앙에 배치
        { type: 'conferenceTable', gridX: 3, gridY: 3 },

        // 우상단 회의 테이블 쪽 의자 3개
        // 테이블 상단 모서리(gy=3 라인) 바깥쪽에 배치, 테이블을 향해 앉음 (SW 방향)
        // 테이블 gx 범위(3~8) 중앙부에 균등 배치
        { type: 'chair', gridX: 3.5, gridY: 2.2, facing: 'SW' },
        { type: 'chair', gridX: 5, gridY: 2.2, facing: 'SW' },
        { type: 'chair', gridX: 6.5, gridY: 2.2, facing: 'SW' },
        { type: 'chair', gridX: 2.3, gridY: 3.8, facing: 'SE' },
        { type: 'chair', gridX: 7.6, gridY: 3.8, facing: 'NW' },
        { type: 'chair', gridX: 3.5, gridY: 5.6, facing: 'NE' },
        { type: 'chair', gridX: 5, gridY: 5.6, facing: 'NE' },
        { type: 'chair', gridX: 6.5, gridY: 5.6, facing: 'NE' },
        // 우상단 사이드 체어 (빨간색 오피스 체어)
        { type: 'sideChair', gridX: 9.5, gridY: 1.5, facing: 'SW' },    ];

    // ==================== Seat Positions ====================
    // Positions where avatars can sit at workstations
    // Aligned with workstation positions, slightly offset for sitting
    const SEAT_POSITIONS = [
        // Row 1
        { gridX: 2, gridY: 2.5, workstationIdx: 0 },
        { gridX: 4, gridY: 2.5, workstationIdx: 1 },
        { gridX: 6, gridY: 2.5, workstationIdx: 2 },
        { gridX: 8, gridY: 2.5, workstationIdx: 3 },
        // Row 2
        { gridX: 2, gridY: 4.5, workstationIdx: 4 },
        { gridX: 4, gridY: 4.5, workstationIdx: 5 },
        { gridX: 6, gridY: 4.5, workstationIdx: 6 },
        { gridX: 8, gridY: 4.5, workstationIdx: 7 },
        // Row 3
        { gridX: 2, gridY: 6.5, workstationIdx: 8 },
        { gridX: 4, gridY: 6.5, workstationIdx: 9 },
        { gridX: 6, gridY: 6.5, workstationIdx: 10 },
        { gridX: 8, gridY: 6.5, workstationIdx: 11 },
    ];

    // ==================== Idle Positions ====================
    // Where avatars go when not seated (lounge/wander spots)
    const IDLE_POSITIONS = [
        { gridX: 10, gridY: 3.5, label: 'corner1' },
        { gridX: 10, gridY: 5, label: 'corner2' },
        { gridX: 5, gridY: 8, label: 'hallway' },
        { gridX: 3, gridY: 8, label: 'entrance' },
        { gridX: 7, gridY: 8, label: 'lounge' },
        { gridX: 1, gridY: 3, label: 'side1' },
        { gridX: 1, gridY: 6, label: 'side2' },
    ];

    // ==================== Walkability Map Generator ====================
    function generateWalkableMap() {
        const map = [];
        for (let y = 0; y < ROOM.HEIGHT; y++) {
            map[y] = [];
            for (let x = 0; x < ROOM.WIDTH; x++) {
                // Default: walkable inside room, not on walls
                map[y][x] = (x >= 1 && x < ROOM.WIDTH - 1 && y >= 1 && y < ROOM.HEIGHT);
            }
        }

        // Block furniture tiles (desks)
        for (const f of FURNITURE) {
            if (f.wallMount || f.onDesk) continue;
            const gx = Math.floor(f.gridX);
            const gy = Math.floor(f.gridY);

            if (f.type === 'conferenceTable') {
                // 5x3 회의 테이블 영역 블로킹 (gx방향 5, gy방향 3)
                for (let dy = 0; dy < 3; dy++) {
                    for (let dx = 0; dx < 5; dx++) {
                        const tx = gx + dx;
                        const ty = gy + dy;
                        if (tx >= 0 && tx < ROOM.WIDTH && ty >= 0 && ty < ROOM.HEIGHT) {
                            map[ty][tx] = false;
                        }
                    }
                }
            } else if (f.type === 'workstation') {
                if (gx >= 0 && gx < ROOM.WIDTH && gy >= 0 && gy < ROOM.HEIGHT) {
                    map[gy][gx] = false;
                }
            }
        }

        return map;
    }

    // ==================== Export ====================
    window.CompanyView.Layout = {
        ROOM,
        TILE,
        FURNITURE,
        SEAT_POSITIONS,
        IDLE_POSITIONS,
        generateWalkableMap,
    };

})();
