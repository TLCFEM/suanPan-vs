/**
 * Snippet metadata.
 *
 * The syntax files shipped with the extension contain one template per
 * command/type.  Those templates are a direct transcription of the manual and
 * carry the argument documentation as leading comments, e.g.
 *
 *     element T2D2 ${1:(1)} ${2:(2)} ...
 *     # (1) int, unique element tag
 *     # (2) int, node i
 *
 * This module turns that data into a small, typed argument model that is used
 * by hover, signature help, completion and go-to-definition.
 */

export interface SnippetArg {
    /** 1-based argument number used in the template/comments. */
    num: number;
    /** Whether the argument is optional (square bracket in the manual). */
    optional: boolean;
    /** Raw type such as `int`, `double`, `bool string`. */
    kind: string;
    /** Human readable description (may be empty). */
    description: string;
    /** Index of the first token in the concrete statement (0-based). */
    tokenIndex: number;
    /** Number of consecutive tokens this argument covers (`(2...9)`, `[5...]`). */
    count: number;
}

export interface SnippetEntry {
    prefix: string;
    summary: string;
    /** Command name of the first template line, lower case. */
    verb: string;
    /** Secondary keyword (`element <type>`, `set <property>`, ...). */
    typeName?: string;
    /** All template lines of this entry. */
    templates: string[];
    /** Argument metadata of the primary template line. */
    args: SnippetArg[];
}

const PLACEHOLDER = /\$\{(\d+):([^}]*)\}/;
export const RANGE_MARKER = /^[([（]\s*(\d+)\.\.\.(\d*|\*)?\s*[)\]）]$/;
const COMMENT_ARG = /^#\s*([([（]\s*\d+(?:\.\.\.(?:\d*|\*))?\s*[)\]）])\s*(.*)$/;
const ARG_LABEL = /^[([（]\s*(\d+)(?:\.\.\.(\d*|\*))?\s*[)\]）]$/;

/** Last argument number described by a label; undefined for a variadic one. */
function argumentEnd(label: RegExpExecArray): number | undefined {
    if (!label[0].includes('...')) return Number(label[1]);
    if (label[2] === undefined || label[2] === '' || label[2] === '*') return undefined;
    return Number(label[2]);
}

/** Number of consecutive statement tokens described by an argument label. */
function argumentCount(label: RegExpExecArray): number {
    const end = argumentEnd(label);
    if (end === undefined) return Number.POSITIVE_INFINITY;
    return Math.max(1, end - Number(label[1]) + 1);
}

/** Replace snippet placeholders with their human readable fallback text. */
export function plainTemplate(template: string): string {
    return template
        .replace(/\$\{(\d+):([^}]*)\}/g, (_match, _num: string, body: string) => body)
        .replace(/\$\{(\d+)\|([^|]*)\|[^}]*\}/g, (_match, _num: string, body: string) => body);
}

/** Extract the argument metadata encoded in a snippet body. */
export function parseSnippetBody(body: string[]): { templates: string[]; args: SnippetArg[] } {
    const templates = body.filter(line => !line.trimStart().startsWith('#') && line.trim() !== '');
    const args: SnippetArg[] = [];
    if (templates.length === 0) return { templates, args };

    const counts = new Map<number, number>();
    const documentation = new Map<number, { optional: boolean; kind: string; description: string }>();
    for (const line of body) {
        const match = COMMENT_ARG.exec(line.trim());
        if (!match) continue;
        const label = ARG_LABEL.exec(match[1]);
        if (!label) continue;
        const num = Number(label[1]);
        if (documentation.has(num)) continue;
        const text = match[2].trim();
        const comma = text.indexOf(',');
        counts.set(num, argumentCount(label));
        documentation.set(num, {
            optional: /^\s*\[/.test(match[1]),
            kind: comma < 0 ? text : text.slice(0, comma).trim(),
            description: comma < 0 ? '' : text.slice(comma + 1).trim(),
        });
    }

    // Ranged placeholders such as `(2...9)` occupy several statement tokens,
    // so accumulate their width instead of using the template word position.
    // A variadic range (`(2...)`, `(2...*)`) makes later positions unknowable.
    const tokenIndex = new Map<number, number>();
    let cursor: number | undefined = 0;
    const words = templates[0].split(/\s+/);
    for (const [position, token] of words.entries()) {
        const placeholder = PLACEHOLDER.exec(token);
        const marker = placeholder ? undefined : RANGE_MARKER.exec(token);
        const label = placeholder ?? marker;
        if (!label) {
            if (cursor !== undefined) cursor += 1;
            continue;
        }

        const start = Number(label[1]);
        if (placeholder) {
            const index = cursor ?? -1;
            const count = counts.get(start) ?? 1;
            tokenIndex.set(start, index);
            if (Number.isFinite(count)) {
                cursor = cursor === undefined ? undefined : cursor + count;
            } else {
                // A variadic argument followed by more arguments has no
                // knowable width; do not let it swallow the trailing ones.
                const hasTail = words
                    .slice(position + 1)
                    .some(word => PLACEHOLDER.test(word) || RANGE_MARKER.test(word));
                counts.set(start, hasTail ? 1 : Number.POSITIVE_INFINITY);
                cursor = undefined;
            }
            continue;
        }

        const end = argumentEnd(marker!);
        const index = cursor ?? -1;
        if (end === undefined) {
            // A variadic range followed by more arguments has no knowable
            // width; do not let it swallow the trailing arguments.
            const hasTail = words
                .slice(position + 1)
                .some(word => PLACEHOLDER.test(word) || RANGE_MARKER.test(word));
            tokenIndex.set(start, index);
            counts.set(start, hasTail ? 1 : Number.POSITIVE_INFINITY);
            cursor = undefined;
            continue;
        }

        const width = end - start + 1;
        const documented = Array.from({ length: width }, (_, offset) => documentation.has(start + offset)).every(
            Boolean
        );
        if (documented) {
            // `(2...14)` with one comment per argument: keep each token.
            for (let num = start; num <= end; num++) {
                tokenIndex.set(num, index + (num - start));
                counts.set(num, 1);
            }
        } else {
            tokenIndex.set(start, index);
            counts.set(start, width);
        }
        cursor = cursor === undefined ? undefined : cursor + width;
    }

    for (const [num, index] of tokenIndex) {
        const info = documentation.get(num) ?? { optional: false, kind: '', description: '' };
        args.push({ num, ...info, tokenIndex: index, count: counts.get(num) ?? 1 });
    }

    args.sort((a, b) => a.num - b.num);
    return { templates, args };
}
