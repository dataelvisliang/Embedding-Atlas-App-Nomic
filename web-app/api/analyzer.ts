import type { VercelRequest, VercelResponse } from '@vercel/node';

const OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions";

const ANALYZER_SYSTEM_PROMPT = `You are a specialized Wine Review Analyzer Agent.

Your task is to analyze a set of wine reviews and extract:
1. **Category/Theme**: A concise label (2-3 words) describing the main varietal, style, or region (e.g., "Tuscan Sangiovese", "Napa Cabernet", "Crisp White")
2. **Quality Perception**: Overall impression of quality (Excellent, Good, Mediocre)
3. **Flavor Notes**: List of 2-5 specific flavor notes or characteristics found in the reviews (e.g., "cherry", "oak", "earthy", "high tannins")
4. **Top Quotes**: Extract 2-3 representative short quotes (max 100 chars each) that best describe the wine's character
5. **Semantic Purity**: A score from 0.0 to 1.0 estimating the share of sampled reviews that support one dominant coherent wine theme. A region can be pure even when it is irrelevant to the user's intent.
6. **Intent Match**: A score from 0.0 to 1.0 estimating how strongly the sampled region satisfies the supplied user intent and constraints. A region can match weakly even when internally pure.

Calibration:
- 0.90-1.00: nearly all sampled evidence supports the criterion
- 0.70-0.89: strong majority support
- 0.40-0.69: mixed or partial support
- 0.10-0.39: weak support
- 0.00-0.09: absent or contradicted

Output your analysis as JSON:
{
  "category": "...",
  "sentiment": "Excellent|Good|Mediocre",
  "themes": ["note1", "note2", ...],
  "quotes": ["quote1", "quote2", "quote3"],
  "purity": 0.0,
  "purity_rationale": "one short evidence-based sentence",
  "intent_match": 0.0,
  "intent_match_rationale": "one short evidence-based sentence",
  "outlier_count": 0
}

Score the supplied reviews only. Do not infer from coordinates or density. Be precise and data-driven. The category should be informative.`;

interface AnalyzerRequest {
    region: {
        id?: string;
        center_x: number;
        center_y: number;
        radius: number;
    };
    intent: string;
    reviews: any[];
}

interface AnalyzerResponse {
    category: string;
    sentiment: string;
    themes: string[];
    quotes: string[];
    count: number;
    avg_points: number;
    review_ids: number[];
    region_id?: string;
    center_x: number;
    center_y: number;
    radius: number;
    purity: number;
    purity_rationale: string;
    intent_match: number;
    intent_match_rationale: string;
    outlier_count: number;
}

const normalizedScore = (value: unknown, fallback = 0.5): number => {
    const score = Number(value);
    return Number.isFinite(score) ? Math.round(Math.min(1, Math.max(0, score)) * 1000) / 1000 : fallback;
};

