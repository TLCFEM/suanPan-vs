import * as vscode from 'vscode';

import { DocumentCache, Runtime } from './core/cache';
import { CommandDatabase } from './core/database';
import { registerInsertCommand } from './features/commands';
import { registerCompletion } from './features/completion';
import { registerDefinition } from './features/definition';
import { registerDiagnostics } from './features/diagnostics';
import { registerFolding } from './features/folding';
import { registerHover } from './features/hover';
import { registerReferences } from './features/references';
import { registerRun, registerSetup } from './features/run';
import { registerSignatureHelp } from './features/signature';
import { registerSymbols } from './features/symbols';

export function activate(context: vscode.ExtensionContext): void {
    let database: CommandDatabase;
    try {
        database = CommandDatabase.load(context.extensionPath);
    } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        vscode.window.showErrorMessage(`suanPan: failed to load the command database (${message}).`);
        return;
    }

    const runtime: Runtime = { database, cache: new DocumentCache(database) };

    registerSetup(context);
    registerRun(context);

    registerHover(context, runtime);
    registerCompletion(context, runtime);
    registerSignatureHelp(context, runtime);
    registerDiagnostics(context, runtime);
    registerSymbols(context, runtime);
    registerDefinition(context, runtime);
    registerReferences(context, runtime);
    registerFolding(context, runtime);
    registerInsertCommand(context, runtime);

    context.subscriptions.push(
        vscode.workspace.onDidCloseTextDocument(document => runtime.cache.forget(document))
    );
}

export function deactivate(): void {
    // Nothing to dispose explicitly; subscriptions handle cleanup.
}
