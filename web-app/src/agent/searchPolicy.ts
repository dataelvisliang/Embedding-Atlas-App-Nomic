import type { ToolCall, ToolResult } from '../tools/toolExecutor';

interface Region {
    id?: string;
    center_x: number;
    center_y: number;
    radius: number;
}

interface PolicyLimits {
    maxToolCalls: number;
    maxScans: number;
    maxSearches: number;
    maxInspectedRegions: number;
    maxRefinements: number;
    maxComparisons: number;
    maxSavedCategories: number;
    maxNoProgressRounds: number;
    maxRefineDepthPerBranch: number;
    maxModelTokens: number;
    maxElapsedMs: number;
}

interface PolicyCounters {
    toolCalls: number;
    scans: number;
    searches: number;
    inspectedRegions: number;
    refinements: number;
    comparisons: number;
    savedCategories: number;
    modelTokens: number;
}

interface PolicyEvent {
    sequence: number;
    tool: string;
    status: 'accepted' | 'filtered' | 'blocked' | 'completed' | 'failed';
    detail?: string;
    newThemes?: string[];
    parameters?: unknown;
}

export type CandidateAction = 'accept' | 'refine' | 'resample' | 'compare' | 'explore' | 'reject';

export interface CandidateAssessment extends Region {
    id: string;
    category: string;
    themes: string[];
    purity: number;
    intent_match: number;
    novelty: number;
    coverage_gain: number;
    confidence: number;
    utility: number;
    recommended_action: CandidateAction;
    sample_size: number;
    review_ids: number[];
    sample_rounds: number;
    score_stability: number | null;
    parent_id?: string;
    refine_depth: number;
    analysis_failed: boolean;
}

export interface SearchPolicySnapshot {
    must_stop: boolean;
    stop_reason: string | null;
    objective: { target_accepted_regions: number; requires_comparison: boolean };
    remaining: PolicyCounters;
    inspected_region_count: number;
    accepted_region_count: number;
    discovered_themes: string[];
    relevant_themes: string[];
    no_progress_rounds: number;
    elapsed_ms: number;
    frontier: CandidateAssessment[];
    candidates: CandidateAssessment[];
    recent_events: PolicyEvent[];
    trajectory: PolicyEvent[];
}

export interface PolicyDecision {
    call?: ToolCall;
    blockedResult?: ToolResult;
}

const DEFAULT_LIMITS: PolicyLimits = {
    maxToolCalls: 18,
    maxScans: 2,
    maxSearches: 4,
    maxInspectedRegions: 24,
    maxRefinements: 5,
    maxComparisons: 4,
    maxSavedCategories: 8,
    maxNoProgressRounds: 2,
    maxRefineDepthPerBranch: 1,
    maxModelTokens: 80_000,
    maxElapsedMs: 120_000
};

const clamp01 = (value: unknown): number => Math.min(1, Math.max(0, Number(value) || 0));

function parseArguments(call: ToolCall): Record<string, unknown> {
    try {
        const value = JSON.parse(call.function.arguments || '{}');
        return value && typeof value === 'object' ? value as Record<string, unknown> : {};
    } catch {
        return {};
    }
}

function stableValue(value: unknown): unknown {
    if (Array.isArray(value)) return value.map(stableValue);
    if (value && typeof value === 'object') {
        return Object.fromEntries(Object.entries(value as Record<string, unknown>)
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([key, item]) => [key, stableValue(item)]));
    }
    return value;
}

function signature(value: unknown): string {
    return JSON.stringify(stableValue(value));
}

function asRegion(value: unknown): Region | null {
    if (!value || typeof value !== 'object') return null;
    const item = value as Record<string, unknown>;
    const centerX = Number(item.center_x), centerY = Number(item.center_y), radius = Number(item.radius);
    if (![centerX, centerY, radius].every(Number.isFinite) || radius <= 0) return null;
    return { id: typeof item.id === 'string' ? item.id : undefined, center_x: centerX, center_y: centerY, radius };
}

function nearlySameCircle(a: Region, b: Region): boolean {
    const centerDistance = Math.hypot(a.center_x - b.center_x, a.center_y - b.center_y);
    const scale = Math.max(Math.min(a.radius, b.radius), 1e-9);
    return centerDistance <= scale * 0.25 && Math.max(a.radius, b.radius) / scale <= 1.25;
}

