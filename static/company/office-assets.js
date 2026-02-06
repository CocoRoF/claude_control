/**
 * Office Assets - Isometric furniture and decorations drawn via PIXI Graphics
 * All furniture is drawn procedurally for a cute, pixel-art tycoon aesthetic
 */
window.CompanyView = window.CompanyView || {};

(function () {
    'use strict';

    const ISO = window.CompanyView.ISO;
    const Prims = window.CompanyView.IsoPrimitives;

    // ==================== Color Palettes ====================
    const PALETTE = {
        desk: {
            top: 0xD4A574,      // warm wood
            left: 0xBE8C5E,
            right: 0xC9996A,
            legDark: 0x8B7355,
            legLight: 0x9E8468,
        },
        deskModern: {
            top: 0xE8DED1,
            left: 0xCFC2B3,
            right: 0xDBCFBF,
            legDark: 0x6B6B6B,
            legLight: 0x808080,
        },
        chair: {
            seat: 0x5B9BD5,     // blue office chair
            back: 0x4A8AC4,
            dark: 0x3D7AB3,
            leg: 0x555555,
        },
        chairGreen: {
            seat: 0x6BBF6B,
            back: 0x5AAD5A,
            dark: 0x4A9D4A,
            leg: 0x555555,
        },
        chairPink: {
            seat: 0xE88BA8,
            back: 0xD77A97,
            dark: 0xC66986,
            leg: 0x555555,
        },
        monitor: {
            frame: 0x333333,
            screen: 0x1A3A5C,
            screenGlow: 0x2A5A8C,
            stand: 0x444444,
        },
        carpet: {
            main: 0xE8B4B8,      // pink carpet
            border: 0xD4949A,
        },
        wall: {
            back: 0xFFF5E6,
            side: 0xF0E0CC,
            trim: 0xE8D4B8,
        },
        wallPink: {
            back: 0xFFE0E8,
            side: 0xF0C8D4,
            trim: 0xE8B8C8,
        },
        floor: {
            tile1: 0xF5E6D3,
            tile2: 0xEDDCC5,
            tilePink: 0xF8E0E0,
        },
    };

    // ==================== Asset Generators ====================

    /**
     * Create a desk (occupies 1x1 tile)
     * @param {string} variant - 'wood' or 'modern'
     * @returns {PIXI.Graphics}
     */
    function createDesk(variant = 'wood') {
        const g = new PIXI.Graphics();
        const pal = variant === 'modern' ? PALETTE.deskModern : PALETTE.desk;
        const W = ISO.TILE_W;
        const H = ISO.TILE_H;

        // Desk legs (4 thin isometric columns)
        const legW = 6;
        const legH = 3;
        const legDepth = 14;
        const offsets = [
            { x: -W * 0.32, y: -H * 0.05 },
            { x: W * 0.32, y: -H * 0.05 },
            { x: -W * 0.08, y: -H * 0.35 },
            { x: W * 0.08, y: H * 0.25 },
        ];
        for (const off of offsets) {
            Prims.drawBox(g, off.x, off.y + legDepth, legW, legH, legDepth,
                pal.legLight, pal.legDark, pal.legLight);
        }

        // Desktop surface
        const deskDepth = 4;
        Prims.drawBoxOutlined(g, 0, 0, W * 0.85, H * 0.85, deskDepth,
            pal.top, pal.left, pal.right);

        return g;
    }

    /**
     * Create a monitor on desk
     * @returns {PIXI.Graphics}
     */
    function createMonitor() {
        const g = new PIXI.Graphics();

        // Stand base
        g.beginFill(PALETTE.monitor.stand);
        g.drawRect(-4, 2, 8, 3);
        g.endFill();

        // Stand pole
        g.beginFill(PALETTE.monitor.stand);
        g.drawRect(-1.5, -8, 3, 10);
        g.endFill();

        // Screen frame
        g.beginFill(PALETTE.monitor.frame);
        g.drawRoundedRect(-12, -22, 24, 16, 2);
        g.endFill();

        // Screen
        g.beginFill(PALETTE.monitor.screen);
        g.drawRect(-10, -20, 20, 12);
        g.endFill();

        // Screen glow effect
        g.beginFill(PALETTE.monitor.screenGlow, 0.3);
        g.drawRect(-8, -18, 16, 4);
        g.endFill();

        // Text lines on screen
        g.beginFill(0x4A9ADA, 0.6);
        g.drawRect(-7, -13, 10, 1);
        g.endFill();
        g.beginFill(0x6BBF6B, 0.5);
        g.drawRect(-7, -11, 8, 1);
        g.endFill();
        g.beginFill(0x4A9ADA, 0.4);
        g.drawRect(-7, -9, 12, 1);
        g.endFill();

        return g;
    }

    /**
     * Create an office chair
     * @param {string} color - 'blue', 'green', or 'pink'
     * @returns {PIXI.Graphics}
     */
    function createChair(color = 'blue') {
        const g = new PIXI.Graphics();
        let pal;
        switch (color) {
            case 'green': pal = PALETTE.chairGreen; break;
            case 'pink': pal = PALETTE.chairPink; break;
            default: pal = PALETTE.chair;
        }

        // Chair base (star wheel)
        g.beginFill(pal.leg);
        g.drawCircle(0, 6, 5);
        g.endFill();

        // Pole
        g.beginFill(pal.leg);
        g.drawRect(-1.5, -2, 3, 8);
        g.endFill();

        // Seat
        g.beginFill(pal.seat);
        g.moveTo(0, -5);
        g.lineTo(10, 0);
        g.lineTo(0, 5);
        g.lineTo(-10, 0);
        g.closePath();
        g.endFill();

        // Backrest
        g.beginFill(pal.back);
        g.moveTo(-10, 0);
        g.lineTo(-8, -10);
        g.lineTo(2, -7);
        g.lineTo(0, -5);
        g.lineTo(-10, 0);
        g.closePath();
        g.endFill();

        // Backrest highlight
        g.beginFill(pal.dark, 0.3);
        g.moveTo(-10, 0);
        g.lineTo(-9, -5);
        g.lineTo(1, -6);
        g.lineTo(0, -5);
        g.closePath();
        g.endFill();

        return g;
    }

    /**
     * Create a desk with monitor setup (combined for a workstation)
     */
    function createWorkstation(chairColor = 'blue', variant = 'wood') {
        const container = new PIXI.Container();

        const chair = createChair(chairColor);
        chair.x = 4;
        chair.y = 12;
        container.addChild(chair);

        const desk = createDesk(variant);
        container.addChild(desk);

        const monitor = createMonitor();
        monitor.x = -2;
        monitor.y = -8;
        monitor.scale.set(0.7);
        container.addChild(monitor);

        return container;
    }

    // ==================== Floor Tile Generators ====================

    function createFloorTile(color1, color2, gx, gy) {
        const g = new PIXI.Graphics();
        const color = (gx + gy) % 2 === 0 ? color1 : color2;

        Prims.drawDiamond(g, 0, 0, ISO.TILE_W, ISO.TILE_H, color);

        // Subtle grid line
        g.lineStyle(0.5, 0x000000, 0.05);
        g.moveTo(0, -ISO.TILE_H / 2);
        g.lineTo(ISO.TILE_W / 2, 0);
        g.lineTo(0, ISO.TILE_H / 2);
        g.lineTo(-ISO.TILE_W / 2, 0);
        g.lineTo(0, -ISO.TILE_H / 2);
        g.lineStyle(0);

        return g;
    }

    function createCarpetTile(gx, gy, width, height) {
        const g = new PIXI.Graphics();
        const pal = PALETTE.carpet;

        // Check if it's a border tile
        const isBorder = gx === 0 || gy === 0 || gx === width - 1 || gy === height - 1;
        const color = isBorder ? pal.border : pal.main;

        Prims.drawDiamond(g, 0, 0, ISO.TILE_W, ISO.TILE_H, color, 0.7);

        return g;
    }

    // ==================== Wall Generators ====================

    function createBackWall(length) {
        const g = new PIXI.Graphics();
        const pal = PALETTE.wallPink;
        const wallHeight = 65;

        // Back wall follows the top-left edge of y=0 tiles
        // Use top corners of tiles (center.x, center.y - TILE_H/2)
        for (let i = 0; i < length; i++) {
            const pos = ISO.gridToScreen(i, 0);
            const nextPos = ISO.gridToScreen(i + 1, 0);

            // Top corners of tiles
            const x1 = pos.x;
            const y1 = pos.y - ISO.TILE_H / 2;
            const x2 = nextPos.x;
            const y2 = nextPos.y - ISO.TILE_H / 2;

            // Wall face (left-facing wall along the top)
            g.beginFill(pal.back);
            g.moveTo(x1, y1 - wallHeight);
            g.lineTo(x2, y2 - wallHeight);
            g.lineTo(x2, y2);
            g.lineTo(x1, y1);
            g.closePath();
            g.endFill();

            // Wall top trim
            g.beginFill(pal.trim, 0.6);
            g.moveTo(x1, y1 - wallHeight);
            g.lineTo(x2, y2 - wallHeight);
            g.lineTo(x2, y2 - wallHeight + 3);
            g.lineTo(x1, y1 - wallHeight + 3);
            g.closePath();
            g.endFill();

            // Baseboard
            g.beginFill(pal.trim, 0.4);
            g.moveTo(x1, y1 - 4);
            g.lineTo(x2, y2 - 4);
            g.lineTo(x2, y2);
            g.lineTo(x1, y1);
            g.closePath();
            g.endFill();
        }

        return g;
    }

    function createSideWall(length) {
        const g = new PIXI.Graphics();
        const pal = PALETTE.wall;
        const wallHeight = 65;

        // Side wall follows the top-right edge of x=0 tiles
        // Use top corners of tiles (center.x, center.y - TILE_H/2)
        for (let j = 0; j < length; j++) {
            const pos = ISO.gridToScreen(0, j);
            const nextPos = ISO.gridToScreen(0, j + 1);

            // Top corners of tiles
            const x1 = pos.x;
            const y1 = pos.y - ISO.TILE_H / 2;
            const x2 = nextPos.x;
            const y2 = nextPos.y - ISO.TILE_H / 2;

            // Wall face (right-facing wall along the left)
            g.beginFill(pal.back);
            g.moveTo(x1, y1 - wallHeight);
            g.lineTo(x2, y2 - wallHeight);
            g.lineTo(x2, y2);
            g.lineTo(x1, y1);
            g.closePath();
            g.endFill();

            // Wall trim
            g.beginFill(pal.trim, 0.6);
            g.moveTo(x1, y1 - wallHeight);
            g.lineTo(x2, y2 - wallHeight);
            g.lineTo(x2, y2 - wallHeight + 3);
            g.lineTo(x1, y1 - wallHeight + 3);
            g.closePath();
            g.endFill();

            // Baseboard
            g.beginFill(pal.trim, 0.4);
            g.moveTo(x1, y1 - 4);
            g.lineTo(x2, y2 - 4);
            g.lineTo(x2, y2);
            g.lineTo(x1, y1);
            g.closePath();
            g.endFill();
        }

        return g;
    }

    // ==================== Export ====================
    window.CompanyView.Assets = {
        PALETTE,
        createDesk,
        createMonitor,
        createChair,
        createWorkstation,
        createFloorTile,
        createCarpetTile,
        createBackWall,
        createSideWall,
    };

})();
