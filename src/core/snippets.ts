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
    /** Index of the token in the template line (0-based). */
    tokenIndex: number;
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
const COMMENT_ARG = /^#\s*[([（]\s*(\d+)(?:\.\.\.)?\s*[)\]）]\s*(.*)$/;

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

    const primary = templates[0];
    const tokenIndex = new Map<number, number>();
    primary.split(/\s+/).forEach((token, index) => {
        const match = PLACEHOLDER.exec(token);
        if (match) tokenIndex.set(Number(match[1]), index);
    });

    const seen = new Set<number>();
    for (const line of body) {
        const match = COMMENT_ARG.exec(line.trim());
        if (!match) continue;
        const num = Number(match[1]);
        if (seen.has(num)) continue;
        seen.add(num);
        const text = match[2].trim();
        const comma = text.indexOf(',');
        const kind = comma < 0 ? text : text.slice(0, comma).trim();
        const description = comma < 0 ? '' : text.slice(comma + 1).trim();
        args.push({
            num,
            optional: /^\s*\[/.test(line.trim()),
            kind,
            description,
            tokenIndex: tokenIndex.get(num) ?? -1,
        });
    }

    // Arguments without documentation still get an entry so the position stays
    // stable for signature help.
    for (const [num, index] of tokenIndex) {
        if (!seen.has(num) && args.every(arg => arg.num !== num)) {
            args.push({ num, optional: false, kind: '', description: '', tokenIndex: index });
        }
    }

    args.sort((a, b) => a.num - b.num);
    return { templates, args };
}
