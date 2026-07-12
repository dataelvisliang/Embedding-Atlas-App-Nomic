/* DuckDB rows and LLM tool payloads are runtime-shaped at this browser boundary. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { Coordinator } from '@uwdata/mosaic-core';
export { TOOL_DEFINITIONS } from './toolDefinitions';

export interface ToolCall {
    id: string;
    type: 'function';
    function: { name: string; arguments: string };
}

export interface ToolResult {
    name: string;
    call_id: string;
    result: any;
    error?: string;
}

interface SearchFilters {
    terms?: string[];
    term_mode?: 'AND' | 'OR';
    countries?: string[];
    varieties?: string[];
    min_points?: number;
    max_points?: number;
    min_price?: number;
    max_price?: number;
}

interface RegionProbe {
    id?: string;
    center_x: number;
    center_y: number;
    radius: number;
}

const quote = (value: unknown) => `'${String(value).replace(/'/g, "''")}'`;
const finite = (value: unknown, fallback: number) => Number.isFinite(Number(value)) ? Number(value) : fallback;
const clamp = (value: unknown, fallback: number, min: number, max: number) => Math.min(max, Math.max(min, finite(value, fallback)));

function filterClause(filters: SearchFilters = {}): string {
    const conditions: string[] = [];
    const terms = Array.isArray(filters.terms) ? filters.terms.map(String).map(t => t.trim()).filter(Boolean).slice(0, 10) : [];
    if (terms.length) {
        const termConditions = terms.map(term => `description ILIKE ${quote(`%${term}%`)}`);
        conditions.push(`(${termConditions.join(filters.term_mode === 'OR' ? ' OR ' : ' AND ')})`);
    }
    if (filters.countries?.length) conditions.push(`country IN (${filters.countries.slice(0, 20).map(quote).join(',')})`);
    if (filters.varieties?.length) conditions.push(`variety IN (${filters.varieties.slice(0, 20).map(quote).join(',')})`);
    if (Number.isFinite(filters.min_points)) conditions.push(`points >= ${Number(filters.min_points)}`);
    if (Number.isFinite(filters.max_points)) conditions.push(`points <= ${Number(filters.max_points)}`);
    if (Number.isFinite(filters.min_price)) conditions.push(`price >= ${Number(filters.min_price)}`);
    if (Number.isFinite(filters.max_price)) conditions.push(`price <= ${Number(filters.max_price)}`);
    return conditions.length ? ` WHERE ${conditions.join(' AND ')}` : '';
}

function circlePredicate(region: RegionProbe): string {
    const x = finite(region.center_x, 0);
    const y = finite(region.center_y, 0);
    const radius = clamp(region.radius, 1, 0.0001, 100000);
    return `(projection_x - ${x}) * (projection_x - ${x}) + (projection_y - ${y}) * (projection_y - ${y}) <= ${radius * radius}`;
}

function normalizeRows(rows: any[]): any[] {
    return rows.map(row => Object.fromEntries(Object.entries(row).map(([key, value]) =>
        [key, typeof value === 'bigint' ? Number(value) : value]
    )));
}

/** Browser-side implementation backed by DuckDB-WASM. */
export class ToolExecutor {
    private coordinator: Coordinator;

    constructor(coordinator: Coordinator) {
        this.coordinator = coordinator;
    }

    async execute(toolCall: ToolCall): Promise<ToolResult> {
        const { name, arguments: rawArguments } = toolCall.function;
        let args: any;
        try {
            args = JSON.parse(rawArguments || '{}');
        } catch {
            return { name, call_id: toolCall.id, result: null, error: `Invalid JSON arguments: ${rawArguments}` };
        }

        try {
            switch (name) {
                case 'search_reviews': return await this.searchReviews(toolCall.id, args);
                case 'scan_regions': return await this.scanRegions(toolCall.id, args);
                case 'inspect_regions': return await this.inspectRegions(toolCall.id, args.regions, args.intent, args.sample_size);
                case 'refine_region': return await this.refineRegion(toolCall.id, args);
                case 'compare_regions': return await this.compareRegions(toolCall.id, args.regions);
                case 'save_results': return this.saveResults(toolCall.id, args.review_ids, args.category);
                default: return { name, call_id: toolCall.id, result: null, error: `Unknown tool: ${name}` };
            }
        } catch (error) {
            return { name, call_id: toolCall.id, result: null, error: error instanceof Error ? error.message : 'Tool execution failed' };
        }
    }

