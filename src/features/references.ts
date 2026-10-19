import * as vscode from 'vscode';

import { Runtime } from '../core/cache';
import { findSymbol, referenceAt, tagTokenIndex } from '../core/model';
import { Statement, statementAt, tokenAt, tokenIndex } from '../core/parser';

interface Target {
    category: string;
    tag: number;
}

function resolveTarget(statement: Statement, index: number, runtime: Runtime): Target | undefined {
    const definitionIndex = tagTokenIndex(statement, runtime.database);
    if (index === definitionIndex) {
        const command = runtime.database.findCommand(statement.verb);
        const tag = Number(statement.tokens[index]?.value);
        if (command?.category && Number.isInteger(tag)) return { category: command.category, tag };
    }
    const reference = referenceAt(statement, index, runtime.database);
    return reference ? { category: reference.category, tag: reference.tag } : undefined;
}

function locationOf(document: vscode.TextDocument, statement: Statement, index: number): vscode.Location {
    const token = statement.tokens[index];
    return new vscode.Location(
        document.uri,
        new vscode.Range(token.line, token.start, token.endLine, token.end)
    );
}

/** Register find-all-references for tags. */
export function registerReferences(context: vscode.ExtensionContext, runtime: Runtime): void {
    const provider: vscode.ReferenceProvider = {
        provideReferences(document, position, options) {
            const model = runtime.cache.get(document);
            const statement = statementAt(model.parsed, position.line);
            if (!statement) return undefined;

            const token = tokenAt(statement, position.line, position.character);
            if (!token) return undefined;

            const target = resolveTarget(statement, tokenIndex(statement, token), runtime);
            if (!target) return undefined;

            const locations: vscode.Location[] = [];

            if (options.includeDeclaration) {
                const symbol = findSymbol(model, target.category, target.tag);
                if (symbol) {
                    locations.push(
                        new vscode.Location(
                            document.uri,
                            new vscode.Range(symbol.token.line, symbol.token.start, symbol.token.endLine, symbol.token.end)
                        )
                    );
                }
            }

            for (const candidate of model.parsed.statements) {
                for (let index = 0; index < candidate.tokens.length; index++) {
                    if (candidate === statement && index === tokenIndex(statement, token)) continue;
                    const reference = referenceAt(candidate, index, runtime.database);
                    if (!reference) continue;
                    if (reference.category !== target.category || reference.tag !== target.tag) continue;
                    locations.push(locationOf(document, candidate, index));
                }
            }

            return locations.filter((location, index) => {
                const key = `${location.range.start.line}:${location.range.start.character}`;
                return locations.findIndex(other => `${other.range.start.line}:${other.range.start.character}` === key) === index;
            });
        },
    };

    context.subscriptions.push(
        vscode.languages.registerReferenceProvider({ language: 'suanPan' }, provider)
    );
}
