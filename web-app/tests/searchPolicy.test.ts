import assert from 'node:assert/strict';
import { SearchPolicy } from '../src/agent/searchPolicy';
import type { ToolCall, ToolResult } from '../src/tools/toolExecutor';

let nextId = 1;
const call = (name: string, args: object): ToolCall => ({
    id: `call-${nextId++}`,
    type: 'function',
    function: { name, arguments: JSON.stringify(args) }
});

const completedInspection = (source: ToolCall, themes: string[], purity = 0.8, intentMatch = 0.8): ToolResult => ({
    name: 'inspect_regions',
    call_id: source.id,
    result: { regions: [{ id: `region-${source.id}`, center_x: Number(source.id.replace(/\D/g, '')), center_y: 0, radius: 1, category: themes[0] || 'Known theme', themes, purity, intent_match: intentMatch, sample_size: 12, review_ids: [Number(source.id.replace(/\D/g, ''))] }] }
});

const duplicatePolicy = new SearchPolicy();
const scan = call('scan_regions', { grid_size: 1, top_k: 12 });
assert.ok(duplicatePolicy.evaluate(scan).call, 'first scan should pass');
assert.equal(duplicatePolicy.evaluate(call('scan_regions', { top_k: 12, grid_size: 1 })).blockedResult?.result.policy_blocked, true, 'canonical duplicate scan should be blocked');

const contextPolicy = new SearchPolicy({}, 'find affordable white wines under $25');
const scopedScan = contextPolicy.evaluate(call('scan_regions', { grid_size: 2 })).call;
assert.equal(JSON.parse(scopedScan!.function.arguments).search_context.hard_filters.max_price, 25, 'scan must receive the controller-owned hard filter context');
const scopedInspection = contextPolicy.evaluate(call('inspect_regions', { intent: 'affordable white wine', regions: [{ id: 'scoped', center_x: 0, center_y: 0, radius: 1 }] })).call;
assert.equal(JSON.parse(scopedInspection!.function.arguments).search_context.hard_filters.max_price, 25, 'inspect must inherit the same hard filter context');

const provenancePolicy = new SearchPolicy();
const provenanceScan = call('scan_regions', { grid_size: 6, top_k: 3 });
assert.ok(provenancePolicy.evaluate(provenanceScan).call);
provenancePolicy.record({ name: 'scan_regions', call_id: provenanceScan.id, result: { regions: [{ id: 'scan-1', center_x: 0, center_y: 0, suggested_radius: 2 }] } });
assert.equal(provenancePolicy.evaluate(call('inspect_regions', { intent: 'test', regions: [{ id: 'probe-A', center_x: 1, center_y: 1, radius: 1 }] })).blockedResult?.result.policy_blocked, true, 'invented probe IDs must be rejected after a scan');
assert.ok(provenancePolicy.evaluate(call('inspect_regions', { intent: 'test', regions: [{ id: 'scan-1', center_x: 0, center_y: 0, radius: 2 }] })).call, 'scan candidate with exact geometry should be inspectable');

const budgetPolicy = new SearchPolicy({ maxInspectedRegions: 2 });
const oversizedBatch = call('inspect_regions', {
    intent: 'bold red wine',
    regions: [
        { center_x: 0, center_y: 0, radius: 1 },
        { center_x: 4, center_y: 0, radius: 1 },
        { center_x: 8, center_y: 0, radius: 1 }
    ]
});
const rewritten = budgetPolicy.evaluate(oversizedBatch).call;
assert.ok(rewritten, 'a partially affordable batch should pass');
assert.equal(JSON.parse(rewritten.function.arguments).regions.length, 2, 'batch should be truncated to remaining probe budget');

const progressPolicy = new SearchPolicy({ maxNoProgressRounds: 2 });
const probes = [0, 5, 10].map(x => call('inspect_regions', { intent: 'cherry wine', regions: [{ center_x: x, center_y: 0, radius: 1 }] }));
for (const probe of probes) {
    assert.ok(progressPolicy.evaluate(probe).call);
    progressPolicy.record(completedInspection(probe, ['cherry']));
}
assert.equal(progressPolicy.snapshot().must_stop, true, 'two rounds without a new theme should trigger stopping');

const circlePolicy = new SearchPolicy();
assert.ok(circlePolicy.evaluate(call('inspect_regions', { intent: 'red wine', regions: [{ center_x: 1, center_y: 1, radius: 2 }] })).call);
const nearDuplicate = circlePolicy.evaluate(call('inspect_regions', { intent: 'red wine', regions: [{ center_x: 1.2, center_y: 1.1, radius: 2.1 }] }));
assert.equal(nearDuplicate.blockedResult?.result.policy_blocked, true, 'near-identical circles should be blocked');

