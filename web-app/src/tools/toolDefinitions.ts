/**
 * The agent-facing tools intentionally expose orthogonal search operations.
 * DuckDB remains an implementation detail instead of an unrestricted agent tool.
 */
export const TOOL_DEFINITIONS = [
    {
        type: 'function' as const,
        function: {
            name: 'search_reviews',
            description: 'Structured lexical and metadata retrieval. Use it for a known flavor, grape, country, score, or price constraint; do not use it to explore unknown spatial themes.',
            parameters: {
                type: 'object',
                properties: {
                    terms: { type: 'array', items: { type: 'string' }, description: 'Optional words or phrases matched against review descriptions.' },
                    term_mode: { type: 'string', enum: ['AND', 'OR'], description: 'Whether all terms or any term must match. Default AND.' },
                    countries: { type: 'array', items: { type: 'string' } },
                    varieties: { type: 'array', items: { type: 'string' } },
                    min_points: { type: 'number' },
                    max_points: { type: 'number' },
                    min_price: { type: 'number' },
                    max_price: { type: 'number' },
                    limit: { type: 'number', description: 'Maximum returned reviews; default 15, maximum 50.' }
                }
            }
        }
    },
    {
        type: 'function' as const,
        function: {
            name: 'scan_regions',
            description: 'Coarse global scan of the 2D projection. Returns the densest grid cells as candidate regions with centers, suggested radii, density, and summary statistics. This proposes where to inspect; it does not interpret themes.',
            parameters: {
                type: 'object',
                properties: {
                    grid_size: { type: 'number', description: 'Grid resolution in projection units; default 1.0.' },
                    top_k: { type: 'number', description: 'Candidate regions to return; default 12, maximum 30.' },
                    countries: { type: 'array', items: { type: 'string' } },
                    varieties: { type: 'array', items: { type: 'string' } },
                    terms: { type: 'array', items: { type: 'string' } },
                    term_mode: { type: 'string', enum: ['AND', 'OR'] },
                    min_points: { type: 'number' },
                    max_points: { type: 'number' },
                    min_price: { type: 'number' },
                    max_price: { type: 'number' }
                }
            }
        }
    },
    {
        type: 'function' as const,
        function: {
            name: 'inspect_regions',
            description: 'Place several circular probes in one call. Each circle is sampled and delegated to the Analyzer Agent, returning density, themes, representative reviews, and a high-dimensional-neighbor agreement signal. Use after scan_regions and inspect multiple candidates at once.',
            parameters: {
                type: 'object',
                properties: {
                    regions: {
                        type: 'array', minItems: 1, maxItems: 8,
                        items: {
                            type: 'object',
                            properties: {
                                id: { type: 'string' }, center_x: { type: 'number' }, center_y: { type: 'number' }, radius: { type: 'number' }
                            },
                            required: ['center_x', 'center_y', 'radius']
                        }
                    },
                    intent: { type: 'string', description: 'Concise semantic target shared by all probes in this batch, including user constraints (for example: bold chocolate-flavored red wines under $20).' },
                    resample_ids: { type: 'array', items: { type: 'string' }, description: 'Optional inspected candidate IDs explicitly recommended for one additional independent sample.' },
                    sample_size: { type: 'number', description: 'Reviews analyzed per circle; default 12, maximum 50.' }
                },
                required: ['regions', 'intent']
            }
        }
    },
    {
        type: 'function' as const,
        function: {
            name: 'refine_region',
            description: 'Zoom into one promising circular region and propose smaller child regions for projection-guided purification. Use when an inspected region is relevant but broad, mixed, or needs distinct subthemes.',
            parameters: {
                type: 'object',
                properties: {
                    parent_id: { type: 'string', description: 'ID of an inspected candidate whose policy recommendation is refine or explore.' },
                    center_x: { type: 'number' }, center_y: { type: 'number' }, radius: { type: 'number' },
                    objective: {
                        type: 'string',
                        enum: ['maximize_purity', 'maximize_intent_match', 'find_distinct_subthemes'],
                        description: 'Refinement goal. Use maximize_purity for mixed relevant regions, maximize_intent_match for weakly relevant regions, and find_distinct_subthemes when the user asks for diverse themes.'
                    },
                    subdivisions: { type: 'number', description: 'Cells across the parent diameter; default 4, range 2-10.' },
                    top_k: { type: 'number', description: 'Child regions to return; default 6, maximum 12.' }
                },
                required: ['parent_id', 'center_x', 'center_y', 'radius']
            }
        }
    },
    {
        type: 'function' as const,
        function: {
            name: 'compare_regions',
            description: 'Compare two to six circular regions using consistent density, score, price, country, and variety summaries. Use for contrastive questions or to choose between inspected candidates.',
            parameters: {
                type: 'object',
                properties: {
                    regions: {
                        type: 'array', minItems: 2, maxItems: 6,
                        items: {
                            type: 'object',
                            properties: { id: { type: 'string' }, center_x: { type: 'number' }, center_y: { type: 'number' }, radius: { type: 'number' } },
                            required: ['id', 'center_x', 'center_y', 'radius']
                        }
                    }
                },
                required: ['regions']
            }
        }
    },
    {
        type: 'function' as const,
        function: {
            name: 'save_results',
            description: 'Persist already verified review IDs under a category for UI cards. This is a presentation/memory action, not a retrieval action. Reference the exact category later as {{CATEGORY_NAME}}.',
            parameters: {
                type: 'object',
                properties: {
                    review_ids: { type: 'array', items: { type: 'number' } },
                    category: { type: 'string' }
                },
                required: ['review_ids', 'category']
            }
        }
    }
] as const;
