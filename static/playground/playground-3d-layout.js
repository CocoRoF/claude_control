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
        WIDTH: 21,   // X axis (tiles) - more breathing room
        DEPTH: 21,   // Z axis (tiles) - more breathing room
        TILE_SIZE: 1
    };

    // ==================== City Grid Definition ====================
    // Legend:
    // === Roads ===
    // 'R' = Road straight (vertical, Z-axis direction)
    // 'H' = Road straight (horizontal, X-axis direction)
    // '+' = Crossroad (4-way intersection)
    //
    // === T-Intersection (3-way, one side blocked) ===
    // 'T1' = T-intersection, North blocked  ┬  (opens to S, E, W)
    // 'T2' = T-intersection, South blocked  ┴  (opens to N, E, W)
    // 'T3' = T-intersection, East blocked   ├  (opens to N, S, W)
    // 'T4' = T-intersection, West blocked   ┤  (opens to N, S, E)
    //
    // === L-Bend/Corner (2-way, connects two adjacent directions) ===
    // 'L1' = Bend connecting South + East   └  (bottom-left corner)
    // 'L2' = Bend connecting South + West   ┘  (bottom-right corner)
    // 'L3' = Bend connecting North + West   ┐  (top-right corner)
    // 'L4' = Bend connecting North + East   ┌  (top-left corner)
    //
    // === Minigolf Grass Tiles (with rotation indicator) ===
    // 'C1' = Corner tile, rotation 0°    (grass edge at South+East, └ shape)
    // 'C2' = Corner tile, rotation 90°   (grass edge at South+West, ┘ shape)
    // 'C3' = Corner tile, rotation 180°  (grass edge at North+West, ┐ shape)
    // 'C4' = Corner tile, rotation 270°  (grass edge at North+East, ┌ shape)
    // 'S1' = Side tile, rotation 0°      (grass edge at North)
    // 'S2' = Side tile, rotation 90°     (grass edge at East)
    // 'S3' = Side tile, rotation 180°    (grass edge at South)
    // 'S4' = Side tile, rotation 270°    (grass edge at West)
    //
    // === Non-Road ===
    // 'B' = Building slot
    // 'P' = Park/nature area (large nature park)
    // 'G' = Green space / small garden
    // 'M' = Market floor tile (checkered tile from mini-market)
    // '.' = Empty ground tile

    const CITY_GRID = [
        // Z=0 (back row)
        ['B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'C3', 'S2', 'S2', 'S2', 'S2', 'C2'],
        // Z=1
        ['B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'S3', 'P', 'P', 'P', 'P', 'S1'],
        // Z=2 (road row)
        ['R', 'R', '+', 'R', 'R', '+', 'R', 'R', '+', 'R', 'R', '+', 'R', 'R', 'T4', 'S3', 'P', 'P', 'P', 'P', 'S1'],
        // Z=3
        ['B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'S3', 'P', 'P', 'P', 'P', 'S1'],
        // Z=4
        ['B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'S3', 'P', 'P', 'P', 'P', 'S1'],
        // Z=5 (road row)
        ['R', 'R', '+', 'R', 'R', '+', 'R', 'R', '+', 'R', 'R', '+', 'R', 'R', 'T4', 'S3', 'P', 'P', 'P', 'P', 'S1'],
        // Z=6
        ['B', 'B', 'H', 'B', 'B', 'H', 'C3', 'C2', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'S3', 'P', 'P', 'P', 'P', 'S1'],
        // Z=7
        ['B', 'B', 'H', 'B', 'B', 'H', 'C4', 'C1', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'C4', 'S4', 'S4', 'S4', 'S4', 'C1'],
        // Z=8 (road row)
        ['R', 'R', '+', 'R', 'R', '+', 'R', 'R', '+', 'R', 'R', '+', 'R', 'R', '+', 'R', 'R', 'R', 'R', 'R', 'R'],
        // Z=9
        ['B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'B', 'B', 'B', 'B'],
        // Z=10
        ['B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'B', 'B', 'B', 'B'],
        // Z=11 (road row)
        ['R', 'R', '+', 'R', 'R', '+', 'R', 'R', '+', 'R', 'R', '+', 'R', 'R', '+', 'R', 'R', 'R', 'R', 'R', 'R'],
        // Z=12
        ['B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'B', 'B', 'B', 'B'],
        // Z=13
        ['B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'B', 'B', 'B', 'B'],
        // Z=14 (road row)
        ['R', 'R', '+', 'R', 'R', '+', 'R', 'R', '+', 'R', 'R', '+', 'R', 'R', '+', 'R', 'R', 'R', 'R', 'R', 'R'],
        // Z=15
        ['C3', 'C2', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'C3', 'S2', 'S2', 'S2', 'S2', 'C2'],
        // Z=16
        ['C4', 'C1', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'C4', 'S4', 'S4', 'S4', 'S4', 'C1'],
        // Z=17 (road row)
        ['R', 'R', '+', 'R', 'R', '+', 'R', 'R', '+', 'R', 'R', '+', 'R', 'R', '+', 'R', 'R', 'R', 'R', 'R', 'R'],
        // Z=18
        ['B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'C3', 'S2', 'S2', 'S2', 'S2', 'C2'],
        // Z=19
        ['B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'B', 'B', 'H', 'C4', 'S4', 'S4', 'S4', 'S4', 'C1'],
        // Z=20 (front row)
        ['R', 'R', '+', 'R', 'R', '+', 'R', 'R', '+', 'R', 'R', '+', 'R', 'R', '+', 'R', 'R', 'R', 'R', 'R', 'R']
    ];

    // ==================== Building Definitions ====================
    // Define which building goes where - Spacious city with proper breathing room
    const BUILDINGS = [
        // ===== Zone A: Back-left blocks (Z=0-1, X=0-1 and Z=3-4, X=0-1) =====
        { gx: 0, gz: 0, type: 'building', name: 'skyscraperA', rotation: 0 },
        { gx: 1, gz: 0, type: 'building', name: 'a', rotation: 0 },
        { gx: 0, gz: 1, type: 'building', name: 'b', rotation: 0 },
        { gx: 1, gz: 1, type: 'building', name: 'c', rotation: 0 },
        { gx: 0, gz: 3, type: 'building', name: 'd', rotation: 0 },
        { gx: 1, gz: 3, type: 'building', name: 'e', rotation: 0 },
        { gx: 0, gz: 4, type: 'building', name: 'f', rotation: 0 },
        { gx: 1, gz: 4, type: 'building', name: 'g', rotation: 0 },

        // ===== Zone B: Second column (X=3-4) =====
        { gx: 3, gz: 0, type: 'building', name: 'skyscraperB', rotation: Math.PI / 2 },
        { gx: 4, gz: 0, type: 'building', name: 'h', rotation: Math.PI / 2 },
        { gx: 3, gz: 1, type: 'building', name: 'a', rotation: Math.PI / 2 },
        { gx: 4, gz: 1, type: 'building', name: 'b', rotation: Math.PI / 2 },
        { gx: 3, gz: 3, type: 'building', name: 'c', rotation: Math.PI / 2 },
        { gx: 4, gz: 3, type: 'building', name: 'd', rotation: Math.PI / 2 },
        { gx: 3, gz: 4, type: 'building', name: 'e', rotation: Math.PI / 2 },
        { gx: 4, gz: 4, type: 'building', name: 'skyscraperA', rotation: Math.PI / 2 },

        // ===== Zone C: Third column (X=6-7) =====
        { gx: 6, gz: 0, type: 'building', name: 'f', rotation: 0 },
        { gx: 7, gz: 0, type: 'building', name: 'g', rotation: 0 },
        { gx: 6, gz: 1, type: 'building', name: 'h', rotation: 0 },
        { gx: 7, gz: 1, type: 'building', name: 'skyscraperB', rotation: 0 },
        { gx: 6, gz: 3, type: 'building', name: 'a', rotation: 0 },
        { gx: 7, gz: 3, type: 'building', name: 'b', rotation: 0 },
        { gx: 6, gz: 4, type: 'building', name: 'c', rotation: 0 },
        { gx: 7, gz: 4, type: 'building', name: 'd', rotation: 0 },

        // ===== Zone D: Fourth column (X=9-10) =====
        { gx: 9, gz: 0, type: 'building', name: 'skyscraperA', rotation: Math.PI },
        { gx: 10, gz: 0, type: 'building', name: 'e', rotation: Math.PI },
        { gx: 9, gz: 1, type: 'building', name: 'f', rotation: Math.PI },
        { gx: 10, gz: 1, type: 'building', name: 'g', rotation: Math.PI },
        { gx: 9, gz: 3, type: 'building', name: 'h', rotation: Math.PI },
        { gx: 10, gz: 3, type: 'building', name: 'a', rotation: Math.PI },
        { gx: 9, gz: 4, type: 'building', name: 'b', rotation: Math.PI },
        { gx: 10, gz: 4, type: 'building', name: 'skyscraperB', rotation: Math.PI },

        // ===== Zone E: Fifth column (X=12-13) =====
        { gx: 12, gz: 0, type: 'building', name: 'c', rotation: -Math.PI / 2 },
        { gx: 13, gz: 0, type: 'building', name: 'd', rotation: -Math.PI / 2 },
        { gx: 12, gz: 1, type: 'building', name: 'e', rotation: -Math.PI / 2 },
        { gx: 13, gz: 1, type: 'building', name: 'f', rotation: -Math.PI / 2 },
        { gx: 12, gz: 3, type: 'building', name: 'g', rotation: -Math.PI / 2 },
        { gx: 13, gz: 3, type: 'building', name: 'h', rotation: -Math.PI / 2 },
        { gx: 12, gz: 4, type: 'building', name: 'a', rotation: -Math.PI / 2 },
        { gx: 13, gz: 4, type: 'building', name: 'skyscraperA', rotation: -Math.PI / 2 },

        // ===== Central blocks (Z=6-7, X=0-4 and Z=9-10, X=0-4) - skipping small garden =====
        { gx: 0, gz: 6, type: 'building', name: 'b', rotation: 0 },
        { gx: 1, gz: 6, type: 'building', name: 'c', rotation: 0 },
        { gx: 0, gz: 7, type: 'building', name: 'd', rotation: 0 },
        { gx: 1, gz: 7, type: 'building', name: 'e', rotation: 0 },
        { gx: 3, gz: 6, type: 'building', name: 'f', rotation: Math.PI / 2 },
        { gx: 4, gz: 6, type: 'building', name: 'skyscraperB', rotation: Math.PI / 2 },
        { gx: 3, gz: 7, type: 'building', name: 'g', rotation: Math.PI / 2 },
        { gx: 4, gz: 7, type: 'building', name: 'h', rotation: Math.PI / 2 },
        // Garden at gx=6-7, gz=6-7

        { gx: 9, gz: 6, type: 'building', name: 'a', rotation: Math.PI },
        { gx: 10, gz: 6, type: 'building', name: 'b', rotation: Math.PI },
        { gx: 9, gz: 7, type: 'building', name: 'c', rotation: Math.PI },
        { gx: 10, gz: 7, type: 'building', name: 'd', rotation: Math.PI },
        { gx: 12, gz: 6, type: 'building', name: 'e', rotation: -Math.PI / 2 },
        { gx: 13, gz: 6, type: 'building', name: 'skyscraperA', rotation: -Math.PI / 2 },
        { gx: 12, gz: 7, type: 'building', name: 'f', rotation: -Math.PI / 2 },
        { gx: 13, gz: 7, type: 'building', name: 'g', rotation: -Math.PI / 2 },

        // ===== Zone F: Lower section (Z=9-10, Z=12-13) =====
        { gx: 0, gz: 9, type: 'building', name: 'skyscraperB', rotation: 0 },
        { gx: 1, gz: 9, type: 'building', name: 'h', rotation: 0 },
        { gx: 0, gz: 10, type: 'building', name: 'a', rotation: 0 },
        { gx: 1, gz: 10, type: 'building', name: 'b', rotation: 0 },
        { gx: 3, gz: 9, type: 'building', name: 'c', rotation: Math.PI / 2 },
        { gx: 4, gz: 9, type: 'building', name: 'd', rotation: Math.PI / 2 },
        { gx: 3, gz: 10, type: 'building', name: 'e', rotation: Math.PI / 2 },
        { gx: 4, gz: 10, type: 'building', name: 'f', rotation: Math.PI / 2 },
        { gx: 6, gz: 9, type: 'building', name: 'g', rotation: 0 },
        { gx: 7, gz: 9, type: 'building', name: 'skyscraperA', rotation: 0 },
        { gx: 6, gz: 10, type: 'building', name: 'h', rotation: 0 },
        { gx: 7, gz: 10, type: 'building', name: 'a', rotation: 0 },
        { gx: 9, gz: 9, type: 'building', name: 'b', rotation: Math.PI },
        { gx: 10, gz: 9, type: 'building', name: 'c', rotation: Math.PI },
        { gx: 9, gz: 10, type: 'building', name: 'd', rotation: Math.PI },
        { gx: 10, gz: 10, type: 'building', name: 'skyscraperB', rotation: Math.PI },
        { gx: 12, gz: 9, type: 'building', name: 'e', rotation: -Math.PI / 2 },
        { gx: 13, gz: 9, type: 'building', name: 'f', rotation: -Math.PI / 2 },
        { gx: 12, gz: 10, type: 'building', name: 'g', rotation: -Math.PI / 2 },
        { gx: 13, gz: 10, type: 'building', name: 'h', rotation: -Math.PI / 2 },

        // Bottom rows continuing
        { gx: 0, gz: 12, type: 'building', name: 'a', rotation: 0 },
        { gx: 1, gz: 12, type: 'building', name: 'skyscraperA', rotation: 0 },
        { gx: 0, gz: 13, type: 'building', name: 'b', rotation: 0 },
        { gx: 1, gz: 13, type: 'building', name: 'c', rotation: 0 },
        { gx: 3, gz: 12, type: 'building', name: 'd', rotation: Math.PI / 2 },
        { gx: 4, gz: 12, type: 'building', name: 'e', rotation: Math.PI / 2 },
        { gx: 3, gz: 13, type: 'building', name: 'f', rotation: Math.PI / 2 },
        { gx: 4, gz: 13, type: 'building', name: 'skyscraperB', rotation: Math.PI / 2 },
        { gx: 6, gz: 12, type: 'building', name: 'g', rotation: 0 },
        { gx: 7, gz: 12, type: 'building', name: 'h', rotation: 0 },
        { gx: 6, gz: 13, type: 'building', name: 'a', rotation: 0 },
        { gx: 7, gz: 13, type: 'building', name: 'b', rotation: 0 },
        { gx: 9, gz: 12, type: 'building', name: 'c', rotation: Math.PI },
        { gx: 10, gz: 12, type: 'building', name: 'd', rotation: Math.PI },
        { gx: 9, gz: 13, type: 'building', name: 'e', rotation: Math.PI },
        { gx: 10, gz: 13, type: 'building', name: 'skyscraperA', rotation: Math.PI },
        { gx: 12, gz: 12, type: 'building', name: 'f', rotation: -Math.PI / 2 },
        { gx: 13, gz: 12, type: 'building', name: 'g', rotation: -Math.PI / 2 },
        { gx: 12, gz: 13, type: 'building', name: 'h', rotation: -Math.PI / 2 },
        { gx: 13, gz: 13, type: 'building', name: 'a', rotation: -Math.PI / 2 },

        // ===== Rows with garden at front-left (Z=15-16, skipping X=0-1) =====
        { gx: 3, gz: 15, type: 'building', name: 'b', rotation: Math.PI / 2 },
        { gx: 4, gz: 15, type: 'building', name: 'c', rotation: Math.PI / 2 },
        { gx: 3, gz: 16, type: 'building', name: 'd', rotation: Math.PI / 2 },
        { gx: 4, gz: 16, type: 'building', name: 'skyscraperB', rotation: Math.PI / 2 },
        { gx: 6, gz: 15, type: 'building', name: 'e', rotation: 0 },
        { gx: 7, gz: 15, type: 'building', name: 'f', rotation: 0 },
        { gx: 6, gz: 16, type: 'building', name: 'g', rotation: 0 },
        { gx: 7, gz: 16, type: 'building', name: 'h', rotation: 0 },
        { gx: 9, gz: 15, type: 'building', name: 'a', rotation: Math.PI },
        { gx: 10, gz: 15, type: 'building', name: 'skyscraperA', rotation: Math.PI },
        { gx: 9, gz: 16, type: 'building', name: 'b', rotation: Math.PI },
        { gx: 10, gz: 16, type: 'building', name: 'c', rotation: Math.PI },
        { gx: 12, gz: 15, type: 'building', name: 'd', rotation: -Math.PI / 2 },
        { gx: 13, gz: 15, type: 'building', name: 'e', rotation: -Math.PI / 2 },
        { gx: 12, gz: 16, type: 'building', name: 'f', rotation: -Math.PI / 2 },
        { gx: 13, gz: 16, type: 'building', name: 'skyscraperB', rotation: -Math.PI / 2 },

        // ===== Bottom rows (Z=18-19) =====
        { gx: 0, gz: 18, type: 'building', name: 'g', rotation: 0 },
        { gx: 1, gz: 18, type: 'building', name: 'h', rotation: 0 },
        { gx: 0, gz: 19, type: 'building', name: 'skyscraperA', rotation: 0 },
        { gx: 1, gz: 19, type: 'building', name: 'a', rotation: 0 },
        { gx: 3, gz: 18, type: 'building', name: 'b', rotation: Math.PI / 2 },
        { gx: 4, gz: 18, type: 'building', name: 'c', rotation: Math.PI / 2 },
        { gx: 3, gz: 19, type: 'building', name: 'd', rotation: Math.PI / 2 },
        { gx: 4, gz: 19, type: 'building', name: 'e', rotation: Math.PI / 2 },
        { gx: 6, gz: 18, type: 'building', name: 'f', rotation: 0 },
        { gx: 7, gz: 18, type: 'building', name: 'skyscraperB', rotation: 0 },
        { gx: 6, gz: 19, type: 'building', name: 'g', rotation: 0 },
        { gx: 7, gz: 19, type: 'building', name: 'h', rotation: 0 },
        { gx: 9, gz: 18, type: 'building', name: 'a', rotation: Math.PI },
        { gx: 10, gz: 18, type: 'building', name: 'b', rotation: Math.PI },
        { gx: 9, gz: 19, type: 'building', name: 'c', rotation: Math.PI },
        { gx: 10, gz: 19, type: 'building', name: 'skyscraperA', rotation: Math.PI },
        { gx: 12, gz: 18, type: 'building', name: 'd', rotation: -Math.PI / 2 },
        { gx: 13, gz: 18, type: 'building', name: 'e', rotation: -Math.PI / 2 },
        { gx: 12, gz: 19, type: 'building', name: 'f', rotation: -Math.PI / 2 },
        { gx: 13, gz: 19, type: 'building', name: 'g', rotation: -Math.PI / 2 },

        // Right side buildings (X=15-16, various Z not in park)
        { gx: 15, gz: 9, type: 'building', name: 'h', rotation: -Math.PI / 2 },
        { gx: 16, gz: 9, type: 'building', name: 'skyscraperB', rotation: -Math.PI / 2 },
        { gx: 17, gz: 9, type: 'building', name: 'a', rotation: -Math.PI / 2 },
        { gx: 18, gz: 9, type: 'building', name: 'b', rotation: -Math.PI / 2 },
        { gx: 19, gz: 9, type: 'building', name: 'c', rotation: -Math.PI / 2 },
        { gx: 20, gz: 9, type: 'building', name: 'd', rotation: -Math.PI / 2 },
        { gx: 15, gz: 10, type: 'building', name: 'e', rotation: -Math.PI / 2 },
        { gx: 16, gz: 10, type: 'building', name: 'f', rotation: -Math.PI / 2 },
        { gx: 17, gz: 10, type: 'building', name: 'skyscraperA', rotation: -Math.PI / 2 },
        { gx: 18, gz: 10, type: 'building', name: 'g', rotation: -Math.PI / 2 },
        { gx: 19, gz: 10, type: 'building', name: 'h', rotation: -Math.PI / 2 },
        { gx: 20, gz: 10, type: 'building', name: 'a', rotation: -Math.PI / 2 },

        { gx: 15, gz: 12, type: 'building', name: 'b', rotation: -Math.PI / 2 },
        { gx: 16, gz: 12, type: 'building', name: 'c', rotation: -Math.PI / 2 },
        { gx: 17, gz: 12, type: 'building', name: 'd', rotation: -Math.PI / 2 },
        { gx: 18, gz: 12, type: 'building', name: 'skyscraperB', rotation: -Math.PI / 2 },
        { gx: 19, gz: 12, type: 'building', name: 'e', rotation: -Math.PI / 2 },
        { gx: 20, gz: 12, type: 'building', name: 'f', rotation: -Math.PI / 2 },
        { gx: 15, gz: 13, type: 'building', name: 'g', rotation: -Math.PI / 2 },
        { gx: 16, gz: 13, type: 'building', name: 'h', rotation: -Math.PI / 2 },
        { gx: 17, gz: 13, type: 'building', name: 'a', rotation: -Math.PI / 2 },
        { gx: 18, gz: 13, type: 'building', name: 'b', rotation: -Math.PI / 2 },
        { gx: 19, gz: 13, type: 'building', name: 'skyscraperA', rotation: -Math.PI / 2 },
        { gx: 20, gz: 13, type: 'building', name: 'c', rotation: -Math.PI / 2 },

        { gx: 15, gz: 15, type: 'building', name: 'd', rotation: -Math.PI / 2 },
        { gx: 16, gz: 15, type: 'building', name: 'e', rotation: -Math.PI / 2 },
        { gx: 15, gz: 16, type: 'building', name: 'f', rotation: -Math.PI / 2 },
        { gx: 16, gz: 16, type: 'building', name: 'skyscraperB', rotation: -Math.PI / 2 },

        { gx: 15, gz: 18, type: 'building', name: 'g', rotation: -Math.PI / 2 },
        { gx: 16, gz: 18, type: 'building', name: 'h', rotation: -Math.PI / 2 }
        // Bottom-right corner is garden (X=17-20, Z=18-19)
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

                // Simple road types
                if (cell === 'R') {
                    roadType = 'straight';
                    rotation = 0;
                } else if (cell === 'H') {
                    roadType = 'straight';
                    rotation = Math.PI / 2;
                } else if (cell === '+') {
                    roadType = 'crossroad';
                    rotation = 0;
                }
                // T-Intersection variants
                else if (cell === 'T1') {
                    roadType = 'intersection';
                    rotation = 0;           // North blocked ┴
                } else if (cell === 'T2') {
                    roadType = 'intersection';
                    rotation = Math.PI;     // South blocked ┬
                } else if (cell === 'T3') {
                    roadType = 'intersection';
                    rotation = Math.PI / 2; // East blocked ├
                } else if (cell === 'T4') {
                    roadType = 'intersection';
                    rotation = -Math.PI / 2; // West blocked ┤
                }
                // L-Bend variants
                else if (cell === 'L1') {
                    roadType = 'bend';
                    rotation = 0;           // S+E └
                } else if (cell === 'L2') {
                    roadType = 'bend';
                    rotation = Math.PI / 2; // S+W ┘
                } else if (cell === 'L3') {
                    roadType = 'bend';
                    rotation = Math.PI;     // N+W ┐
                } else if (cell === 'L4') {
                    roadType = 'bend';
                    rotation = -Math.PI / 2; // N+E ┌
                }
                // Legacy support for old T and L
                else if (cell === 'T') {
                    roadType = 'intersection';
                    rotation = 0;
                } else if (cell === 'L') {
                    roadType = 'bend';
                    rotation = 0;
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
    // Main Park at X=15-20, Z=0-7 - A well-designed natural park with survival kit assets
    const NATURE = [
        // =============== MAIN PARK (X=15-20, Z=0-7) ===============

        // === Perimeter Trees - Northern Edge (Z=0) ===
        { gx: 15, gz: 0, type: 'park', name: 'treeTall', rotation: 0, scale: 1.2 },
        { gx: 16.5, gz: 0.3, type: 'park', name: 'tree', rotation: Math.PI / 6 },
        { gx: 18, gz: 0, type: 'park', name: 'treeAutumnTall', rotation: Math.PI / 3 },
        { gx: 19.5, gz: 0.2, type: 'park', name: 'treeTall', rotation: Math.PI / 2 },

        // === Perimeter Trees - Eastern Edge (X=20) ===
        { gx: 20, gz: 1, type: 'park', name: 'tree', rotation: -Math.PI / 4 },
        { gx: 20, gz: 3, type: 'park', name: 'treeAutumn', rotation: 0 },
        { gx: 20, gz: 5, type: 'park', name: 'treeTall', rotation: Math.PI / 5 },
        { gx: 20, gz: 7, type: 'park', name: 'tree', rotation: Math.PI / 3 },

        // === Perimeter Trees - Western Edge (X=15) ===
        { gx: 15, gz: 1.5, type: 'park', name: 'treeAutumn', rotation: Math.PI / 4 },
        { gx: 15, gz: 3.5, type: 'park', name: 'tree', rotation: -Math.PI / 6 },
        { gx: 15, gz: 5.5, type: 'park', name: 'treeTall', rotation: Math.PI / 2 },
        { gx: 15, gz: 7, type: 'park', name: 'treeAutumnTall', rotation: 0 },

        // === Central Pond Area with Rocks (X=17-19, Z=2-4) ===
        { gx: 17.5, gz: 3, type: 'park', name: 'rockFlatGrass', rotation: 0, scale: 1.5 },
        { gx: 17, gz: 2.5, type: 'park', name: 'rockA', rotation: Math.PI / 4 },
        { gx: 18.5, gz: 2.3, type: 'park', name: 'rockB', rotation: Math.PI / 2 },
        { gx: 19, gz: 3.5, type: 'park', name: 'rockC', rotation: -Math.PI / 3 },
        { gx: 17.2, gz: 4, type: 'park', name: 'rockFlat', rotation: Math.PI },
        { gx: 18.8, gz: 4.2, type: 'park', name: 'rockA', rotation: 0 },

        // === Grass Patches around pond ===
        { gx: 16.2, gz: 2, type: 'park', name: 'patchGrassLarge', rotation: 0 },
        { gx: 19.3, gz: 2, type: 'park', name: 'patchGrass', rotation: Math.PI / 3 },
        { gx: 16.5, gz: 4.5, type: 'park', name: 'grassLarge', rotation: Math.PI / 4 },
        { gx: 19, gz: 4.8, type: 'park', name: 'grass', rotation: -Math.PI / 6 },

        // === Campfire Gathering Area (X=16-18, Z=5.5-7) ===
        { gx: 17, gz: 6, type: 'park', name: 'campfirePit', rotation: 0 },
        { gx: 16.2, gz: 5.8, type: 'park', name: 'treeLog', rotation: Math.PI / 4 },
        { gx: 17.8, gz: 5.6, type: 'park', name: 'treeLogSmall', rotation: -Math.PI / 3 },
        { gx: 16.5, gz: 6.8, type: 'park', name: 'treeLogSmall', rotation: Math.PI / 2 },
        { gx: 17.5, gz: 6.5, type: 'park', name: 'bucket', rotation: 0 },

        // === Scattered Interior Trees ===
        { gx: 16.3, gz: 1.2, type: 'park', name: 'tree', rotation: Math.PI / 5 },
        { gx: 18.7, gz: 1, type: 'park', name: 'treeAutumn', rotation: -Math.PI / 4 },
        { gx: 19.2, gz: 5.5, type: 'park', name: 'tree', rotation: Math.PI / 3 },
        { gx: 16, gz: 4.8, type: 'park', name: 'treeTall', rotation: 0 },

        // === Park Entrance & Signage (near road at Z=8) ===
        { gx: 17.5, gz: 7.5, type: 'park', name: 'signpost', rotation: Math.PI },
        { gx: 16, gz: 7.3, type: 'park', name: 'grass', rotation: 0 },
        { gx: 19, gz: 7.2, type: 'park', name: 'patchGrass', rotation: Math.PI / 6 },

        // === Additional Decoration ===
        { gx: 18.3, gz: 0.8, type: 'park', name: 'rockB', rotation: Math.PI / 5 },
        { gx: 15.5, gz: 2.5, type: 'park', name: 'grass', rotation: 0 },
        { gx: 19.5, gz: 6, type: 'park', name: 'barrel', rotation: Math.PI / 4 },
        { gx: 16.8, gz: 3.2, type: 'park', name: 'patchGrass', rotation: Math.PI / 2 },

        // =============== SMALL GARDEN A (X=6-7, Z=6-7) ===============
        { gx: 6.3, gz: 6.3, type: 'park', name: 'tree', rotation: 0 },
        { gx: 7.2, gz: 6.5, type: 'park', name: 'patchGrassLarge', rotation: Math.PI / 4 },
        { gx: 6.5, gz: 7.2, type: 'park', name: 'rockFlatGrass', rotation: 0 },
        { gx: 7.5, gz: 7.5, type: 'park', name: 'grass', rotation: Math.PI / 3 },

        // =============== SMALL GARDEN B (X=0-1, Z=15-16) ===============
        { gx: 0.3, gz: 15.3, type: 'park', name: 'treeTall', rotation: Math.PI / 6 },
        { gx: 1.5, gz: 15.5, type: 'park', name: 'patchGrass', rotation: 0 },
        { gx: 0.5, gz: 16.5, type: 'park', name: 'rockA', rotation: Math.PI / 2 },
        { gx: 1.2, gz: 16.2, type: 'park', name: 'grass', rotation: -Math.PI / 4 },
        { gx: 0.8, gz: 15.8, type: 'park', name: 'signpostSingle', rotation: Math.PI },

        // =============== SMALL GARDEN C (X=17-20, Z=18-19) ===============
        { gx: 17.5, gz: 18.3, type: 'park', name: 'treeAutumn', rotation: 0 },
        { gx: 19, gz: 18.5, type: 'park', name: 'tree', rotation: Math.PI / 3 },
        { gx: 20, gz: 18.2, type: 'park', name: 'treeTall', rotation: -Math.PI / 4 },
        { gx: 18, gz: 19.3, type: 'park', name: 'patchGrassLarge', rotation: Math.PI / 6 },
        { gx: 19.5, gz: 19.5, type: 'park', name: 'rockB', rotation: 0 },
        { gx: 17.3, gz: 19, type: 'park', name: 'grass', rotation: Math.PI / 2 },
        { gx: 20, gz: 19.2, type: 'park', name: 'treeAutumnTall', rotation: Math.PI / 5 }
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
        gx: 10,
        gz: 20,  // Front road (center of 21x21 city)
        direction: 'N'
    };

    // ==================== Pathfinding Grid ====================
    function generateWalkableMap() {
        const grid = [];
        const roadTypes = ['R', 'H', '+', 'T', 'L', 'T1', 'T2', 'T3', 'T4', 'L1', 'L2', 'L3', 'L4', 'P', 'G', 'M', 'C1', 'C2', 'C3', 'C4', 'S1', 'S2', 'S3', 'S4'];

        for (let gz = 0; gz < CITY.DEPTH; gz++) {
            const row = [];
            for (let gx = 0; gx < CITY.WIDTH; gx++) {
                const cell = CITY_GRID[gz][gx];
                // Roads, parks and gardens are walkable
                const walkable = roadTypes.includes(cell);
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
                // Place ground tiles under buildings (concrete)
                if (cell === 'B' || cell === '.') {
                    tiles.push({ gx, gz, type: 'tile', name: 'low' });
                }
                // Parks and gardens get beautiful minigolf grass tiles
                else if (cell === 'P' || cell === 'G') {
                    tiles.push({ gx, gz, type: 'minigolf', name: 'open', isGround: true });
                }
                // Market floor tiles (checkered pattern)
                else if (cell === 'M') {
                    tiles.push({ gx, gz, type: 'market', name: 'floor', isGround: true });
                }
                // Minigolf corner tiles (C1-C4)
                else if (cell === 'C1') {
                    tiles.push({ gx, gz, type: 'minigolf', name: 'corner', rotation: 0, isGround: true });
                } else if (cell === 'C2') {
                    tiles.push({ gx, gz, type: 'minigolf', name: 'corner', rotation: Math.PI / 2, isGround: true });
                } else if (cell === 'C3') {
                    tiles.push({ gx, gz, type: 'minigolf', name: 'corner', rotation: Math.PI, isGround: true });
                } else if (cell === 'C4') {
                    tiles.push({ gx, gz, type: 'minigolf', name: 'corner', rotation: -Math.PI / 2, isGround: true });
                }
                // Minigolf side tiles (S1-S4)
                else if (cell === 'S1') {
                    tiles.push({ gx, gz, type: 'minigolf', name: 'side', rotation: 0, isGround: true });
                } else if (cell === 'S2') {
                    tiles.push({ gx, gz, type: 'minigolf', name: 'side', rotation: Math.PI / 2, isGround: true });
                } else if (cell === 'S3') {
                    tiles.push({ gx, gz, type: 'minigolf', name: 'side', rotation: Math.PI, isGround: true });
                } else if (cell === 'S4') {
                    tiles.push({ gx, gz, type: 'minigolf', name: 'side', rotation: -Math.PI / 2, isGround: true });
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
