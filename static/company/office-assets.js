/**
 * Office Assets - Kenney Isometric Miniature 기반 렌더링
 * dungeon, farm, library 에셋만 사용
 * 모든 스프라이트: 256x512, 앵커 (0.5, 1.0)
 */
window.CompanyView = window.CompanyView || {};

(function () {
    'use strict';

    // ==================== 바닥 타일 생성 ====================
    /**
     * 바닥 타일 스프라이트 생성
     * @param {number} gx - 그리드 X
     * @param {number} gy - 그리드 Y
     * @param {string} floorType - 'stone', 'planks', 'dirt', 'carpet'
     * @returns {PIXI.Sprite|PIXI.Graphics}
     */
    function createFloorTile(gx, gy, floorType = 'stone') {
        const AssetManager = window.CompanyView.AssetManager;
        const ISO = window.CompanyView.ISO;

        let sprite = null;

        // 바닥 타입에 따른 에셋 선택
        switch (floorType) {
            case 'carpet':
                sprite = AssetManager.createSprite('floor', 'carpet_S');
                break;
            case 'planks':
                sprite = AssetManager.createSprite('floor', 'planks_E');
                break;
            case 'dirt':
                sprite = AssetManager.createSprite('floor', 'dirt_E');
                break;
            case 'stoneTile':
                sprite = AssetManager.createSprite('floor', 'stoneTile_E');
                break;
            case 'stone':
            default:
                sprite = AssetManager.createSprite('floor', 'stone_E');
                break;
        }

        if (sprite) {
            // 앵커는 AssetManager에서 (0.5, 1.0)으로 설정됨
            return sprite;
        }

        // 폴백: Graphics로 그리기
        return createFloorTileFallback(gx, gy, floorType);
    }

    /**
     * 폴백용 Graphics 바닥 타일
     */
    function createFloorTileFallback(gx, gy, floorType) {
        const ISO = window.CompanyView.ISO;
        const g = new PIXI.Graphics();

        // 타입별 색상
        const colors = {
            stone: 0x808080,
            stoneTile: 0x909090,
            planks: 0x8B4513,
            dirt: 0x654321,
            carpet: 0x8B0000,
        };
        const color = colors[floorType] || colors.stone;

        // 아이소메트릭 다이아몬드 (하단 기준)
        g.beginFill(color);
        g.moveTo(0, -ISO.TILE_H);           // 상단
        g.lineTo(ISO.TILE_W / 2, -ISO.TILE_H / 2);  // 우측
        g.lineTo(0, 0);                      // 하단
        g.lineTo(-ISO.TILE_W / 2, -ISO.TILE_H / 2); // 좌측
        g.closePath();
        g.endFill();

        // 미세한 테두리
        g.lineStyle(1, 0x000000, 0.1);
        g.moveTo(0, -ISO.TILE_H);
        g.lineTo(ISO.TILE_W / 2, -ISO.TILE_H / 2);
        g.lineTo(0, 0);
        g.lineTo(-ISO.TILE_W / 2, -ISO.TILE_H / 2);
        g.closePath();

        return g;
    }

    // ==================== 벽 세그먼트 생성 ====================
    /**
     * 벽 스프라이트 생성
     * @param {string} wallStyle - 'stone', 'wood', 'books'
     * @param {string} wallType - 'straight', 'window', 'door', 'corner', 'archway'
     * @param {string} direction - E, S, N, W
     * @returns {PIXI.Sprite|PIXI.Graphics}
     */
    function createWallSegment(wallStyle, wallType, direction) {
        const AssetManager = window.CompanyView.AssetManager;

        let assetKey;

        // 벽 스타일별 에셋 키 생성
        if (wallStyle === 'stone') {
            switch (wallType) {
                case 'corner':
                    assetKey = `stoneCorner_${direction}`;
                    break;
                case 'window':
                    assetKey = `stoneWindow_${direction}`;
                    break;
                case 'door':
                    assetKey = `stoneDoor_${direction}`;
                    break;
                case 'archway':
                    assetKey = `stoneArchway_${direction}`;
                    break;
                default:
                    assetKey = `stone_${direction}`;
            }
        } else if (wallStyle === 'wood') {
            switch (wallType) {
                case 'corner':
                    assetKey = `woodCorner_${direction}`;
                    break;
                case 'window':
                    assetKey = `woodWindow_${direction}`;
                    break;
                case 'door':
                    assetKey = `woodDoorway_${direction}`;
                    break;
                default:
                    assetKey = `wood_${direction}`;
            }
        } else if (wallStyle === 'books') {
            switch (wallType) {
                case 'door':
                    assetKey = `doorway_${direction}`;
                    break;
                default:
                    assetKey = `books_${direction}`;
            }
        } else {
            assetKey = `stone_${direction}`;
        }

        const sprite = AssetManager.createSprite('wall', assetKey);

        if (sprite) {
            return sprite;
        }

        // 폴백
        return createWallSegmentFallback(wallStyle, direction);
    }

    /**
     * 폴백용 Graphics 벽
     */
    function createWallSegmentFallback(wallStyle, direction) {
        const ISO = window.CompanyView.ISO;
        const g = new PIXI.Graphics();

        const wallHeight = 200;
        const wallColors = {
            stone: 0x666666,
            wood: 0x8B4513,
            books: 0x4a3728,
        };
        const wallColor = wallColors[wallStyle] || wallColors.stone;

        const isEast = direction === 'E' || direction === 'N';

        // 벽 면
        g.beginFill(wallColor);
        if (isEast) {
            // E/N 방향 벽 (왼쪽으로 기울어짐)
            g.moveTo(0, -wallHeight - ISO.TILE_H / 2);          // 좌상단
            g.lineTo(ISO.TILE_W / 2, -wallHeight);               // 우상단
            g.lineTo(ISO.TILE_W / 2, 0);                         // 우하단
            g.lineTo(0, -ISO.TILE_H / 2);                        // 좌하단
        } else {
            // S/W 방향 벽 (오른쪽으로 기울어짐)
            g.moveTo(-ISO.TILE_W / 2, -wallHeight);              // 좌상단
            g.lineTo(0, -wallHeight - ISO.TILE_H / 2);           // 우상단
            g.lineTo(0, -ISO.TILE_H / 2);                        // 우하단
            g.lineTo(-ISO.TILE_W / 2, 0);                        // 좌하단
        }
        g.closePath();
        g.endFill();

        return g;
    }

    // ==================== 가구 생성 ====================
    /**
     * 범용 가구 스프라이트 생성
     * @param {string} category - bookcase, table, chair, decor 등
     * @param {string} assetKey - 에셋 키 (books_E, long_S 등)
     * @returns {PIXI.Sprite|null}
     */
    function createFurniture(category, assetKey) {
        const AssetManager = window.CompanyView.AssetManager;
        return AssetManager.createSprite(category, assetKey);
    }

    // ==================== 특화 가구 팩토리 ====================

    function createBookcase(assetKey) {
        return createFurniture('bookcase', assetKey);
    }

    function createTable(assetKey) {
        return createFurniture('table', assetKey);
    }

    function createChair(assetKey) {
        return createFurniture('chair', assetKey);
    }

    function createDecor(assetKey) {
        return createFurniture('decor', assetKey);
    }

    function createStairs(assetKey) {
        return createFurniture('stairs', assetKey);
    }

    function createStructure(assetKey) {
        return createFurniture('structure', assetKey);
    }

    // ==================== 통합 가구 팩토리 ====================
    /**
     * 레이아웃 데이터 기반 가구 생성
     * @param {object} data - { type, asset, gridX, gridY, ... }
     * @returns {PIXI.Sprite|null}
     */
    function createFurnitureFromLayout(data) {
        const { type, asset } = data;

        switch (type) {
            case 'bookcase':
                return createBookcase(asset);
            case 'table':
            case 'longTable':
            case 'roundTable':
            case 'shortTable':
                return createTable(asset);
            case 'chair':
                return createChair(asset);
            case 'decor':
                return createDecor(asset);
            case 'stairs':
                return createStairs(asset);
            case 'structure':
                return createStructure(asset);
            default:
                console.warn(`Unknown furniture type: ${type}`);
                return null;
        }
    }

    // ==================== Export ====================
    window.CompanyView.Assets = {
        createFloorTile,
        createFloorTileFallback,
        createWallSegment,
        createWallSegmentFallback,
        createFurniture,
        createBookcase,
        createTable,
        createChair,
        createDecor,
        createStairs,
        createStructure,
        createFurnitureFromLayout,
    };

})();