const retryPolicy = new SearchPolicy();
retryPolicy.evaluate(call('scan_regions', { grid_size: 1 }));
retryPolicy.evaluate(call('scan_regions', { grid_size: 1 }));
retryPolicy.evaluate(call('scan_regions', { grid_size: 1 }));
assert.equal(retryPolicy.snapshot().must_stop, true, 'repeated blocked retries should force convergence');

const matrixPolicy = new SearchPolicy({}, 'recommend bold red wine');
const matrixCall = call('inspect_regions', {
    intent: 'bold red wine',
    regions: [
        { id: 'accept-me', center_x: 0, center_y: 0, radius: 1 },
        { id: 'refine-me', center_x: 3, center_y: 0, radius: 1 },
        { id: 'resample-me', center_x: 6, center_y: 0, radius: 1 },
        { id: 'reject-me', center_x: 9, center_y: 0, radius: 1 }
    ]
});
assert.ok(matrixPolicy.evaluate(matrixCall).call);
matrixPolicy.record({
    name: 'inspect_regions', call_id: matrixCall.id, result: { regions: [
        { id: 'accept-me', center_x: 0, center_y: 0, radius: 1, category: 'A', themes: ['a'], purity: 0.8, intent_match: 0.9, hard_constraint_match: true, sample_size: 12, review_ids: [101] },
        { id: 'refine-me', center_x: 3, center_y: 0, radius: 1, category: 'B', themes: ['b'], purity: 0.5, intent_match: 0.9, hard_constraint_match: true, sample_size: 12, review_ids: [102] },
        { id: 'resample-me', center_x: 6, center_y: 0, radius: 1, category: 'C', themes: ['c'], purity: 0.8, intent_match: 0.6, hard_constraint_match: true, sample_size: 12, review_ids: [103] },
        { id: 'reject-me', center_x: 9, center_y: 0, radius: 1, category: 'D', themes: ['d'], purity: 0.9, intent_match: 0.2, hard_constraint_match: true, sample_size: 12, review_ids: [104] }
    ] }
});
const actions = Object.fromEntries(matrixPolicy.snapshot().candidates.map(candidate => [candidate.id, candidate.recommended_action]));
assert.deepEqual(actions, { 'accept-me': 'accept', 'refine-me': 'refine', 'resample-me': 'resample', 'reject-me': 'reject' });
assert.ok(matrixPolicy.evaluate(call('refine_region', { parent_id: 'refine-me', center_x: 3, center_y: 0, radius: 1 })).call, 'refine recommendation should authorize refinement');
assert.equal(matrixPolicy.evaluate(call('refine_region', { parent_id: 'accept-me', center_x: 0, center_y: 0, radius: 1 })).blockedResult?.result.policy_blocked, true, 'accepted branch should not be refined');
const childCall = call('inspect_regions', { intent: 'bold red wine', regions: [{ id: 'refine-me-1', center_x: 3.2, center_y: 0, radius: 0.5 }] });
assert.ok(matrixPolicy.evaluate(childCall).call, 'refined child inspection should pass');
matrixPolicy.record({ name: 'inspect_regions', call_id: childCall.id, result: { regions: [
    { id: 'refine-me-1', center_x: 3.2, center_y: 0, radius: 0.5, category: 'B child', themes: ['b child'], purity: 0.5, intent_match: 0.9, hard_constraint_match: true, sample_size: 12, review_ids: [106] }
] } });
assert.equal(matrixPolicy.evaluate(call('refine_region', { parent_id: 'refine-me-1', center_x: 3.2, center_y: 0, radius: 0.5 })).blockedResult?.result.policy_blocked, true, 'refine depth should be capped per branch');
const resampleCall = call('inspect_regions', {
    intent: 'bold red wine', resample_ids: ['resample-me'],
    regions: [{ id: 'resample-me', center_x: 6, center_y: 0, radius: 1 }]
});
assert.ok(matrixPolicy.evaluate(resampleCall).call, 'one explicitly recommended resample should pass deduplication');
matrixPolicy.record({ name: 'inspect_regions', call_id: resampleCall.id, result: { regions: [
    { id: 'resample-me', center_x: 6, center_y: 0, radius: 1, category: 'C', themes: ['c'], purity: 0.82, intent_match: 0.64, hard_constraint_match: true, sample_size: 12, review_ids: [105] }
] } });
const resampled = matrixPolicy.snapshot().candidates.find(candidate => candidate.id === 'resample-me');
assert.equal(resampled?.recommended_action, 'compare', 'a medium-match candidate should move from resample to compare');
assert.equal(resampled?.sample_rounds, 2);
assert.ok((resampled?.score_stability || 0) > 0.9, 'stable repeated scores should report high stability');

