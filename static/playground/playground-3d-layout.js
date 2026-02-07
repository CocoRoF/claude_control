/**
 * City 3D Layout
 * Defines a city grid with buildings, roads, and nature
 *
 * Coordinate System:
 * - X: Left to Right
 * - Y: Up (height)
 * - Z: Back to Front
 *
 * Grid: Each cell is 1x1 unit (roads and buildings occupy cells)
 */
(function() {
    'use strict';

    window.Playground = window.Playground || {};

    // ==================== City Configuration ====================
    const CITY = {
        WIDTH: 17,   // X axis (tiles) - expanded from 9
        DEPTH: 17,   // Z axis (tiles) - expanded from 9
        TILE_SIZE: 1
    };

    // ==================== City Grid Definition ====================
    // Legend:
    // 'R' = Road straight (vertical)
    // 'H' = Road straight (horizontal)
    // '+' = Crossroad
    // 'T' = T-intersection
    // 'L' = Bend/corner
    // 'B' = Building slot
    // 'P' = Park/nature area
    // '.' = Empty ground tile

    const CITY_GRID = [
        // Z=0 (back row) - outer boundary
        ['B', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'P', 'P', 'P', 'P'],
        // Z=1
        ['B', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'P', 'P', 'P', 'P'],
        // Z=2
        ['B', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'P', 'P', 'P', 'P'],
        // Z=3 (road row)
        ['R', 'R', 'R', '+', 'R', 'R', '+', 'R', 'R', '+', 'R', 'R', '+', 'R', 'R', 'R', 'R'],
        // Z=4
        ['B', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'B', 'B'],
        // Z=5
        ['B', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'B', 'B'],
        // Z=6 (road row)
        ['R', 'R', 'R', '+', 'R', 'R', '+', 'R', 'R', '+', 'R', 'R', '+', 'R', 'R', 'R', 'R'],
        // Z=7
        ['B', 'B', 'B', 'H', 'B', 'B', 'H', 'P', 'P', 'H', 'B', 'B', 'H', 'B', 'B', 'B', 'B'],
        // Z=8 - Central park area
        ['B', 'B', 'B', 'H', 'B', 'B', 'H', 'P', 'P', 'H', 'B', 'B', 'H', 'B', 'B', 'B', 'B'],
        // Z=9 (road row)
        ['R', 'R', 'R', '+', 'R', 'R', '+', 'R', 'R', '+', 'R', 'R', '+', 'R', 'R', 'R', 'R'],
        // Z=10
        ['B', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'B', 'B'],
        // Z=11
        ['B', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'B', 'B'],
        // Z=12 (road row)
        ['R', 'R', 'R', '+', 'R', 'R', '+', 'R', 'R', '+', 'R', 'R', '+', 'R', 'R', 'R', 'R'],
        // Z=13
        ['P', 'P', 'P', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'B', 'B'],
        // Z=14
        ['P', 'P', 'P', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'B', 'B'],
        // Z=15
        ['P', 'P', 'P', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'B', 'B'],
        // Z=16 (front row) - outer boundary road
        ['R', 'R', 'R', '+', 'R', 'R', '+', 'R', 'R', '+', 'R', 'R', '+', 'R', 'R', 'R', 'R']
    ];

    // ==================== Building Definitions ====================
    // Define which building goes where - Larger, more diverse city
    const BUILDINGS = [
        // ===== Row 0-2 (Back section) =====
        // Block A1 (far back left)
        { gx: 0, gz: 0, type: 'building', name: 'skyscraperA', rotation: 0 },
        { gx: 1, gz: 0, type: 'building', name: 'a', rotation: 0 },
        { gx: 2, gz: 0, type: 'building', name: 'b', rotation: 0 },
        { gx: 0, gz: 1, type: 'building', name: 'c', rotation: 0 },
        { gx: 1, gz: 1, type: 'building', name: 'd', rotation: 0 },
        { gx: 2, gz: 1, type: 'building', name: 'e', rotation: 0 },
        { gx: 0, gz: 2, type: 'building', name: 'f', rotation: 0 },
        { gx: 1, gz: 2, type: 'building', name: 'g', rotation: 0 },
        { gx: 2, gz: 2, type: 'building', name: 'h', rotation: 0 },

        // Block A2
        { gx: 4, gz: 0, type: 'building', name: 'skyscraperB', rotation: 0 },
        { gx: 5, gz: 0, type: 'building', name: 'a', rotation: Math.PI / 2 },
        { gx: 4, gz: 1, type: 'building', name: 'b', rotation: Math.PI / 2 },
        { gx: 5, gz: 1, type: 'building', name: 'c', rotation: Math.PI / 2 },
        { gx: 4, gz: 2, type: 'building', name: 'd', rotation: Math.PI / 2 },
        { gx: 5, gz: 2, type: 'building', name: 'e', rotation: Math.PI / 2 },

        // Block A3
        { gx: 7, gz: 0, type: 'building', name: 'skyscraperA', rotation: Math.PI },
        { gx: 8, gz: 0, type: 'building', name: 'skyscraperB', rotation: Math.PI },
        { gx: 7, gz: 1, type: 'building', name: 'f', rotation: 0 },
        { gx: 8, gz: 1, type: 'building', name: 'g', rotation: 0 },
        { gx: 7, gz: 2, type: 'building', name: 'h', rotation: 0 },
        { gx: 8, gz: 2, type: 'building', name: 'a', rotation: Math.PI },

        // Block A4
        { gx: 10, gz: 0, type: 'building', name: 'b', rotation: Math.PI },
        { gx: 11, gz: 0, type: 'building', name: 'c', rotation: Math.PI },
        { gx: 10, gz: 1, type: 'building', name: 'd', rotation: Math.PI },
        { gx: 11, gz: 1, type: 'building', name: 'skyscraperA', rotation: -Math.PI / 2 },
        { gx: 10, gz: 2, type: 'building', name: 'e', rotation: Math.PI },
        { gx: 11, gz: 2, type: 'building', name: 'f', rotation: Math.PI },

        // ===== Row 4-5 (Second section) =====
        // Block B1
        { gx: 0, gz: 4, type: 'building', name: 'g', rotation: 0 },
        { gx: 1, gz: 4, type: 'building', name: 'h', rotation: 0 },
        { gx: 2, gz: 4, type: 'building', name: 'skyscraperB', rotation: 0 },
        { gx: 0, gz: 5, type: 'building', name: 'a', rotation: 0 },
        { gx: 1, gz: 5, type: 'building', name: 'b', rotation: 0 },
        { gx: 2, gz: 5, type: 'building', name: 'c', rotation: 0 },

        // Block B2
        { gx: 4, gz: 4, type: 'building', name: 'd', rotation: Math.PI / 2 },
        { gx: 5, gz: 4, type: 'building', name: 'e', rotation: Math.PI / 2 },
        { gx: 4, gz: 5, type: 'building', name: 'f', rotation: Math.PI / 2 },
        { gx: 5, gz: 5, type: 'building', name: 'skyscraperA', rotation: Math.PI / 2 },

        // Block B3
        { gx: 7, gz: 4, type: 'building', name: 'g', rotation: 0 },
        { gx: 8, gz: 4, type: 'building', name: 'h', rotation: 0 },
        { gx: 7, gz: 5, type: 'building', name: 'a', rotation: Math.PI },
        { gx: 8, gz: 5, type: 'building', name: 'b', rotation: Math.PI },

        // Block B4
        { gx: 10, gz: 4, type: 'building', name: 'c', rotation: -Math.PI / 2 },
        { gx: 11, gz: 4, type: 'building', name: 'd', rotation: -Math.PI / 2 },
        { gx: 10, gz: 5, type: 'building', name: 'e', rotation: -Math.PI / 2 },
        { gx: 11, gz: 5, type: 'building', name: 'f', rotation: -Math.PI / 2 },

        // Block B5 (far right)
        { gx: 13, gz: 4, type: 'building', name: 'skyscraperB', rotation: -Math.PI / 2 },
        { gx: 14, gz: 4, type: 'building', name: 'g', rotation: -Math.PI / 2 },
        { gx: 15, gz: 4, type: 'building', name: 'h', rotation: -Math.PI / 2 },
        { gx: 16, gz: 4, type: 'building', name: 'a', rotation: -Math.PI / 2 },
        { gx: 13, gz: 5, type: 'building', name: 'b', rotation: -Math.PI / 2 },
        { gx: 14, gz: 5, type: 'building', name: 'c', rotation: -Math.PI / 2 },
        { gx: 15, gz: 5, type: 'building', name: 'd', rotation: -Math.PI / 2 },
        { gx: 16, gz: 5, type: 'building', name: 'e', rotation: -Math.PI / 2 },

        // ===== Row 7-8 (Central section with park) =====
        // Block C1
        { gx: 0, gz: 7, type: 'building', name: 'f', rotation: 0 },
        { gx: 1, gz: 7, type: 'building', name: 'skyscraperA', rotation: 0 },
        { gx: 2, gz: 7, type: 'building', name: 'g', rotation: 0 },
        { gx: 0, gz: 8, type: 'building', name: 'h', rotation: 0 },
        { gx: 1, gz: 8, type: 'building', name: 'a', rotation: 0 },
        { gx: 2, gz: 8, type: 'building', name: 'b', rotation: 0 },

        // Block C2
        { gx: 4, gz: 7, type: 'building', name: 'c', rotation: Math.PI / 2 },
        { gx: 5, gz: 7, type: 'building', name: 'd', rotation: Math.PI / 2 },
        { gx: 4, gz: 8, type: 'building', name: 'e', rotation: Math.PI / 2 },
        { gx: 5, gz: 8, type: 'building', name: 'f', rotation: Math.PI / 2 },

        // (Central park at 7-8, 7-8)

        // Block C4
        { gx: 10, gz: 7, type: 'building', name: 'skyscraperB', rotation: Math.PI },
        { gx: 11, gz: 7, type: 'building', name: 'g', rotation: Math.PI },
        { gx: 10, gz: 8, type: 'building', name: 'h', rotation: Math.PI },
        { gx: 11, gz: 8, type: 'building', name: 'a', rotation: Math.PI },

        // Block C5
        { gx: 13, gz: 7, type: 'building', name: 'b', rotation: -Math.PI / 2 },
        { gx: 14, gz: 7, type: 'building', name: 'skyscraperA', rotation: -Math.PI / 2 },
        { gx: 15, gz: 7, type: 'building', name: 'c', rotation: -Math.PI / 2 },
        { gx: 16, gz: 7, type: 'building', name: 'd', rotation: -Math.PI / 2 },
        { gx: 13, gz: 8, type: 'building', name: 'e', rotation: -Math.PI / 2 },
        { gx: 14, gz: 8, type: 'building', name: 'f', rotation: -Math.PI / 2 },
        { gx: 15, gz: 8, type: 'building', name: 'g', rotation: -Math.PI / 2 },
        { gx: 16, gz: 8, type: 'building', name: 'skyscraperB', rotation: -Math.PI / 2 },

        // ===== Row 10-11 =====
        // Block D1
        { gx: 0, gz: 10, type: 'building', name: 'h', rotation: 0 },
        { gx: 1, gz: 10, type: 'building', name: 'a', rotation: 0 },
        { gx: 2, gz: 10, type: 'building', name: 'b', rotation: 0 },
        { gx: 0, gz: 11, type: 'building', name: 'skyscraperB', rotation: 0 },
        { gx: 1, gz: 11, type: 'building', name: 'c', rotation: 0 },
        { gx: 2, gz: 11, type: 'building', name: 'd', rotation: 0 },

        // Block D2
        { gx: 4, gz: 10, type: 'building', name: 'e', rotation: Math.PI / 2 },
        { gx: 5, gz: 10, type: 'building', name: 'f', rotation: Math.PI / 2 },
        { gx: 4, gz: 11, type: 'building', name: 'g', rotation: Math.PI / 2 },
        { gx: 5, gz: 11, type: 'building', name: 'h', rotation: Math.PI / 2 },

        // Block D3
        { gx: 7, gz: 10, type: 'building', name: 'skyscraperA', rotation: 0 },
        { gx: 8, gz: 10, type: 'building', name: 'a', rotation: 0 },
        { gx: 7, gz: 11, type: 'building', name: 'b', rotation: Math.PI },
        { gx: 8, gz: 11, type: 'building', name: 'skyscraperB', rotation: Math.PI },

        // Block D4
        { gx: 10, gz: 10, type: 'building', name: 'c', rotation: Math.PI },
        { gx: 11, gz: 10, type: 'building', name: 'd', rotation: Math.PI },
        { gx: 10, gz: 11, type: 'building', name: 'e', rotation: Math.PI },
        { gx: 11, gz: 11, type: 'building', name: 'f', rotation: Math.PI },

        // Block D5
        { gx: 13, gz: 10, type: 'building', name: 'g', rotation: -Math.PI / 2 },
        { gx: 14, gz: 10, type: 'building', name: 'h', rotation: -Math.PI / 2 },
        { gx: 15, gz: 10, type: 'building', name: 'skyscraperA', rotation: -Math.PI / 2 },
        { gx: 16, gz: 10, type: 'building', name: 'a', rotation: -Math.PI / 2 },
        { gx: 13, gz: 11, type: 'building', name: 'b', rotation: -Math.PI / 2 },
        { gx: 14, gz: 11, type: 'building', name: 'c', rotation: -Math.PI / 2 },
        { gx: 15, gz: 11, type: 'building', name: 'd', rotation: -Math.PI / 2 },
        { gx: 16, gz: 11, type: 'building', name: 'e', rotation: -Math.PI / 2 },

        // ===== Row 13-15 (Front section) =====
        // Block E2
        { gx: 4, gz: 13, type: 'building', name: 'f', rotation: Math.PI / 2 },
        { gx: 5, gz: 13, type: 'building', name: 'skyscraperB', rotation: Math.PI / 2 },
        { gx: 4, gz: 14, type: 'building', name: 'g', rotation: Math.PI / 2 },
        { gx: 5, gz: 14, type: 'building', name: 'h', rotation: Math.PI / 2 },
        { gx: 4, gz: 15, type: 'building', name: 'a', rotation: Math.PI / 2 },
        { gx: 5, gz: 15, type: 'building', name: 'b', rotation: Math.PI / 2 },

        // Block E3
        { gx: 7, gz: 13, type: 'building', name: 'c', rotation: 0 },
        { gx: 8, gz: 13, type: 'building', name: 'd', rotation: 0 },
        { gx: 7, gz: 14, type: 'building', name: 'skyscraperA', rotation: Math.PI },
        { gx: 8, gz: 14, type: 'building', name: 'e', rotation: Math.PI },
        { gx: 7, gz: 15, type: 'building', name: 'f', rotation: Math.PI },
        { gx: 8, gz: 15, type: 'building', name: 'g', rotation: Math.PI },

        // Block E4
        { gx: 10, gz: 13, type: 'building', name: 'h', rotation: Math.PI },
        { gx: 11, gz: 13, type: 'building', name: 'skyscraperB', rotation: Math.PI },
        { gx: 10, gz: 14, type: 'building', name: 'a', rotation: Math.PI },
        { gx: 11, gz: 14, type: 'building', name: 'b', rotation: Math.PI },
        { gx: 10, gz: 15, type: 'building', name: 'c', rotation: Math.PI },
        { gx: 11, gz: 15, type: 'building', name: 'd', rotation: Math.PI },

        // Block E5 (far right front)
        { gx: 13, gz: 13, type: 'building', name: 'e', rotation: -Math.PI / 2 },
        { gx: 14, gz: 13, type: 'building', name: 'f', rotation: -Math.PI / 2 },
        { gx: 15, gz: 13, type: 'building', name: 'g', rotation: -Math.PI / 2 },
        { gx: 16, gz: 13, type: 'building', name: 'skyscraperA', rotation: -Math.PI / 2 },
        { gx: 13, gz: 14, type: 'building', name: 'h', rotation: -Math.PI / 2 },
        { gx: 14, gz: 14, type: 'building', name: 'skyscraperB', rotation: -Math.PI / 2 },
        { gx: 15, gz: 14, type: 'building', name: 'a', rotation: -Math.PI / 2 },
        { gx: 16, gz: 14, type: 'building', name: 'b', rotation: -Math.PI / 2 },
        { gx: 13, gz: 15, type: 'building', name: 'c', rotation: -Math.PI / 2 },
        { gx: 14, gz: 15, type: 'building', name: 'd', rotation: -Math.PI / 2 },
        { gx: 15, gz: 15, type: 'building', name: 'e', rotation: -Math.PI / 2 },
        { gx: 16, gz: 15, type: 'building', name: 'f', rotation: -Math.PI / 2 }
    ];

    // ==================== Road Definitions ====================
    // Roads are placed based on the grid
    function getRoads() {
        const roads = [];

        for (let gz = 0; gz < CITY.DEPTH; gz++) {
            for (let gx = 0; gx < CITY.WIDTH; gx++) {
                const cell = CITY_GRID[gz][gx];
                let roadType = null;
                let rotation = 0;

                switch (cell) {
                    case 'R': // Vertical road
                        roadType = 'straight';
                        rotation = 0;
                        break;
                    case 'H': // Horizontal road
                        roadType = 'straight';
                        rotation = Math.PI / 2;
                        break;
                    case '+': // Crossroad
                        roadType = 'crossroad';
                        rotation = 0;
                        break;
                    case 'T': // T-intersection
                        roadType = 'intersection';
                        rotation = 0;
                        break;
                    case 'L': // Bend
                        roadType = 'bend';
                        rotation = 0;
                        break;
                }

                if (roadType) {
                    roads.push({
                        gx,
                        gz,
                        type: 'road',
                        name: roadType,
                        rotation
                    });
                }
            }
        }

        return roads;
    }

    // ==================== Nature/Park Definitions ====================
    const NATURE = [
        // Back-right park area (Z=0-2, X=13-16)
        { gx: 13, gz: 0, type: 'nature', name: 'treeLarge', rotation: 0 },
        { gx: 14, gz: 0, type: 'nature', name: 'treeSmall', rotation: Math.PI / 3 },
        { gx: 15, gz: 0, type: 'nature', name: 'planter', rotation: 0 },
        { gx: 16, gz: 0, type: 'nature', name: 'treeLarge', rotation: Math.PI / 2 },
        { gx: 13, gz: 1, type: 'nature', name: 'treeSmall', rotation: 0 },
        { gx: 14, gz: 1, type: 'nature', name: 'treeLarge', rotation: Math.PI / 4 },
        { gx: 15, gz: 1, type: 'nature', name: 'treeSmall', rotation: Math.PI },
        { gx: 16, gz: 1, type: 'nature', name: 'planter', rotation: Math.PI / 2 },
        { gx: 13, gz: 2, type: 'nature', name: 'planter', rotation: Math.PI },
        { gx: 14, gz: 2, type: 'nature', name: 'treeSmall', rotation: 0 },
        { gx: 15, gz: 2, type: 'nature', name: 'treeLarge', rotation: Math.PI / 6 },
        { gx: 16, gz: 2, type: 'nature', name: 'treeSmall', rotation: Math.PI / 3 },

        // Central park area (Z=7-8, X=7-8)
        { gx: 7, gz: 7, type: 'nature', name: 'treeLarge', rotation: 0 },
        { gx: 8, gz: 7, type: 'nature', name: 'planter', rotation: Math.PI / 4 },
        { gx: 7, gz: 8, type: 'nature', name: 'planter', rotation: Math.PI / 2 },
        { gx: 8, gz: 8, type: 'nature', name: 'treeLarge', rotation: Math.PI },

        // Front-left park area (Z=13-15, X=0-2)
        { gx: 0, gz: 13, type: 'nature', name: 'treeLarge', rotation: 0 },
        { gx: 1, gz: 13, type: 'nature', name: 'treeSmall', rotation: Math.PI / 3 },
        { gx: 2, gz: 13, type: 'nature', name: 'planter', rotation: 0 },
        { gx: 0, gz: 14, type: 'nature', name: 'treeSmall', rotation: Math.PI / 4 },
        { gx: 1, gz: 14, type: 'nature', name: 'treeLarge', rotation: Math.PI / 2 },
        { gx: 2, gz: 14, type: 'nature', name: 'treeSmall', rotation: Math.PI },
        { gx: 0, gz: 15, type: 'nature', name: 'planter', rotation: Math.PI / 6 },
        { gx: 1, gz: 15, type: 'nature', name: 'treeSmall', rotation: 0 },
        { gx: 2, gz: 15, type: 'nature', name: 'treeLarge', rotation: Math.PI / 3 }
    ];

    // ==================== Work Positions (Buildings) ====================
    // Characters "work" inside buildings - these are the building positions
    const WORK_POSITIONS = BUILDINGS.map((building, index) => ({
        gx: building.gx,
        gz: building.gz,
        buildingIndex: index,
        buildingName: building.name
    }));

    // ==================== Entrance Position ====================
    const ENTRANCE = {
        gx: 8,
        gz: 16,  // Front road (center of expanded city)
        direction: 'N'
    };

    // ==================== Pathfinding Grid ====================
    function generateWalkableMap() {
        const grid = [];

        for (let gz = 0; gz < CITY.DEPTH; gz++) {
            const row = [];
            for (let gx = 0; gx < CITY.WIDTH; gx++) {
                const cell = CITY_GRID[gz][gx];
                // Roads and parks are walkable
                const walkable = (cell === 'R' || cell === 'H' || cell === '+' ||
                                  cell === 'T' || cell === 'L' || cell === 'P');
                row.push(walkable ? 1 : 0);
            }
            grid.push(row);
        }

        return {
            grid: grid,
            width: CITY.WIDTH,
            height: CITY.DEPTH
        };
    }

    // ==================== Get Ground Tiles ====================
    function getGroundTiles() {
        const tiles = [];

        for (let gz = 0; gz < CITY.DEPTH; gz++) {
            for (let gx = 0; gx < CITY.WIDTH; gx++) {
                const cell = CITY_GRID[gz][gx];
                // Only place ground tiles under buildings and parks
                if (cell === 'B' || cell === 'P' || cell === '.') {
                    tiles.push({ gx, gz, type: 'tile', name: 'low' });
                }
            }
        }

        return tiles;
    }

    // ==================== Direction Helpers ====================
    const DIRECTION_TO_ROTATION = {
        'N': Math.PI,
        'NE': Math.PI * 0.75,
        'E': Math.PI * 0.5,
        'SE': Math.PI * 0.25,
        'S': 0,
        'SW': -Math.PI * 0.25,
        'W': -Math.PI * 0.5,
        'NW': -Math.PI * 0.75
    };

    function directionToRotation(direction) {
        return DIRECTION_TO_ROTATION[direction] || 0;
    }

    // ==================== Export ====================
    window.Playground.Layout3D = {
        CITY,
        CITY_GRID,
        BUILDINGS,
        NATURE,
        WORK_POSITIONS,
        ENTRANCE,
        getRoads,
        getGroundTiles,
        generateWalkableMap,
        directionToRotation,
        DIRECTION_TO_ROTATION
    };

    console.log('[City3DLayout] Module loaded');

})();