    private async query(sql: string): Promise<any[]> {
        const result = await this.coordinator.query(sql);
        return normalizeRows(result.toArray());
    }

    private async searchReviews(callId: string, args: SearchFilters & { limit?: number }): Promise<ToolResult> {
        const limit = Math.floor(clamp(args.limit, 15, 1, 50));
        const where = filterClause(args);
        const rows = await this.query(`
            SELECT __row_index__, points, description, title, price, variety, country, projection_x, projection_y
            FROM reviews${where}
            ORDER BY points DESC NULLS LAST
            LIMIT ${limit}
        `);
        const countRows = await this.query(`SELECT COUNT(*) AS total FROM reviews${where}`);
        return {
            name: 'search_reviews', call_id: callId,
            result: {
                total_matches: Number(countRows[0]?.total || 0),
                matches_returned: rows.length,
                reviews: rows.map(row => ({
                    id: row.__row_index__, points: row.points, title: row.title, price: row.price,
                    variety: row.variety, country: row.country,
                    projection_x: row.projection_x, projection_y: row.projection_y,
                    excerpt: row.description?.length > 300 ? `${row.description.slice(0, 300)}...` : row.description
                }))
            }
        };
    }

    private async scanRegions(callId: string, args: SearchFilters & { grid_size?: number; top_k?: number }): Promise<ToolResult> {
        const gridSize = clamp(args.grid_size, 1, 0.05, 1000);
        const topK = Math.floor(clamp(args.top_k, 12, 1, 30));
        const rows = await this.query(`
            SELECT FLOOR(projection_x / ${gridSize}) AS bin_x,
                   FLOOR(projection_y / ${gridSize}) AS bin_y,
                   COUNT(*) AS density,
                   AVG(points) AS avg_points,
                   AVG(price) AS avg_price
            FROM reviews${filterClause(args)}
            GROUP BY bin_x, bin_y
            ORDER BY density DESC
            LIMIT ${topK}
        `);
        const regions = rows.map((row, index) => ({
            id: `scan-${index + 1}`,
            center_x: (Number(row.bin_x) + 0.5) * gridSize,
            center_y: (Number(row.bin_y) + 0.5) * gridSize,
            suggested_radius: gridSize * Math.SQRT1_2,
            grid_size: gridSize,
            density: Number(row.density),
            avg_points: row.avg_points == null ? null : Number(row.avg_points).toFixed(1),
            avg_price: row.avg_price == null ? null : Number(row.avg_price).toFixed(2)
        }));
        return { name: 'scan_regions', call_id: callId, result: { strategy: 'coarse_grid_scan', regions } };
    }

    private async inspectRegions(callId: string, regions: RegionProbe[], intentValue: unknown, sampleSizeValue?: number): Promise<ToolResult> {
        if (!Array.isArray(regions) || regions.length === 0) throw new Error('regions must contain at least one circular probe');
        const probes = regions.slice(0, 8);
        const sampleSize = Math.floor(clamp(sampleSizeValue, 12, 3, 50));
        const intent = String(intentValue || 'Open-ended wine theme discovery').trim().slice(0, 500);
        const analyses = await Promise.all(probes.map((region, index) => this.inspectOneRegion(region, index, sampleSize, intent)));
        return { name: 'inspect_regions', call_id: callId, result: { strategy: 'parallel_circular_probes', intent, regions: analyses } };
    }