const diversityPolicy = new SearchPolicy({}, 'explore three distinct savory red wine regions');
const diversityCall = call('inspect_regions', {
    intent: 'savory red wine regions',
    regions: [
        { id: 'diverse-a', center_x: 0, center_y: 0, radius: 1 },
        { id: 'diverse-b', center_x: 3, center_y: 0, radius: 1 }
    ]
});
assert.ok(diversityPolicy.evaluate(diversityCall).call);
diversityPolicy.record({ name: 'inspect_regions', call_id: diversityCall.id, result: { regions: [
    { id: 'diverse-a', center_x: 0, center_y: 0, radius: 1, category: 'earthy Rioja', themes: ['earthy rioja'], purity: 0.8, intent_match: 0.62, hard_constraint_match: true, sample_size: 12, review_ids: [401] },
    { id: 'diverse-b', center_x: 3, center_y: 0, radius: 1, category: 'peppery Syrah', themes: ['peppery syrah'], purity: 0.78, intent_match: 0.63, hard_constraint_match: true, sample_size: 12, review_ids: [402] }
] } });
const diversityActions = Object.fromEntries(diversityPolicy.snapshot().candidates.map(candidate => [candidate.id, [candidate.recommended_action, candidate.acceptance_tier]]));
assert.deepEqual(diversityActions, { 'diverse-a': ['accept', 'diversity'], 'diverse-b': ['accept', 'diversity'] });

const constrainedPolicy = new SearchPolicy({}, 'recommend an affordable red wine under $25');
const constrainedCall = call('inspect_regions', { intent: 'affordable red wine under $25', regions: [{ id: 'white-region', center_x: 0, center_y: 0, radius: 1 }] });
assert.ok(constrainedPolicy.evaluate(constrainedCall).call);
constrainedPolicy.record({ name: 'inspect_regions', call_id: constrainedCall.id, result: { regions: [
    { id: 'white-region', center_x: 0, center_y: 0, radius: 1, category: 'Crisp white', themes: ['citrus'], purity: 0.95, intent_match: 0.95, hard_constraint_match: false, sample_size: 12, review_ids: [501] }
] } });
assert.equal(constrainedPolicy.snapshot().candidates[0]?.recommended_action, 'reject', 'a hard-constraint conflict must never be accepted');

const failurePolicy = new SearchPolicy();
const failureCall = call('inspect_regions', { intent: 'savory red', regions: [{ id: 'failed', center_x: 0, center_y: 0, radius: 1 }] });
failurePolicy.evaluate(failureCall);
failurePolicy.record({ name: 'inspect_regions', call_id: failureCall.id, result: { regions: [
    { id: 'failed', center_x: 0, center_y: 0, radius: 1, category: 'Analysis failed', themes: [], purity: 0.5, intent_match: 0.5, sample_size: 12, review_ids: [301], analysis_failed: true }
] } });
const failed = failurePolicy.snapshot().candidates.find(candidate => candidate.id === 'failed');
assert.equal(failed?.recommended_action, 'reject', 'analysis_failed regions should not become neutral frontier candidates');
assert.equal(failed?.utility, 0);

const targetPolicy = new SearchPolicy({}, 'recommend 1 wine');
const targetCall = call('inspect_regions', { intent: 'earthy red', regions: [{ id: 'winner', center_x: 0, center_y: 0, radius: 1 }] });
targetPolicy.evaluate(targetCall);
targetPolicy.record({ name: 'inspect_regions', call_id: targetCall.id, result: { regions: [
    { id: 'winner', center_x: 0, center_y: 0, radius: 1, category: 'Earthy red', themes: ['earthy'], purity: 0.9, intent_match: 0.9, sample_size: 12, review_ids: [201] }
] } });
assert.equal(targetPolicy.snapshot().must_stop, true, 'objective-aware evidence target should stop search');
const saveAfterStop = call('save_results', { category: 'Earthy red', review_ids: [201] });
assert.ok(targetPolicy.evaluate(saveAfterStop).call, 'one final save after stopping should pass');
const duplicateSave = targetPolicy.evaluate(call('save_results', { category: 'Earthy red', review_ids: [201] }));
assert.equal(duplicateSave.blockedResult?.result.policy_blocked, true, 'duplicate save after stopping should be blocked');
assert.match(String(duplicateSave.blockedResult?.result.instruction), /final answer now/i, 'blocked duplicate save should force finalization');

console.log('searchPolicy tests passed');
