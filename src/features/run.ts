import * as os from 'os';
import * as path from 'path';
import * as vscode from 'vscode';

function quote(value: string): string {
    if (!value.startsWith('"')) value = `"${value}`;
    if (!value.endsWith('"')) value += '"';
    return value;
}

function configuration() {
    return vscode.workspace.getConfiguration('suanpan');
}

async function ensureExecutablePath(): Promise<void> {
    const config = configuration();
    if (config.get<boolean>('docker')) return;
    if ((config.get<string>('path') ?? '') !== '') return;

    const selection = await vscode.window.showInformationMessage(
        'suanPan executable path is not set. Do you want to set it now?',
        'Yes',
        'No'
    );
    if (selection !== 'Yes') return;

    const files = await vscode.window.showOpenDialog({
        canSelectFiles: true,
        canSelectFolders: false,
        canSelectMany: false,
        title: 'Select suanPan executable',
    });
    if (files?.[0]) {
        await config.update('path', files[0].fsPath, vscode.ConfigurationTarget.Global);
    }
}

/** Ask for the executable path on first use. */
export function registerSetup(context: vscode.ExtensionContext): void {
    context.subscriptions.push(
        vscode.commands.registerCommand('suanpan.setPath', async () => {
            const files = await vscode.window.showOpenDialog({
                canSelectFiles: true,
                canSelectFolders: false,
                canSelectMany: false,
                title: 'Select suanPan executable',
            });
            if (files?.[0]) {
                await configuration().update(
                    'path',
                    files[0].fsPath,
                    vscode.ConfigurationTarget.Global
                );
                vscode.window.showInformationMessage(`suanPan executable: ${files[0].fsPath}`);
            }
        })
    );

    void ensureExecutablePath();
}

/** Register the `suanpan.run` command. */
export function registerRun(context: vscode.ExtensionContext): void {
    context.subscriptions.push(
        vscode.commands.registerCommand('suanpan.run', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) return;

            const saved = await editor.document.save();
            if (!saved) return;

            const modelFile = editor.document.fileName;
            const config = configuration();

            const color = config.get<boolean>('color');
            const verbose = config.get<boolean>('verbose');
            const docker = config.get<boolean>('docker');
            const image = config.get<string>('image') || 'tlcfem/suanpan';
            const workingDirectory =
                config.get<string>('directory') || path.dirname(modelFile);

            let cpus = config.get<number>('cpus') || 0;
            const available = os.cpus().length;
            if (cpus <= 0 || cpus > available) cpus = available;

            let executable: string;
            if (docker) {
                executable = 'sp';
            } else {
                executable = config.get<string>('path') || '';
                if (!executable) {
                    void ensureExecutablePath();
                    vscode.window.showErrorMessage(
                        'suanPan executable not found. Please set the path in the settings.'
                    );
                    return;
                }
                executable = quote(executable);
            }

            if (!color) executable += ' -nc';
            if (verbose) executable += ' -vb';

            const directory = quote(workingDirectory);
            const fileName = path.basename(modelFile);

            const command = docker
                ? `docker run --rm --cpus=${cpus} -v ${directory}:/dirty -w /dirty ${image} ${executable} -f ${fileName}`
                : process.platform === 'win32'
                  ? `cd ${directory}; ${executable} -f ${quote(modelFile)}`
                  : `cd ${directory} && ${executable} -f ${quote(modelFile)}`;

            const task = new vscode.Task(
                { type: 'shell' },
                vscode.TaskScope.Workspace,
                fileName,
                'suanPan',
                new vscode.ShellExecution(command)
            );

            await vscode.tasks.executeTask(task);
        })
    );
}
