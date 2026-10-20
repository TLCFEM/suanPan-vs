import * as vscode from 'vscode';

import { Runtime } from '../core/cache';

/** Register folding for comment blocks, continuations and object groups. */
export function registerFolding(context: vscode.ExtensionContext, runtime: Runtime): void {
    const provider: vscode.FoldingRangeProvider = {
        provideFoldingRanges(document) {
            const model = runtime.cache.get(document);
            const ranges: vscode.FoldingRange[] = [];

            // Consecutive comment lines.
            let start = -1;
            let previous = -2;
            for (const line of model.parsed.commentLines) {
                if (line !== previous + 1) {
                    if (start >= 0 && previous > start) {
                        ranges.push(new vscode.FoldingRange(start, previous, vscode.FoldingRangeKind.Comment));
                    }
                    start = line;
                }
                previous = line;
            }
            if (start >= 0 && previous > start) {
                ranges.push(new vscode.FoldingRange(start, previous, vscode.FoldingRangeKind.Comment));
            }

            // Multi-line commands joined with backslashes.
            for (const statement of model.parsed.statements) {
                if (statement.endLine > statement.line) {
                    ranges.push(new vscode.FoldingRange(statement.line, statement.endLine, vscode.FoldingRangeKind.Region));
                }
            }

            // Contiguous definitions of the same category.
            let group: typeof model.parsed.statements = [];
            const flush = () => {
                if (group.length >= 3) {
                    const first = group[0].line;
                    const last = group[group.length - 1].endLine;
                    if (last > first) {
                        ranges.push(new vscode.FoldingRange(first, last, vscode.FoldingRangeKind.Region));
                    }
                }
                group = [];
            };

            for (const statement of model.parsed.statements) {
                const command = runtime.database.findCommand(statement.verb);
                const category = command?.category;
                const previousCategory = group.length
                    ? runtime.database.findCommand(group[group.length - 1].verb)?.category
                    : undefined;
                if (category && category === previousCategory && command?.types?.length) {
                    group.push(statement);
                } else {
                    flush();
                    if (category && command?.types?.length) group = [statement];
                }
            }
            flush();

            // Folding ranges cannot overlap freely; drop duplicates.
            const seen = new Set<string>();
            return ranges.filter(range => {
                const key = `${range.start}:${range.end}`;
                if (seen.has(key)) return false;
                seen.add(key);
                return true;
            }).sort((a, b) => a.start - b.start || b.end - a.end);
        },
    };

    context.subscriptions.push(
        vscode.languages.registerFoldingRangeProvider({ language: 'suanPan' }, provider)
    );
}
