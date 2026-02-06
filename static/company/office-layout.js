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
    const FURNITURE = [
        // Row 1 - Back desks (near back wall)
        { type: 'workstation', gridX: 2, gridY: 2, chairColor: 'blue', variant: 'wood' },
        { type: 'workstation', gridX: 4, gridY: 2, chairColor: 'green', variant: 'wood' },
        { type: 'workstation', gridX: 6, gridY: 2, chairColor: 'pink', variant: 'wood' },
        { type: 'workstation', gridX: 8, gridY: 2, chairColor: 'blue', variant: 'wood' },

        // Row 2 - Middle desks
        { type: 'workstation', gridX: 2, gridY: 4, chairColor: 'green', variant: 'modern' },
        { type: 'workstation', gridX: 4, gridY: 4, chairColor: 'pink', variant: 'modern' },
        { type: 'workstation', gridX: 6, gridY: 4, chairColor: 'blue', variant: 'modern' },
        { type: 'workstation', gridX: 8, gridY: 4, chairColor: 'green', variant: 'modern' },

        // Row 3 - Front desks
        { type: 'workstation', gridX: 2, gridY: 6, chairColor: 'pink', variant: 'wood' },
        { type: 'workstation', gridX: 4, gridY: 6, chairColor: 'blue', variant: 'wood' },
        { type: 'workstation', gridX: 6, gridY: 6, chairColor: 'green', variant: 'wood' },
        { type: 'workstation', gridX: 8, gridY: 6, chairColor: 'pink', variant: 'wood' },
    ];

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
            if (gx >= 0 && gx < ROOM.WIDTH && gy >= 0 && gy < ROOM.HEIGHT) {
                // Workstations block their tile
                if (f.type === 'workstation') {
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
