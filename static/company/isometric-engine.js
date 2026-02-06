/**
 * Isometric Engine - Core coordinate system, camera, and depth sorting
 * Provides 2:1 isometric projection math and camera controls
 */
window.CompanyView = window.CompanyView || {};

(function () {
    'use strict';

    // ==================== Isometric Math ====================
    const ISO = {
        TILE_W: 64,
        TILE_H: 32,

        /** Grid coordinate to screen pixel */
        gridToScreen(gx, gy) {
            return {
                x: (gx - gy) * (this.TILE_W / 2),
                y: (gx + gy) * (this.TILE_H / 2)
            };
        },

        /** Screen pixel to grid coordinate (floating) */
        screenToGrid(sx, sy) {
            return {
                x: (sx / (this.TILE_W / 2) + sy / (this.TILE_H / 2)) / 2,
                y: (sy / (this.TILE_H / 2) - sx / (this.TILE_W / 2)) / 2
            };
        },

        /** Get the four corner points of an isometric tile at grid (gx, gy) */
        getTileCorners(gx, gy) {
            const center = this.gridToScreen(gx, gy);
            return {
                top: { x: center.x, y: center.y - this.TILE_H / 2 },
                right: { x: center.x + this.TILE_W / 2, y: center.y },
                bottom: { x: center.x, y: center.y + this.TILE_H / 2 },
                left: { x: center.x - this.TILE_W / 2, y: center.y }
            };
        },

        /** Depth sort key for isometric objects - higher = drawn later (on top) */
        depthKey(gx, gy, layer = 0) {
            return (gx + gy) * 100 + layer;
        }
    };

    // ==================== Camera ====================
    class IsometricCamera {
        constructor() {
            this.x = 0;
            this.y = 0;
            this.zoom = 1.0;
            this.targetX = 0;
            this.targetY = 0;
            this.targetZoom = 1.0;
            this.minZoom = 0.4;
            this.maxZoom = 2.5;
            this.smoothing = 0.12;
            this._dragging = false;
            this._dragStart = { x: 0, y: 0 };
            this._camStart = { x: 0, y: 0 };
        }

        /** Smoothly move camera toward target */
        update() {
            this.x += (this.targetX - this.x) * this.smoothing;
            this.y += (this.targetY - this.y) * this.smoothing;
            this.zoom += (this.targetZoom - this.zoom) * this.smoothing;
        }

        /** Apply camera transform to a PIXI container */
        applyTo(container) {
            container.x = this.x;
            container.y = this.y;
            container.scale.set(this.zoom);
        }

        /** Pan by delta pixels (in screen space) */
        pan(dx, dy) {
            this.targetX += dx;
            this.targetY += dy;
        }

        /** Zoom by factor around a screen point */
        zoomAt(factor, screenX, screenY, containerX, containerY) {
            const newZoom = Math.max(this.minZoom, Math.min(this.maxZoom, this.targetZoom * factor));
            const zoomRatio = newZoom / this.targetZoom;

            this.targetX = screenX - (screenX - containerX) * zoomRatio;
            this.targetY = screenY - (screenY - containerY) * zoomRatio;
            this.targetZoom = newZoom;
        }

        /** Center camera on a grid position within a viewport */
        centerOn(gx, gy, viewportW, viewportH) {
            const screen = ISO.gridToScreen(gx, gy);
            this.targetX = viewportW / 2 - screen.x * this.targetZoom;
            this.targetY = viewportH / 2 - screen.y * this.targetZoom;
        }

        /** Begin drag operation */
        startDrag(screenX, screenY) {
            this._dragging = true;
            this._dragStart = { x: screenX, y: screenY };
            this._camStart = { x: this.targetX, y: this.targetY };
        }

        /** Update drag */
        moveDrag(screenX, screenY) {
            if (!this._dragging) return;
            this.targetX = this._camStart.x + (screenX - this._dragStart.x);
            this.targetY = this._camStart.y + (screenY - this._dragStart.y);
        }

        /** End drag */
        endDrag() {
            this._dragging = false;
        }

        get isDragging() {
            return this._dragging;
        }
    }

    // ==================== Depth-Sorted Container ====================
    class DepthSortedContainer extends PIXI.Container {
        constructor() {
            super();
            this._needsSort = true;
        }

        /** Mark that sorting is needed */
        markDirty() {
            this._needsSort = true;
        }

        /** Sort children by their depth value (zIndex) */
        depthSort() {
            if (!this._needsSort) return;
            this.children.sort((a, b) => (a.zIndex || 0) - (b.zIndex || 0));
            this._needsSort = false;
        }
    }

    // ==================== Isometric Drawing Primitives ====================
    const IsoPrimitives = {
        /** Draw a filled isometric diamond (floor tile) */
        drawDiamond(graphics, cx, cy, w, h, color, alpha = 1) {
            graphics.beginFill(color, alpha);
            graphics.moveTo(cx, cy - h / 2);
            graphics.lineTo(cx + w / 2, cy);
            graphics.lineTo(cx, cy + h / 2);
            graphics.lineTo(cx - w / 2, cy);
            graphics.closePath();
            graphics.endFill();
        },

        /** Draw an isometric box (top + left face + right face) */
        drawBox(graphics, cx, cy, w, h, depth, topColor, leftColor, rightColor) {
            // Top face
            graphics.beginFill(topColor);
            graphics.moveTo(cx, cy - h / 2 - depth);
            graphics.lineTo(cx + w / 2, cy - depth);
            graphics.lineTo(cx, cy + h / 2 - depth);
            graphics.lineTo(cx - w / 2, cy - depth);
            graphics.closePath();
            graphics.endFill();

            // Left face
            graphics.beginFill(leftColor);
            graphics.moveTo(cx - w / 2, cy - depth);
            graphics.lineTo(cx, cy + h / 2 - depth);
            graphics.lineTo(cx, cy + h / 2);
            graphics.lineTo(cx - w / 2, cy);
            graphics.closePath();
            graphics.endFill();

            // Right face
            graphics.beginFill(rightColor);
            graphics.moveTo(cx + w / 2, cy - depth);
            graphics.lineTo(cx, cy + h / 2 - depth);
            graphics.lineTo(cx, cy + h / 2);
            graphics.lineTo(cx + w / 2, cy);
            graphics.closePath();
            graphics.endFill();
        },

        /** Draw isometric box with outline */
        drawBoxOutlined(graphics, cx, cy, w, h, depth, topColor, leftColor, rightColor, lineColor = 0x000000, lineAlpha = 0.08) {
            this.drawBox(graphics, cx, cy, w, h, depth, topColor, leftColor, rightColor);

            // Outline
            graphics.lineStyle(1, lineColor, lineAlpha);
            // Top face outline
            graphics.moveTo(cx, cy - h / 2 - depth);
            graphics.lineTo(cx + w / 2, cy - depth);
            graphics.lineTo(cx, cy + h / 2 - depth);
            graphics.lineTo(cx - w / 2, cy - depth);
            graphics.lineTo(cx, cy - h / 2 - depth);
            // Vertical edges
            graphics.moveTo(cx - w / 2, cy - depth);
            graphics.lineTo(cx - w / 2, cy);
            graphics.moveTo(cx, cy + h / 2 - depth);
            graphics.lineTo(cx, cy + h / 2);
            graphics.moveTo(cx + w / 2, cy - depth);
            graphics.lineTo(cx + w / 2, cy);
            graphics.lineStyle(0);
        },

        /** Draw a wall panel (vertical rectangle in isometric) */
        drawWallPanel(graphics, x1, y1, x2, y2, height, faceColor, edgeColor) {
            // Face
            graphics.beginFill(faceColor);
            graphics.moveTo(x1, y1 - height);
            graphics.lineTo(x2, y2 - height);
            graphics.lineTo(x2, y2);
            graphics.lineTo(x1, y1);
            graphics.closePath();
            graphics.endFill();

            // Top edge
            graphics.lineStyle(1, edgeColor, 0.3);
            graphics.moveTo(x1, y1 - height);
            graphics.lineTo(x2, y2 - height);
            graphics.lineStyle(0);
        }
    };

    // ==================== Export ====================
    window.CompanyView.ISO = ISO;
    window.CompanyView.IsometricCamera = IsometricCamera;
    window.CompanyView.DepthSortedContainer = DepthSortedContainer;
    window.CompanyView.IsoPrimitives = IsoPrimitives;

})();