export default async function handler(req: VercelRequest, res: VercelResponse) {
    // CORS headers
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

    if (req.method === 'OPTIONS') {
        return res.status(200).end();
    }

    if (req.method !== 'POST') {
        return res.status(405).json({ error: 'Method not allowed' });
    }

    const apiKey = process.env.OPENROUTER_API_KEY;
    const model = process.env.OPENROUTER_MODEL || 'nvidia/nemotron-3-nano-30b-a3b:free';

    if (!apiKey) {
        return res.status(500).json({ error: 'OpenRouter API key not configured' });
    }

    try {
        const { region, reviews, intent }: AnalyzerRequest = req.body;

        if (!region || typeof region.center_x !== 'number' || typeof region.center_y !== 'number' || typeof region.radius !== 'number') {
            return res.status(400).json({ error: 'Invalid request: a circular region with center_x, center_y, and radius is required' });
        }

        // This would normally fetch from DuckDB, but since we're server-side,
        // we need to receive the reviews data from the client
        // For now, we'll expect the client to send reviews directly
        if (!reviews || !Array.isArray(reviews)) {
            return res.status(400).json({
                error: 'Reviews array required. Please send reviews data in request body.'
            });
        }

        if (reviews.length === 0) {
            return res.status(200).json({
                category: 'Empty Cluster',
                sentiment: 'N/A',
                themes: [],
                quotes: [],
                count: 0,
                avg_points: 0,
                review_ids: [],
                region_id: region.id,
                center_x: region.center_x,
                center_y: region.center_y,
                radius: region.radius,
                purity: 0,
                purity_rationale: 'The circle contains no reviews.',
                intent_match: 0,
                intent_match_rationale: 'No evidence is available for intent matching.',
                outlier_count: 0
            });
        }

        // Calculate stats
        const points = reviews.map((r: any) => r.points || r.rating || r.Rating).filter((r: any) => typeof r === 'number');
        const avg_points = points.length > 0
            ? points.reduce((a: number, b: number) => a + b, 0) / points.length
            : 0;

        // Format reviews for LLM
        const reviewsText = reviews.map((r: any, idx: number) =>
            `[${idx + 1}] Points: ${r.points || r.rating || r.Rating}\nTitle: ${r.title || 'Unknown'}\n${r.text || r.description || r.excerpt}`
        ).join('\n\n');

        // Call Analyzer Agent (LLM)
        console.log(`[Analyzer] Analyzing ${reviews.length} reviews in circle (${region.center_x}, ${region.center_y}, r=${region.radius})`);

        const llmResponse = await fetch(OPENROUTER_API_URL, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${apiKey}`,
                'Content-Type': 'application/json',
                'HTTP-Referer': req.headers.referer as string || req.headers.origin as string || 'https://localhost',
                'X-Title': 'Wine Review Analyzer Agent'
            },
            body: JSON.stringify({
                model,
                messages: [
                    { role: 'system', content: ANALYZER_SYSTEM_PROMPT },
                    { role: 'user', content: `User intent: ${String(intent || 'Open-ended wine theme discovery').slice(0, 500)}\n\nAnalyze these ${reviews.length} reviews and score both semantic purity and intent match independently:\n\n${reviewsText}` }
                ],
                temperature: 0.3,  // Low temp for consistent analysis
                max_tokens: 700
            })
        });

        if (!llmResponse.ok) {
            const errorText = await llmResponse.text();
            console.error('[Analyzer] LLM error:', llmResponse.status, errorText);
            return res.status(llmResponse.status).json({
                error: `Analyzer Agent failed: ${llmResponse.statusText}`
            });
        }

        const llmData = await llmResponse.json();
        console.log('[Analyzer] LLM response:', {
            hasChoices: !!llmData.choices,
            choicesLength: llmData.choices?.length,
            firstChoice: llmData.choices?.[0],
            message: llmData.choices?.[0]?.message
        });
        
        // Handle both standard and reasoning token responses
        const message = llmData.choices?.[0]?.message;
        let content = message?.content;
        
        // If content is empty but there are reasoning_details, try to extract from there
        if (!content && message?.reasoning_details) {
            content = message.reasoning_details.map((d: any) => d.content).join('\n');
        }

        if (!content) {
            console.error('[Analyzer] No content in response. Message object:', message);
            return res.status(500).json({ error: 'No response from Analyzer Agent' });
        }
        
        console.log('[Analyzer] Extracted content:', content.substring(0, 200) + '...');

        // Parse JSON from LLM response
        let analysis: any;
        try {
            // Try to extract JSON from markdown code blocks if present
            const jsonMatch = content.match(/```json\n([\s\S]+?)\n```/) || content.match(/\{[\s\S]+\}/);
            const jsonStr = jsonMatch ? (jsonMatch[1] || jsonMatch[0]) : content;
            analysis = JSON.parse(jsonStr);
        } catch {
            console.error('[Analyzer] Failed to parse LLM JSON:', content);
            // Fallback: create a basic analysis
            analysis = {
                category: 'General Wines',
                sentiment: avg_points >= 88 ? 'Excellent' : 'Good',
                themes: ['Various Styles'],
                quotes: [],
                purity: 0.5,
                purity_rationale: 'Structured analysis was unavailable; neutral fallback used.',
                intent_match: 0.5,
                intent_match_rationale: 'Structured analysis was unavailable; neutral fallback used.',
                outlier_count: 0
            };
        }

        const response: AnalyzerResponse = {
            category: analysis.category || 'Unknown',
            sentiment: analysis.sentiment || 'Good',
            themes: analysis.themes || [],
            quotes: analysis.quotes || [],
            count: reviews.length,
            avg_points: Math.round(avg_points * 10) / 10,
            review_ids: reviews.map((r: any) => r.id || r.__row_index__).filter((id: any) => id !== undefined),
            region_id: region.id,
            center_x: region.center_x,
            center_y: region.center_y,
            radius: region.radius,
            purity: normalizedScore(analysis.purity),
            purity_rationale: String(analysis.purity_rationale || 'No rationale returned.'),
            intent_match: normalizedScore(analysis.intent_match),
            intent_match_rationale: String(analysis.intent_match_rationale || 'No rationale returned.'),
            outlier_count: Math.max(0, Math.min(reviews.length, Math.round(Number(analysis.outlier_count) || 0)))
        };

        const responseWithUsage = {
            ...response,
            analyzer_usage: llmData.usage
        };

        console.log(`[Analyzer] Analysis complete: ${response.category} (${response.sentiment})`);
        return res.status(200).json(responseWithUsage);

    } catch (error) {
        console.error('[Analyzer] Error:', error);
        return res.status(500).json({
            error: error instanceof Error ? error.message : 'Internal server error'
        });
    }
}