    private async inspectOneRegion(region: RegionProbe, index: number, sampleSize: number, intent: string): Promise<any> {
        const probe = {
            id: region.id || `probe-${index + 1}`,
            center_x: finite(region.center_x, 0),
            center_y: finite(region.center_y, 0),
            radius: clamp(region.radius, 1, 0.0001, 100000)
        };
        const predicate = circlePredicate(probe);
        const countRows = await this.query(`SELECT COUNT(*) AS density FROM reviews WHERE ${predicate}`);
        const rows = await this.query(`
            SELECT __row_index__, points, description, title, price, variety, country, projection_x, projection_y, neighbors
            FROM reviews WHERE ${predicate}
            ORDER BY RANDOM() LIMIT ${sampleSize}
        `);
        const reviews = rows.map(row => ({
            id: row.__row_index__, points: row.points, title: row.title, price: row.price,
            variety: row.variety, country: row.country, text: row.description,
            projection_x: row.projection_x, projection_y: row.projection_y, neighbors: row.neighbors
        }));
        if (!reviews.length) return {
            ...probe, intent, density: 0, category: 'Empty region', themes: [], review_ids: [], reviews: [],
            purity: 0, purity_rationale: 'The circle contains no sampled reviews.',
            intent_match: 0, intent_match_rationale: 'No evidence is available to match the requested intent.'
        };

        const projectionAgreement = await this.projectionAgreement(reviews, probe);
        const response = await fetch('/api/analyzer', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ region: probe, intent, reviews })
        });
        if (!response.ok) throw new Error(`Analyzer API returned ${response.status}: ${await response.text()}`);
        const analysis = await response.json();
        return {
            ...analysis, ...probe, intent, density: Number(countRows[0]?.density || 0),
            sample_size: reviews.length,
            projection_agreement: projectionAgreement,
            projection_agreement_note: 'Share of sampled high-dimensional neighbors that also fall inside this 2D circle; diagnostic only.',
            reviews
        };
    }

    private async projectionAgreement(reviews: any[], region: RegionProbe): Promise<number | null> {
        const neighborIds = new Set<number>();
        for (const review of reviews) {
            let neighbors = review.neighbors;
            if (typeof neighbors === 'string') {
                try { neighbors = JSON.parse(neighbors); } catch { continue; }
            }
            const ids = Array.isArray(neighbors?.ids) ? neighbors.ids : [];
            ids.slice(1, 11).forEach((id: unknown) => { if (Number.isFinite(Number(id))) neighborIds.add(Number(id)); });
        }
        if (!neighborIds.size) return null;
        const ids = [...neighborIds].slice(0, 300);
        const coordinates = await this.query(`
            SELECT __row_index__, projection_x, projection_y FROM reviews
            WHERE __row_index__ IN (${ids.join(',')})
        `);
        if (!coordinates.length) return null;
        const x = finite(region.center_x, 0), y = finite(region.center_y, 0), r2 = region.radius * region.radius;
        const inside = coordinates.filter(row => {
            const dx = Number(row.projection_x) - x, dy = Number(row.projection_y) - y;
            return dx * dx + dy * dy <= r2;
        }).length;
        return Math.round((inside / coordinates.length) * 1000) / 1000;
    }

    private async refineRegion(callId: string, args: RegionProbe & { parent_id?: string; objective?: string; subdivisions?: number; top_k?: number }): Promise<ToolResult> {
        const parent: RegionProbe = {
            center_x: finite(args.center_x, 0), center_y: finite(args.center_y, 0),
            radius: clamp(args.radius, 1, 0.0001, 100000)
        };
        const objective = ['maximize_purity', 'maximize_intent_match', 'find_distinct_subthemes'].includes(String(args.objective))
            ? String(args.objective)
            : 'maximize_purity';
        const subdivisions = Math.floor(clamp(args.subdivisions, 4, 2, 10));
        const topK = Math.floor(clamp(args.top_k, 6, 1, 12));
        const cellSize = (parent.radius * 2) / subdivisions;
        const originX = parent.center_x - parent.radius;
        const originY = parent.center_y - parent.radius;
        const rows = await this.query(`
            SELECT FLOOR((projection_x - ${originX}) / ${cellSize}) AS cell_x,
                   FLOOR((projection_y - ${originY}) / ${cellSize}) AS cell_y,
                   COUNT(*) AS density, AVG(points) AS avg_points, AVG(price) AS avg_price,
                   COUNT(DISTINCT variety) AS variety_count, COUNT(DISTINCT country) AS country_count
            FROM reviews
            WHERE ${circlePredicate(parent)}
            GROUP BY cell_x, cell_y ORDER BY density DESC LIMIT ${topK}
        `);
        const children = await Promise.all(rows.map(async (row, index) => {
            const child = {
                id: `${args.parent_id || args.id || 'refined'}-${index + 1}`,
                center_x: originX + (Number(row.cell_x) + 0.5) * cellSize,
                center_y: originY + (Number(row.cell_y) + 0.5) * cellSize,
                radius: cellSize * Math.SQRT1_2,
                suggested_radius: cellSize * Math.SQRT1_2
            };
            const predicate = circlePredicate(child);
            const dominantVarieties = await this.query(`
                SELECT variety, COUNT(*) AS count FROM reviews
                WHERE ${predicate} AND variety IS NOT NULL
                GROUP BY variety ORDER BY count DESC LIMIT 4
            `);
            const dominantCountries = await this.query(`
                SELECT country, COUNT(*) AS count FROM reviews
                WHERE ${predicate} AND country IS NOT NULL
                GROUP BY country ORDER BY count DESC LIMIT 4
            `);
            return {
                ...child,
                objective,
                parent_overlap: 1,
                density: Number(row.density),
                avg_points: row.avg_points == null ? null : Number(row.avg_points).toFixed(1),
                avg_price: row.avg_price == null ? null : Number(row.avg_price).toFixed(2),
                variety_count: Number(row.variety_count || 0),
                country_count: Number(row.country_count || 0),
                dominant_varieties: dominantVarieties,
                dominant_countries: dominantCountries
            };
        }));
        return { name: 'refine_region', call_id: callId, result: { parent, objective, strategy: 'projection_guided_purification', children } };
    }

    private async compareRegions(callId: string, regions: RegionProbe[]): Promise<ToolResult> {
        if (!Array.isArray(regions) || regions.length < 2) throw new Error('compare_regions requires at least two regions');
        const comparisons = await Promise.all(regions.slice(0, 6).map(async (region, index) => {
            const probe = { id: region.id || `region-${index + 1}`, center_x: finite(region.center_x, 0), center_y: finite(region.center_y, 0), radius: clamp(region.radius, 1, 0.0001, 100000) };
            const predicate = circlePredicate(probe);
            const [summary] = await this.query(`
                SELECT COUNT(*) AS density, AVG(points) AS avg_points, AVG(price) AS avg_price,
                       MIN(points) AS min_points, MAX(points) AS max_points
                FROM reviews WHERE ${predicate}
            `);
            const categories = await this.query(`
                SELECT country, variety, COUNT(*) AS count FROM reviews
                WHERE ${predicate} GROUP BY country, variety ORDER BY count DESC LIMIT 5
            `);
            return { ...probe, ...summary, dominant_country_varieties: categories };
        }));
        return { name: 'compare_regions', call_id: callId, result: { regions: comparisons } };
    }

    private saveResults(callId: string, reviewIds: number[], category: string): ToolResult {
        const ids = Array.isArray(reviewIds) ? [...new Set(reviewIds.map(Number).filter(Number.isFinite))] : [];
        if (!ids.length || !String(category || '').trim()) {
            return { name: 'save_results', call_id: callId, result: null, error: 'review_ids and category are required' };
        }
        return { name: 'save_results', call_id: callId, result: { saved: true, count: ids.length, category: String(category).trim(), review_ids: ids } };
    }
}
