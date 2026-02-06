/**
 * A* Pathfinding on isometric grid
 * Simple grid-based pathfinding for avatar movement
 */
window.CompanyView = window.CompanyView || {};

(function () {
    'use strict';

    class PathNode {
        constructor(x, y) {
            this.x = x;
            this.y = y;
            this.g = 0; // cost from start
            this.h = 0; // heuristic to end
            this.f = 0; // g + h
            this.parent = null;
            this.closed = false;
            this.opened = false;
        }
    }

    class PathfindingGrid {
        constructor(width, height) {
            this.width = width;
            this.height = height;
            this.walkable = [];

            for (let y = 0; y < height; y++) {
                this.walkable[y] = [];
                for (let x = 0; x < width; x++) {
                    this.walkable[y][x] = true;
                }
            }
        }

        setWalkable(x, y, walkable) {
            if (this.isInBounds(x, y)) {
                this.walkable[y][x] = walkable;
            }
        }

        isWalkable(x, y) {
            return this.isInBounds(x, y) && this.walkable[y][x];
        }

        isInBounds(x, y) {
            return x >= 0 && x < this.width && y >= 0 && y < this.height;
        }

        getNeighbors(node) {
            const neighbors = [];
            const dirs = [
                { x: 0, y: -1 }, { x: 1, y: 0 },
                { x: 0, y: 1 }, { x: -1, y: 0 },
                // Diagonals
                { x: 1, y: -1 }, { x: 1, y: 1 },
                { x: -1, y: 1 }, { x: -1, y: -1 }
            ];

            for (const dir of dirs) {
                const nx = node.x + dir.x;
                const ny = node.y + dir.y;
                if (this.isWalkable(nx, ny)) {
                    // For diagonal movement, check that adjacent tiles are also walkable
                    if (dir.x !== 0 && dir.y !== 0) {
                        if (!this.isWalkable(node.x + dir.x, node.y) ||
                            !this.isWalkable(node.x, node.y + dir.y)) {
                            continue;
                        }
                    }
                    neighbors.push({ x: nx, y: ny, diagonal: dir.x !== 0 && dir.y !== 0 });
                }
            }

            return neighbors;
        }
    }

    class Pathfinder {
        constructor(grid) {
            this.grid = grid;
        }

        /** Find path from (sx, sy) to (ex, ey) using A* */
        findPath(sx, sy, ex, ey) {
            if (!this.grid.isWalkable(ex, ey)) return [];
            if (sx === ex && sy === ey) return [{ x: sx, y: sy }];

            // Create node map
            const nodes = [];
            for (let y = 0; y < this.grid.height; y++) {
                nodes[y] = [];
                for (let x = 0; x < this.grid.width; x++) {
                    nodes[y][x] = new PathNode(x, y);
                }
            }

            const openList = [];
            const startNode = nodes[sy][sx];
            const endNode = nodes[ey][ex];

            startNode.g = 0;
            startNode.h = this._heuristic(sx, sy, ex, ey);
            startNode.f = startNode.h;
            startNode.opened = true;
            openList.push(startNode);

            while (openList.length > 0) {
                // Find node with lowest f
                let lowestIdx = 0;
                for (let i = 1; i < openList.length; i++) {
                    if (openList[i].f < openList[lowestIdx].f) {
                        lowestIdx = i;
                    }
                }

                const current = openList[lowestIdx];

                // Found the path
                if (current === endNode) {
                    return this._backtrace(endNode);
                }

                // Move current from open to closed
                openList.splice(lowestIdx, 1);
                current.closed = true;

                // Check neighbors
                const neighbors = this.grid.getNeighbors(current);
                for (const nb of neighbors) {
                    const neighbor = nodes[nb.y][nb.x];
                    if (neighbor.closed) continue;

                    const moveCost = nb.diagonal ? 1.414 : 1;
                    const newG = current.g + moveCost;

                    if (!neighbor.opened || newG < neighbor.g) {
                        neighbor.g = newG;
                        neighbor.h = this._heuristic(nb.x, nb.y, ex, ey);
                        neighbor.f = neighbor.g + neighbor.h;
                        neighbor.parent = current;

                        if (!neighbor.opened) {
                            neighbor.opened = true;
                            openList.push(neighbor);
                        }
                    }
                }
            }

            // No path found
            return [];
        }

        _heuristic(ax, ay, bx, by) {
            // Octile distance
            const dx = Math.abs(ax - bx);
            const dy = Math.abs(ay - by);
            return Math.max(dx, dy) + 0.414 * Math.min(dx, dy);
        }

        _backtrace(node) {
            const path = [];
            let current = node;
            while (current) {
                path.unshift({ x: current.x, y: current.y });
                current = current.parent;
            }
            return path;
        }
    }

    // ==================== Export ====================
    window.CompanyView.PathfindingGrid = PathfindingGrid;
    window.CompanyView.Pathfinder = Pathfinder;

})();
