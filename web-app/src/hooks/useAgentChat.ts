import { useState, useCallback, useRef } from 'react';
import { Coordinator } from '@uwdata/mosaic-core';
import { ToolExecutor } from '../tools/toolExecutor';
import type { ToolCall, ToolResult } from '../tools/toolExecutor';
import { SearchPolicy } from '../agent/searchPolicy';
import type { SearchPolicySnapshot } from '../agent/searchPolicy';

export interface Message {
    role: 'user' | 'assistant' | 'tool';
    content: string;
    tool_calls?: any[]; // For storing raw tool calls from LLM
    toolCalls?: ToolCall[];
    toolResults?: {
        name: string;
        call_id: string;
        result: any;
    }[];
    isToolExecution?: boolean;
}

export interface AgentState {
    messages: Message[];
    isLoading: boolean;
    isExecutingTools: boolean;
    currentStep: string;
    error: string | null;
    toolsExecuted: string[];
    highlightIds: number[] | null;  // IDs of points to highlight on the map from tool results
    savedCategories: Map<string, any[]>;  // Category-based memory: category name -> array of review objects
    inspectedRegionsCache: any[];  // Region analyses retained so save_results can build UI cards
    searchPolicy: SearchPolicySnapshot | null; // Reproducible trajectory, budgets, and stop state
}

const INITIAL_MESSAGE: Message = {
    role: 'assistant',
    content: `Hello! I'm your AI Sommelier and Wine Data Analyst.

I can help you explore the wine review projection by:

- **Scanning** the semantic landscape for dense candidate regions
- **Probing several circles in parallel** to discover themes
- **Refining and comparing** promising regions
- **Searching** directly when you already know the flavor, grape, country, or budget

Try asking: "Find me good value reds under $20" or "What are the common flavors in Tuscan wines?"`
};

/**
 * Custom hook for agentic chat with tool execution.
 * Implements the agent loop: LLM → tool calls → execute → LLM → response
 */
