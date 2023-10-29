import * as vscode from 'vscode';

export function activate(context: vscode.ExtensionContext) {
	let disposable = vscode.commands.registerCommand('suanPan-vs.run', () => {
		const editor = vscode.window.activeTextEditor;
		if (!editor) {
			return;
		}

		const sp_file = editor.document.fileName;
		const sp_config = vscode.workspace.getConfiguration('suanPan-vs');
		const sp_color = sp_config.get('color');
		const sp_verbose = sp_config.get('verbose');
		let sp_path = sp_config.get('path');
		let sp_pwd = sp_config.get('directory');

		if (sp_path === "") sp_path = "suanPan";

		if (sp_pwd === "") sp_pwd = sp_file.substring(0, sp_file.lastIndexOf("/"));

		if (!sp_color) sp_path += " -nc";
		if (sp_verbose) sp_path += " -vb";

		const terminal = vscode.window.createTerminal('suanPan');
		terminal.show();

		terminal.sendText(`cd ${sp_pwd}`);
		terminal.sendText(`${sp_path} -f ${sp_file}`);
	});

	context.subscriptions.push(disposable);
}

// This method is called when your extension is deactivated
export function deactivate() { }
