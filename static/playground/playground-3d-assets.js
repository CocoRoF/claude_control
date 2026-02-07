/**
 * City 3D Asset Loader
 * Loads GLB models from Kenney city kits
 */
(function() {
    'use strict';

    window.Playground = window.Playground || {};

    const DEBUG = true;
    function debugLog(...args) {
        if (DEBUG) console.log('[City3DAssets]', ...args);
    }

    // ==================== Asset Paths ====================
    const ASSET_BASE = '/static/assets/';
    const ASSET_PACKS = {
        commercial: ASSET_BASE + 'kenney_city-kit-commercial_2.1/Models/GLB format/',
        industrial: ASSET_BASE + 'kenney_city-kit-industrial_1.0/Models/GLB format/',
        roads: ASSET_BASE + 'kenney_city-kit-roads/Models/GLB format/',
        suburban: ASSET_BASE + 'kenney_city-kit-suburban_20/Models/GLB format/',
        characters: ASSET_BASE + 'kenney_mini-characters/Models/GLB format/'
    };

    // ==================== Asset Manifest ====================
    const ASSET_MANIFEST = {
        // Commercial buildings
        building: {
            a: { pack: 'commercial', file: 'building-a.glb' },
            b: { pack: 'commercial', file: 'building-b.glb' },
            c: { pack: 'commercial', file: 'building-c.glb' },
            d: { pack: 'commercial', file: 'building-d.glb' },
            e: { pack: 'commercial', file: 'building-e.glb' },
            f: { pack: 'commercial', file: 'building-f.glb' },
            g: { pack: 'commercial', file: 'building-g.glb' },
            h: { pack: 'commercial', file: 'building-h.glb' },
            i: { pack: 'commercial', file: 'building-i.glb' },
            j: { pack: 'commercial', file: 'building-j.glb' },
            k: { pack: 'commercial', file: 'building-k.glb' },
            l: { pack: 'commercial', file: 'building-l.glb' },
            skyscraperA: { pack: 'commercial', file: 'building-skyscraper-a.glb' },
            skyscraperB: { pack: 'commercial', file: 'building-skyscraper-b.glb' },
            skyscraperC: { pack: 'commercial', file: 'building-skyscraper-c.glb' }
        },

        // Suburban buildings
        suburban: {
            typeA: { pack: 'suburban', file: 'building-type-a.glb' },
            typeB: { pack: 'suburban', file: 'building-type-b.glb' },
            typeC: { pack: 'suburban', file: 'building-type-c.glb' },
            typeD: { pack: 'suburban', file: 'building-type-d.glb' },
            typeE: { pack: 'suburban', file: 'building-type-e.glb' },
            typeF: { pack: 'suburban', file: 'building-type-f.glb' },
            typeG: { pack: 'suburban', file: 'building-type-g.glb' },
            typeH: { pack: 'suburban', file: 'building-type-h.glb' }
        },

        // Roads
        road: {
            straight: { pack: 'roads', file: 'road-straight.glb' },
            bend: { pack: 'roads', file: 'road-bend.glb' },
            crossing: { pack: 'roads', file: 'road-crossing.glb' },
            crossroad: { pack: 'roads', file: 'road-crossroad.glb' },
            intersection: { pack: 'roads', file: 'road-intersection.glb' },
            end: { pack: 'roads', file: 'road-end.glb' }
        },

        // Road tiles (ground)
        tile: {
            high: { pack: 'roads', file: 'tile-high.glb' },
            low: { pack: 'roads', file: 'tile-low.glb' }
        },

        // Details
        detail: {
            awning: { pack: 'commercial', file: 'detail-awning.glb' },
            awningWide: { pack: 'commercial', file: 'detail-awning-wide.glb' },
            parasolA: { pack: 'commercial', file: 'detail-parasol-a.glb' },
            parasolB: { pack: 'commercial', file: 'detail-parasol-b.glb' }
        },

        // Nature
        nature: {
            treeLarge: { pack: 'suburban', file: 'tree-large.glb' },
            treeSmall: { pack: 'suburban', file: 'tree-small.glb' },
            planter: { pack: 'suburban', file: 'planter.glb' }
        },

        // Paths and driveways
        path: {
            long: { pack: 'suburban', file: 'path-long.glb' },
            short: { pack: 'suburban', file: 'path-short.glb' },
            drivewayLong: { pack: 'suburban', file: 'driveway-long.glb' },
            drivewayShort: { pack: 'suburban', file: 'driveway-short.glb' }
        }
    };

    // ==================== Asset Loader Class ====================
    class Asset3DLoader {
        constructor() {
            this.models = new Map();
            this.gltfLoader = null;
            this.ready = false;
        }

        init() {
            if (!THREE.GLTFLoader) {
                console.error('THREE.GLTFLoader not available');
                return false;
            }
            this.gltfLoader = new THREE.GLTFLoader();
            debugLog('Asset3DLoader initialized');
            return true;
        }

        async loadAll(progressCallback) {
            if (!this.gltfLoader) {
                console.error('Loader not initialized');
                return;
            }

            const assets = [];
            for (const category of Object.keys(ASSET_MANIFEST)) {
                for (const name of Object.keys(ASSET_MANIFEST[category])) {
                    const asset = ASSET_MANIFEST[category][name];
                    assets.push({
                        category,
                        name,
                        url: ASSET_PACKS[asset.pack] + asset.file
                    });
                }
            }

            const total = assets.length;
            let loaded = 0;

            debugLog(`Loading ${total} models...`);

            const loadPromises = assets.map(asset => {
                return new Promise((resolve) => {
                    this.gltfLoader.load(
                        asset.url,
                        (gltf) => {
                            const model = gltf.scene;
                            const key = `${asset.category}/${asset.name}`;
                            this.models.set(key, model);
                            loaded++;
                            if (progressCallback) progressCallback(loaded, total, asset.url);
                            resolve();
                        },
                        undefined,
                        (error) => {
                            console.warn(`Failed to load ${asset.url}:`, error.message);
                            loaded++;
                            if (progressCallback) progressCallback(loaded, total, asset.url);
                            resolve();
                        }
                    );
                });
            });

            await Promise.all(loadPromises);
            this.ready = true;
            debugLog(`All models loaded. Total: ${this.models.size}`);
        }

        async loadEssential(progressCallback) {
            if (!this.gltfLoader) {
                console.error('Loader not initialized');
                return;
            }

            // Essential models for the city
            const essentialKeys = [
                'building/a', 'building/b', 'building/c', 'building/d',
                'building/e', 'building/f', 'building/g', 'building/h',
                'building/skyscraperA', 'building/skyscraperB',
                'road/straight', 'road/bend', 'road/crossing', 'road/crossroad', 'road/intersection',
                'tile/low',
                'nature/treeLarge', 'nature/treeSmall', 'nature/planter'
            ];

            const assets = [];
            for (const key of essentialKeys) {
                const [category, name] = key.split('/');
                if (ASSET_MANIFEST[category] && ASSET_MANIFEST[category][name]) {
                    const asset = ASSET_MANIFEST[category][name];
                    assets.push({
                        category,
                        name,
                        url: ASSET_PACKS[asset.pack] + asset.file
                    });
                }
            }

            const total = assets.length;
            let loaded = 0;

            debugLog(`Loading ${total} essential models...`);

            const loadPromises = assets.map(asset => {
                return new Promise((resolve) => {
                    this.gltfLoader.load(
                        asset.url,
                        (gltf) => {
                            const key = `${asset.category}/${asset.name}`;
                            this.models.set(key, gltf.scene);
                            loaded++;
                            if (progressCallback) progressCallback(loaded, total, asset.url);
                            resolve();
                        },
                        undefined,
                        (error) => {
                            console.warn(`Failed to load ${asset.url}`);
                            loaded++;
                            if (progressCallback) progressCallback(loaded, total, asset.url);
                            resolve();
                        }
                    );
                });
            });

            await Promise.all(loadPromises);
            this.ready = true;
            debugLog('Essential models loaded');
        }

        getModel(category, name) {
            const key = `${category}/${name}`;
            const template = this.models.get(key);
            if (!template) {
                return null;
            }
            return template.clone();
        }

        hasModel(category, name) {
            return this.models.has(`${category}/${name}`);
        }

        dispose() {
            for (const [key, model] of this.models) {
                model.traverse((child) => {
                    if (child.geometry) child.geometry.dispose();
                    if (child.material) {
                        if (Array.isArray(child.material)) {
                            child.material.forEach(m => m.dispose());
                        } else {
                            child.material.dispose();
                        }
                    }
                });
            }
            this.models.clear();
            this.ready = false;
        }
    }

    // Export
    window.Playground.Asset3DLoader = Asset3DLoader;
    window.Playground.ASSET_MANIFEST_3D = ASSET_MANIFEST;
    window.Playground.ASSET_PACKS = ASSET_PACKS;

    debugLog('City3DAssets module loaded');

})();