function requestedResultCount(objective: string): number {
    const match = objective.match(/(?:find|show|recommend|top|compare|找|推荐|给我|比较|对比)\D{0,12}([1-8])(?!\d)\s*(?:wines?|options?|regions?|种|个|款)?/i);
    return match ? Number(match[1]) : 3;
}

function frontierAction(action: CandidateAction): boolean {
    return ['refine', 'resample', 'compare', 'explore'].includes(action);
}

export class SearchPolicy {
    private limits: PolicyLimits;
    private counters: PolicyCounters = {
        toolCalls: 0, scans: 0, searches: 0, inspectedRegions: 0,
        refinements: 0, comparisons: 0, savedCategories: 0, modelTokens: 0
    };
    private objective: { targetAcceptedRegions: number; requiresComparison: boolean };
    private visitedRegions: Region[] = [];
    private scanSignatures = new Set<string>();
    private refinementSignatures = new Set<string>();
    private comparisonSignatures = new Set<string>();
    private saveSignatures = new Set<string>();
    private discoveredThemes = new Set<string>();
    private relevantThemes = new Set<string>();
    private candidates = new Map<string, CandidateAssessment>();
    private resampledCandidates = new Set<string>();
    private noProgressRounds = 0;
    private probeRounds = 0;
    private stopReason: string | null = null;
    private events: PolicyEvent[] = [];
    private startedAt = Date.now();
    private consecutiveBlockedActions = 0;
    private savedAfterStop = false;

    constructor(limits: Partial<PolicyLimits> = {}, objective = '') {
        this.limits = { ...DEFAULT_LIMITS, ...limits };
        this.objective = {
            targetAcceptedRegions: requestedResultCount(objective),
            requiresComparison: /\b(compare|comparison|difference|different|versus|vs\.?)\b|比较|对比|差异/i.test(objective)
        };
    }

    evaluate(call: ToolCall): PolicyDecision {
        const tool = call.function.name;
        const args = parseArguments(call);
        if (this.stopReason && tool !== 'save_results') return this.block(call, `Search stopped: ${this.stopReason}`);
        if (this.counters.toolCalls >= this.limits.maxToolCalls && tool !== 'save_results') {
            this.stopReason = `tool-call budget ${this.limits.maxToolCalls} exhausted`;
            return this.block(call, this.stopReason);
        }

        switch (tool) {
            case 'scan_regions': return this.evaluateScan(call, args);
            case 'search_reviews': return this.evaluateSearch(call);
            case 'inspect_regions': return this.evaluateInspection(call, args);
            case 'refine_region': return this.evaluateRefinement(call, args);
            case 'compare_regions': return this.evaluateComparison(call, args);
            case 'save_results': return this.evaluateSave(call);
            default: return this.block(call, `Unknown or non-policy tool: ${tool}`);
        }
    }

    record(result: ToolResult): void {
        if (result.error) {
            this.addEvent(result.name, 'failed', result.error);
            return;
        }
        if (result.name !== 'inspect_regions') {
            this.addEvent(result.name, 'completed');
            return;
        }

        type ProbeResult = Region & {
            id?: string; category?: unknown; themes?: unknown[]; purity?: unknown; intent_match?: unknown;
            projection_agreement?: unknown; sample_size?: unknown; review_ids?: unknown[];
            analyzer_usage?: { total_tokens?: unknown };
            analysis_failed?: unknown;
        };
        const payload = result.result as { regions?: ProbeResult[] } | null;
        const themesBefore = new Set(this.discoveredThemes);
        const relevantBefore = new Set(this.relevantThemes);
        const newThemes = new Set<string>();
        const newRelevantThemes = new Set<string>();
        let newPromisingCandidate = false;