export function useAgentChat(coordinator: Coordinator | null) {
    const [state, setState] = useState<AgentState>({
        messages: [INITIAL_MESSAGE],
        isLoading: false,
        isExecutingTools: false,
        currentStep: '',
        error: null,
        toolsExecuted: [],
        highlightIds: null,
        savedCategories: new Map(),
        inspectedRegionsCache: [],
        searchPolicy: null
    });

    const toolExecutorRef = useRef<ToolExecutor | null>(null);
    const abortControllerRef = useRef<AbortController | null>(null);
    const inspectedRegionsCacheRef = useRef<any[]>([]);

    // Initialize tool executor when coordinator is available
    if (coordinator && !toolExecutorRef.current) {
        toolExecutorRef.current = new ToolExecutor(coordinator);
    }

    /**
     * Extract point IDs from tool results for map highlighting
     */
    const extractHighlightIds = (toolResults: ToolResult[]): number[] => {
        const ids: number[] = [];
        for (const result of toolResults) {
            if (result.result?.reviews && Array.isArray(result.result.reviews)) {
                for (const review of result.result.reviews) {
                    if (typeof review.id === 'number') {
                        ids.push(review.id);
                    }
                }
            }
            if (result.result?.regions && Array.isArray(result.result.regions)) {
                for (const region of result.result.regions) {
                    if (Array.isArray(region.reviews)) {
                        for (const review of region.reviews) {
                            if (typeof review.id === 'number') ids.push(review.id);
                        }
                    }
                }
            }
        }
        return [...new Set(ids)]; // Remove duplicates
    };

    /**
     * Send a message and run the agent loop
     */
    const sendMessage = useCallback(async (userMessage: string, selectedPoints?: any[], selectionPredicate?: string | null) => {
        // Debug: Log what selectedPoints we receive
        console.log("[AgentChat] sendMessage called with selectedPoints:", selectedPoints?.length, "points");
        console.log("[AgentChat] Selection predicate:", selectionPredicate);
        if (selectedPoints && selectedPoints.length > 0) {
            console.log("[AgentChat] First point structure:", JSON.stringify(selectedPoints[0], null, 2));
        }

        if (!userMessage.trim() || state.isLoading) return;
        if (!toolExecutorRef.current) {
            setState(prev => ({
                ...prev,
                error: 'Database not ready. Please wait for initialization.'
            }));
            return;
        }

        // Add user message to chat
        const userMsg: Message = { role: 'user', content: userMessage };
        setState(prev => ({
            ...prev,
            messages: [...prev.messages, userMsg],
            isLoading: true,
            error: null,
            currentStep: 'Thinking...',
            toolsExecuted: []
        }));

        // Create abort controller for this request
        abortControllerRef.current = new AbortController();
        const signal = abortControllerRef.current.signal;

        try {
            // Build conversation history for the API
            let conversationMessages = state.messages
                .filter(m => m.role === 'user' || (m.role === 'assistant' && !m.isToolExecution))
                .map(m => ({ role: m.role, content: m.content }));

            // Add the new user message
            conversationMessages.push({ role: 'user', content: userMessage });

            // If user has selected points, build context from the pre-fetched data
            if (selectedPoints && selectedPoints.length > 0) {
                console.log("[AgentChat] Building context from selected points...");

                // Get total count (attached to array by App.tsx)
                const totalSelected = (selectedPoints as any).totalCount || selectedPoints.length;
                console.log("[AgentChat] Total selected:", totalSelected, "Available:", selectedPoints.length);

                // Token limit: ~25000 tokens ≈ 100000 characters (4 chars per token estimate)
                // Model has 256k context, so this leaves plenty of room for response + tool results
                const MAX_CONTEXT_CHARS = 100000;
                const HEADER_RESERVE = 1000; // Reserve for header/footer text

                // Build reviews list, adding reviews until we hit the token limit
                const reviewsFormatted: string[] = [];
                let totalChars = 0;
                let reviewsIncluded = 0;

                for (let i = 0; i < selectedPoints.length; i++) {
                    const p = selectedPoints[i];
                    // Updated to use points instead of Rating
                    const points = p.fields?.points ?? p.fields?.Rating ?? 'N/A'; 
                    const title = p.fields?.title ?? 'Unknown Wine';
                    const description = p.fields?.description ?? p.text ?? 'No description';

                    const reviewText = `[Review ${i + 1}] Points: ${points} | Title: ${title}\n${description}`;

                    // Check if adding this review would exceed the limit
                    if (totalChars + reviewText.length + 4 > MAX_CONTEXT_CHARS - HEADER_RESERVE) {
                        console.log("[AgentChat] Token limit reached at review", i + 1);
                        break;
                    }

                    reviewsFormatted.push(reviewText);
                    totalChars += reviewText.length + 4; // +4 for "\n\n" separator
                    reviewsIncluded++;
                }

                const reviewsList = reviewsFormatted.join('\n\n');

                // Calculate statistics from included reviews
                const includedPoints = selectedPoints.slice(0, reviewsIncluded);
                const scores = includedPoints
                    .map((p: any) => p.fields?.points ?? p.fields?.Rating)
                    .filter((r: any): r is number => typeof r === 'number');

                const avgScore = scores.length > 0
                    ? (scores.reduce((a: number, b: number) => a + b, 0) / scores.length).toFixed(1)
                    : 'N/A';

                const scoreCounts = scores.reduce((acc: Record<number, number>, r: number) => {
                    acc[r] = (acc[r] || 0) + 1;
                    return acc;
                }, {} as Record<number, number>);

                const distributionText = Object.entries(scoreCounts)
                    .sort(([a], [b]) => Number(b) - Number(a))
                    .slice(0, 10) // Only show top 10 most common scores to save space
                    .map(([score, count]) => `${score}: ${count}`)
                    .join(', ');

                const truncatedNote = reviewsIncluded < totalSelected
                    ? `(Showing ${reviewsIncluded} of ${totalSelected} selected reviews in context)`
                    : '';

                const selectionContext = `
**IMPORTANT: The user has selected ${totalSelected} reviews on the visualization.**
They are asking about THIS SPECIFIC SUBSET, not the entire dataset.

**Selection Statistics:**
- Total selected: ${totalSelected} reviews
- Reviews shown below: ${reviewsIncluded}
- Average score (of shown): ${avgScore}
- Score distribution (of shown): ${distributionText || 'N/A'}
${truncatedNote}
**Selected Reviews:**
${reviewsList}

---
**Instructions:**
1. Answer based on the selected reviews shown above
2. Treat the ${reviewsIncluded} reviews shown above as the available representative sample of that selection.
3. Do not run a global spatial scan unless the user explicitly asks to compare the selection with the full map.
`;

                // Prepend selection context to the user's message
                conversationMessages[conversationMessages.length - 1].content =
                    `${selectionContext}\n\nUser question: ${userMessage}`;

                console.log("[AgentChat] Selection context built with", reviewsIncluded, "reviews (~" + Math.round(totalChars / 4) + " tokens), total selected:", totalSelected);
            }

            const searchPolicy = new SearchPolicy({}, userMessage);
            const maxIterations = 22; // Policy budgets normally stop exploration before this safety ceiling.
            let iteration = 0;
            const allToolsExecuted: string[] = [];

            while (iteration < maxIterations) {
                iteration++;

                // Call the agent API
                setState(prev => ({
                    ...prev,
                    currentStep: iteration === 1 ? 'Thinking...' : `Processing step ${iteration}/${maxIterations}...`
                }));

                // If we're approaching the limit, hint the LLM to wrap up
                // Give agent 3 steps to respond (inject at step 27, 28, 29)
                const policySnapshot = searchPolicy.snapshot();
                let messagesToSend = [
                    ...conversationMessages,
                    {
                        role: 'system',
                        content: `SEARCH_POLICY_STATE (controller-enforced):\n${JSON.stringify(policySnapshot)}\nRespect remaining budgets. If must_stop=true, call only save_results if needed and then provide the final answer.`
                    } as any
                ];
                if (iteration >= maxIterations - 3) {
                    const stepsRemaining = maxIterations - iteration;
                    // Add a system hint to stop using tools and give final answer
                    messagesToSend = [
                        ...messagesToSend,
                        {
                            role: 'system',
                            content: `IMPORTANT: You are approaching the step limit (${stepsRemaining} step${stepsRemaining > 1 ? 's' : ''} remaining). Please finalize your findings and provide the final comprehensive answer now. Do NOT call any more tools unless absolutely critical.`
                        } as any
                    ];
                }

                const response = await fetch('/api/agent', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ messages: messagesToSend }),
                    signal
                });

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    throw new Error(errorData.error || `Request failed: ${response.status}`);
                }

                // Parse the JSON response
                const data = await response.json();
                searchPolicy.recordModelUsage(data.usage);

                // If the LLM wants to call tools
                if (data.type === 'tool_calls' && data.tool_calls && data.tool_calls.length > 0) {
                    setState(prev => ({
                        ...prev,
                        isExecutingTools: true,
                        currentStep: `Executing ${data.tool_calls.length} tool(s)...`
                    }));

                    // Execute each tool
                    const toolResults: ToolResult[] = [];
                    for (const toolCall of data.tool_calls) {
                        const toolName = toolCall.function?.name || 'unknown';
                        allToolsExecuted.push(toolName);

                        setState(prev => ({
                            ...prev,
                            currentStep: `Running: ${toolName}...`,
                            toolsExecuted: [...allToolsExecuted]
                        }));

                        const decision = searchPolicy.evaluate(toolCall as ToolCall);
                        if (decision.blockedResult) {
                            toolResults.push(decision.blockedResult);
                            setState(prev => ({ ...prev, searchPolicy: searchPolicy.snapshot() }));
                            console.log(`[Agent] Policy blocked ${toolName}:`, decision.blockedResult.result);
                            continue;
                        }

                        const result = await toolExecutorRef.current!.execute(decision.call!);
                        searchPolicy.record(result);
                        toolResults.push(result);

                        setState(prev => ({ ...prev, searchPolicy: searchPolicy.snapshot() }));

                        // Cache each inspected circle so a later save_results call can build rich cards.
                        if (result.name === 'inspect_regions' && Array.isArray(result.result?.regions)) {
                            inspectedRegionsCacheRef.current.push(...result.result.regions);
                            console.log('[Agent] Cached inspected regions:', inspectedRegionsCacheRef.current.length);
                        }
                        if (result.name === 'search_reviews' && Array.isArray(result.result?.reviews)) {
                            const reviews = result.result.reviews;
                            inspectedRegionsCacheRef.current.push({
                                category: 'Structured search', sentiment: 'N/A', themes: [], quotes: [],
                                review_ids: reviews.map((review: any) => review.id), reviews
                            });
                        }

                        console.log(`[Agent] Tool ${toolName} result:`, result);
                    }

                    // save_results is deliberately separate from retrieval; resolve its IDs against prior probes.
                    for (const toolResult of toolResults) {
                        if (toolResult.name === 'save_results' && toolResult.result?.saved) {
                            const { review_ids, category } = toolResult.result;
                            const matchedRegions: any[] = [];
                            const matchedReviews: any[] = [];
                            for (const region of inspectedRegionsCacheRef.current) {
                                const matchingIds = review_ids.filter((id: number) => region.review_ids?.includes(id));
                                if (matchingIds.length > 0) {
                                    matchedRegions.push(region);
                                    matchedReviews.push(...(region.reviews || []).filter((review: any) => matchingIds.includes(review.id)));
                                }
                            }

                            const uniqueReviews = [...new Map(matchedReviews.map(review => [review.id, review])).values()];
                            const averageMetric = (key: string) => {
                                const values = matchedRegions.map(region => Number(region[key])).filter(Number.isFinite);
                                return values.length ? Math.round((values.reduce((sum, value) => sum + value, 0) / values.length) * 1000) / 1000 : null;
                            };
                            const categoryData = matchedRegions.length ? {
                                category,
                                analyzer_category: matchedRegions.map(region => region.category).filter(Boolean).join(' + '),
                                sentiment: matchedRegions.map(region => region.sentiment).filter(Boolean).join(', '),
                                themes: [...new Set(matchedRegions.flatMap(region => region.themes || []))],
                                quotes: [...new Set(matchedRegions.flatMap(region => region.quotes || []))],
                                avg_points: matchedRegions[0].avg_points,
                                intent: matchedRegions[0].intent,
                                purity: averageMetric('purity'),
                                intent_match: averageMetric('intent_match'),
                                purity_rationales: matchedRegions.map(region => region.purity_rationale).filter(Boolean),
                                intent_match_rationales: matchedRegions.map(region => region.intent_match_rationale).filter(Boolean),
                                review_ids: uniqueReviews.map(review => review.id),
                                reviews: uniqueReviews,
                                regions: matchedRegions.map(region => ({
                                    id: region.id, center_x: region.center_x, center_y: region.center_y,
                                    radius: region.radius,
                                    purity: region.purity,
                                    intent_match: region.intent_match,
                                    projection_agreement: region.projection_agreement
                                })),
                                count: uniqueReviews.length
                            } : null;

                            // Update savedCategories state
                            if (categoryData) {
                                setState(prev => ({
                                    ...prev,
                                    savedCategories: new Map(prev.savedCategories).set(
                                        category,
                                        [categoryData]
                                    )
                                }));
                            }
                        }
                    }

                    // Extract IDs from tool results and update highlight
                    const newHighlightIds = extractHighlightIds(toolResults);
                    if (newHighlightIds.length > 0) {
                        setState(prev => ({
                            ...prev,
                            highlightIds: newHighlightIds
                        }));
                    }

                    // Add the assistant's tool call message to the conversation
                    conversationMessages.push({
                        role: 'assistant',
                        content: '',
                        tool_calls: data.tool_calls
                    } as any);

                    // Add tool results to the conversation
                    for (const result of toolResults) {
                        conversationMessages.push({
                            role: 'tool',
                            content: JSON.stringify(result.result || result.error),
                            tool_call_id: result.call_id
                        } as any);
                    }

                    // Continue the loop to get the final response
                    continue;
                }

                // Final response from the agent
                const assistantMsg: Message = {
                    role: 'assistant',
                    content: data.content || 'I apologize, but I could not generate a response.',
                    toolResults: allToolsExecuted.length > 0 ?
                        allToolsExecuted.map(name => ({ name, call_id: '', result: {} })) : undefined
                };

                setState(prev => ({
                    ...prev,
                    messages: [...prev.messages, assistantMsg],
                    isLoading: false,
                    isExecutingTools: false,
                    currentStep: '',
                    toolsExecuted: allToolsExecuted,
                    searchPolicy: searchPolicy.snapshot()
                }));

                console.log('[Agent] Final search policy and trajectory:', searchPolicy.snapshot());

                return;
            }

            // If we hit max iterations, provide a summary of what was done
            const toolsSummary = allToolsExecuted.length > 0
                ? `Tools used: ${[...new Set(allToolsExecuted)].join(', ')}.`
                : '';
            throw new Error(`Analysis reached the limit of ${maxIterations} steps. ${toolsSummary} Please try a more specific question.`);

        } catch (error) {
            // Check if this was an abort
            if (error instanceof Error && error.name === 'AbortError') {
                console.log('[AgentChat] Request was cancelled by user');
                setState(prev => ({
                    ...prev,
                    isLoading: false,
                    isExecutingTools: false,
                    currentStep: '',
                    messages: [...prev.messages, {
                        role: 'assistant',
                        content: 'Request cancelled.'
                    }]
                }));
                return;
            }

            console.error('[AgentChat] Error:', error);
            const errorMessage = error instanceof Error ? error.message : 'An unexpected error occurred';

            setState(prev => ({
                ...prev,
                isLoading: false,
                isExecutingTools: false,
                currentStep: '',
                error: errorMessage,
                messages: [...prev.messages, {
                    role: 'assistant',
                    content: `I encountered an error: ${errorMessage}\n\nPlease try again or rephrase your question.`
                }]
            }));
        } finally {
            abortControllerRef.current = null;
        }
    }, [state.messages, state.isLoading, coordinator]);

    /**
     * Clear chat history and highlight
     */
    const clearChat = useCallback(() => {
        setState({
            messages: [INITIAL_MESSAGE],
            isLoading: false,
            isExecutingTools: false,
            currentStep: '',
            error: null,
            toolsExecuted: [],
            highlightIds: null,
            savedCategories: new Map(),
            inspectedRegionsCache: [],
            searchPolicy: null
        });
        inspectedRegionsCacheRef.current = [];
    }, []);

    /**
     * Clear highlight without clearing chat
     */
    const clearHighlight = useCallback(() => {
        setState(prev => ({
            ...prev,
            highlightIds: null
        }));
    }, []);

    /**
     * Stop the current generation/thinking process
     */
    const stopGeneration = useCallback(() => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }
    }, []);

    return {
        ...state,
        sendMessage,
        clearChat,
        clearHighlight,
        stopGeneration
    };
}
