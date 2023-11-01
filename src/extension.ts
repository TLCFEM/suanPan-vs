import * as vscode from 'vscode';

function setPath() {
	const sp_config = vscode.workspace.getConfiguration('suanpan');
	let sp_path = sp_config.get('path');

	if ("" !== sp_path) return;

	vscode.window.showInformationMessage("suanPan executable path is not set. Do you want to set it now?", "Yes", "No").then(selection => {
		if (selection !== "Yes") return;

		vscode.window.showOpenDialog({
			canSelectFiles: true,
			canSelectFolders: false,
			canSelectMany: false,
			title: "Select suanPan executable"
		}).then(fileUri => {
			if (fileUri && fileUri[0]) {
				sp_path = fileUri[0].fsPath;
				sp_config.update('path', sp_path, vscode.ConfigurationTarget.Global);
			}
		});
	});
}

export function activate(context: vscode.ExtensionContext) {
	setPath();

	let disposable = vscode.commands.registerCommand('suanpan.run', () => {
		const editor = vscode.window.activeTextEditor;
		if (!editor) return;

		const sp_file = editor.document.fileName;
		const sp_config = vscode.workspace.getConfiguration('suanpan');
		const sp_color = sp_config.get('color');
		const sp_verbose = sp_config.get('verbose');
		let sp_path = sp_config.get('path');
		let sp_pwd = sp_config.get('directory');

		if (!sp_path) return vscode.window.showErrorMessage("suanPan executable not found. Please set the path in the settings.");

		if ("" === sp_pwd) sp_pwd = sp_file.substring(0, sp_file.lastIndexOf("/"));
		if (!sp_color) sp_path += " -nc";
		if (sp_verbose) sp_path += " -vb";

		const terminal = vscode.window.createTerminal('suanPan');
		terminal.sendText(`cd ${sp_pwd}`);
		terminal.sendText(`${sp_path} -f ${sp_file}`);
		terminal.show();
	});

	context.subscriptions.push(disposable);

	let tooltip = vscode.languages.registerHoverProvider({ language: 'suanPan' }, {
		provideHover(document, position, token) {
			return handle_hover(document, position, token);
		}
	});

	context.subscriptions.push(tooltip);
}

export function deactivate() { }

function handle_hover(document: vscode.TextDocument, position: vscode.Position, token: vscode.CancellationToken) {
	const wordRange = document.getWordRangeAtPosition(position);
	if (!wordRange) return new vscode.Hover(['']);

	const word = document.getText(wordRange).toLowerCase();

	const line = document.lineAt(position.line);
	const lineText = line.text.toLowerCase();
	const indexOfWord = lineText.indexOf(word);
	if (indexOfWord === 0 && 'element' === word) return new vscode.Hover(['create elements']);

	return new vscode.Hover(['']);
}