        for (const [index, region] of (payload?.regions || []).entries()) {
            this.recordModelUsage(region.analyzer_usage);
            const themes = [...(region.themes || []), region.category]
                .filter((value): value is string => typeof value === 'string' && Boolean(value.trim()))
                .map(value => value.trim().toLowerCase());
            const uniqueThemes = [...new Set(themes)];
            uniqueThemes.filter(theme => !themesBefore.has(theme)).forEach(theme => newThemes.add(theme));

            const id = region.id || `probe-${this.probeRounds + 1}-${index + 1}`;
            const prior = this.candidates.get(id);
            const analysisFailed = Boolean(region.analysis_failed);
            const rawPurity = analysisFailed ? 0 : clamp01(region.purity);
            const rawIntentMatch = analysisFailed ? 0 : clamp01(region.intent_match);
            const sampleRounds = (prior?.sample_rounds || 0) + 1;
            const purity = prior ? (prior.purity * prior.sample_rounds + rawPurity) / sampleRounds : rawPurity;
            const intentMatch = prior ? (prior.intent_match * prior.sample_rounds + rawIntentMatch) / sampleRounds : rawIntentMatch;
            const scoreStability = prior ? clamp01(1 - Math.max(Math.abs(prior.purity - rawPurity), Math.abs(prior.intent_match - rawIntentMatch))) : null;
            if (!analysisFailed && !prior && intentMatch >= 0.60 && intentMatch < 0.75 && uniqueThemes.some(theme => !themesBefore.has(theme))) {
                newPromisingCandidate = true;
            }
            const combinedThemes = [...new Set([...(prior?.themes || []), ...uniqueThemes])];
            if (!analysisFailed && intentMatch >= 0.75) {
                uniqueThemes.filter(theme => !relevantBefore.has(theme)).forEach(theme => newRelevantThemes.add(theme));
            }
            const novelty = uniqueThemes.length ? uniqueThemes.filter(theme => !themesBefore.has(theme)).length / uniqueThemes.length : 0;
            const coverageGain = intentMatch >= 0.75 && uniqueThemes.length
                ? uniqueThemes.filter(theme => !relevantBefore.has(theme)).length / uniqueThemes.length : 0;
            const sampleSize = Math.max(0, Number(region.sample_size) || 0);
            const agreement = Number(region.projection_agreement);
            const projectionConfidence = Number.isFinite(agreement) ? 0.5 + 0.5 * clamp01(agreement) : 0.75;
            const confidence = clamp01(Math.min(1, sampleSize / 12) * projectionConfidence);
            const rawUtility = analysisFailed ? 0 : 0.45 * intentMatch + 0.20 * purity + 0.15 * novelty + 0.10 * coverageGain + 0.10 * confidence - 0.05;
            const utility = clamp01(rawUtility);
            const recommendedAction = analysisFailed ? 'reject' : this.recommend(intentMatch, purity, sampleRounds);
            const parentId = prior?.parent_id || this.findParentId(id);
            const parent = parentId ? this.candidates.get(parentId) : undefined;
            const refineDepth = prior?.refine_depth ?? (parent ? parent.refine_depth + 1 : 0);
            this.candidates.set(id, {
                id, center_x: Number(region.center_x), center_y: Number(region.center_y), radius: Number(region.radius),
                category: typeof region.category === 'string' ? region.category : prior?.category || 'Unknown', themes: combinedThemes,
                purity: Math.round(purity * 1000) / 1000, intent_match: Math.round(intentMatch * 1000) / 1000,
                novelty: Math.round(novelty * 1000) / 1000,
                coverage_gain: Math.round(coverageGain * 1000) / 1000,
                confidence: Math.round(confidence * 1000) / 1000,
                utility: Math.round(utility * 1000) / 1000,
                recommended_action: recommendedAction, sample_size: (prior?.sample_size || 0) + sampleSize,
                review_ids: [...new Set([...(prior?.review_ids || []), ...(region.review_ids || []).map(Number).filter(Number.isFinite)])],
                sample_rounds: sampleRounds,
                score_stability: scoreStability == null ? null : Math.round(scoreStability * 1000) / 1000,
                parent_id: parentId,
                refine_depth: refineDepth,
                analysis_failed: analysisFailed
            });
        }

        newThemes.forEach(theme => this.discoveredThemes.add(theme));
        newRelevantThemes.forEach(theme => this.relevantThemes.add(theme));
        this.probeRounds++;
        this.noProgressRounds = newRelevantThemes.size || newPromisingCandidate ? 0 : this.noProgressRounds + 1;
        this.addEvent(result.name, 'completed', `${payload?.regions?.length || 0} probes; ${newRelevantThemes.size} new relevant themes`, [...newThemes]);
        this.evaluateSemanticStop();
    }

    recordModelUsage(usage?: { total_tokens?: unknown }): void {
        const tokens = Number(usage?.total_tokens);
        if (Number.isFinite(tokens) && tokens > 0) this.counters.modelTokens += tokens;
        if (this.counters.modelTokens >= this.limits.maxModelTokens) this.stopReason = `model-token budget ${this.limits.maxModelTokens} exhausted`;
    }

