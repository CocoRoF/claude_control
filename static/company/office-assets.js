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
        bookshelf: {
            frame: 0xC9996A,
            frameDark: 0xBE8C5E,
            frameRight: 0xB88050,
            shelf: 0xD4A574,
        },
        carpet: {
            main: 0xE8B4B8,      // pink carpet
            border: 0xD4949A,
        },
        plant: {
            pot: 0xC4794E,
            potDark: 0xA8633C,
            soil: 0x5E3D2B,
            leaf1: 0x5DAE5D,
            leaf2: 0x4B9E4B,
            leaf3: 0x6BBE6B,
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
        waterCooler: {
            body: 0xE0E8F0,
            bodyDark: 0xC0D0E0,
            water: 0x8ECAE6,
            cap: 0xB0C4DE,
        },
        whiteboard: {
            board: 0xFAFAFA,
            frame: 0xA0A0A0,
            frameDark: 0x888888,
        },
        clock: {
            face: 0xFAFAFA,
            frame: 0xD4A574,
            hands: 0x333333,
        },
        window: {
            frame: 0xD0D0D0,
            glass: 0xC5E8F7,
            sky: 0xA8D8EA,
            curtain: 0xFFB6C1,
        },
        cactus: {
            body: 0x5DAE5D,
            bodyDark: 0x4B9E4B,
            pot: 0xC4794E,
            potDark: 0xA8633C,
            flower: 0xFF8FAB,
        }
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
     * Create a bookshelf (tall furniture piece)
     * @returns {PIXI.Graphics}
     */
    function createBookshelf() {
        const g = new PIXI.Graphics();
        const pal = PALETTE.bookshelf;
        const W = 40;
        const H = 20;
        const depth = 50;

        // Main body
        Prims.drawBoxOutlined(g, 0, 0, W, H, depth, pal.shelf, pal.frameDark, pal.frameRight);

        // Shelf dividers (horizontal)
        for (let i = 1; i < 4; i++) {
            const shelfY = -depth + i * 12;
            g.beginFill(pal.shelf, 0.7);
            g.moveTo(0, shelfY - H / 2 + 2);
            g.lineTo(W / 2 - 2, shelfY + 2);
            g.lineTo(0, shelfY + H / 2 + 2);
            g.lineTo(-W / 2 + 2, shelfY + 2);
            g.closePath();
            g.endFill();
        }

        // Books
        const bookColors = [0xE55B5B, 0x5B7BE5, 0x5BE58B, 0xE5C95B, 0xC55BE5, 0x5BBCE5];
        for (let shelf = 0; shelf < 3; shelf++) {
            const baseY = -depth + shelf * 12 + 4;
            const numBooks = 3 + Math.floor(Math.random() * 3);
            for (let b = 0; b < numBooks; b++) {
                const bookColor = bookColors[(shelf * 3 + b) % bookColors.length];
                const bx = -12 + b * 7;
                const bookH = 6 + Math.random() * 4;
                g.beginFill(bookColor);
                g.drawRect(bx, baseY - bookH, 5, bookH);
                g.endFill();
            }
        }

        // Photo frame on top
        g.beginFill(0xD4A574);
        g.drawRect(-5, -depth - 4, 10, 8);
        g.endFill();
        g.beginFill(0xE8D4B8);
        g.drawRect(-3, -depth - 2, 6, 4);
        g.endFill();

        return g;
    }

    /**
     * Create a potted plant
     * @param {string} type - 'small' or 'large'
     * @returns {PIXI.Graphics}
     */
    function createPlant(type = 'small') {
        const g = new PIXI.Graphics();
        const pal = PALETTE.plant;

        if (type === 'large') {
            // Large floor plant (like in the reference image)
            // Pot
            g.beginFill(pal.pot);
            g.moveTo(-10, 0);
            g.lineTo(-8, -12);
            g.lineTo(8, -12);
            g.lineTo(10, 0);
            g.closePath();
            g.endFill();
            g.beginFill(pal.potDark);
            g.moveTo(-10, 0);
            g.lineTo(0, 5);
            g.lineTo(10, 0);
            g.lineTo(8, -12);
            g.lineTo(-8, -12);
            g.closePath();
            g.endFill();

            // Soil
            g.beginFill(pal.soil);
            g.drawEllipse(0, -12, 8, 3);
            g.endFill();

            // Leaves (tropical style)
            const leafPositions = [
                { x: 0, y: -30, angle: 0, scale: 1.0 },
                { x: -8, y: -25, angle: -0.5, scale: 0.8 },
                { x: 8, y: -25, angle: 0.5, scale: 0.8 },
                { x: -12, y: -20, angle: -0.8, scale: 0.7 },
                { x: 12, y: -20, angle: 0.8, scale: 0.7 },
                { x: 0, y: -35, angle: 0, scale: 0.9 },
                { x: -5, y: -32, angle: -0.3, scale: 0.85 },
                { x: 5, y: -32, angle: 0.3, scale: 0.85 },
            ];
            for (const lp of leafPositions) {
                const leafColor = [pal.leaf1, pal.leaf2, pal.leaf3][Math.floor(Math.random() * 3)];
                g.beginFill(leafColor, 0.9);
                g.drawEllipse(lp.x, lp.y, 7 * lp.scale, 12 * lp.scale);
                g.endFill();
                // Leaf vein
                g.lineStyle(0.5, 0x3D8E3D, 0.3);
                g.moveTo(lp.x, lp.y - 8 * lp.scale);
                g.lineTo(lp.x, lp.y + 8 * lp.scale);
                g.lineStyle(0);
            }
        } else {
            // Small desk plant / cactus
            const pal2 = PALETTE.cactus;
            // Small pot
            g.beginFill(pal2.pot);
            g.moveTo(-5, 0);
            g.lineTo(-4, -6);
            g.lineTo(4, -6);
            g.lineTo(5, 0);
            g.closePath();
            g.endFill();
            g.beginFill(pal2.potDark);
            g.drawEllipse(0, 0, 5, 2);
            g.endFill();
            g.beginFill(pal2.potDark, 0.5);
            g.drawEllipse(0, -6, 4, 1.5);
            g.endFill();

            // Cactus body
            g.beginFill(pal2.body);
            g.drawRoundedRect(-3, -16, 6, 10, 3);
            g.endFill();
            g.beginFill(pal2.bodyDark);
            g.drawRoundedRect(-1, -16, 2, 10, 1);
            g.endFill();

            // Small arms
            g.beginFill(pal2.body);
            g.drawRoundedRect(-7, -14, 5, 3, 1.5);
            g.endFill();
            g.beginFill(pal2.body);
            g.drawRoundedRect(2, -12, 5, 3, 1.5);
            g.endFill();

            // Flower
            g.beginFill(pal2.flower);
            g.drawCircle(0, -17, 2.5);
            g.endFill();
            g.beginFill(0xFFD700);
            g.drawCircle(0, -17, 1);
            g.endFill();
        }

        return g;
    }

    /**
     * Create a water cooler
     * @returns {PIXI.Graphics}
     */
    function createWaterCooler() {
        const g = new PIXI.Graphics();
        const pal = PALETTE.waterCooler;

        // Base
        g.beginFill(pal.bodyDark);
        g.drawRoundedRect(-8, -2, 16, 6, 2);
        g.endFill();

        // Body
        g.beginFill(pal.body);
        g.drawRoundedRect(-7, -22, 14, 20, 2);
        g.endFill();

        // Shadow on body
        g.beginFill(pal.bodyDark, 0.3);
        g.drawRect(3, -20, 4, 16);
        g.endFill();

        // Water bottle on top
        g.beginFill(pal.water, 0.7);
        g.drawRoundedRect(-5, -36, 10, 14, 4);
        g.endFill();

        // Water level
        g.beginFill(pal.water, 0.4);
        g.drawRect(-4, -28, 8, 5);
        g.endFill();

        // Cap
        g.beginFill(pal.cap);
        g.drawRoundedRect(-4, -37, 8, 3, 1);
        g.endFill();

        // Tap
        g.beginFill(0xCC3333);
        g.drawRect(-9, -14, 3, 3);
        g.endFill();
        g.beginFill(0x3366CC);
        g.drawRect(-9, -10, 3, 3);
        g.endFill();

        return g;
    }

    /**
     * Create a wall clock
     * @returns {PIXI.Graphics}
     */
    function createClock() {
        const g = new PIXI.Graphics();
        const pal = PALETTE.clock;

        // Frame
        g.beginFill(pal.frame);
        g.drawCircle(0, 0, 10);
        g.endFill();

        // Face
        g.beginFill(pal.face);
        g.drawCircle(0, 0, 8);
        g.endFill();

        // Hour markers
        for (let i = 0; i < 12; i++) {
            const angle = (i * 30 - 90) * Math.PI / 180;
            const len = i % 3 === 0 ? 2 : 1;
            g.lineStyle(i % 3 === 0 ? 1.5 : 0.5, pal.hands);
            g.moveTo(Math.cos(angle) * (6 - len), Math.sin(angle) * (6 - len));
            g.lineTo(Math.cos(angle) * 6, Math.sin(angle) * 6);
        }

        // Hour hand
        g.lineStyle(1.5, pal.hands);
        g.moveTo(0, 0);
        g.lineTo(-2, -4);

        // Minute hand
        g.lineStyle(1, pal.hands);
        g.moveTo(0, 0);
        g.lineTo(4, -2);

        // Center dot
        g.beginFill(0xCC3333);
        g.drawCircle(0, 0, 1);
        g.endFill();

        g.lineStyle(0);

        return g;
    }

    /**
     * Create a window (wall decoration)
     * @returns {PIXI.Graphics}
     */
    function createWindow() {
        const g = new PIXI.Graphics();
        const pal = PALETTE.window;

        // Frame
        g.beginFill(pal.frame);
        g.drawRoundedRect(-16, -20, 32, 24, 2);
        g.endFill();

        // Glass
        g.beginFill(pal.glass, 0.8);
        g.drawRect(-14, -18, 13, 20);
        g.endFill();
        g.beginFill(pal.glass, 0.8);
        g.drawRect(1, -18, 13, 20);
        g.endFill();

        // Sky gradient (simplified)
        g.beginFill(pal.sky, 0.4);
        g.drawRect(-14, -18, 28, 8);
        g.endFill();

        // Light reflection
        g.beginFill(0xFFFFFF, 0.15);
        g.drawRect(-12, -16, 4, 12);
        g.endFill();

        // Curtains
        g.beginFill(pal.curtain, 0.6);
        g.drawRect(-18, -20, 5, 26);
        g.endFill();
        g.beginFill(pal.curtain, 0.6);
        g.drawRect(13, -20, 5, 26);
        g.endFill();

        // Curtain details (folds)
        g.lineStyle(0.5, pal.curtain, 0.8);
        g.moveTo(-16, -20);
        g.lineTo(-16, 6);
        g.moveTo(-14, -20);
        g.lineTo(-14, 6);
        g.moveTo(15, -20);
        g.lineTo(15, 6);
        g.moveTo(17, -20);
        g.lineTo(17, 6);
        g.lineStyle(0);

        return g;
    }

    /**
     * Create a whiteboard
     * @returns {PIXI.Graphics}
     */
    function createWhiteboard() {
        const g = new PIXI.Graphics();
        const pal = PALETTE.whiteboard;

        // Frame
        g.beginFill(pal.frameDark);
        g.drawRoundedRect(-20, -16, 40, 24, 1);
        g.endFill();

        // Board
        g.beginFill(pal.board);
        g.drawRect(-18, -14, 36, 20);
        g.endFill();

        // Some "writing" on the board
        g.lineStyle(1, 0x3366CC, 0.4);
        g.moveTo(-14, -10);
        g.lineTo(-2, -10);
        g.moveTo(-14, -6);
        g.lineTo(4, -6);
        g.moveTo(-14, -2);
        g.lineTo(-4, -2);

        // A simple chart
        g.lineStyle(1, 0xCC3333, 0.5);
        g.moveTo(6, 2);
        g.lineTo(8, -4);
        g.lineTo(10, -2);
        g.lineTo(14, -8);

        g.lineStyle(0);

        // Marker tray
        g.beginFill(pal.frame);
        g.drawRect(-12, 8, 24, 2);
        g.endFill();

        // Markers
        const markerColors = [0xCC3333, 0x3366CC, 0x33AA33];
        for (let i = 0; i < 3; i++) {
            g.beginFill(markerColors[i]);
            g.drawRect(-8 + i * 6, 6, 4, 2);
            g.endFill();
        }

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

        for (let i = 0; i < length; i++) {
            const pos = ISO.gridToScreen(i, 0);
            const nextPos = ISO.gridToScreen(i + 1, 0);

            // Wall face (left-facing wall along the top)
            g.beginFill(pal.back);
            g.moveTo(pos.x - ISO.TILE_W / 2, pos.y - wallHeight);
            g.lineTo(nextPos.x - ISO.TILE_W / 2, nextPos.y - wallHeight);
            g.lineTo(nextPos.x - ISO.TILE_W / 2, nextPos.y);
            g.lineTo(pos.x - ISO.TILE_W / 2, pos.y);
            g.closePath();
            g.endFill();

            // Wall top trim
            g.beginFill(pal.trim, 0.6);
            g.moveTo(pos.x - ISO.TILE_W / 2, pos.y - wallHeight);
            g.lineTo(nextPos.x - ISO.TILE_W / 2, nextPos.y - wallHeight);
            g.lineTo(nextPos.x - ISO.TILE_W / 2, nextPos.y - wallHeight + 3);
            g.lineTo(pos.x - ISO.TILE_W / 2, pos.y - wallHeight + 3);
            g.closePath();
            g.endFill();

            // Baseboard
            g.beginFill(pal.trim, 0.4);
            g.moveTo(pos.x - ISO.TILE_W / 2, pos.y - 4);
            g.lineTo(nextPos.x - ISO.TILE_W / 2, nextPos.y - 4);
            g.lineTo(nextPos.x - ISO.TILE_W / 2, nextPos.y);
            g.lineTo(pos.x - ISO.TILE_W / 2, pos.y);
            g.closePath();
            g.endFill();
        }

        return g;
    }

    function createSideWall(length) {
        const g = new PIXI.Graphics();
        const pal = PALETTE.wall;
        const wallHeight = 65;

        for (let j = 0; j < length; j++) {
            const pos = ISO.gridToScreen(0, j);
            const nextPos = ISO.gridToScreen(0, j + 1);

            // Wall face (right-facing wall along the left)
            g.beginFill(pal.back);
            g.moveTo(pos.x + ISO.TILE_W / 2, pos.y - wallHeight);
            g.lineTo(nextPos.x + ISO.TILE_W / 2, nextPos.y - wallHeight);
            g.lineTo(nextPos.x + ISO.TILE_W / 2, nextPos.y);
            g.lineTo(pos.x + ISO.TILE_W / 2, pos.y);
            g.closePath();
            g.endFill();

            // Wall trim
            g.beginFill(pal.trim, 0.6);
            g.moveTo(pos.x + ISO.TILE_W / 2, pos.y - wallHeight);
            g.lineTo(nextPos.x + ISO.TILE_W / 2, nextPos.y - wallHeight);
            g.lineTo(nextPos.x + ISO.TILE_W / 2, nextPos.y - wallHeight + 3);
            g.lineTo(pos.x + ISO.TILE_W / 2, pos.y - wallHeight + 3);
            g.closePath();
            g.endFill();

            // Baseboard
            g.beginFill(pal.trim, 0.4);
            g.moveTo(pos.x + ISO.TILE_W / 2, pos.y - 4);
            g.lineTo(nextPos.x + ISO.TILE_W / 2, nextPos.y - 4);
            g.lineTo(nextPos.x + ISO.TILE_W / 2, nextPos.y);
            g.lineTo(pos.x + ISO.TILE_W / 2, pos.y);
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
        createBookshelf,
        createPlant,
        createWaterCooler,
        createClock,
        createWindow,
        createWhiteboard,
        createWorkstation,
        createFloorTile,
        createCarpetTile,
        createBackWall,
        createSideWall,
    };

})();
