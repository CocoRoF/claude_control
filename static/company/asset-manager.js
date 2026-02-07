/**
 * Asset Manager - Kenney Isometric Miniature 에셋 전용
 * 사용 팩: dungeon, farm, library (prototype 제외)
 * 모든 에셋: 256x512, 바닥 다이아몬드 하단 148px
 */
window.CompanyView = window.CompanyView || {};

(function () {
    'use strict';

    // ==================== 에셋 경로 정의 ====================
    const ASSET_BASE = '/static/assets/';

    const ASSET_PATHS = {
        dungeon: `${ASSET_BASE}kenney_isometric-miniature-dungeon/Isometric/`,
        farm: `${ASSET_BASE}kenney_isometric-miniature-farm/Isometric/`,
        library: `${ASSET_BASE}kenney_isometric-miniature-library/Isometric/`,
        // 캐릭터 (mini-characters 사용)
        characters: `${ASSET_BASE}kenney_mini-characters/Previews/`,
    };

    // ==================== 에셋 목록 정의 ====================
    // 방향: E, N, S, W (miniature 시리즈 표준)
    const ASSET_MANIFEST = {
        // ========== 바닥 (FLOOR) ==========
        floor: {
            // Dungeon - 돌 바닥
            stone_E: { path: 'dungeon', file: 'stone_E.png' },
            stone_S: { path: 'dungeon', file: 'stone_S.png' },
            stoneTile_E: { path: 'dungeon', file: 'stoneTile_E.png' },
            stoneTile_S: { path: 'dungeon', file: 'stoneTile_S.png' },
            stoneUneven_E: { path: 'dungeon', file: 'stoneUneven_E.png' },
            stoneMissing_E: { path: 'dungeon', file: 'stoneMissingTiles_E.png' },
            dirt_E: { path: 'dungeon', file: 'dirt_E.png' },
            dirt_S: { path: 'dungeon', file: 'dirt_S.png' },
            dirtTiles_E: { path: 'dungeon', file: 'dirtTiles_E.png' },
            planks_E: { path: 'dungeon', file: 'planks_E.png' },
            planks_S: { path: 'dungeon', file: 'planks_S.png' },
            planksBroken_E: { path: 'dungeon', file: 'planksBroken_E.png' },
            planksHole_E: { path: 'dungeon', file: 'planksHole_E.png' },
            // Farm - 나무 바닥
            farmPlanks_E: { path: 'farm', file: 'planks_E.png' },
            farmPlanks_S: { path: 'farm', file: 'planks_S.png' },
            farmPlanksOld_E: { path: 'farm', file: 'planksOld_E.png' },
            farmDirt_E: { path: 'farm', file: 'dirt_E.png' },
            // Library - 카펫
            carpet_E: { path: 'library', file: 'floorCarpet_E.png' },
            carpet_S: { path: 'library', file: 'floorCarpet_S.png' },
            carpetEnd_E: { path: 'library', file: 'floorCarpetEnd_E.png' },
            carpetEnd_S: { path: 'library', file: 'floorCarpetEnd_S.png' },
            carpetSmall_E: { path: 'library', file: 'floorCarpetSmall_E.png' },
            carpetSmall_S: { path: 'library', file: 'floorCarpetSmall_S.png' },
        },

        // ========== 벽 (WALL) ==========
        wall: {
            // Dungeon - 돌 벽
            stone_E: { path: 'dungeon', file: 'stoneWall_E.png' },
            stone_S: { path: 'dungeon', file: 'stoneWall_S.png' },
            stone_N: { path: 'dungeon', file: 'stoneWall_N.png' },
            stone_W: { path: 'dungeon', file: 'stoneWall_W.png' },
            stoneCorner_E: { path: 'dungeon', file: 'stoneWallCorner_E.png' },
            stoneCorner_S: { path: 'dungeon', file: 'stoneWallCorner_S.png' },
            stoneWindow_E: { path: 'dungeon', file: 'stoneWallWindow_E.png' },
            stoneWindow_S: { path: 'dungeon', file: 'stoneWallWindow_S.png' },
            stoneDoor_E: { path: 'dungeon', file: 'stoneWallDoor_E.png' },
            stoneDoor_S: { path: 'dungeon', file: 'stoneWallDoor_S.png' },
            stoneDoorOpen_E: { path: 'dungeon', file: 'stoneWallDoorOpen_E.png' },
            stoneArchway_E: { path: 'dungeon', file: 'stoneWallArchway_E.png' },
            stoneArchway_S: { path: 'dungeon', file: 'stoneWallArchway_S.png' },
            stoneHalf_E: { path: 'dungeon', file: 'stoneWallHalf_E.png' },
            stoneColumn_E: { path: 'dungeon', file: 'stoneWallColumn_E.png' },
            stoneAged_E: { path: 'dungeon', file: 'stoneWallAged_E.png' },
            stoneBroken_E: { path: 'dungeon', file: 'stoneWallBroken_E.png' },
            // Farm - 나무 벽
            wood_E: { path: 'farm', file: 'woodWall_E.png' },
            wood_S: { path: 'farm', file: 'woodWall_S.png' },
            wood_N: { path: 'farm', file: 'woodWall_N.png' },
            wood_W: { path: 'farm', file: 'woodWall_W.png' },
            woodCorner_E: { path: 'farm', file: 'woodWallCorner_E.png' },
            woodCorner_S: { path: 'farm', file: 'woodWallCorner_S.png' },
            woodWindow_E: { path: 'farm', file: 'woodWallWindow_E.png' },
            woodWindow_S: { path: 'farm', file: 'woodWallWindow_S.png' },
            woodWindowGlass_E: { path: 'farm', file: 'woodWallWindowGlass_E.png' },
            woodDoorway_E: { path: 'farm', file: 'woodWallDoorway_E.png' },
            woodDoorway_S: { path: 'farm', file: 'woodWallDoorway_S.png' },
            woodDoorOpen_E: { path: 'farm', file: 'woodWallDoorOpen_E.png' },
            woodDoorClosed_E: { path: 'farm', file: 'woodWallDoorClosed_E.png' },
            woodEmpty_E: { path: 'farm', file: 'woodWallEmpty_E.png' },
            woodSupport_E: { path: 'farm', file: 'woodWallSupport_E.png' },
            // Library - 책장 벽
            books_E: { path: 'library', file: 'wallBooks_E.png' },
            books_S: { path: 'library', file: 'wallBooks_S.png' },
            books_N: { path: 'library', file: 'wallBooks_N.png' },
            books_W: { path: 'library', file: 'wallBooks_W.png' },
            doorway_E: { path: 'library', file: 'wallDoorway_E.png' },
            doorway_S: { path: 'library', file: 'wallDoorway_S.png' },
        },

        // ========== 책장 (BOOKCASE) - Library ==========
        bookcase: {
            books_E: { path: 'library', file: 'bookcaseBooks_E.png' },
            books_S: { path: 'library', file: 'bookcaseBooks_S.png' },
            books_N: { path: 'library', file: 'bookcaseBooks_N.png' },
            books_W: { path: 'library', file: 'bookcaseBooks_W.png' },
            booksLadder_E: { path: 'library', file: 'bookcaseBooksLadder_E.png' },
            booksLadder_S: { path: 'library', file: 'bookcaseBooksLadder_S.png' },
            empty_E: { path: 'library', file: 'bookcaseEmpty_E.png' },
            empty_S: { path: 'library', file: 'bookcaseEmpty_S.png' },
            glass_E: { path: 'library', file: 'bookcaseGlass_E.png' },
            glass_S: { path: 'library', file: 'bookcaseGlass_S.png' },
            half_E: { path: 'library', file: 'bookcaseHalfBooks_E.png' },
            half_S: { path: 'library', file: 'bookcaseHalfBooks_S.png' },
            wide_E: { path: 'library', file: 'bookcaseWideBooks_E.png' },
            wide_S: { path: 'library', file: 'bookcaseWideBooks_S.png' },
            wideDesk_E: { path: 'library', file: 'bookcaseWideBooksDesk_E.png' },
            wideDesk_S: { path: 'library', file: 'bookcaseWideBooksDesk_S.png' },
            wideLadder_E: { path: 'library', file: 'bookcaseWideBooksLadder_E.png' },
            destroyed_E: { path: 'library', file: 'bookcaseDestroyed_E.png' },
            fallen_E: { path: 'library', file: 'bookcaseFallen_E.png' },
        },

        // ========== 테이블 (TABLE) ==========
        table: {
            // Library - 긴 테이블
            long_E: { path: 'library', file: 'longTable_E.png' },
            long_S: { path: 'library', file: 'longTable_S.png' },
            long_N: { path: 'library', file: 'longTable_N.png' },
            long_W: { path: 'library', file: 'longTable_W.png' },
            longChairs_E: { path: 'library', file: 'longTableChairs_E.png' },
            longChairs_S: { path: 'library', file: 'longTableChairs_S.png' },
            longDecorated_E: { path: 'library', file: 'longTableDecorated_E.png' },
            longDecorated_S: { path: 'library', file: 'longTableDecorated_S.png' },
            longDecoratedChairs_E: { path: 'library', file: 'longTableDecoratedChairs_E.png' },
            longDecoratedChairs_S: { path: 'library', file: 'longTableDecoratedChairs_S.png' },
            longDecoratedChairsBooks_E: { path: 'library', file: 'longTableDecoratedChairsBooks_E.png' },
            longDecoratedChairsBooks_S: { path: 'library', file: 'longTableDecoratedChairsBooks_S.png' },
            longLarge_E: { path: 'library', file: 'longTableLarge_E.png' },
            // Dungeon - 둥근/짧은 테이블
            round_E: { path: 'dungeon', file: 'tableRound_E.png' },
            round_S: { path: 'dungeon', file: 'tableRound_S.png' },
            roundChairs_E: { path: 'dungeon', file: 'tableRoundChairs_E.png' },
            roundChairs_S: { path: 'dungeon', file: 'tableRoundChairs_S.png' },
            roundItems_E: { path: 'dungeon', file: 'tableRoundItemsChairs_E.png' },
            short_E: { path: 'dungeon', file: 'tableShort_E.png' },
            short_S: { path: 'dungeon', file: 'tableShort_S.png' },
            shortChairs_E: { path: 'dungeon', file: 'tableShortChairs_E.png' },
        },

        // ========== 의자 (CHAIR) ==========
        chair: {
            // Library
            library_E: { path: 'library', file: 'libraryChair_E.png' },
            library_S: { path: 'library', file: 'libraryChair_S.png' },
            library_N: { path: 'library', file: 'libraryChair_N.png' },
            library_W: { path: 'library', file: 'libraryChair_W.png' },
            // Dungeon
            dungeon_E: { path: 'dungeon', file: 'chair_E.png' },
            dungeon_S: { path: 'dungeon', file: 'chair_S.png' },
            dungeon_N: { path: 'dungeon', file: 'chair_N.png' },
            dungeon_W: { path: 'dungeon', file: 'chair_W.png' },
        },

        // ========== 장식품 (DECOR) ==========
        decor: {
            // Library
            bookStand_E: { path: 'library', file: 'bookStand_E.png' },
            bookStand_S: { path: 'library', file: 'bookStand_S.png' },
            bookStandEmpty_E: { path: 'library', file: 'bookStandEmpty_E.png' },
            candleStand_E: { path: 'library', file: 'candleStand_E.png' },
            candleStand_S: { path: 'library', file: 'candleStand_S.png' },
            candleDouble_E: { path: 'library', file: 'candleStandDouble_E.png' },
            displayCase_E: { path: 'library', file: 'displayCase_E.png' },
            displayCaseBooks_E: { path: 'library', file: 'displayCaseBooks_E.png' },
            displayCaseSword_E: { path: 'library', file: 'displayCaseSword_E.png' },
            // Dungeon
            barrel_E: { path: 'dungeon', file: 'barrel_E.png' },
            barrel_S: { path: 'dungeon', file: 'barrel_S.png' },
            barrels_E: { path: 'dungeon', file: 'barrels_E.png' },
            barrelsStacked_E: { path: 'dungeon', file: 'barrelsStacked_E.png' },
            chestClosed_E: { path: 'dungeon', file: 'chestClosed_E.png' },
            chestClosed_S: { path: 'dungeon', file: 'chestClosed_S.png' },
            chestOpen_E: { path: 'dungeon', file: 'chestOpen_E.png' },
            woodenCrate_E: { path: 'dungeon', file: 'woodenCrate_E.png' },
            woodenCrates_E: { path: 'dungeon', file: 'woodenCrates_E.png' },
            woodenPile_E: { path: 'dungeon', file: 'woodenPile_E.png' },
            stoneColumn_E: { path: 'dungeon', file: 'stoneColumn_E.png' },
            // Farm
            hay_E: { path: 'farm', file: 'hay_E.png' },
            hayBales_E: { path: 'farm', file: 'hayBales_E.png' },
            hayBalesStacked_E: { path: 'farm', file: 'hayBalesStacked_E.png' },
            sack_E: { path: 'farm', file: 'sack_E.png' },
            sacksCrate_E: { path: 'farm', file: 'sacksCrate_E.png' },
            ladder_E: { path: 'farm', file: 'ladderStand_E.png' },
            fenceHigh_E: { path: 'farm', file: 'fenceHigh_E.png' },
            fenceLow_E: { path: 'farm', file: 'fenceLow_E.png' },
        },

        // ========== 계단 (STAIRS) ==========
        stairs: {
            // Dungeon
            stone_E: { path: 'dungeon', file: 'stairs_E.png' },
            stone_S: { path: 'dungeon', file: 'stairs_S.png' },
            stoneAged_E: { path: 'dungeon', file: 'stairsAged_E.png' },
            stoneCorner_E: { path: 'dungeon', file: 'stairsCorner_E.png' },
            spiral_E: { path: 'dungeon', file: 'stairsSpiral_E.png' },
        },

        // ========== 지붕 (ROOF) - Farm ==========
        roof: {
            regular_E: { path: 'farm', file: 'roof_E.png' },
            regular_S: { path: 'farm', file: 'roof_S.png' },
            corner_E: { path: 'farm', file: 'roofCorner_E.png' },
            innerCorner_E: { path: 'farm', file: 'roofInnerCorner_E.png' },
            single_E: { path: 'farm', file: 'roofSingle_E.png' },
            singleWall_E: { path: 'farm', file: 'roofSingleWall_E.png' },
        },

        // ========== 구조물 (STRUCTURE) ==========
        structure: {
            // Dungeon - 지지대
            woodenSupports_E: { path: 'dungeon', file: 'woodenSupports_E.png' },
            woodenSupportsBeam_E: { path: 'dungeon', file: 'woodenSupportsBeam_E.png' },
            woodenSupportBeams_E: { path: 'dungeon', file: 'woodenSupportBeams_E.png' },
            bridge_E: { path: 'dungeon', file: 'bridge_E.png' },
            bridgeBroken_E: { path: 'dungeon', file: 'bridgeBroken_E.png' },
            // Farm - 굴뚝
            chimneyBase_E: { path: 'farm', file: 'chimneyBase_E.png' },
            chimneyTop_E: { path: 'farm', file: 'chimneyTop_E.png' },
        },
    };

    // ==================== 캐릭터 에셋 ====================
    // kenney_mini-characters: 12 캐릭터 (female-a~f, male-a~f)
    const CHARACTER_LIST = [
        'character-female-a', 'character-female-b', 'character-female-c',
        'character-female-d', 'character-female-e', 'character-female-f',
        'character-male-a', 'character-male-b', 'character-male-c',
        'character-male-d', 'character-male-e', 'character-male-f',
    ];
    const CHARACTER_VARIANTS = CHARACTER_LIST.length;
    const CHARACTER_ANIMATIONS = {
        idle: { prefix: '', frames: 1 },  // 정적 이미지 (애니메이션 없음)
    };

    // ==================== Asset Manager Class ====================
    class AssetManager {
        constructor() {
            this.textures = new Map();
            this.loaded = false;
            this.loadProgress = 0;
            this.onProgress = null;
        }

        /**
         * 모든 에셋 로딩
         * @param {Function} onProgress - 진행률 콜백 (0-1)
         */
        async loadAll(onProgress) {
            this.onProgress = onProgress;

            const allAssets = [];

            // 일반 에셋 수집
            for (const [category, items] of Object.entries(ASSET_MANIFEST)) {
                for (const [name, config] of Object.entries(items)) {
                    const fullPath = ASSET_PATHS[config.path] + config.file;
                    allAssets.push({
                        key: `${category}/${name}`,
                        path: fullPath
                    });
                }
            }

            // 캐릭터 에셋 수집 (mini-characters)
            for (let variant = 0; variant < CHARACTER_VARIANTS; variant++) {
                const characterName = CHARACTER_LIST[variant];
                const fileName = `${characterName}.png`;
                const fullPath = ASSET_PATHS.characters + fileName;
                allAssets.push({
                    key: `character/${variant}/idle/0`,
                    path: fullPath
                });
            }

            console.log(`[AssetManager] Loading ${allAssets.length} assets...`);

            let loadedCount = 0;
            const totalCount = allAssets.length;

            const loadPromises = allAssets.map(async (asset) => {
                try {
                    const cached = PIXI.Assets.cache.get(asset.path);
                    if (cached) {
                        this.textures.set(asset.key, cached);
                    } else {
                        const texture = await PIXI.Assets.load(asset.path);
                        this.textures.set(asset.key, texture);
                    }
                } catch (err) {
                    // 로드 실패 - 조용히 진행
                }
                loadedCount++;
                this.loadProgress = loadedCount / totalCount;
                if (this.onProgress) {
                    this.onProgress(this.loadProgress);
                }
            });

            await Promise.all(loadPromises);

            this.loaded = true;
            console.log(`[AssetManager] Loaded ${this.textures.size}/${totalCount} assets`);

            return this;
        }

        /**
         * 텍스처 가져오기
         */
        getTexture(category, name) {
            const key = `${category}/${name}`;
            return this.textures.get(key) || null;
        }

        /**
         * 스프라이트 생성
         * 앵커: (0.5, 1.0) - 이미지 하단 중앙 (miniature 표준)
         */
        createSprite(category, name) {
            const texture = this.getTexture(category, name);
            if (!texture) {
                console.warn(`[AssetManager] Texture not found: ${category}/${name}`);
                return null;
            }
            const sprite = new PIXI.Sprite(texture);
            sprite.anchor.set(0.5, 1.0);
            return sprite;
        }

        /**
         * 캐릭터 텍스처 가져오기
         */
        getCharacterTexture(variant, animation, frame = 0) {
            const key = `character/${variant}/${animation}/${frame}`;
            return this.textures.get(key) || null;
        }

        /**
         * 캐릭터 스프라이트 생성
         */
        createCharacterSprite(variant, animation = 'idle', frame = 0) {
            const texture = this.getCharacterTexture(variant, animation, frame);
            if (!texture) {
                return null;
            }
            const sprite = new PIXI.Sprite(texture);
            sprite.anchor.set(0.5, 1.0);
            return sprite;
        }

        /**
         * 캐릭터 애니메이션 프레임 배열
         */
        getCharacterFrames(variant, animation) {
            const frames = [];
            const animConfig = CHARACTER_ANIMATIONS[animation];
            if (!animConfig) return frames;

            for (let i = 0; i < animConfig.frames; i++) {
                const texture = this.getCharacterTexture(variant, animation, i);
                if (texture) {
                    frames.push(texture);
                }
            }
            return frames;
        }
    }

    // ==================== 싱글톤 인스턴스 ====================
    const assetManager = new AssetManager();

    // Export
    window.CompanyView.AssetManager = assetManager;
    window.CompanyView.ASSET_PATHS = ASSET_PATHS;
    window.CompanyView.ASSET_MANIFEST = ASSET_MANIFEST;
    window.CompanyView.CHARACTER_LIST = CHARACTER_LIST;
    window.CompanyView.CHARACTER_VARIANTS = CHARACTER_VARIANTS;
    window.CompanyView.CHARACTER_ANIMATIONS = CHARACTER_ANIMATIONS;

})();
