/**
 * Window Assets - Isometric window rendering for walls
 * Creates windows that align with isometric wall angles
 */
window.CompanyView = window.CompanyView || {};

(function () {
    'use strict';

    const ISO = window.CompanyView.ISO;

    // Window color palette
    const WINDOW_PALETTE = {
        frame: 0x8B7355,        // wood frame
        frameDark: 0x6B5344,
        glass: 0x87CEEB,        // sky blue glass
        glassReflect: 0xB0E0E6,
        sill: 0xD8D8D0,
    };

    const WALL_HEIGHT = 65;

    /**
     * Create a window for the back wall (y=0, along x-axis)
     * Back wall direction: as x increases, screen goes right-down (\ slope)
     * Wall direction vector: (TILE_W/2, TILE_H/2) per grid unit
     * @param {number} tileIndex - Which tile position (0 to length-1)
     * @param {number} windowWidth - Width along the wall (default 28)
     * @param {number} windowHeight - Height in pixels (default 30)
     * @returns {PIXI.Graphics}
     */
    function createBackWallWindow(tileIndex, windowWidth = 28, windowHeight = 30) {
        const g = new PIXI.Graphics();

        // Get the center position of the tile on the wall
        const pos = ISO.gridToScreen(tileIndex + 0.5, 0);

        // Wall base Y (top corner of tile)
        const wallBaseY = pos.y - ISO.TILE_H / 2;

        // Window center position on the wall face
        const centerX = pos.x;
        const centerY = wallBaseY - WALL_HEIGHT * 0.5;

        // Back wall direction vector (normalized): going along x-axis in grid = right-down on screen
        // For 1 grid unit in x: screen moves (TILE_W/2, TILE_H/2)
        // Unit vector along wall: (2/sqrt(5), 1/sqrt(5)) ≈ (0.894, 0.447)
        const sqrt5 = Math.sqrt(5);
        const ux = 2 / sqrt5;  // horizontal component of wall direction
        const uy = 1 / sqrt5;  // vertical component of wall direction (positive = down)

        // Half dimensions
        const hw = windowWidth / 2;
        const hh = windowHeight / 2;

        // Window corners - parallelogram aligned to wall direction
        // Left/Right are along wall, Top/Bottom are vertical
        const topLeft = { x: centerX - ux * hw, y: centerY - hh - uy * hw };
        const topRight = { x: centerX + ux * hw, y: centerY - hh + uy * hw };
        const bottomRight = { x: centerX + ux * hw, y: centerY + hh + uy * hw };
        const bottomLeft = { x: centerX - ux * hw, y: centerY + hh - uy * hw };

        // Draw window frame (outer border)
        const frameWidth = 3;
        g.beginFill(WINDOW_PALETTE.frame);
        g.moveTo(topLeft.x - ux * frameWidth, topLeft.y - frameWidth - uy * frameWidth);
        g.lineTo(topRight.x + ux * frameWidth, topRight.y - frameWidth + uy * frameWidth);
        g.lineTo(bottomRight.x + ux * frameWidth, bottomRight.y + frameWidth + uy * frameWidth);
        g.lineTo(bottomLeft.x - ux * frameWidth, bottomLeft.y + frameWidth - uy * frameWidth);
        g.closePath();
        g.endFill();

        // Glass pane
        g.beginFill(WINDOW_PALETTE.glass, 0.75);
        g.moveTo(topLeft.x, topLeft.y);
        g.lineTo(topRight.x, topRight.y);
        g.lineTo(bottomRight.x, bottomRight.y);
        g.lineTo(bottomLeft.x, bottomLeft.y);
        g.closePath();
        g.endFill();

        // Horizontal divider (cross frame)
        g.beginFill(WINDOW_PALETTE.frameDark);
        const midLeftX = (topLeft.x + bottomLeft.x) / 2;
        const midLeftY = (topLeft.y + bottomLeft.y) / 2;
        const midRightX = (topRight.x + bottomRight.x) / 2;
        const midRightY = (topRight.y + bottomRight.y) / 2;
        g.moveTo(midLeftX, midLeftY - 1.5);
        g.lineTo(midRightX, midRightY - 1.5);
        g.lineTo(midRightX, midRightY + 1.5);
        g.lineTo(midLeftX, midLeftY + 1.5);
        g.closePath();
        g.endFill();

        // Window sill
        g.beginFill(WINDOW_PALETTE.sill);
        const sillDepth = 4;
        g.moveTo(bottomLeft.x - ux * 4, bottomLeft.y + 2 - uy * 4);
        g.lineTo(bottomRight.x + ux * 4, bottomRight.y + 2 + uy * 4);
        g.lineTo(bottomRight.x + ux * 4, bottomRight.y + 2 + sillDepth + uy * 4);
        g.lineTo(bottomLeft.x - ux * 4, bottomLeft.y + 2 + sillDepth - uy * 4);
        g.closePath();
        g.endFill();

        return g;
    }

    /**
     * Create a window for the side wall (x=0, along y-axis)
     * Side wall direction: as y increases, screen goes left-down (/ slope)
     * Wall direction vector: (-TILE_W/2, TILE_H/2) per grid unit
     * @param {number} tileIndex - Which tile position (0 to length-1)
     * @param {number} windowWidth - Width along the wall (default 28)
     * @param {number} windowHeight - Height in pixels (default 30)
     * @returns {PIXI.Graphics}
     */
    function createSideWallWindow(tileIndex, windowWidth = 28, windowHeight = 30) {
        const g = new PIXI.Graphics();

        // Get the center position of the tile on the wall
        const pos = ISO.gridToScreen(0, tileIndex + 0.5);

        // Wall base Y (top corner of tile)
        const wallBaseY = pos.y - ISO.TILE_H / 2;

        // Window center position on the wall face
        const centerX = pos.x;
        const centerY = wallBaseY - WALL_HEIGHT * 0.5;

        // Side wall direction vector (normalized): going along y-axis in grid = left-down on screen
        // For 1 grid unit in y: screen moves (-TILE_W/2, TILE_H/2)
        // Unit vector along wall: (-2/sqrt(5), 1/sqrt(5)) ≈ (-0.894, 0.447)
        const sqrt5 = Math.sqrt(5);
        const ux = -2 / sqrt5;  // horizontal component of wall direction (negative = left)
        const uy = 1 / sqrt5;   // vertical component of wall direction (positive = down)

        // Half dimensions
        const hw = windowWidth / 2;
        const hh = windowHeight / 2;

        // Window corners - parallelogram aligned to wall direction
        // Left/Right are along wall, Top/Bottom are vertical
        const topLeft = { x: centerX - ux * hw, y: centerY - hh - uy * hw };
        const topRight = { x: centerX + ux * hw, y: centerY - hh + uy * hw };
        const bottomRight = { x: centerX + ux * hw, y: centerY + hh + uy * hw };
        const bottomLeft = { x: centerX - ux * hw, y: centerY + hh - uy * hw };

        // Draw window frame (outer border)
        const frameWidth = 3;
        g.beginFill(WINDOW_PALETTE.frame);
        g.moveTo(topLeft.x - ux * frameWidth, topLeft.y - frameWidth - uy * frameWidth);
        g.lineTo(topRight.x + ux * frameWidth, topRight.y - frameWidth + uy * frameWidth);
        g.lineTo(bottomRight.x + ux * frameWidth, bottomRight.y + frameWidth + uy * frameWidth);
        g.lineTo(bottomLeft.x - ux * frameWidth, bottomLeft.y + frameWidth - uy * frameWidth);
        g.closePath();
        g.endFill();

        // Glass pane
        g.beginFill(WINDOW_PALETTE.glass, 0.75);
        g.moveTo(topLeft.x, topLeft.y);
        g.lineTo(topRight.x, topRight.y);
        g.lineTo(bottomRight.x, bottomRight.y);
        g.lineTo(bottomLeft.x, bottomLeft.y);
        g.closePath();
        g.endFill();

        // Horizontal divider (cross frame)
        g.beginFill(WINDOW_PALETTE.frameDark);
        const midLeftX = (topLeft.x + bottomLeft.x) / 2;
        const midLeftY = (topLeft.y + bottomLeft.y) / 2;
        const midRightX = (topRight.x + bottomRight.x) / 2;
        const midRightY = (topRight.y + bottomRight.y) / 2;
        g.moveTo(midLeftX, midLeftY - 1.5);
        g.lineTo(midRightX, midRightY - 1.5);
        g.lineTo(midRightX, midRightY + 1.5);
        g.lineTo(midLeftX, midLeftY + 1.5);
        g.closePath();
        g.endFill();

        // Window sill
        g.beginFill(WINDOW_PALETTE.sill);
        const sillDepth = 4;
        g.moveTo(bottomLeft.x - ux * 4, bottomLeft.y + 2 - uy * 4);
        g.lineTo(bottomRight.x + ux * 4, bottomRight.y + 2 + uy * 4);
        g.lineTo(bottomRight.x + ux * 4, bottomRight.y + 2 + sillDepth + uy * 4);
        g.lineTo(bottomLeft.x - ux * 4, bottomLeft.y + 2 + sillDepth - uy * 4);
        g.closePath();
        g.endFill();

        return g;
    }

    // ==================== Export ====================
    window.CompanyView.WindowAssets = {
        WINDOW_PALETTE,
        createBackWallWindow,
        createSideWallWindow,
    };

})();
