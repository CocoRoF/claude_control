/**
 * Office Assets - Floor tiles and walls drawn via PIXI Graphics
 */
window.CompanyView = window.CompanyView || {};

(function () {
    'use strict';

    const ISO = window.CompanyView.ISO;
    const Prims = window.CompanyView.IsoPrimitives;

    // ==================== Color Palettes ====================
    const PALETTE = {
        carpet: {
            main: 0xB8C4D4,      // soft blue-gray carpet
            border: 0x9AACBC,
        },
        wall: {
            back: 0xF5F5F0,      // warm white
            side: 0xE8E8E0,
            trim: 0xD8D8D0,
        },
        wallPink: {
            back: 0xEBEBE5,      // slightly darker warm white (no pink)
            side: 0xDEDED8,
            trim: 0xD0D0C8,
        },
        floor: {
            tile1: 0xE8E4DC,     // warm beige
            tile2: 0xDFDBD3,
            tilePink: 0xE5E1D9,
        },
    };

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
        createFloorTile,
        createCarpetTile,
        createBackWall,
        createSideWall,
    };

})();