    snapshot(): SearchPolicySnapshot {
        const elapsedMs = Date.now() - this.startedAt;
        if (elapsedMs >= this.limits.maxElapsedMs && !this.stopReason) this.stopReason = `wall-clock budget ${this.limits.maxElapsedMs}ms exhausted`;
        const candidates = [...this.candidates.values()].sort((a, b) => b.utility - a.utility);
        const frontier = candidates.filter(candidate => frontierAction(candidate.recommended_action) && candidate.utility >= 0.40);
        return {
            must_stop: Boolean(this.stopReason),
            stop_reason: this.stopReason,
            objective: { target_accepted_regions: this.objective.targetAcceptedRegions, requires_comparison: this.objective.requiresComparison },
            remaining: {
                toolCalls: Math.max(0, this.limits.maxToolCalls - this.counters.toolCalls),
                scans: Math.max(0, this.limits.maxScans - this.counters.scans),
                searches: Math.max(0, this.limits.maxSearches - this.counters.searches),
                inspectedRegions: Math.max(0, this.limits.maxInspectedRegions - this.counters.inspectedRegions),
                refinements: Math.max(0, this.limits.maxRefinements - this.counters.refinements),
                comparisons: Math.max(0, this.limits.maxComparisons - this.counters.comparisons),
                savedCategories: Math.max(0, this.limits.maxSavedCategories - this.counters.savedCategories),
                modelTokens: Math.max(0, this.limits.maxModelTokens - this.counters.modelTokens)
            },
            inspected_region_count: this.visitedRegions.length,
            accepted_region_count: candidates.filter(candidate => candidate.recommended_action === 'accept').length,
            discovered_themes: [...this.discoveredThemes].slice(-30),
            relevant_themes: [...this.relevantThemes].slice(-30),
            no_progress_rounds: this.noProgressRounds,
            elapsed_ms: elapsedMs,
            frontier,
            candidates,
            recent_events: this.events.slice(-8),
            trajectory: [...this.events]
        };
    }

    private recommend(intentMatch: number, purity: number, sampleRounds: number): CandidateAction {
        if (intentMatch >= 0.75) return purity >= 0.70 ? 'accept' : 'refine';
        if (intentMatch >= 0.60) return purity >= 0.70 ? (sampleRounds > 1 ? 'compare' : 'resample') : 'explore';
        return 'reject';
    }

    private evaluateSemanticStop(): void {
        if (this.stopReason) return;
        const candidates = [...this.candidates.values()];
        const accepted = candidates.filter(candidate => candidate.recommended_action === 'accept');
        const highPurity = accepted.filter(candidate => candidate.purity >= 0.70);
        const comparisonSatisfied = !this.objective.requiresComparison || this.counters.comparisons > 0;
        const frontier = candidates.filter(candidate => frontierAction(candidate.recommended_action) && candidate.utility >= 0.40);
        const bestFrontierUtility = frontier.length ? Math.max(...frontier.map(candidate => candidate.utility)) : 0;
        const bestAcceptedUtility = accepted.length ? Math.max(...accepted.map(candidate => candidate.utility)) : 0;
        if (accepted.length >= this.objective.targetAcceptedRegions &&
            highPurity.length >= Math.min(2, this.objective.targetAcceptedRegions) &&
            this.relevantThemes.size >= Math.min(2, this.objective.targetAcceptedRegions) && comparisonSatisfied) {
            this.stopReason = `semantic evidence target satisfied: ${accepted.length} accepted regions and ${this.relevantThemes.size} relevant themes`;
            return;
        }
        if (accepted.length >= Math.max(1, this.objective.targetAcceptedRegions - 1) &&
            this.relevantThemes.size >= Math.min(2, this.objective.targetAcceptedRegions) &&
            comparisonSatisfied && (bestFrontierUtility === 0 || bestFrontierUtility < bestAcceptedUtility * 0.65)) {
            this.stopReason = `diminishing returns: ${accepted.length} accepted regions and no high-utility frontier remain`;
            return;
        }
        if (this.noProgressRounds >= this.limits.maxNoProgressRounds) {
            this.stopReason = `${this.noProgressRounds} consecutive probe rounds found no new relevant themes`;
            return;
        }
        if (this.probeRounds >= 2 && frontier.length === 0 && accepted.length > 0 &&
            (accepted.length >= this.objective.targetAcceptedRegions || this.relevantThemes.size >= Math.min(2, this.objective.targetAcceptedRegions))) {
            this.stopReason = 'no remaining frontier candidate meets utility threshold 0.40';
            return;
        }
        if (this.probeRounds >= 2 && bestFrontierUtility > 0 && bestFrontierUtility < 0.45) {
            this.stopReason = 'best remaining candidate utility is below 0.45';
        }
    }

