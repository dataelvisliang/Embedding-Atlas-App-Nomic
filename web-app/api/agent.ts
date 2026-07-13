import type { VercelRequest, VercelResponse } from '@vercel/node';
import { TOOL_DEFINITIONS } from '../src/tools/toolDefinitions';
import { SPATIAL_SYSTEM_PROMPT } from './agentPrompt';

const OPENROUTER_API_URL = 'https://openrouter.ai/api/v1/chat/completions';

interface AgentMessage {
    role: 'system' | 'user' | 'assistant' | 'tool';
    content: string;
    tool_calls?: unknown[];
    tool_call_id?: string;
}

interface AgentRequest {
    messages: AgentMessage[];
}

interface OpenRouterResponse {
    model?: string;
    usage?: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number };
    choices?: Array<{
        message?: {
            content?: string;
            tool_calls?: unknown[];
        };
    }>;
}

function errorMessage(error: unknown): string {
    return error instanceof Error ? error.message : 'Internal server error';
}

export default async function handler(req: VercelRequest, res: VercelResponse) {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

    if (req.method === 'OPTIONS') return res.status(200).end();
    if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

    const apiKey = process.env.OPENROUTER_API_KEY;
    const model = process.env.OPENROUTER_MODEL || 'nvidia/nemotron-3-nano-30b-a3b:free';
    if (!apiKey) return res.status(500).json({ error: 'OpenRouter API key not configured' });

    const { messages } = req.body as AgentRequest;
    if (!Array.isArray(messages)) return res.status(400).json({ error: 'Invalid request: messages array required' });

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 60_000);
    req.on('close', () => {
        controller.abort();
        clearTimeout(timeout);
    });

    try {
        const apiMessages: AgentMessage[] = [
            { role: 'system', content: SPATIAL_SYSTEM_PROMPT },
            ...messages
        ];
        const response = await fetch(OPENROUTER_API_URL, {
            method: 'POST',
            headers: {
                Authorization: `Bearer ${apiKey}`,
                'Content-Type': 'application/json',
                'HTTP-Referer': String(req.headers.referer || req.headers.origin || 'https://localhost'),
                'X-Title': 'Wine Review Atlas Agent'
            },
            body: JSON.stringify({
                model,
                messages: apiMessages,
                tools: TOOL_DEFINITIONS,
                tool_choice: 'auto',
                temperature: 0,
                max_tokens: 900,
                reasoning: { effort: 'none', exclude: true }
            }),
            signal: controller.signal
        });
        clearTimeout(timeout);

        if (!response.ok) {
            const errorText = await response.text();
            let detail = response.statusText;
            try {
                const parsed = JSON.parse(errorText) as { error?: { message?: string } };
                detail = parsed.error?.message || detail;
            } catch {
                if (errorText.length < 200) detail = errorText;
            }
            return res.status(response.status).json({ error: `OpenRouter API error: ${detail}` });
        }

        const data = await response.json() as OpenRouterResponse;
        const message = data.choices?.[0]?.message;
        if (!message) return res.status(500).json({ error: 'No response from LLM' });
        if (message.tool_calls?.length) {
            return res.status(200).json({ type: 'tool_calls', tool_calls: message.tool_calls, message, usage: data.usage });
        }
        return res.status(200).json({ type: 'response', content: message.content || 'No response generated', model: data.model, usage: data.usage });
    } catch (error: unknown) {
        clearTimeout(timeout);
        if (error instanceof Error && error.name === 'AbortError') {
            return res.status(499).json({ error: 'Client closed request' });
        }
        return res.status(500).json({ error: errorMessage(error) });
    }
}
