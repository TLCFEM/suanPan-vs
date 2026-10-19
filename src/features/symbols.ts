import * as vscode from 'vscode';

import { Runtime } from '../core/cache';

const SYMBOL_KIND: Record<string, vscode.SymbolKind> = {
    node: vscode.SymbolKind.Number,
    element: vscode.SymbolKind.Struct,
    material: vscode.SymbolKind.Class,
    section: vscode.SymbolKind.Interface,
    constraint: vscode.SymbolKind.Key,
    load: vscode.SymbolKind.Operator,
    amplitude: vscode.SymbolKind.Event,
    expression: vscode.SymbolKind.Function,
    group: vscode.SymbolKind.Namespace,
    step: vscode.SymbolKind.Event,
    solver: vscode.SymbolKind.Function,
    integrator: vscode.SymbolKind.Function,
    converger: vscode.SymbolKind.Function,
    criterion: vscode.SymbolKind.Function,
    recorder: vscode.SymbolKind.Array,
    modifier: vscode.SymbolKind.Object,
    orientation: vscode.SymbolKind.Object,
    interaction: vscode.SymbolKind.Object,
    domain: vscode.SymbolKind.Module,
    mass: vscode.SymbolKind.Number,
};

/** Register the outline (document symbols) provider. */
export function registerSymbols(context: vscode.ExtensionContext, runtime: Runtime): void {
    const provider: vscode.DocumentSymbolProvider = {
        provideDocumentSymbols(document) {
            const model = runtime.cache.get(document);
            const symbols: vscode.DocumentSymbol[] = [];

            for (const definition of model.definitions) {
                const line = model.parsed.lines[definition.statement.line] ?? '';
                const label = `${definition.category} ${definition.tag}`;
                const detail = definition.typeName ? `${definition.typeName}` : definition.category;
                const symbol = new vscode.DocumentSymbol(
                    label,
                    detail,
                    SYMBOL_KIND[definition.category] ?? vscode.SymbolKind.Object,
                    new vscode.Range(
                        definition.statement.line,
                        0,
                        definition.statement.endLine,
                        model.parsed.lines[definition.statement.endLine]?.length ?? line.length
                    ),
                    new vscode.Range(
                        definition.token.line,
                        definition.token.start,
                        definition.token.endLine,
                        definition.token.end
                    )
                );
                symbols.push(symbol);
            }

            symbols.sort((a, b) => a.range.start.line - b.range.start.line);
            return symbols;
        },
    };

    context.subscriptions.push(
        vscode.languages.registerDocumentSymbolProvider({ language: 'suanPan' }, provider)
    );
}