    private evaluateScan(call: ToolCall, args: Record<string, unknown>): PolicyDecision {
        const key = signature(args);
        if (this.scanSignatures.has(key)) return this.block(call, 'duplicate scan request');
        if (this.counters.scans >= this.limits.maxScans) return this.block(call, 'scan budget exhausted');
        this.scanSignatures.add(key);
        this.counters.scans++;
        return this.accept(call);
    }

    private evaluateSearch(call: ToolCall): PolicyDecision {
        if (this.counters.searches >= this.limits.maxSearches) return this.block(call, 'structured-search budget exhausted');
        this.counters.searches++;
        return this.accept(call);
    }

    private evaluateInspection(call: ToolCall, args: Record<string, unknown>): PolicyDecision {
        const requested = Array.isArray(args.regions) ? args.regions.map(asRegion).filter((item): item is Region => item !== null) : [];
        if (!requested.length) return this.block(call, 'no valid circular probes supplied');
        if (typeof args.intent !== 'string' || !args.intent.trim()) return this.block(call, 'inspect_regions requires an explicit semantic intent');
        const remaining = this.limits.maxInspectedRegions - this.counters.inspectedRegions;
        if (remaining <= 0) {
            this.stopReason = 'circular-probe budget exhausted';
            return this.block(call, this.stopReason);
        }
        const unique: Region[] = [];
        const requestedResamples = new Set(Array.isArray(args.resample_ids) ? args.resample_ids.map(String) : []);
        for (const region of requested) {
            const duplicate = [...this.visitedRegions, ...unique].some(previous => nearlySameCircle(previous, region));
            const canResample = Boolean(region.id && requestedResamples.has(region.id) &&
                this.candidates.get(region.id)?.recommended_action === 'resample' && !this.resampledCandidates.has(region.id));
            if (!duplicate || canResample) {
                unique.push(region);
                if (canResample && region.id) this.resampledCandidates.add(region.id);
            }
        }
        const accepted = unique.slice(0, remaining);
        if (!accepted.length) return this.block(call, 'all requested circles duplicate previously inspected regions');
        this.visitedRegions.push(...accepted);
        this.consecutiveBlockedActions = 0;
        this.counters.inspectedRegions += accepted.length;
        const rewritten: ToolCall = { ...call, function: { ...call.function, arguments: JSON.stringify({ ...args, regions: accepted }) } };
        this.addEvent(call.function.name, accepted.length === requested.length ? 'accepted' : 'filtered', `${accepted.length}/${requested.length} unique probes`, undefined, { ...args, regions: accepted });
        this.counters.toolCalls++;
        return { call: rewritten };
    }

    private evaluateRefinement(call: ToolCall, args: Record<string, unknown>): PolicyDecision {
        const parentId = typeof args.parent_id === 'string' ? args.parent_id : '';
        const candidate = this.candidates.get(parentId);
        if (!candidate) return this.block(call, 'refine_region requires parent_id from an inspected candidate');
        if (candidate.refine_depth >= this.limits.maxRefineDepthPerBranch) {
            return this.block(call, `candidate ${parentId} already reached refine depth ${this.limits.maxRefineDepthPerBranch}`);
        }
        if (!['refine', 'explore'].includes(candidate.recommended_action)) {
            return this.block(call, `candidate ${parentId} is ${candidate.recommended_action}, not a refinement branch`);
        }
        const key = signature(args);
        if (this.refinementSignatures.has(key)) return this.block(call, 'duplicate refinement request');
        if (this.counters.refinements >= this.limits.maxRefinements) return this.block(call, 'refinement budget exhausted');
        this.refinementSignatures.add(key);
        this.counters.refinements++;
        return this.accept(call);
    }

