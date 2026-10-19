import * as vscode from 'vscode';

import { Runtime } from '../core/cache';

interface CommandPick extends vscode.QuickPickItem {
    command: string;
}

/** Register the command palette helper that inserts a documented template. */
export function registerInsertCommand(context: vscode.ExtensionContext, runtime: Runtime): void {
    context.subscriptions.push(
        vscode.commands.registerCommand('suanpan.insertCommand', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) {
                vscode.window.showInformationMessage('Open a suanPan model first.');
                return;
            }

            const items: CommandPick[] = runtime.database.listCommands().map(command => ({
                label: command.name,
                description: command.category ?? 'control',
                detail: command.summary,
                command: command.name,
            }));

            const picked = await vscode.window.showQuickPick(items, {
                title: `suanPan ${runtime.database.version} commands`,
                placeHolder: 'Select a command to insert',
                matchOnDescription: true,
                matchOnDetail: true,
            });
            if (!picked) return;

            const snippet = runtime.database.snippetFor(picked.command, [picked.command]);
            const text = snippet?.templates[0] ?? picked.command;
            const word = editor.document.getWordRangeAtPosition(editor.selection.active, /[^\s,!#]+/);
            await editor.insertSnippet(new vscode.SnippetString(text), word ?? editor.selection.active);
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('suanpan.showVersion', () => {
            vscode.window.showInformationMessage(
                `suanPan language support — database built for suanPan ${runtime.database.version}.`
            );
        })
    );
}