    private evaluateComparison(call: ToolCall, args: Record<string, unknown>): PolicyDecision {
        const regions = Array.isArray(args.regions) ? args.regions : [];
        const ids = regions.map(region => region && typeof region === 'object' ? (region as Record<string, unknown>).id : null);
        if (ids.length < 2 || ids.some(id => typeof id !== 'string' || !this.candidates.has(id))) {
            return this.block(call, 'compare_regions requires at least two IDs from inspected candidates');
        }
        if (ids.some(id => this.candidates.get(String(id))?.recommended_action === 'reject')) {
            return this.block(call, 'rejected candidates should not consume comparison budget');
        }
        const key = signature(args);
        if (this.comparisonSignatures.has(key)) return this.block(call, 'duplicate comparison request');
        if (this.counters.comparisons >= this.limits.maxComparisons) return this.block(call, 'comparison budget exhausted');
        this.comparisonSignatures.add(key);
        this.counters.comparisons++;
        const decision = this.accept(call);
        this.evaluateSemanticStop();
        return decision;
    }

    private evaluateSave(call: ToolCall): PolicyDecision {
        if (this.counters.savedCategories >= this.limits.maxSavedCategories) return this.block(call, 'saved-category budget exhausted');
        const args = parseArguments(call);
        const requestedIds = Array.isArray(args.review_ids) ? args.review_ids.map(Number).filter(Number.isFinite) : [];
        const category = typeof args.category === 'string' ? args.category.trim().toLowerCase() : '';
        const saveKey = signature({ category, review_ids: [...new Set(requestedIds)].sort((a, b) => a - b) });
        if (this.stopReason && this.savedAfterStop) {
            return this.block(call, 'search is already stopped and final save has already been attempted; answer now without more tools');
        }
        if (this.saveSignatures.has(saveKey)) {
            return this.block(call, 'duplicate save_results request; answer now without more tools');
        }
        const inspectedIds = new Set([...this.candidates.values()].flatMap(candidate => candidate.review_ids));
        const acceptedIds = new Set([...this.candidates.values()]
            .filter(candidate => candidate.recommended_action === 'accept')
            .flatMap(candidate => candidate.review_ids));
        const eligibleIds = requestedIds.filter(id => !inspectedIds.has(id) || acceptedIds.has(id));
        if (requestedIds.some(id => inspectedIds.has(id)) && !eligibleIds.length) {
            return this.block(call, 'save_results may only save accepted spatial candidates; refine, resample, or reject the current branch first');
        }
        this.counters.savedCategories++;
        const rewritten = eligibleIds.length === requestedIds.length ? call : {
            ...call,
            function: { ...call.function, arguments: JSON.stringify({ ...args, review_ids: eligibleIds }) }
        };
        this.saveSignatures.add(saveKey);
        if (this.stopReason) this.savedAfterStop = true;
        return this.accept(rewritten, false);
    }

    private accept(call: ToolCall, countsTowardToolBudget = true): PolicyDecision {
        this.consecutiveBlockedActions = 0;
        if (countsTowardToolBudget) this.counters.toolCalls++;
        this.addEvent(call.function.name, 'accepted', undefined, undefined, parseArguments(call));
        return { call };
    }

    private block(call: ToolCall, reason: string): PolicyDecision {
        this.consecutiveBlockedActions++;
        if (this.consecutiveBlockedActions >= 2 && !this.stopReason) this.stopReason = `${this.consecutiveBlockedActions} consecutive actions were rejected by the search policy`;
        this.addEvent(call.function.name, 'blocked', reason, undefined, parseArguments(call));
        return {
            blockedResult: {
                name: call.function.name,
                call_id: call.id,
                result: {
                    policy_blocked: true,
                    reason,
                    instruction: this.stopReason ? 'Do not call more tools. Provide the final answer now, using verified findings and noting any missing target count.' : 'Follow the candidate recommendations and remaining budget in SEARCH_POLICY_STATE.',
                    policy: this.snapshot()
                }
            }
        };
    }

    private addEvent(tool: string, status: PolicyEvent['status'], detail?: string, newThemes?: string[], parameters?: unknown): void {
        this.events.push({ sequence: this.events.length + 1, tool, status, detail, newThemes, parameters });
    }

    private findParentId(id: string): string | undefined {
        const matches = [...this.candidates.keys()]
            .filter(candidateId => id.startsWith(`${candidateId}-`))
            .sort((a, b) => b.length - a.length);
        return matches[0];
    }
}
